# HY3 × DeepSWE v1.1 — 5 题 smoke 报告（2026-10-20）

> 目的：验证 HY3 + mini-swe-agent + Pier 的评测管线，并测每题的 token/step 规模。
> 结论：**管线已跑通，但 30 步上限太低，5 题全部在步数上限处被截断，pass@1 = 0/5。这不是 HY3 的能力估计。**

## 配置

| 项 | 值 |
|---|---|
| Benchmark | DeepSWE v1.1，5 题（seed 0） |
| Harness | mini-swe-agent v2 via Pier 0.3.1 |
| Model | HY3（any4 本地 relay → 太极 API） |
| step_limit | **30** |
| concurrency | 2 |
| N | 1 |
| 日期 | 2026-10-20，约 12:00–12:30 CST |

## 结果

| Task | Steps | Input tokens | Output tokens | Reward |
|---|---:|---:|---:|---:|
| effect-sse-httpapi-streaming | 30（cap） | 769,187 | — | 0 |
| ipython-session-bundle-replay | 30（cap） | 547,219 | — | 0 |
| koota-query-predicates | 30（cap） | 877,452 | — | 0 |
| returns-validated-error-accumulation | 30（cap） | 630,907 | — | 0 |
| scriggo-method-declarations | 30（cap） | 446,790 | — | 0 |
| **合计** | — | **3,271,555** | **104,535** | **0/5** |

- 平均每题：**654K input tokens / 30 steps**
- 5/5 完成、0 infra error（这一轮 infra 是干净的）
- pass@1 = **0.0**

## 判读

1. **所有 task 都打满 30 步**，说明 30 步预算不足以完成 DeepSWE 的长程任务；分数被预算截断，不能当作 HY3 的 DeepSWE 能力。
2. 参考实现 mini-swe-agent 的 SWE-bench 配置默认 `step_limit: 250`；DeepSeek 官方 DeepSWE 数字也是在官方 harness 默认预算下得到的。
3. 按当前 token 规模线性外推：
   - step_limit=100：约 2M input tokens/task，113 题约 **226M tokens**
   - step_limit=250：约 5M input tokens/task，113 题约 **565M tokens**
   - step_limit=30 的 113 题：约 **74M tokens**，但大概率仍是 0%

## Infra 修复记录（这轮踩的坑）

1. any4 `/data` 100% 满 → relay audit 写入失败返回 500；relay 日志改到 `/root`
2. 113 个 task 使用 113 个不同 base image → 改 Pier 的 `write_agent_dockerfile`，统一注入 apt no-op、预装 uv、腾讯 PyPI 镜像
3. agent 以非 root 运行 → Dockerfile 末尾 `USER root`
4. 缺 `mcp` → agent 安装时补 `uv pip install mcp`
5. 并发 trial 只有一个能连 relay → bridge watcher 改为持续连接所有 `-main-1` 容器
6. 反向隧道断 → any4 加 `relay_tunnel_watch.sh` 保活

## 建议

- **不要用 step_limit=30 跑 113 题**：会得到 0%，浪费 ~74M tokens。
- 先把 step_limit 提到 **100**（折中）或 **250**（对齐官方 harness 默认），再跑 5 题复测。
- 若 5 题在 100 步下仍全 0，再讨论是否需要换 harness/模型，而不是继续加预算。
