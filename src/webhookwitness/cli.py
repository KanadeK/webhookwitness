"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from webhookwitness import __version__
from webhookwitness.errors import WebhookWitnessError
from webhookwitness.report import write_reports
from webhookwitness.runner import run_scenario
from webhookwitness.scenario import load_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webhookwitness",
        description="Run local webhook delivery contracts against an existing handler.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a scenario without starting it")
    validate.add_argument("scenario", type=Path)
    run = commands.add_parser("run", help="execute a scenario and write evidence")
    run.add_argument("scenario", type=Path)
    run.add_argument(
        "--artifacts",
        type=Path,
        default=Path("webhookwitness-artifacts"),
        help="artifact directory (default: webhookwitness-artifacts)",
    )
    commands.add_parser("version", help="print the installed version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "version":
            print(f"WebhookWitness {__version__}")
            return 0
        scenario = load_scenario(args.scenario)
        if args.command == "validate":
            print(
                f"VALID {scenario.name}: {len(scenario.events)} events, "
                f"{len(scenario.deliveries)} deliveries"
            )
            return 0
        result = run_scenario(scenario, args.artifacts)
        write_reports(result, args.artifacts.resolve())
        label = "PASS" if result.passed else "FAIL"
        print(f"{label} {result.scenario_name}: reports in {args.artifacts.resolve()}")
        return 0 if result.passed else 1
    except WebhookWitnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
