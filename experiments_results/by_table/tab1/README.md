# tab1 — main results table

`cells.json` lists one entry per printed cell: the cell name, the value printed in the paper, and
the trace glob that produces it. Paths are relative to `experiments_results/`.

Run `python3 ../_paper/verify.py` to recompute every cell and print the reproduced share.
The current tree reproduces 12/12 cells.

Row order matches the paper: tau2 retail/airline/telecom, ALFWorld, LongMemEval, LoCoMo, each
with a no-memory and a PredictMem cell.
