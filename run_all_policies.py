#!/usr/bin/env python3
"""Run the risk landscaper pipeline against every file in policy_examples/."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

POLICY_DIR = Path(__file__).parent / "policy_examples"
RUNS_DIR = Path(__file__).parent / "runs"
NEXUS_BASE_DIR = "/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="LLM API base URL")
    parser.add_argument("model", help="LLM model name")
    args = parser.parse_args()

    if RUNS_DIR.exists():
        shutil.rmtree(RUNS_DIR)
    RUNS_DIR.mkdir()

    policies = sorted(POLICY_DIR.iterdir())
    if not policies:
        print("No policy files found in policy_examples/")
        sys.exit(1)

    failed = []
    for policy in policies:
        if policy.name.startswith("."):
            continue
        name = policy.stem
        out = RUNS_DIR / name
        print(f"=== {name} ===")
        result = subprocess.run(
            [
                "uv", "run", "risk-landscaper", "run", str(policy), "-o", str(out),
                "--base-url", args.base_url,
                "--model", args.model,
                "--nexus-base-dir", NEXUS_BASE_DIR,
            ],
        )
        if result.returncode != 0:
            failed.append(name)
            print(f"  !! FAILED\n")
        else:
            print(f"  -> {out}\n")

    succeeded = len(policies) - len(failed)
    print(f"Done. {succeeded} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Output: {RUNS_DIR}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
