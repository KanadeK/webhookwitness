# WebhookWitness v0.1 Specification

## Objective

WebhookWitness is a local-first black-box contract runner for webhook handlers.
It starts a user-declared local service, sends an explicitly ordered series of
webhook deliveries, runs one read-only state probe, and writes evidence showing
whether duplicate, retry, delayed, and out-of-order deliveries preserved the
declared business invariant.

The target user is an application developer whose handler already exists but
whose ordinary happy-path tests do not prove idempotency or monotonic state.

## Assumptions

1. v0.1 tests services reachable on loopback only; it is not a load tester.
2. Scenarios are strict JSON so the standard library can parse them without a
   runtime dependency.
3. A service command remains in the foreground for the lifetime of the run.
4. A probe is an argv array that prints one JSON value to stdout and does not
   mutate the system under test.
5. Delivery order is authored explicitly. `delay_ms` adds a bounded pause
   before a delivery; v0.1 does not model concurrent races.

## Commands

```text
uv sync --locked --extra dev
uv run webhookwitness validate examples/passing.json
uv run webhookwitness run examples/passing.json --artifacts artifacts/passing
uv run python scripts/verify_release.py
```

## Project Structure

```text
src/webhookwitness/  package and CLI
tests/               unit and integration tests
examples/            runnable service, probe, and passing/failing scenarios
docs/                architecture, format, research, and release notes
scripts/             release-equivalent verification
tasks/               implementation plan and checklist
```

## Code Style

Straightforward typed Python 3.11 with immutable dataclasses for validated
input. Boundary validation happens once; core execution receives valid models.
Commands are always passed as argv arrays and never through a shell.

```python
scenario = load_scenario(path)
result = run_scenario(scenario, artifacts)
return 0 if result.passed else 1
```

## Testing Strategy

- Write focused failing tests before each behavior.
- Unit-test strict parsing, loopback enforcement, request construction, probe
  comparison, and report serialization.
- Integration-test a real subprocess HTTP handler for both a passing contract
  and a deliberately broken handler.
- Require at least 90% branch coverage plus Ruff, formatting, and strict mypy.
- Build wheel/sdist and smoke-test the installed console command.

## Boundaries

- Always: remain offline at runtime, preserve exact request bytes, terminate the
  owned service, emit machine and human reports, and distinguish contract
  failure (exit 1) from invalid setup/input (exit 2).
- Ask first: future support for remote targets, concurrent delivery, provider
  secrets/signing helpers, or persistent captured webhook data.
- Never: invoke a shell, fetch remote fixtures, hide a mismatch, claim
  exactly-once delivery, or treat a green run as proof about untested events.

## Success Criteria

1. A valid example starts a real HTTP service, delivers completed, older, and
   duplicate events, and proves one side effect with the newest state retained.
2. A broken-handler example performs the same sequence and predictably exits 1
   because its final probe differs.
3. Invalid schemas, non-loopback URLs, failed readiness, unexpected HTTP status,
   invalid probe JSON, and early service exit have tested diagnostics.
4. Every run writes `report.json`, `report.md`, `junit.xml`, plus local service
   stdout/stderr logs without embedding those logs into reports.
5. CI passes on Linux and Windows; wheel and sdist install and execute cleanly.
6. A public GitHub v0.1.0 Release contains the distributions, example bundle,
   and checksums, and the published wheel passes an isolated smoke test.

## Open Questions

None for v0.1. Deferred capabilities are explicit non-goals above.
