#!/usr/bin/env python3
"""Run the risk landscaper pipeline against every file in policy_examples/."""

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
POLICY_DIR = ROOT / "policy_examples"
RUNS_DIR = ROOT / "runs"
NEXUS_BASE_DIR = "/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus"

POLICY_EXTENSIONS = {".json", ".md", ".txt", ".pdf", ".docx", ".html", ".htm"}


def run_one(policy: Path, base_url: str, model: str, runs_dir: Path, max_context: int = 0) -> tuple[str, bool, str]:
    name = policy.stem
    out = runs_dir / name
    cmd = [
        "uv", "run", "risk-landscaper", "run", str(policy), "-o", str(out),
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="LLM API base URL")
    parser.add_argument("model", help="LLM model name")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count(), help="Max parallel jobs (default: CPU count)")
    parser.add_argument("-d", "--dir", type=str, default=None, help="Subdirectory of policy_examples/ to run (e.g. frontier_safety)")
    parser.add_argument("--max-context", type=int, default=0, help="Model context window size in tokens (passed to risk-landscaper)")
    args = parser.parse_args()

    source_dir = POLICY_DIR / args.dir if args.dir else POLICY_DIR
    if not source_dir.is_dir():
        print(f"Directory not found: {source_dir}")
        sys.exit(1)

    runs_dir = RUNS_DIR / args.dir if args.dir else RUNS_DIR
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    runs_dir.mkdir(parents=True)

    policies = sorted(
        p for p in source_dir.rglob("*")
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in POLICY_EXTENSIONS
    )
    if not policies:
        print(f"No policy files found in {source_dir}")
        sys.exit(1)

    print(f"Running {len(policies)} policies with {args.jobs} parallel jobs\n")

    failed = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, policy, args.base_url, args.model, runs_dir, args.max_context): policy
            for policy in policies
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

    print(f"\nDone. {len(policies) - len(failed)} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Output: {runs_dir}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
