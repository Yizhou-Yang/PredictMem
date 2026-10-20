# HY3 × DeepSWE v1.1 — 100 步 5 题报告（2026-10-20）

> 目的：在比 30 步更合理的预算下复测 5 题，判断 HY3 是否具备 DeepSWE 解题能力。
> 结论：**1/5 解出（pass@1 = 20%）**，说明 30 步的 0/5 是预算截断；但单题成本约 5.6M input tokens。

## 配置

| 项 | 值 |
|---|---|
| Benchmark | DeepSWE v1.1，5 题（seed 0） |
| Harness | mini-swe-agent v2 via Pier 0.3.1 |
| Model | HY3（any4 relay → 太极 API） |
| step_limit | **100** |
| concurrency | 2 |
| N | 1 |

## 结果

| Task | Steps | Reward | Input tokens |
|---|---:|---:|---:|
| returns-validated-error-accumulation | 78 | **1** | 3,884,098 |
| ipython-session-bundle-replay | 77 | 0 | 2,988,970 |
| scriggo-method-declarations | 100（cap） | 0 | 5,582,828 |
| effect-sse-httpapi-streaming | 100（cap） | 0 | 7,380,293 |
| koota-query-predicates | 100（cap） | 0 | 8,293,319 |
| **合计** | — | **1/5** | **28,129,508** |

- pass@1 = **0.20**
- output tokens 合计 292,590
- 平均 **5.63M input tokens / 题**
- 5/5 完成、0 infra error

## 与 30 步对比

| 预算 | pass@1 | 总 input tokens | 备注 |
|---|---:|---:|---|
| 30 步 | 0/5 | 3.27M | 全部在步数上限截断 |
| 100 步 | **1/5** | 28.13M | 1 题 78 步解出；其余 3 题打满 100 步 |

## 113 题全量估算

- tokens：5.63M × 113 ≈ **636M input tokens**（output 约 6.6M）
- 时间：单题 40–60 分钟；v100 内存 38G，每个 task 容器 8G，**并发最多 4**（8 并发会 OOM）→ 约 **24 小时**
- 磁盘：113 个 base image × 2.6G ≈ 294G，v100 剩 337G，**需要分批 + 清理**，否则会写满
- 30 步全量只要 ~74M tokens，但大概率仍是 0%

## 建议

1. **不要一次铺 113 题**：按 20–25 题一批，批间 `docker image prune`，避免磁盘写满
2. 并发用 **4**（内存上限），不要用 8
3. 若只关心 pass@1 量级，可以先跑 30–40 题的随机子集
4. 若目标是和 DeepSeek 官方 77.0 对齐，需要换 `deepseek-flash` 模型 + 官方 step 预算；HY3 的结果只能作 method-transfer
