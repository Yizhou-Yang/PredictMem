# Security incident — litellm 1.107.0 (2026-10-22)

## Alert

Corporate IT flagged a suspicious pip package on **any2 (9.135.100.240)** at 2026-10-22
00:40:41: `litellm 1.107.0`, path `pip-litellm-1.107.0`.

## Verdict: true positive

litellm 1.107.0 is the compromised release from the 2026-10-21 supply-chain attack
(malicious wheels on PyPI/Docker Hub; credential theft and remote code loading):

- https://docs.litellm.ai/blog/security-incident-oct-21-2026
- https://research.jfrog.com/post/litellm-hijacked-again/
- https://www.chainguard.dev/unchained/litellm-attacked-again-malicious-1-107-0-wheels-on-pypi-and-docker-hub-october-2026

This is **not** caused by test cases. It comes from the Pier agent image build:
`uv tool install mini-swe-agent` was unpinned, so it resolved the newest litellm, which was
1.107.0 at build time. Every task using the mini-swe-agent image would install it.

## Scope

- 103 locally built Pier agent images (`*__*-main:latest`) contained
  `litellm-1.107.0.dist-info`. All were removed with `docker rmi`; containers and networks
  pruned.
- Host Python `~/.local/lib/python3.14/site-packages/litellm` is **1.83.7** (old, not the
  compromised release). The uv cache had no 1.107.0 wheel.
- Containers received `OPENAI_API_KEY=dummy`; no real model key was passed. Egress was through
  the Pier proxy.
- any2 has an SSH private key (`~/.ssh/id_rsa`, Jun 2025). No `~/.git-credentials` and no
  `gh` config were found; no model/GitHub tokens were in the environment.

## Remediation

1. Pier install command now pins the dependency
   (`.../pier/agents/installed/mini_swe_agent.py`):
   ```
   uv tool install mini-swe-agent...
   uv pip install --python /root/.local/share/uv/tools/mini-swe-agent/bin/python 'litellm<1.107.0'
   ```
2. Rebuilt one image to verify: **litellm 1.106.2** (safe).
3. Do not rebuild unpinned. Check every new image with:
   `docker run --rm <image> /root/.local/share/uv/tools/mini-swe-agent/bin/python -c "from importlib.metadata import version; print(version('litellm'))"`

## Recommended follow-ups

- Rotate the any2 SSH key and any credential that was readable from that host.
- Report the finding to IT/security with the scope above; the EDR alert is correct.
- Audit the pre-existing `background_agent_cli` cron entry (`* * * * *`) on any2 — it is not
  part of PredictMem.
- Treat any result produced by images built between 2026-10-21 00:00 and 2026-10-22 11:00 as
  produced in a potentially compromised environment; the numerical outputs are unaffected in
  principle, but the host should be treated as untrusted until cleared.
