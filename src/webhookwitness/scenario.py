"""Strict scenario parsing and boundary validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast
from urllib.parse import urlsplit

from webhookwitness.errors import ScenarioError

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

MAX_BODY_BYTES = 1_048_576
MAX_DELIVERIES = 100
FORBIDDEN_HEADERS = {"connection", "content-length", "host", "transfer-encoding"}


@dataclass(frozen=True)
class ReadySpec:
    url: str
    timeout_seconds: float
    interval_ms: int


@dataclass(frozen=True)
class ServiceSpec:
    command: tuple[str, ...]
    cwd: Path
    ready: ReadySpec
    shutdown_timeout_seconds: float


@dataclass(frozen=True)
class DefaultsSpec:
    url: str
    headers: dict[str, str]
    timeout_seconds: float


@dataclass(frozen=True)
class EventSpec:
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True)
class DeliverySpec:
    name: str
    event: str
    delay_ms: int
    expected_statuses: tuple[int, ...]


@dataclass(frozen=True)
class ProbeSpec:
    command: tuple[str, ...]
    cwd: Path
    timeout_seconds: float
    expected_exit_code: int
    expected_json: JsonValue


@dataclass(frozen=True)
class Scenario:
    source: Path
    name: str
    service: ServiceSpec
    defaults: DefaultsSpec
    events: dict[str, EventSpec]
    deliveries: tuple[DeliverySpec, ...]
    probe: ProbeSpec


def load_scenario(path: Path) -> Scenario:
    source = path.resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ScenarioError(f"cannot read scenario JSON: {error}") from error
    root = _object(raw, "scenario")
    _keys(
        root,
        {"version", "name", "service", "defaults", "events", "deliveries", "probe"},
        "scenario",
    )
    if root.get("version") != 1:
        raise ScenarioError("scenario.version must be 1")

    base = source.parent
    service = _parse_service(root.get("service"), base)
    defaults = _parse_defaults(root.get("defaults"))
    events = _parse_events(root.get("events"), base)
    deliveries = _parse_deliveries(root.get("deliveries"), events)
    probe = _parse_probe(root.get("probe"), base)
    return Scenario(
        source=source,
        name=_nonempty_string(root.get("name"), "scenario.name"),
        service=service,
        defaults=defaults,
        events=events,
        deliveries=deliveries,
        probe=probe,
    )


def _parse_service(value: object, base: Path) -> ServiceSpec:
    data = _object(value, "scenario.service")
    _keys(data, {"command", "cwd", "ready", "shutdown_timeout_seconds"}, "scenario.service")
    ready_data = _object(data.get("ready"), "scenario.service.ready")
    _keys(ready_data, {"url", "timeout_seconds", "interval_ms"}, "scenario.service.ready")
    ready = ReadySpec(
        url=_loopback_url(ready_data.get("url"), "scenario.service.ready.url"),
        timeout_seconds=_bounded_number(
            ready_data.get("timeout_seconds", 5), "scenario.service.ready.timeout_seconds", 0.1, 60
        ),
        interval_ms=_bounded_integer(
            ready_data.get("interval_ms", 100), "scenario.service.ready.interval_ms", 10, 5_000
        ),
    )
    return ServiceSpec(
        command=_command(data.get("command"), "scenario.service.command"),
        cwd=_relative_directory(data.get("cwd", "."), base, "scenario.service.cwd"),
        ready=ready,
        shutdown_timeout_seconds=_bounded_number(
            data.get("shutdown_timeout_seconds", 3),
            "scenario.service.shutdown_timeout_seconds",
            0.1,
            30,
        ),
    )


def _parse_defaults(value: object) -> DefaultsSpec:
    data = _object(value, "scenario.defaults")
    _keys(data, {"url", "headers", "timeout_seconds"}, "scenario.defaults")
    return DefaultsSpec(
        url=_loopback_url(data.get("url"), "scenario.defaults.url"),
        headers=_headers(data.get("headers", {}), "scenario.defaults.headers"),
        timeout_seconds=_bounded_number(
            data.get("timeout_seconds", 5), "scenario.defaults.timeout_seconds", 0.1, 30
        ),
    )


def _parse_events(value: object, base: Path) -> dict[str, EventSpec]:
    data = _object(value, "scenario.events")
    if not data:
        raise ScenarioError("scenario.events must not be empty")
    events: dict[str, EventSpec] = {}
    for name, raw_event in data.items():
        _nonempty_string(name, "scenario.events key")
        event = _object(raw_event, f"scenario.events.{name}")
        _keys(event, {"body", "body_file", "headers"}, f"scenario.events.{name}")
        has_body = "body" in event
        has_file = "body_file" in event
        if has_body == has_file:
            raise ScenarioError(
                f"scenario.events.{name} must contain exactly one of body or body_file"
            )
        if has_body:
            body = json.dumps(
                cast(JsonValue, event["body"]), ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        else:
            body_path = _relative_file(
                event["body_file"], base, f"scenario.events.{name}.body_file"
            )
            try:
                body = body_path.read_bytes()
            except OSError as error:
                raise ScenarioError(f"cannot read {body_path}: {error}") from error
        if len(body) > MAX_BODY_BYTES:
            raise ScenarioError(f"scenario.events.{name} body exceeds {MAX_BODY_BYTES} bytes")
        events[name] = EventSpec(
            body=body,
            headers=_headers(event.get("headers", {}), f"scenario.events.{name}.headers"),
        )
    return events


def _parse_deliveries(value: object, events: dict[str, EventSpec]) -> tuple[DeliverySpec, ...]:
    items = _array(value, "scenario.deliveries")
    if not 1 <= len(items) <= MAX_DELIVERIES:
        raise ScenarioError(f"scenario.deliveries must contain 1 to {MAX_DELIVERIES} items")
    deliveries: list[DeliverySpec] = []
    seen_names: set[str] = set()
    for index, raw_delivery in enumerate(items):
        location = f"scenario.deliveries[{index}]"
        delivery = _object(raw_delivery, location)
        _keys(delivery, {"name", "event", "delay_ms", "expect"}, location)
        name = _nonempty_string(delivery.get("name"), f"{location}.name")
        if name in seen_names:
            raise ScenarioError(f"duplicate delivery name: {name}")
        seen_names.add(name)
        event = _nonempty_string(delivery.get("event"), f"{location}.event")
        if event not in events:
            raise ScenarioError(f"{location}.event references unknown event: {event}")
        expect = _object(delivery.get("expect"), f"{location}.expect")
        _keys(expect, {"statuses"}, f"{location}.expect")
        statuses = _statuses(expect.get("statuses"), f"{location}.expect.statuses")
        deliveries.append(
            DeliverySpec(
                name=name,
                event=event,
                delay_ms=_bounded_integer(
                    delivery.get("delay_ms", 0), f"{location}.delay_ms", 0, 10_000
                ),
                expected_statuses=statuses,
            )
        )
    return tuple(deliveries)


def _parse_probe(value: object, base: Path) -> ProbeSpec:
    data = _object(value, "scenario.probe")
    _keys(data, {"command", "cwd", "timeout_seconds", "expect"}, "scenario.probe")
    expect = _object(data.get("expect"), "scenario.probe.expect")
    _keys(expect, {"exit_code", "json"}, "scenario.probe.expect")
    if "json" not in expect:
        raise ScenarioError("scenario.probe.expect.json is required")
    return ProbeSpec(
        command=_command(data.get("command"), "scenario.probe.command"),
        cwd=_relative_directory(data.get("cwd", "."), base, "scenario.probe.cwd"),
        timeout_seconds=_bounded_number(
            data.get("timeout_seconds", 10), "scenario.probe.timeout_seconds", 0.1, 60
        ),
        expected_exit_code=_bounded_integer(
            expect.get("exit_code", 0), "scenario.probe.expect.exit_code", 0, 255
        ),
        expected_json=cast(JsonValue, expect["json"]),
    )


def _object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ScenarioError(f"{location} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ScenarioError(f"{location} must be an array")
    return cast(list[object], value)


def _keys(data: dict[str, object], allowed: set[str], location: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ScenarioError(f"{location} contains unknown field(s): {', '.join(unknown)}")


def _nonempty_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{location} must be a non-empty string")
    return value


def _command(value: object, location: str) -> tuple[str, ...]:
    items = _array(value, location)
    if not items or any(not isinstance(item, str) or not item for item in items):
        raise ScenarioError(f"{location} must be a non-empty argv array of strings")
    return tuple(cast(list[str], items))


def _headers(value: object, location: str) -> dict[str, str]:
    data = _object(value, location)
    headers: dict[str, str] = {}
    for name, raw_value in data.items():
        if not isinstance(raw_value, str):
            raise ScenarioError(f"{location}.{name} must be a string")
        if name.lower() in FORBIDDEN_HEADERS:
            raise ScenarioError(f"{location} cannot set transport header: {name}")
        if "\r" in name or "\n" in name or "\r" in raw_value or "\n" in raw_value:
            raise ScenarioError(f"{location} header names and values cannot contain newlines")
        headers[name] = raw_value
    return headers


def _loopback_url(value: object, location: str) -> str:
    url = _nonempty_string(value, location)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ScenarioError(f"{location} must be an http(s) loopback URL")
    return url


def _relative_directory(value: object, base: Path, location: str) -> Path:
    directory = _inside_base(value, base, location)
    if not directory.is_dir():
        raise ScenarioError(f"{location} must name an existing directory")
    return directory


def _relative_file(value: object, base: Path, location: str) -> Path:
    path = _inside_base(value, base, location)
    if not path.is_file():
        raise ScenarioError(f"{location} must name an existing file")
    return path


def _inside_base(value: object, base: Path, location: str) -> Path:
    relative = Path(_nonempty_string(value, location))
    if relative.is_absolute():
        raise ScenarioError(f"{location} must stay inside the scenario directory")
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ScenarioError(f"{location} must stay inside the scenario directory")
    return resolved


def _bounded_number(value: object, location: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ScenarioError(f"{location} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ScenarioError(f"{location} must be between {minimum} and {maximum}")
    return result


def _bounded_integer(value: object, location: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScenarioError(f"{location} must be an integer")
    if not minimum <= value <= maximum:
        raise ScenarioError(f"{location} must be between {minimum} and {maximum}")
    return value


def _statuses(value: object, location: str) -> tuple[int, ...]:
    items = _array(value, location)
    statuses = tuple(_bounded_integer(item, location, 100, 599) for item in items)
    if not statuses:
        raise ScenarioError(f"{location} must not be empty")
    if len(statuses) != len(set(statuses)):
        raise ScenarioError(f"{location} must not contain duplicates")
    return statuses
