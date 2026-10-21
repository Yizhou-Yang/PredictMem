# PredictMem Arm — 设计与实现规格（v1）

> 目标：在 DAEDALUS harness 内从零实现 PredictMem arm，支持 AppWorld 与 τ²，能和 baseline / ACE / ExpeL / DAEDALUS(memory) 在同一 harness、同一模型（HY3）、同一预算下对比。
> 原则：不使用 task outcome 作为记忆写入信号；所有预测/写入/门控只用可观测的 action-effect；全过程可审计、可消融、可复现。

## 1. 方法定义

每个 turn：

1. **Action proposal**：solver 生成 `Thought + code`（沿用现有 ReActAgent 的解析）。
2. **Predict**：Predictor 读取 task instruction、最近 k 轮对话、候选 code，输出结构化预测：
   ```json
   {
     "expected_observation": "…",
     "expected_state_changes": ["…"],
     "expected_success": true,
     "risk": "low|medium|high",
     "confidence": 0.0
   }
   ```
   预测器**不看** task outcome，也不看 verifier。
3. **Execute**：`world.execute(code)`，得到 observation（成功/异常/输出）。
4. **Surprise**：比较 predicted 与 observed，得到 `S ∈ [0,1]` 和 rationale。
5. **Admission**：`S > τ_admit` 且记录有效（有可观测证据）才写入；写入时去重、版本化。
6. **Retrieve（下一步前）**：用 task instruction + 最近对话 + 候选 action 检索 top-k 有效记录。
7. **Gate**：如果检索到的记录对候选 action 给出高风险/负 effect 且置信度足够，触发 warn / probe / block，阻止“预测到会坏还直接做”。

写信号是 **prediction error**，不是 success label；这是与 DAEDALUS/ACE/ExpeL 的核心区别。

## 2. 数据模型

`EffectRecord`：

| 字段 | 说明 |
|---|---|
| `record_id` | UUID |
| `task_id` / `task_signature` | 任务标识 + instruction 的归一化签名 |
| `turn_idx` | 发生轮次 |
| `action` | 代码/动作文本 |
| `action_signature` | 归一化（去空白、去注释、hash） |
| `context_signature` | 最近 k 轮对话的 hash |
| `predicted` | `Prediction`（observation/state_changes/success/risk/confidence） |
| `observed` | `Observation`（success、output、error、state_delta?） |
| `surprise` | 0–1 |
| `surprise_parts` | `{semantic, judge, execution}` |
| `rationale` | surprise 的短解释 |
| `provenance` | `{model, prompt_hash, predictor_call_id, timestamp}` |
| `version` | 从 1 开始 |
| `supersedes` | 被替代的 record_id |
| `valid` | 检索是否可见 |
| `created_at` | ISO 时间 |

版本化规则：
- key = `(task_signature, action_signature, context_signature)`
- 同 key 新记录：若 predicted/observed 冲突（surprise 方向相反或风险等级变化），旧记录 `valid=False`，`superseded_by=新 id`，新记录 `version=旧+1`，`supersedes=旧 id`
- 不冲突则保留两条，检索时按 confidence×recency 排序

## 3. Surprise

三路组合，默认权重 `0.3 / 0.5 / 0.2`：

1. **semantic**：predicted observation 与 observed output 的相似度
   - 优先 BM25/TF-IDF cosine（离线、无额外模型）
   - 可选 dense（Qwen3-Embedding，harness 已支持）
   - `s_sem = 1 - cos`
2. **judge**：一次 LLM judge（HY3，temperature 0）按 rubric 打分：
   - 0 = 完全一致；0.5 = 部分一致；1 = 明显不同/相反
   - 输出 JSON `{score, reason}`，失败时回退到 semantic
3. **execution**：`expected_success` 与实际成功/异常是否一致；不一致记 1，一致记 0

`S = clip(w1*s_sem + w2*s_judge + w3*s_exec, 0, 1)`

Judge 的 prompt 固定 rubric，不含 task outcome；judge 输入只有 predicted 和 observed。

## 4. 写入（Admission）

```
if not record_has_evidence(observed): reject
if S <= tau_admit: reject
if duplicate(action_signature, context_signature, observed_hash): reject
if bank_size >= max_records: evict lowest (confidence * recency)
admit -> versioning -> persist
```

- `tau_admit` 默认 **0.55**；消融可设 0（admit all）
- `record_has_evidence`：执行有输出/异常，不能是空 observation
- 去重：`sha256(action_signature + context_signature + observed.output[:500])`
- 跨 task 默认**不共享**（task-isolated，保证 validity）；`shared_bank: true` 时才跨 task 合并

## 5. 检索

- 索引文本：`task_signature + action + predicted.expected_observation + observed.output[:300]`
- 默认 BM25，top-k=5；可选 dense
- 排序：`score = sim * (0.5 + 0.5*confidence) * recency_decay(turn)`
- 只检索 `valid=True` 的记录
- 每次检索记录 `retrieved_ids` 和分数，供审计

