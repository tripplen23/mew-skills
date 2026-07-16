#!/usr/bin/env python3
"""Differential testing: feed equivalent inputs to old and new implementations, compare outputs.

Usage:
    python diff_test.py --old "python -m src.app" --new "./target/bin/app" --corpus fixtures/ --output parity-report.json

This is a template — adapt the comparison and normalization logic to your system.
"""
import argparse, json, subprocess, sys, os
from datetime import datetime, timezone

def run_implementation(cmd, input_data):
    """Run an implementation with given input and capture output."""
    proc = subprocess.run(
        cmd, shell=True, input=input_data,
        capture_output=True, text=True, timeout=30
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

def normalize(text, rules):
    """Apply normalization rules to output."""
    if "json_keyorder" in rules:
        try:
            text = json.dumps(json.loads(text), sort_keys=True)
        except (json.JSONDecodeError, TypeError):
            pass
    if "whitespace" in rules:
        text = text.strip()
    return text

def compare_outputs(old, new, normalization_rules):
    """Compare two implementation outputs."""
    old_norm = normalize(old["stdout"], normalization_rules)
    new_norm = normalize(new["stdout"], normalization_rules)
    return old_norm == new_norm and old["exit_code"] == new["exit_code"]

def main():
    parser = argparse.ArgumentParser(description="Differential testing")
    parser.add_argument("--old", required=True, help="Command to run old implementation")
    parser.add_argument("--new", required=True, help="Command to run new implementation")
    parser.add_argument("--corpus", required=True, help="Directory with test input files")
    parser.add_argument("--normalize", default="json_keyorder,whitespace", help="Comma-separated normalization rules")
    parser.add_argument("--output", default="parity-report.json")
    args = parser.parse_args()

    rules = args.normalize.split(",")
    results = []
    passed = 0
    mismatches = 0

    for filename in sorted(os.listdir(args.corpus)):
        filepath = os.path.join(args.corpus, filename)
        if not os.path.isfile(filepath):
            continue
        with open(filepath) as f:
            input_data = f.read()

        old_result = run_implementation(args.old, input_data)
        new_result = run_implementation(args.new, input_data)
        equal = compare_outputs(old_result, new_result, rules)

        entry = {
            "input_file": filename,
            "status": "pass" if equal else "mismatch",
            "old_exit": old_result["exit_code"],
            "new_exit": new_result["exit_code"],
            "normalized_equal": equal,
        }
        if not equal:
            entry["old_stdout"] = old_result["stdout"][:500]
            entry["new_stdout"] = new_result["stdout"][:500]
            mismatches += 1
        else:
            passed += 1
        results.append(entry)

    total = passed + mismatches
    verdict = "pass" if mismatches == 0 else ("conditional_pass" if mismatches < total * 0.1 else "fail")

    report = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "total_properties": total,
        "passed": passed,
        "mismatches": mismatches,
        "verdict": verdict,
        "results": results,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDifferential test: {passed}/{total} passed, {mismatches} mismatches → {verdict}")
    print(f"Report: {args.output}")

if __name__ == "__main__":
    main()
