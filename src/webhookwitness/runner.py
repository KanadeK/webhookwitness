"""Execute a validated webhook scenario against one owned local service."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from webhookwitness.errors import SetupError
from webhookwitness.scenario import DeliverySpec, JsonValue, ProbeSpec, Scenario

MAX_PROBE_BYTES = 1_048_576
LOCAL_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class DeliveryResult:
    name: str
    event: str
    status: int | None
    expected_statuses: tuple[int, ...]
    passed: bool
    detail: str


@dataclass(frozen=True)
class ProbeResult:
    exit_code: int | None
    expected_exit_code: int
    actual_json: JsonValue
    expected_json: JsonValue
    passed: bool
    detail: str


@dataclass(frozen=True)
class RunResult:
    scenario_name: str
    deliveries: tuple[DeliveryResult, ...]
    probe: ProbeResult
    passed: bool


def run_scenario(scenario: Scenario, artifacts: Path) -> RunResult:
    artifact_dir = _prepare_artifacts(artifacts)
    stdout_path = artifact_dir / "service.stdout.log"
    stderr_path = artifact_dir / "service.stderr.log"
    try:
        with stdout_path.open("wb") as service_stdout, stderr_path.open("wb") as service_stderr:
            try:
                process = subprocess.Popen(  # noqa: S603
                    _expanded_command(scenario.service.command),
                    cwd=scenario.service.cwd,
                    stdout=service_stdout,
                    stderr=service_stderr,
                )
            except OSError as error:
                raise SetupError(f"cannot start service: {error}") from error
            try:
                _wait_until_ready(process, scenario)
                deliveries = tuple(_deliver(scenario, delivery) for delivery in scenario.deliveries)
                probe = _run_probe(scenario.probe, artifact_dir)
            finally:
                _stop_process(process, scenario.service.shutdown_timeout_seconds)
    except OSError as error:
        raise SetupError(f"cannot use artifact directory: {error}") from error

    passed = all(delivery.passed for delivery in deliveries) and probe.passed
    return RunResult(
        scenario_name=scenario.name,
        deliveries=deliveries,
        probe=probe,
        passed=passed,
    )


def _prepare_artifacts(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SetupError(f"cannot create artifact directory: {error}") from error
    if not resolved.is_dir():
        raise SetupError("artifact path must be a directory")
    return resolved


def _expanded_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if command[0] == "{python}":
        return (sys.executable, *command[1:])
    return command


def _wait_until_ready(process: subprocess.Popen[bytes], scenario: Scenario) -> None:
    ready = scenario.service.ready
    deadline = time.monotonic() + ready.timeout_seconds
    last_detail = "no response"
    while True:
        return_code = process.poll()
        if return_code is not None:
            raise SetupError(f"service exited before readiness with code {return_code}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SetupError(f"service did not become ready: {last_detail}")
        request = Request(ready.url, method="GET")  # noqa: S310 - validated loopback URL
        try:
            with LOCAL_OPENER.open(request, timeout=min(remaining, 1.0)) as response:
                status = response.status
            if 200 <= status < 300:
                return
            last_detail = f"health endpoint returned HTTP {status}"
        except HTTPError as error:
            last_detail = f"health endpoint returned HTTP {error.code}"
        except (URLError, TimeoutError, OSError) as error:
            last_detail = str(error)
        time.sleep(min(ready.interval_ms / 1000, max(0, deadline - time.monotonic())))


def _deliver(scenario: Scenario, spec: DeliverySpec) -> DeliveryResult:
    if spec.delay_ms:
        time.sleep(spec.delay_ms / 1000)
    event = scenario.events[spec.event]
    headers = dict(scenario.defaults.headers)
    headers.update(event.headers)
    request = Request(  # noqa: S310 - validated loopback URL
        scenario.defaults.url,
        data=event.body,
        headers=headers,
        method="POST",
    )
    try:
        with LOCAL_OPENER.open(request, timeout=scenario.defaults.timeout_seconds) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    except (URLError, TimeoutError, OSError) as error:
        return DeliveryResult(
            name=spec.name,
            event=spec.event,
            status=None,
            expected_statuses=spec.expected_statuses,
            passed=False,
            detail=f"request failed: {error}",
        )
    passed = status in spec.expected_statuses
    expected = ", ".join(str(item) for item in spec.expected_statuses)
    return DeliveryResult(
        name=spec.name,
        event=spec.event,
        status=status,
        expected_statuses=spec.expected_statuses,
        passed=passed,
        detail="" if passed else f"expected HTTP {expected}; received {status}",
    )


def _run_probe(probe: ProbeSpec, artifacts: Path) -> ProbeResult:
    stdout_path = artifacts / "probe.stdout.log"
    stderr_path = artifacts / "probe.stderr.log"
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                completed = subprocess.run(  # noqa: S603
                    _expanded_command(probe.command),
                    cwd=probe.cwd,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=probe.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ProbeResult(
                    exit_code=None,
                    expected_exit_code=probe.expected_exit_code,
                    actual_json=None,
                    expected_json=probe.expected_json,
                    passed=False,
                    detail=f"probe exceeded {probe.timeout_seconds:g} seconds",
                )
            except OSError as error:
                raise SetupError(f"cannot run probe: {error}") from error
        if stdout_path.stat().st_size > MAX_PROBE_BYTES:
            return ProbeResult(
                exit_code=completed.returncode,
                expected_exit_code=probe.expected_exit_code,
                actual_json=None,
                expected_json=probe.expected_json,
                passed=False,
                detail=f"probe stdout exceeds {MAX_PROBE_BYTES} bytes",
            )
        try:
            actual = cast(JsonValue, json.loads(stdout_path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ProbeResult(
                exit_code=completed.returncode,
                expected_exit_code=probe.expected_exit_code,
                actual_json=None,
                expected_json=probe.expected_json,
                passed=False,
                detail="probe stdout is not valid JSON",
            )
    except OSError as error:
        raise SetupError(f"cannot use probe logs: {error}") from error

    exit_matches = completed.returncode == probe.expected_exit_code
    json_matches = actual == probe.expected_json
    details: list[str] = []
    if not exit_matches:
        details.append(
            f"expected probe exit {probe.expected_exit_code}; received {completed.returncode}"
        )
    if not json_matches:
        details.append("probe JSON does not equal the expected value")
    return ProbeResult(
        exit_code=completed.returncode,
        expected_exit_code=probe.expected_exit_code,
        actual_json=actual,
        expected_json=probe.expected_json,
        passed=exit_matches and json_matches,
        detail="; ".join(details),
    )


def _stop_process(process: subprocess.Popen[bytes], timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
