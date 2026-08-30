from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from webhookwitness.report import write_reports
from webhookwitness.runner import DeliveryResult, ProbeResult, RunResult


def failing_result() -> RunResult:
    deliveries = (
        DeliveryResult(
            name="first <delivery>",
            event="completed",
            status=202,
            expected_statuses=(202,),
            passed=True,
            detail="",
        ),
        DeliveryResult(
            name="duplicate | delivery",
            event="completed",
            status=500,
            expected_statuses=(200, 202),
            passed=False,
            detail="expected HTTP 200, 202; received 500",
        ),
    )
    probe = ProbeResult(
        exit_code=0,
        expected_exit_code=0,
        actual_json={"effects": 2},
        expected_json={"effects": 1},
        passed=False,
        detail="probe JSON does not equal the expected value",
    )
    return RunResult(
        scenario_name="unsafe <name>", deliveries=deliveries, probe=probe, passed=False
    )


def test_writes_machine_human_and_junit_evidence(tmp_path: Path) -> None:
    write_reports(failing_result(), tmp_path)

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["summary"] == {"deliveries": 2, "delivery_failures": 1, "probe_passed": False}
    assert report["deliveries"][1]["status"] == 500
    assert "headers" not in json.dumps(report)
    assert "body" not in json.dumps(report)

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "unsafe &lt;name&gt;" in markdown
    assert "duplicate &#124; delivery" in markdown
    assert "**Result: FAIL**" in markdown

    suite = ElementTree.parse(tmp_path / "junit.xml").getroot()
    assert suite.attrib == {
        "name": "WebhookWitness: unsafe <name>",
        "tests": "3",
        "failures": "2",
    }
    assert len(suite.findall(".//failure")) == 2


def test_passing_report_has_zero_junit_failures(tmp_path: Path) -> None:
    result = failing_result()
    passing = RunResult(
        scenario_name="pass",
        deliveries=(result.deliveries[0],),
        probe=ProbeResult(
            exit_code=0,
            expected_exit_code=0,
            actual_json={"effects": 1},
            expected_json={"effects": 1},
            passed=True,
            detail="",
        ),
        passed=True,
    )

    write_reports(passing, tmp_path)

    suite = ElementTree.parse(tmp_path / "junit.xml").getroot()
    assert suite.attrib["failures"] == "0"
    assert not suite.findall(".//failure")
