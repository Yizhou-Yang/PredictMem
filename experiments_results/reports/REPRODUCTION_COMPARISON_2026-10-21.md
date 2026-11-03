# DAEDALUS reproduction vs source (2026-10-21)

Source: DAEDALUS paper, gpt-5.4-mini solver, its own scaffold.
This study: HY3, DAEDALUS harness, 5 runs per arm.

| Benchmark / arm | Source | HY3 | Note |
|---|---:|---:|---|
| AppWorld no-memory | 44.3 | 82.62 | HY3 ceiling much higher |
| AppWorld DAEDALUS | 60.2 | **84.88** | +2.26 over no-memory (source: +15.9) |
| AppWorld ACE | 60.5 | 82.62† | legacy frozen bank |
| AppWorld ExpeL | 59.0 | 71.07† | legacy frozen bank |
| τ² no-memory | 57.5 | 51.50 | |
| τ² DAEDALUS | 67.5 | run | old 5-run had one 39/40 |
| τ² ACE | 70.5 | 44.00† | legacy frozen bank |
| τ² ExpeL | 67.0 | 57.50† | legacy frozen bank |

† = bank built in an earlier protocol; execution/scoring verified, bank fidelity unvalidated.

## Reading

- Absolute values are not comparable: model, scaffold, and headroom differ.
- The HY3 no-memory baseline is 82.62, so memory headroom is small; DAEDALUS still gains +2.26.
- Ordering differs from the source; ACE/ExpeL are not same-model reproductions.
- Treat HY3 columns as **method transfer**, report deltas, not cross-paper rankings.

## Baseline stabilization (in progress)

1. Rebuild ACE and ExpeL banks with HY3 on the frozen protocol (AppWorld 90 train, τ² 74 train).
   - ACE AppWorld accumulation started 2026-10-21, 90 tasks, parallel 4.
2. Rerun DAEDALUS memory on τ²: 5 × 40, equal denominators.
3. Record AppWorld version, harness commit, max_turns, and pool construction per arm.
