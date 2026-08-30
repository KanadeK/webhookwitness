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


def test_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "scenario.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ScenarioError, match="cannot read scenario JSON"):
        load_scenario(path)


def test_rejects_non_object_document(tmp_path: Path) -> None:
    path = tmp_path / "scenario.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ScenarioError, match="scenario must be an object"):
        load_scenario(path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"name": "  "}), "non-empty string"),
        (lambda value: value.update({"events": {}}), "events must not be empty"),
        (lambda value: value.update({"deliveries": []}), "deliveries must contain 1 to 100"),
        (
            lambda value: value["deliveries"].append(dict(value["deliveries"][0])),
            "duplicate delivery name",
        ),
        (lambda value: value["service"].update({"command": []}), "non-empty argv"),
        (
            lambda value: value["service"].update({"cwd": "missing-directory"}),
            "existing directory",
        ),
        (
            lambda value: value["defaults"].update({"timeout_seconds": True}),
            "must be a number",
        ),
        (
            lambda value: value["service"]["ready"].update({"interval_ms": 9}),
            "must be between 10 and 5000",
        ),
        (
            lambda value: value["defaults"].update({"headers": {"Host": "example"}}),
            "cannot set transport header",
        ),
        (
            lambda value: value["defaults"].update({"headers": {"X-Test": 7}}),
            "must be a string",
        ),
        (
            lambda value: value["defaults"].update({"headers": {"X-Test": "bad\nvalue"}}),
            "cannot contain newlines",
        ),
        (
            lambda value: value["deliveries"][0].update({"delay_ms": 1.5}),
            "must be an integer",
        ),
        (
            lambda value: value["deliveries"][0]["expect"].update({"statuses": []}),
            "must not be empty",
        ),
        (
            lambda value: value["deliveries"][0]["expect"].update({"statuses": [202, 202]}),
            "must not contain duplicates",
        ),
        (
            lambda value: value["probe"]["expect"].pop("json"),
            "expect.json is required",
        ),
        (
            lambda value: value.update(
                {
                    "events": {"raw": {"body_file": "missing.json"}},
                    "deliveries": [{"name": "raw", "event": "raw", "expect": {"statuses": [202]}}],
                }
            ),
            "existing file",
        ),
    ],
)
def test_rejects_invalid_boundary_values(tmp_path: Path, mutate: object, message: str) -> None:
    document = valid_document()
    assert callable(mutate)
    mutate(document)

    with pytest.raises(ScenarioError, match=message):
        load_scenario(write_scenario(tmp_path, document))


def test_rejects_absolute_working_directory(tmp_path: Path) -> None:
    document = valid_document()
    service = document["service"]
    assert isinstance(service, dict)
    service["cwd"] = str(tmp_path.resolve())

    with pytest.raises(ScenarioError, match="inside the scenario directory"):
        load_scenario(write_scenario(tmp_path, document))


def test_rejects_oversized_event_body(tmp_path: Path) -> None:
    document = valid_document()
    document["events"] = {"large": {"body": "x" * 1_048_577}}
    deliveries = document["deliveries"]
    assert isinstance(deliveries, list)
    deliveries[0]["event"] = "large"

    with pytest.raises(ScenarioError, match="body exceeds 1048576 bytes"):
        load_scenario(write_scenario(tmp_path, document))
