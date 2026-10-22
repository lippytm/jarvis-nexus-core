"""Run source checks, deterministic tests and the offline demo; save evidence.

Run from the repository root: python scripts/verify_control_tower.py
This command performs no installation, model call or deployment.
"""
import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/control_tower_verification.json")
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT) or output.suffix != ".json":
        parser.error("output must be a JSON path inside this repository")
    sources = sorted([*ROOT.joinpath("control_tower").glob("*.py"),
                      *ROOT.joinpath("tests").glob("test_*.py"), *ROOT.joinpath("scripts").glob("*.py")])
    hashes, syntax_errors = {}, []
    for path in sources:
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        hashes[relative] = sha256(content).hexdigest()
        try:
            ast.parse(content.decode("utf-8"), filename=relative)
        except (SyntaxError, UnicodeError, ValueError) as exc:
            syntax_errors.append({"file": relative, "kind": type(exc).__name__})
    for path in sorted([*ROOT.joinpath("web").glob("*.html"), *ROOT.joinpath("tests").glob("*.mjs"),
                        *ROOT.joinpath(".github/workflows").glob("*.yml")]):
        hashes[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    stream = io.StringIO()
    result = None
    if not syntax_errors:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    successful = result is not None and result.wasSuccessful()
    demonstration = None
    if successful:
        from control_tower.demo import demonstrate
        demonstration = demonstrate()
    ci_sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[a-f0-9]{40}", ci_sha):
        ci_sha = None
    report = {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "scope": "syntax_offline_unit_tests_and_synthetic_demo",
        "composer_runtime_tests": "separate Node web test job covers composer, portfolio, diary and media-player helpers; HTML/JS hashes included here",
        "github_checkout_sha": ci_sha,
        "syntax": {"files_checked": len(sources), "errors": syntax_errors},
        "tests": {"run": result.testsRun if result else 0,
                  "failures": len(result.failures) if result else 0,
                  "errors": len(result.errors) if result else 0,
                  "skipped": len(result.skipped) if result else 0,
                  "passed": successful},
        "source_sha256": hashes,
        "synthetic_demo": demonstration,
        "live_integrations_tested": False,
        "independent_human_security_review": "not_performed",
        "production_deployment": "not_performed",
    }
    report["record_sha256"] = sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.with_suffix(".txt").write_text(stream.getvalue(), encoding="utf-8")
    print(json.dumps({"passed": successful, "tests": report["tests"],
                      "syntax_files": len(sources), "evidence": str(output.relative_to(ROOT)),
                      "record_sha256": report["record_sha256"]}))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
