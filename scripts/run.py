"""Launch the unmodified official harness from its required working directory."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("baseline", "smoke", "generation", "generation_smoke", "memory", "consolidate"))
    parser.add_argument("benchmark", choices=("tau2", "appworld"))
    args, extra = parser.parse_known_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        parser.error("Supply OPENAI_BASE_URL and OPENAI_API_KEY at runtime; never commit credentials.")
    # Official tau2 simulator uses its own LiteLLM path, which reads API_BASE.
    os.environ["OPENAI_API_BASE"] = os.environ["OPENAI_BASE_URL"]
    os.environ.setdefault("OPENAI_SERVICE_TIER", "auto")
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    if args.phase == "consolidate":
        if extra:
            parser.error("Consolidation settings are fixed; no extra arguments.")
        cmd = [sys.executable, "-m", "daedalus.scripts.consolidate",
               f"outputs/daedalus/hy3_{args.benchmark}_generation",
               "--model", "openai/hy3", "--reasoning-effort", "high", "--strategy", "single"]
    else:
        module = "generation" if args.phase.startswith("generation") else "inference"
        cmd = [sys.executable, "-m", f"daedalus.scripts.{module}", "--config",
               str(ROOT / "configs" / f"{args.benchmark}_{args.phase}.yaml"), *extra]
    import json
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    for path, expected in {".": lock["daedalus"]["commit"],
                           **lock["daedalus"]["submodules"]}.items():
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=VENDOR / path, text=True).strip()
        if actual != expected:
            raise SystemExit(f"Source revision mismatch: {path}")
        subprocess.run(["git", "diff", "--quiet"], cwd=VENDOR / path, check=True)
        subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=VENDOR / path, check=True)
    # Invoke the locked project interpreter, not whichever Python launched this wrapper.
    cmd[0] = str(VENDOR / ".venv" / "bin" / "python")
    subprocess.run(cmd, cwd=VENDOR, env=os.environ.copy(), check=True)


if __name__ == "__main__":
    main()
