#!/usr/bin/env python3
"""Run the risk landscaper pipeline against a battery config.

Battery configs are YAML files that specify which policy files/directories
to run and with what model. Subdirectories are multi-document groups —
all files in the subdirectory are passed together as one run.

Usage:
    python run_all_policies.py batteries/standard.yaml --base-url http://localhost:8000/v1
    python run_all_policies.py batteries/frontier.yaml --base-url http://localhost:8000/v1 --model override-model
"""

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
RUNS_DIR = ROOT / "runs"
NEXUS_BASE_DIR = "/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus"

POLICY_EXTENSIONS = {".json", ".md", ".txt", ".pdf", ".docx", ".html", ".htm"}


def _is_policy_file(p: Path) -> bool:
    return p.is_file() and not p.name.startswith(".") and p.suffix.lower() in POLICY_EXTENSIONS


def _resolve_run(entry: str) -> tuple[str, list[Path]]:
    """Resolve a battery entry to (name, [files]).

    A file path → single-doc run. A directory path → multi-doc group.
    """
    path = ROOT / entry.rstrip("/")
    if path.is_file():
        return path.stem, [path]
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if _is_policy_file(p))
        if not files:
            print(f"Warning: no policy files in {path}, skipping")
            return path.name, []
        return path.name, files
    print(f"Warning: {path} does not exist, skipping")
    return Path(entry).stem, []


def run_one(policies: list[Path], name: str, base_url: str, model: str, runs_dir: Path, max_context: int = 0) -> tuple[str, bool, str]:
    out = runs_dir / name
    cmd = [
        "uv", "run", "risk-landscaper", "run",
        *[str(p) for p in policies],
        "-o", str(out),
        "--base-url", base_url,
        "--model", model,
        "--nexus-base-dir", NEXUS_BASE_DIR,
    ]
    if max_context > 0:
        cmd.extend(["--max-context", str(max_context)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return name, result.returncode == 0, output


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("battery", type=Path, help="Battery config YAML file (e.g. batteries/standard.yaml)")
    parser.add_argument("--base-url", required=True, help="LLM API base URL")
    parser.add_argument("--model", default=None, help="Override model from battery config")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count(), help="Max parallel jobs (default: CPU count)")
    parser.add_argument("--max-context", type=int, default=None, help="Override max_context from battery config")
    args = parser.parse_args()

    if not args.battery.exists():
        print(f"Battery config not found: {args.battery}")
        sys.exit(1)

    config = yaml.safe_load(args.battery.read_text())
    model = args.model or config.get("model")
    if not model:
        print("Error: model not specified (set in battery config or pass --model)")
        sys.exit(1)

    max_context = args.max_context if args.max_context is not None else config.get("max_context", 0)

    battery_name = args.battery.stem
    runs_dir = RUNS_DIR / battery_name
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    runs_dir.mkdir(parents=True)

    runs: list[tuple[str, list[Path]]] = []
    for entry in config.get("runs", []):
        name, files = _resolve_run(entry)
        if files:
            runs.append((name, files))

    if not runs:
        print("No runs resolved from battery config")
        sys.exit(1)

    n_groups = sum(1 for _, files in runs if len(files) > 1)
    n_single = len(runs) - n_groups
    print(f"Battery: {battery_name} ({model})")
    print(f"Running {len(runs)} runs ({n_single} single-doc, {n_groups} multi-doc) with {args.jobs} parallel jobs\n")

    failed = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, files, name, args.base_url, model, runs_dir, max_context): name
            for name, files in runs
        }
        for future in as_completed(futures):
            name, ok, output = future.result()
            if ok:
                print(f"  OK  {name}")
            else:
                failed.append(name)
                print(f"  FAIL  {name}")
                for line in output.strip().splitlines()[-3:]:
                    print(f"        {line}")

    print(f"\nDone. {len(runs) - len(failed)} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Output: {runs_dir}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
