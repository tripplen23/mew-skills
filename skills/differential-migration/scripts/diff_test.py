#!/usr/bin/env python3
"""Differential testing: feed equivalent inputs to old and new implementations, compare outputs.

Usage:
    python diff_test.py --old "python -m src.app" --new "./target/bin/app" \
        --corpus fixtures/ --output parity-report.json \
        --normalize json_keyorder,whitespace \
        --tolerance exact

Produces a parity-report.json conforming to schemas/parity-report.schema.json.
Exit codes: 0=pass, 1=mismatch, 2=error.
"""
import argparse, json, subprocess, sys, os, hashlib
from datetime import datetime, timezone
from pathlib import Path

def canonicalize_json(text):
    """Sort keys, reject non-finite floats (allow_nan=False), fixed separators."""
    try:
        data = json.loads(text)
        return json.dumps(data, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

def normalize(text, rules):
    """Apply normalization rules to output."""
    if "json_keyorder" in rules:
        canon = canonicalize_json(text)
        if canon is not None:
            return canon
    if "whitespace" in rules:
        text = text.strip()
    return text

def compare_floats(old_val, new_val, tolerance):
    """Compare floats using PEP 485 isclose semantics."""
    if tolerance == "exact":
        return old_val == new_val
    elif tolerance == "isclose":
        rel_tol = 1e-9
        abs_tol = 1e-12
        return abs(old_val - new_val) <= max(
            rel_tol * max(abs(old_val), abs(new_val)), abs_tol
        )
    return old_val == new_val

def run_implementation(cmd, input_data):
    """Run an implementation with given input and capture output."""
    if isinstance(cmd, str):
        import shlex
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = list(cmd)
    try:
        proc = subprocess.run(
            cmd_list, input=input_data,
            capture_output=True, text=True, timeout=30
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT"}
    except FileNotFoundError:
        return {"exit_code": -1, "stdout": "", "stderr": "COMMAND_NOT_FOUND"}

def compare_outputs(old, new, normalization_rules, tolerance):
    """Compare two implementation outputs."""
    old_norm = normalize(old["stdout"], normalization_rules)
    new_norm = normalize(new["stdout"], normalization_rules)
    exit_match = old["exit_code"] == new["exit_code"]
    output_match = old_norm == new_norm
    return exit_match and output_match, {
        "exit_match": exit_match,
        "output_match": output_match,
        "old_exit": old["exit_code"],
        "new_exit": new["exit_code"],
    }

def main():
    parser = argparse.ArgumentParser(
        description="Differential testing — compare old vs new implementation outputs"
    )
    parser.add_argument("--old", required=True, help="Command to run old implementation")
    parser.add_argument("--new", required=True, help="Command to run new implementation")
    parser.add_argument("--corpus", required=True, help="Directory with test input files")
    parser.add_argument("--normalize", default="json_keyorder,whitespace",
                        help="Comma-separated normalization rules")
    parser.add_argument("--tolerance", default="exact",
                        choices=["exact", "isclose", "ulps"],
                        help="Float comparison tolerance class (PEP 485 semantics for isclose)")
    parser.add_argument("--output", default="parity-report.json")
    parser.add_argument("--run-id", help="Run ID (format: YYYYMMDD-HHMMSS-<7chars>). Auto-generated if omitted.")
    args = parser.parse_args()

    rules = [r.strip() for r in args.normalize.split(",") if r.strip()]
    results = []
    passed = 0
    mismatches = 0

    corpus_path = Path(args.corpus)
    if not corpus_path.is_dir():
        print(f"Error: corpus directory not found: {args.corpus}", file=sys.stderr)
        sys.exit(2)

    for filename in sorted(os.listdir(args.corpus)):
        filepath = corpus_path / filename
        if not filepath.is_file():
            continue
        input_data = filepath.read_text()

        old_result = run_implementation(args.old, input_data)
        new_result = run_implementation(args.new, input_data)
        equal, detail = compare_outputs(old_result, new_result, rules, args.tolerance)

        # Property IDs follow the parity-report schema pattern: P\d{3,}
        prop_id = f"P{len(results) + 1:03d}"
        entry = {
            "property_id": prop_id,
            "status": "pass" if equal else "mismatch",
            "old_output": {"exit_code": old_result["exit_code"]},
            "new_output": {"exit_code": new_result["exit_code"]},
            "normalized_equal": equal,
        }
        if not equal:
            entry["old_output"]["stdout"] = old_result["stdout"][:500]
            entry["new_output"]["stdout"] = new_result["stdout"][:500]
            entry["classification"] = "regression"
            mismatches += 1
        else:
            passed += 1
        results.append(entry)

    total = passed + mismatches
    if total == 0:
        print("Error: no input files found in corpus", file=sys.stderr)
        sys.exit(2)

    verdict = "pass" if mismatches == 0 else (
        "conditional_pass" if mismatches < total * 0.1 else "fail"
    )

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") +         hashlib.sha256(str(datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:7]

    report = {
        "run_id": run_id,
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
    sys.exit(0 if verdict == "pass" else 1)

if __name__ == "__main__":
    main()
