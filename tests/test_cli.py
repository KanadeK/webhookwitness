from __future__ import annotations

import json
from pathlib import Path

from webhookwitness.cli import main


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
