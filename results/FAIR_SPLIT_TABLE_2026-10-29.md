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
