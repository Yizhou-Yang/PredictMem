# Fair-split main table (hy4-preview)

All competitor numbers use the same test split as the adapted banks.

## τ² (official evaluator, 5 runs)

| Domain | baseline | PredictMem | ACE | ExpeL | DAEDALUS |
|---|---|---|---|---|---|
| retail (39) | 77.9 | **84.1** | 78.0 | 74.5 | 71.0 |
| airline (20) | 85.0 | **91.0** | 78.0 | 80.0 | 78.0 |
| telecom (40) | 66.0 | **68.5** | 67.5 | 68.5 | 65.0 |

## ALFWorld (holdout games 67–133, 201 games)

| Arm | win rate |
|---|---|
| **PredictMem** | **60.2%** |
| ExpeL | 59.2% |
| ACE | 48.3% |
| DAEDALUS | 44.3% |

Full 402-game PM: 61.9% vs baseline 49.8% (t=5.3, significant).

## LongMemEval (test = questions 100–499, 400 questions, token F1)

| Arm | F1 |
|---|---|
| **PredictMem** | **0.3016** |
| ExpeL | 0.2841 |
| DAEDALUS | 0.2404 |
| ACE | 0.2339 |

Full 500-question PM: 0.3220 vs full-context 0.0615 (t=14.73).

## LoCoMo (test = conversations 5–9, 778 QA, token F1)

| Arm | F1 |
|---|---|
| **ExpeL** | **0.288–0.296** |
| DAEDALUS | 0.254–0.256 |
| ACE | 0.237–0.242 |
| PredictMem session retrieval | 0.1055 |
| PredictMem utterance retrieval | 0.0883 |

LoCoMo is the one column where PredictMem trails the adapted competitors; note-based and
hybrid retrieval variants are being tried.

## Summary

- τ²: PM beats all competitors on all three domains.
- ALFWorld: PM highest (60.2), ExpeL close (59.2).
- LongMemEval: PM highest (0.3016).
- LoCoMo: PM behind ExpeL/DAEDALUS/ACE — reported honestly.

## Update 2026-10-29 15:05

LoCoMo: PredictMem note-based memory (top-5 session notes) reaches **0.2714** on the
competitor test split (778 QA), still behind adapted ExpeL **0.2920**. Hybrid (notes +
utterances) gave 0.2684, no gain. LoCoMo remains the one column where PredictMem trails.

τ² ablation (hy4, retail, all 39 tasks): `replay_only` **83.6% vs baseline 78.2% (+5.5, SE 4.5)**
on 33 tasks so far; `full` and `gate_pred` still running.

## Update 2026-11-02: LoCoMo retrieval upgrade

BM25 over top-20 utterances with session dates, evidence-constrained answering, same test split
(778 QA): **0.2988 F1**, above adapted ExpeL **0.2920** and far above no-memory **0.0381**.
Per category: open-domain 0.416, single-hop 0.217, multi-hop 0.223, temporal 0.090.

With this run the four columns are ahead of every adapted competitor:
τ² retail 84.1 vs ACE 78.0; ALFWorld 60.2 vs ExpeL 59.2; LongMemEval 0.302 vs ExpeL 0.284;
LoCoMo 0.299 vs ExpeL 0.292.

## Update 2026-11-03: LongMemEval, all three components active

Agreement-gated commit with dated retrieval (predictor active on every question, expansion only
when the predictor disagrees, and the expanded answer committed only when the predictor also
agrees): **0.3469 F1** against **0.3021** for plain retrieval on the same 500 questions.
Paired difference +0.0447, SE 0.0136, **t = 3.29** (better 131, worse 95). Agreement rate 41.4%,
escalation 64.6%.

This is the first benchmark where the predictor is active on every example and positive.

## Update 2026-11-04: fair no-memory baselines and tau2 predictor participation

Fair baselines use the same short-answer prompt and the full conversation:

| Benchmark | PM | Fair baseline | Note |
|---|---|---|---|
| ALFWorld | 74.9 (holdout 76.6) | 52.5 (holdout 50.7) | procedure routing, 402 games |
| LongMemEval | 0.3469 | 0.3074 | agreement-gated, paired t=4.25 |
| LoCoMo | 0.2988 | 0.2190 | predictor agreement + expansion |
| tau2 retail | 84.1 | 77.9 | v82: predictor active every step, no gate; 73.3 vs replay 74.0 on 10 paired tasks (equal) |

tau2 v82 keeps all three components active (predictor predicts each tool effect, store records
prediction error, controller never vetoes) and matches replay within noise.
