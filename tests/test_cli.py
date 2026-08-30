from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from webhookwitness import cli
from webhookwitness.cli import main
from webhookwitness.runner import ProbeResult, RunResult

ROOT = Path(__file__).parents[1]


def minimal_invalid_scenario(tmp_path: Path) -> Path:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    return path


def test_validate_reports_invalid_input_as_exit_two(tmp_path: Path, capsys: object) -> None:
    exit_code = main(["validate", str(minimal_invalid_scenario(tmp_path))])

    assert exit_code == 2
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "error: scenario.version must be 1" in captured.err


def test_version_is_available_from_module(capsys: object) -> None:
    exit_code = main(["version"])

    assert exit_code == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out == "WebhookWitness 0.1.0\n"


def test_validate_reports_scenario_summary(capsys: object) -> None:
    exit_code = main(["validate", str(ROOT / "examples/passing.json")])

    assert exit_code == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out == "VALID dedupe-and-monotonic-state-pass: 2 events, 3 deliveries\n"


def test_run_maps_passing_and_failing_contracts_to_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: object
) -> None:
    passing = tmp_path / "passing"
    failing = tmp_path / "failing"
    scenario = type("ScenarioView", (), {"name": "contract", "events": {}, "deliveries": ()})()
    probe = ProbeResult(
        exit_code=0,
        expected_exit_code=0,
        actual_json={},
        expected_json={},
        passed=True,
        detail="",
    )
    results = iter(
        [
            RunResult("passing contract", (), probe, True),
            RunResult("failing contract", (), probe, False),
        ]
    )
    monkeypatch.setattr(cli, "load_scenario", lambda path: scenario)
    monkeypatch.setattr(cli, "run_scenario", lambda loaded, artifacts: next(results))
    monkeypatch.setattr(cli, "write_reports", lambda result, artifacts: None)

    assert main(["run", str(ROOT / "examples/passing.json"), "--artifacts", str(passing)]) == 0
    assert main(["run", str(ROOT / "examples/failing.json"), "--artifacts", str(failing)]) == 1

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "PASS passing contract" in captured.out
    assert "FAIL failing contract" in captured.out


def test_package_module_entrypoint_prints_version(
    monkeypatch: pytest.MonkeyPatch, capsys: object
) -> None:
    monkeypatch.setattr(sys, "argv", ["webhookwitness", "version"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("webhookwitness.__main__", run_name="__main__")

    assert raised.value.code == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out == "WebhookWitness 0.1.0\n"
