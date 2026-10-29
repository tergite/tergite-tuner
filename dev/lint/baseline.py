# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Fails when a linter finds what its baseline does not list, or the baseline lists what it no longer finds.

    python -m dev.lint.baseline ruff|pylint|vulture [--update]

Findings are keyed by file, rule and message, not by line, so moving code does not
churn the baseline. A commit that fixes a finding runs --update and commits the
shorter baseline; no commit adds to it.
"""

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

PATHS = ["tergite_tuner", "conftest.py", "dev"]
BASELINE_DIR = Path(__file__).parent


def main(tool: str, should_update: bool) -> int:
    findings = Counter(_FINDERS[tool]())
    baseline_path = BASELINE_DIR / f"{tool}_baseline.txt"
    if should_update:
        _write_baseline(baseline_path, findings)
        return 0
    baseline = Counter(baseline_path.read_text().splitlines())
    new_findings = findings - baseline
    fixed_findings = baseline - findings
    _report("New findings, fix them", new_findings)
    _report(
        f"Fixed findings, run `--update` to drop them from {baseline_path}",
        fixed_findings,
    )
    return 1 if new_findings or fixed_findings else 0


def get_ruff_findings() -> list[str]:
    output = _run(["ruff", "check", *PATHS, "--output-format", "json", "--exit-zero"])
    return [
        f"{_relative(item['filename'])}: {item['code']} {item['message']}"
        for item in json.loads(output)
    ]


def get_pylint_findings() -> list[str]:
    output = _run(["pylint", *PATHS, "--output-format", "json2", "--exit-zero"])
    return [_get_pylint_key(item) for item in json.loads(output)["messages"]]


def get_vulture_findings() -> list[str]:
    """Unused definitions only: vulture calls pydantic fields unused variables, and ruff covers real ones."""
    output = _run(["vulture", *PATHS])
    return [
        re.sub(r":\d+: (.*) \(\d+% confidence\)$", r": \1", line)
        for line in output.splitlines()
        if line and not re.search(r": unused (variable|attribute) ", line)
    ]


_FINDERS = {
    "ruff": get_ruff_findings,
    "pylint": get_pylint_findings,
    "vulture": get_vulture_findings,
}


def _write_baseline(path: Path, findings: Counter) -> None:
    path.write_text("".join(f"{finding}\n" for finding in sorted(findings.elements())))


def _report(title: str, findings: Counter) -> None:
    if findings:
        print(f"{title}:")
        for finding in sorted(findings.elements()):
            print(f"  {finding}")


def _run(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout


def _relative(path: str) -> str:
    return str(Path(path).resolve().relative_to(Path.cwd()))


def _get_pylint_key(item: dict) -> str:
    """Duplicates are keyed by the modules they span; size checks by the function, not its count."""
    if item["symbol"] == "duplicate-code":
        modules = sorted(set(re.findall(r"^==([\w.]+):", item["message"], re.M)))
        return f"duplicate-code: {', '.join(modules)}"
    return f"{item['path']}: {item['symbol']} {item['obj']}"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], should_update="--update" in sys.argv[2:]))