## 6. Gate

在 execute 之前：

1. 用候选 action 检索 top-k
2. 计算 `risk_score`：
   - 若记录 `predicted.risk=high` 且 `observed.success=false`，权重最高
   - `risk_score = max over records of (sim * confidence * risk_weight)`
3. 分级：
   - `risk_score < τ_warn`：放行
   - `τ_warn ≤ risk_score < τ_block`：**warn**，向模型注入一条系统提示，要求先验证状态或说明为什么仍然执行
   - `risk_score ≥ τ_block`：**probe**，不执行原 action，改为执行只读探测（如列出状态/查询资源），把探测结果作为 observation 返回；下一轮再决定
4. 所有 gate 决策写入 trace：`{level, risk_score, records, action, probe_code}`

默认 `τ_warn=0.45`、`τ_block=0.75`；消融可关闭 gate。

## 7. 配置

```yaml
predictmem:
  enabled: true
  predictor_model: openai/hy3
  predictor_reasoning_effort: high
  predictor_temperature: 0.0
  judge_model: openai/hy3
  judge_temperature: 0.0
  context_turns: 3
  tau_admit: 0.55
  weights: {semantic: 0.3, judge: 0.5, execution: 0.2}
  retriever: bm25          # bm25 | dense
  top_k: 5
  gate: {enabled: true, tau_warn: 0.45, tau_block: 0.75}
  max_records: 200
  shared_bank: false
  ablation:
    no_predictor: false     # 用固定 prior 代替预测
    admit_all: false
    no_versioning: false
    no_gate: false
```

## 8. 代码结构

```
daedalus/benchmarks/appworld/predictmem/
  __init__.py
  records.py      # EffectRecord, Prediction, Observation
  predictor.py    # LLMPredictor
  surprise.py     # semantic/judge/execution + combine
  store.py        # VersionedEffectStore (JSONL + in-memory index)
  retrieval.py    # BM25 / dense wrapper
  gate.py         # EffectGate
  agent.py        # PredictMemReActAgent
  config.py       # PredictMemConfig
  prompts/
    predict.txt
    judge.txt
    gate_warn.txt
tests/
  test_predictmem_records.py
  test_predictmem_surprise.py
  test_predictmem_store.py
  test_predictmem_gate.py
```

集成点：
- `daedalus/core/config.py`：`ExperimentConfig.predictmem: PredictMemConfig | None`
- `daedalus/benchmarks/appworld/__init__.py`：构造 agent 时按 `cfg.predictmem.enabled` 返回 `PredictMemReActAgent`
- `scripts/run_verified_reproduction.py`：arm 白名单加 `predictmem`，parallel 默认 8（总预算 24），config 生成加 `predictmem` 段
- τ²：`daedalus/benchmarks/tau2/agent.py` 里做对应包装（先 AppWorld，后 τ²）

## 9. 日志与审计

每个 turn 落一条 JSONL：

```json
{
  "task_id": "...", "turn": 3,
  "action_sha": "...", "context_sha": "...",
  "prediction": {...}, "observation": {...},
  "surprise": {"score": 0.62, "parts": {...}, "rationale": "..."},
  "admitted": true, "record_id": "...", "version": 2,
  "retrieved": [{"id": "...", "score": 0.81, "confidence": 0.7}],
  "gate": {"level": "warn", "risk_score": 0.58},
  "tokens": {"predictor": 1234, "judge": 800, "solver": 5000}
}
```

产物：
- `predictmem_events.jsonl`（逐 turn）
- `predictmem_bank.json`（task 结束时的有效记录）
- `evaluation.json`（沿用 harness）

## 10. 有效性约束

- predictor/judge 的输入**不包含** `world.task_completed()`、verifier、success label
- `shared_bank=false` 时 task 之间零泄漏
- 记录 provenance 含 model、prompt hash、call id；可重放
- 消融开关在配置里冻结，跑前固定
- 与 baseline/ACE/ExpeL/DAEDALUS 使用同一 harness commit、同一模型、同一 max_turns=30、同一 task split

## 11. 成本与并发

- 每 turn 额外 2 次 LLM 调用（predict + judge），30 turn → ~60 次额外调用/task
- AppWorld 840 task-runs：约 50k 额外调用；HY3 在 12–24 并发下可承受，时间约为 memory arm 的 2–3 倍
- predictor 可降 reasoning（low/medium）控成本；消融时关闭 judge 可省一半

## 12. 实施顺序

1. records / store / surprise 单元 + 测试
2. predictor + judge prompt + 解析/重试
3. retrieval + gate
4. agent 集成 + trace
5. 单 task smoke（train 1 题）
6. AppWorld smoke → 5×168 full（parallel 12）
7. τ² 适配 + 5×40
8. 消融（no predictor / admit all / no versioning / no gate）
