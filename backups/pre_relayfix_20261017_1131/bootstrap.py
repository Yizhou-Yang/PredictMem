"""Install pinned upstream source and dependencies without replacing existing files."""
import json
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    subprocess.run(list(args), cwd=cwd, check=True)


def main():
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    src = lock["daedalus"]
    vendor = ROOT / "vendor" / "daedalus"
    vendor.parent.mkdir(exist_ok=True)
    if not vendor.exists():
        run("git", "clone", src["url"], str(vendor))
        run("git", "checkout", src["commit"], cwd=vendor)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=vendor, text=True).strip()
    if actual != src["commit"]:
        raise SystemExit(f"Refusing existing vendor at unexpected commit: {actual}")
    run("git", "submodule", "update", "--init", "--depth", "1",
        *src["submodules"], cwd=vendor)
    for path, expected in src["submodules"].items():
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=vendor / path, text=True).strip()
        if actual != expected:
            raise SystemExit(f"Submodule mismatch: {path}")
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("Install uv first, then rerun. No system package installation is performed.")
    run(uv, "sync", "--project", str(vendor), "--python", lock["python"], "--frozen",
        "--extra", "dev", "--extra", "appworld", "--extra", "tau2")
    python = vendor / ".venv" / "bin" / "python"
    appworld = vendor / ".venv" / "bin" / "appworld"
    run(str(appworld), "install", "--repo", cwd=vendor / "benchmarks" / "appworld")
    # The official downloader deletes an existing data directory. Never invoke it twice.
    if not (vendor / "data").exists():
        run(str(appworld), "download", "data", "--version", "0.2.0", "--mode", "minimal", cwd=vendor)
    else:
        print("Existing AppWorld data preserved; verify version in environment manifest.")
    run(str(python), str(ROOT / "scripts" / "build_configs.py"))


if __name__ == "__main__":
    main()
