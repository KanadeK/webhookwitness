from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from webhookwitness.errors import SetupError
from webhookwitness.runner import run_scenario
from webhookwitness.scenario import load_scenario

FIXTURES = Path(__file__).parent / "fixtures"


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def scenario_document(tmp_path: Path, *, broken: bool = False) -> dict[str, object]:
    port = free_port()
    state = tmp_path / "state.json"
    command = [
        "{python}",
        str(FIXTURES / "service.py"),
        "--port",
        str(port),
        "--state",
        str(state),
    ]
    if broken:
        command.append("--broken")
    expected = {
        "effect_count": 1,
        "processed_event_ids": ["evt-completed", "evt-pending"],
        "sequence": 2,
        "status": "completed",
    }
    return {
        "version": 1,
        "name": "webhook idempotency",
        "service": {
            "command": command,
            "ready": {
                "url": f"http://127.0.0.1:{port}/health",
                "timeout_seconds": 3,
                "interval_ms": 20,
            },
        },
        "defaults": {
            "url": f"http://127.0.0.1:{port}/webhook",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 2,
        },
        "events": {
            "completed": {"body": {"id": "evt-completed", "kind": "completed", "sequence": 2}},
            "pending": {"body": {"id": "evt-pending", "kind": "pending", "sequence": 1}},
        },
        "deliveries": [
            {"name": "newest first", "event": "completed", "expect": {"statuses": [202]}},
            {"name": "stale second", "event": "pending", "expect": {"statuses": [202]}},
            {
                "name": "duplicate newest",
                "event": "completed",
                "delay_ms": 5,
                "expect": {"statuses": [202]},
            },
        ],
        "probe": {
            "command": ["{python}", str(FIXTURES / "probe.py"), str(state)],
            "timeout_seconds": 3,
            "expect": {"exit_code": 0, "json": expected},
        },
    }


def load_document(tmp_path: Path, document: dict[str, object]):  # type: ignore[no-untyped-def]
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return load_scenario(path)


def test_real_handler_passes_duplicate_and_out_of_order_contract(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"

    result = run_scenario(load_document(tmp_path, scenario_document(tmp_path)), artifacts)

    assert result.passed is True
    assert [delivery.status for delivery in result.deliveries] == [202, 202, 202]
    assert result.probe.passed is True
    assert (artifacts / "service.stdout.log").is_file()
    assert (artifacts / "service.stderr.log").is_file()
    assert (artifacts / "probe.stdout.log").is_file()
    assert (artifacts / "probe.stderr.log").is_file()


def test_broken_handler_fails_on_duplicate_effect_and_state_regression(tmp_path: Path) -> None:
    result = run_scenario(
        load_document(tmp_path, scenario_document(tmp_path, broken=True)), tmp_path / "artifacts"
    )

    assert result.passed is False
    assert result.probe.passed is False
    assert result.probe.actual_json == {
        "effect_count": 2,
        "processed_event_ids": ["evt-completed", "evt-pending"],
        "sequence": 2,
        "status": "completed",
    }


def test_unexpected_http_status_fails_delivery_but_still_runs_probe(tmp_path: Path) -> None:
    document = scenario_document(tmp_path)
    events = document["events"]
    assert isinstance(events, dict)
    events["rejected"] = {"body": {"id": "evt-r", "kind": "reject", "sequence": 3}}
    deliveries = document["deliveries"]
    assert isinstance(deliveries, list)
    deliveries.append({"name": "rejected", "event": "rejected", "expect": {"statuses": [202]}})

    result = run_scenario(load_document(tmp_path, document), tmp_path / "artifacts")

    assert result.passed is False
    assert result.deliveries[-1].status == 422
    assert result.deliveries[-1].passed is False
    assert result.probe.passed is True


def test_invalid_probe_json_is_a_contract_failure(tmp_path: Path) -> None:
    document = scenario_document(tmp_path)
    probe = document["probe"]
    assert isinstance(probe, dict)
    command = probe["command"]
    assert isinstance(command, list)
    command.append("--invalid")

    result = run_scenario(load_document(tmp_path, document), tmp_path / "artifacts")

    assert result.passed is False
    assert result.probe.actual_json is None
    assert result.probe.detail == "probe stdout is not valid JSON"


def test_service_exit_before_readiness_is_setup_error(tmp_path: Path) -> None:
    document = scenario_document(tmp_path)
    service = document["service"]
    assert isinstance(service, dict)
    service["command"] = ["{python}", "-c", "raise SystemExit(7)"]

    with pytest.raises(SetupError, match="exited before readiness with code 7"):
        run_scenario(load_document(tmp_path, document), tmp_path / "artifacts")
