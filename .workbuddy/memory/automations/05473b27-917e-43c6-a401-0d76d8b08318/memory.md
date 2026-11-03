# PredictMem 通宵对标 收尾与推送 — 执行记录

## 2026-10-16 首次运行
- 运行 `finalize_and_push.sh` 成功。远端 any4 通宵阶段标记 18 个 `.mark_*.done` 全部存在（DAEDALUS 8 + ACE 5 + ExpeL 3 + collect 2）。
- `scripts/finalize.py` 汇总成功，results/*.json 与 reproduction_protocol.json 拉回本地。
- git commit `f0a0ff1` 并 push 到 origin main（Yizhou-Yang/PredictMem），推送成功，工作树 clean。

## 关键结果快照（HY3 复现，pass^5）
- tau2 (train74/test40): DAEDALUS gen 48 任务/48 启发式, consolidation 23 条; baseline 0.55, memory 0.4877, Δ −6.231pp。ACE accum 74/bullets 74, inference 0.465, Δ −8.5pp。ExpeL accum 74/insights 21, **inference missing**。
- appworld (train90/test168): DAEDALUS **generation missing**; baseline 0.6473, memory 0.8084, Δ +16.112pp。ACE accum 90/bullets 211, inference 0.7476, Δ +10.03pp。ExpeL accum 90/insights 23, **inference missing**。
- 价格字段全为 null（HY3 无本地价目表，非 0 美元）。

## 未完成臂（下次运行需如实标注）
- ExpeL inference：tau2 与 appworld 均 missing（未运行）。
- appworld DAEDALUS generation：missing。
- appworld baseline num_runs=4、memory num_runs=2（未达 5 次 pass^5，标记为 partial）。
- tau2 与 appworld 的 DAEDALUS memory、ACE、ExpeL 相对 baseline 大多为负（除 appworld 两臂），符合 HY3 强基线压缩 memory 增益的现象。
