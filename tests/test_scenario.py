from __future__ import annotations

import json
from pathlib import Path

import pytest

from webhookwitness.errors import ScenarioError
from webhookwitness.scenario import load_scenario


def valid_document() -> dict[str, object]:
    return {
        "version": 1,
        "name": "payment retry contract",
        "service": {
            "command": ["python", "handler.py"],
            "ready": {
                "url": "http://127.0.0.1:8765/health",
                "timeout_seconds": 4,
                "interval_ms": 50,
            },
        },
        "defaults": {
            "url": "http://127.0.0.1:8765/webhook",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 2,
        },
        "events": {
            "completed": {
                "body": {"id": "evt-2", "kind": "completed", "sequence": 2},
                "headers": {"X-Event-ID": "evt-2"},
            }
        },
        "deliveries": [
            {
                "name": "initial completion",
                "event": "completed",
                "delay_ms": 5,
                "expect": {"statuses": [200, 202]},
            }
        ],
        "probe": {
            "command": ["python", "probe.py"],
            "expect": {"exit_code": 0, "json": {"effects": 1}},
        },
    }


def write_scenario(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_loads_strict_scenario_and_canonicalizes_json_body(tmp_path: Path) -> None:
    scenario = load_scenario(write_scenario(tmp_path, valid_document()))

    assert scenario.name == "payment retry contract"
    assert scenario.service.command == ("python", "handler.py")
    assert scenario.events["completed"].body == (b'{"id":"evt-2","kind":"completed","sequence":2}')
    assert scenario.deliveries[0].expected_statuses == (200, 202)
    assert scenario.probe.expected_json == {"effects": 1}


def test_loads_exact_raw_body_from_scenario_directory(tmp_path: Path) -> None:
    (tmp_path / "payload.bin").write_bytes(b'{ "kept": "exact" }\n')
    document = valid_document()
    document["events"] = {"raw": {"body_file": "payload.bin"}}
    deliveries = document["deliveries"]
    assert isinstance(deliveries, list)
    deliveries[0]["event"] = "raw"

    scenario = load_scenario(write_scenario(tmp_path, document))

    assert scenario.events["raw"].body == b'{ "kept": "exact" }\n'


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"surprise": True}), "unknown field"),
        (
            lambda value: value["defaults"].update({"url": "https://example.com/hook"}),
            "loopback",
        ),
        (
            lambda value: value["service"].update({"command": "python handler.py"}),
            "array",
        ),
        (
            lambda value: value["events"]["completed"].update({"body_file": "other.json"}),
            "exactly one",
        ),
    ],
)
def test_rejects_ambiguous_or_unsafe_fields(tmp_path: Path, mutate: object, message: str) -> None:
    document = valid_document()
    assert callable(mutate)
    mutate(document)

    with pytest.raises(ScenarioError, match=message):
        load_scenario(write_scenario(tmp_path, document))


def test_rejects_body_file_outside_scenario_directory(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-payload.json"
    outside.write_text("{}", encoding="utf-8")
    document = valid_document()
    document["events"] = {"raw": {"body_file": "../outside-payload.json"}}
    deliveries = document["deliveries"]
    assert isinstance(deliveries, list)
    deliveries[0]["event"] = "raw"

    with pytest.raises(ScenarioError, match="inside the scenario directory"):
        load_scenario(write_scenario(tmp_path, document))


def test_rejects_unknown_delivery_event(tmp_path: Path) -> None:
    document = valid_document()
    deliveries = document["deliveries"]
    assert isinstance(deliveries, list)
    deliveries[0]["event"] = "missing"

    with pytest.raises(ScenarioError, match="unknown event"):
        load_scenario(write_scenario(tmp_path, document))
