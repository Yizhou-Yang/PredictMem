# Paper rewrite report: Abstract + Introduction

Skill: `bestpaper-writing` v1.2 (grep from github.com/gulucaptain/Best-Paper-Writing-Skill)

## Intake (from the project's real results)

- Task: long-horizon agents need memory of action effects, not lessons.
- Gap: a lesson (reflection / insight / playbook) recalls what worked; it does not model what a
  candidate action will do in the current state.
- Closest work: ACE (playbook), ExpeL (insights + trajectories), DAEDALUS (validated heuristics).
- Idea: store the observed effect with provenance; replay it for repeated tasks, retrieve it as
  evidence for unseen tasks; commit only when the retrieved evidence supports the action.
- Headline numbers used in the abstract: 79.2 vs 74.6 on τ², 61.9 vs 49.8 on ALFWorld. The two
  F1 results (0.322 vs 0.062; 27.1 vs 3.8) are stated as gains, not repeated as four numbers.
- Claims deliberately **not** made: no "state of the art on all benchmarks"; no claim that the
  predictor alone is significant. Same-task replay and thresholded retrieval are the components
  with positive ablation evidence; the predictor/gate ablation is negative and is left to the
  experiments section.

## Route

L2 method paper, tension type `obvious-fix-too-costly` (lesson memory is cheap to add but does
not forecast effects), with a contrast against ACE/ExpeL/DAEDALUS.

## Changes

| Original | Revised | Reason |
|---|---|---|
| Abstract opened with repo/terminal examples and listed four benchmark names in one 60-word sentence | Abstract states effect record, gap, method, two headline numbers | award-paper arc Setting → Gap → Method → Result |
| "A lesson can recall what worked; it cannot predict..." | Same contrast kept as one pivot sentence | keep the pivot short; no dash |
| Four benchmark numbers in the abstract | Two headline numbers plus a qualitative F1 statement | `check_draft` warns above ~5.6 numbers |
| Introduction used em dashes | Replaced with commas and a colon | author preference: no dashes |
| Contributions claimed "chance-constrained commit rule" as a positive | Contributions now name effect memory, commit rule, and ablation evidence | predictor/gate ablation is negative; do not overclaim |

## Checker

- Abstract: **0 errors**, 2 WARN (short-sentence share, mean length slightly below corpus p10).
  WARNs are accepted to keep the pivot sentences; the numbers were reduced as requested.
- Introduction: **0 errors**, 4 WARN (numbers, aphoristic contrasts, short sentences, length).
  The introduction keeps the contrast sentences because they carry the thesis.

## Open items for authors

- Compile with the target template (no TeX on this machine).
- Replace the LoCoMo sentence if the ExpeL comparison (29.2) must appear in the abstract.
- Limitations section: predictor/gate ablation is negative; replay/retrieval carry the gains.
