"""Serialize one run without copying webhook request content."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from webhookwitness.errors import SetupError
from webhookwitness.runner import DeliveryResult, RunResult


def write_reports(result: RunResult, artifacts: Path) -> None:
    try:
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "report.json").write_text(
            json.dumps(_as_dict(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (artifacts / "report.md").write_text(_as_markdown(result), encoding="utf-8")
        _write_junit(result, artifacts / "junit.xml")
    except OSError as error:
        raise SetupError(f"cannot write reports: {error}") from error


def _as_dict(result: RunResult) -> dict[str, Any]:
    delivery_failures = sum(not delivery.passed for delivery in result.deliveries)
    return {
        "schema_version": 1,
        "scenario": result.scenario_name,
        "passed": result.passed,
        "summary": {
            "deliveries": len(result.deliveries),
            "delivery_failures": delivery_failures,
            "probe_passed": result.probe.passed,
        },
        "deliveries": [
            {
                "name": delivery.name,
                "event": delivery.event,
                "status": delivery.status,
                "expected_statuses": list(delivery.expected_statuses),
                "passed": delivery.passed,
                "detail": delivery.detail,
            }
            for delivery in result.deliveries
        ],
        "probe": {
            "exit_code": result.probe.exit_code,
            "expected_exit_code": result.probe.expected_exit_code,
            "actual_json": result.probe.actual_json,
            "expected_json": result.probe.expected_json,
            "passed": result.probe.passed,
            "detail": result.probe.detail,
        },
    }


def _as_markdown(result: RunResult) -> str:
    lines = [
        "# WebhookWitness report",
        "",
        f"Scenario: **{_markdown_text(result.scenario_name)}**",
        "",
        f"**Result: {'PASS' if result.passed else 'FAIL'}**",
        "",
        "## Deliveries",
        "",
        "| Delivery | Event | HTTP | Expected | Result | Detail |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    lines.extend(_delivery_row(delivery) for delivery in result.deliveries)
    lines.extend(
        [
            "",
            "## Final state probe",
            "",
            f"Result: **{'PASS' if result.probe.passed else 'FAIL'}**",
            "",
            f"Exit code: `{result.probe.exit_code}` (expected `{result.probe.expected_exit_code}`)",
            "",
            f"Detail: {_markdown_text(result.probe.detail or 'none')}",
            "",
            "Expected JSON:",
            "",
            f"<pre>{_escaped_json(result.probe.expected_json)}</pre>",
            "",
            "Actual JSON:",
            "",
            f"<pre>{_escaped_json(result.probe.actual_json)}</pre>",
            "",
            "Webhook request bodies and headers are intentionally omitted. See local service logs ",
            "in the same artifact directory when application diagnostics are needed.",
            "",
        ]
    )
    return "\n".join(lines)


def _delivery_row(delivery: DeliveryResult) -> str:
    expected = ", ".join(str(status) for status in delivery.expected_statuses)
    status = "-" if delivery.status is None else str(delivery.status)
    fields = (
        delivery.name,
        delivery.event,
        status,
        expected,
        "PASS" if delivery.passed else "FAIL",
        delivery.detail,
    )
    return "| " + " | ".join(_markdown_text(field) for field in fields) + " |"


def _markdown_text(value: str) -> str:
    return (
        html.escape(value, quote=False).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")
    )


def _escaped_json(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return html.escape(rendered, quote=False)


def _write_junit(result: RunResult, path: Path) -> None:
    failures = sum(not delivery.passed for delivery in result.deliveries) + (
        not result.probe.passed
    )
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": f"WebhookWitness: {result.scenario_name}",
            "tests": str(len(result.deliveries) + 1),
            "failures": str(failures),
        },
    )
    for delivery in result.deliveries:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {"classname": "webhook.delivery", "name": delivery.name},
        )
        if not delivery.passed:
            failure = ElementTree.SubElement(case, "failure", {"message": delivery.detail})
            failure.text = delivery.detail
    probe_case = ElementTree.SubElement(
        suite,
        "testcase",
        {"classname": "webhook.probe", "name": "final state invariant"},
    )
    if not result.probe.passed:
        failure = ElementTree.SubElement(probe_case, "failure", {"message": result.probe.detail})
        failure.text = result.probe.detail
    tree = ElementTree.ElementTree(suite)
    ElementTree.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
