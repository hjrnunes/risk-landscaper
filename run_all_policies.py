#!/usr/bin/env python3
"""Run the risk landscaper pipeline against every file in policy_examples/."""

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

POLICY_DIR = Path(__file__).parent / "policy_examples"
RUNS_DIR = Path(__file__).parent / "runs"
NEXUS_BASE_DIR = "/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus"


def run_one(policy: Path, base_url: str, model: str) -> tuple[str, bool, str]:
    name = policy.stem
    out = RUNS_DIR / name
    result = subprocess.run(
        [
            "uv", "run", "risk-landscaper", "run", str(policy), "-o", str(out),
            "--base-url", base_url,
            "--model", model,
            "--nexus-base-dir", NEXUS_BASE_DIR,
        ],
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
    args = parser.parse_args()

    if RUNS_DIR.exists():
        shutil.rmtree(RUNS_DIR)
    RUNS_DIR.mkdir()

    policies = sorted(p for p in POLICY_DIR.iterdir() if not p.name.startswith("."))
    if not policies:
        print("No policy files found in policy_examples/")
        sys.exit(1)

    print(f"Running {len(policies)} policies with {args.jobs} parallel jobs\n")

    failed = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, policy, args.base_url, args.model): policy
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
    print(f"Output: {RUNS_DIR}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
