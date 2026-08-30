from __future__ import annotations

from pathlib import Path

from webhookwitness.runner import run_scenario
from webhookwitness.scenario import load_scenario

ROOT = Path(__file__).parents[1]


def test_checked_in_passing_example_proves_invariant(tmp_path: Path) -> None:
    result = run_scenario(
        load_scenario(ROOT / "examples/passing.json"), tmp_path / "passing-artifacts"
    )

    assert result.passed is True


def test_checked_in_broken_example_is_detected(tmp_path: Path) -> None:
    result = run_scenario(
        load_scenario(ROOT / "examples/failing.json"), tmp_path / "failing-artifacts"
    )

    assert result.passed is False
    assert result.probe.detail == "probe JSON does not equal the expected value"
