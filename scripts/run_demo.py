"""Run both checked-in examples and verify their opposite outcomes."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = ROOT / ".tmp"


def run(command: list[str], expected: int) -> None:
    print(f"+ {subprocess.list2cmdline(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != expected:
        raise SystemExit(
            f"expected exit {expected}, received {completed.returncode}: "
            f"{subprocess.list2cmdline(command)}"
        )


def main() -> None:
    TMP.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="demo-", dir=TMP) as directory:
        base = Path(directory)
        passing = base / "passing"
        failing = base / "failing"
        module = [sys.executable, "-m", "webhookwitness"]

        run([*module, "validate", "examples/passing.json"], 0)
        run([*module, "run", "examples/passing.json", "--artifacts", str(passing)], 0)
        passing_report = json.loads((passing / "report.json").read_text(encoding="utf-8"))
        if passing_report["passed"] is not True:
            raise SystemExit("passing example report did not pass")

        run([*module, "run", "examples/failing.json", "--artifacts", str(failing)], 1)
        failing_report = json.loads((failing / "report.json").read_text(encoding="utf-8"))
        if failing_report["passed"] is not False or failing_report["probe"]["passed"] is not False:
            raise SystemExit("failing example did not expose a final-state mismatch")

    print("WEBHOOKWITNESS_DEMO=PASS")


if __name__ == "__main__":
    main()
