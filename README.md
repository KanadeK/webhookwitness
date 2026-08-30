# WebhookWitness

[![CI](https://github.com/KanadeK/webhookwitness/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/webhookwitness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/KanadeK/webhookwitness)](https://github.com/KanadeK/webhookwitness/releases/latest)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11--3.13-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Prove that duplicate and out-of-order webhooks do not duplicate side effects
or roll business state backward.**

WebhookWitness is a local-first black-box contract runner for webhook handlers.
It starts your service, sends an exact delivery sequence, runs your read-only
state probe, and fails CI when the final business state is wrong—even when every
HTTP response looked successful.

```text
newer event -> older event -> duplicate retry -> your state probe
       202            202              202              FAIL
```

The package has no runtime dependencies. It invokes commands without a shell,
accepts loopback targets only, and keeps webhook bodies and headers out of its
JSON, Markdown, and JUnit reports.

## Why this exists

Most webhook smoke tests prove that an endpoint answers. That does not prove
that a retry avoids a second charge, or that a delayed `pending` event cannot
overwrite a newer `completed` state. WebhookWitness checks the result that your
application owns instead of guessing from response codes.

Nearby tools are webhook inboxes, relay/replay servers, or provider-specific
examples. WebhookWitness is intentionally the smaller missing piece: a generic
CI contract around an existing local handler. See the
[prior-art record](docs/research.md) for the comparison.

## Quick start

Requirements: Python 3.11-3.13 and [uv](https://docs.astral.sh/uv/).

```console
git clone https://github.com/KanadeK/webhookwitness.git
cd webhookwitness
uv sync --locked --extra dev

uv run webhookwitness validate examples/passing.json
uv run webhookwitness run examples/passing.json --artifacts .tmp/passing
```

The passing example prints:

```text
VALID dedupe-and-monotonic-state-pass: 2 events, 3 deliveries
PASS dedupe-and-monotonic-state-pass: reports in .../.tmp/passing
```

Now prove that the same contract detects a broken handler:

```console
uv run webhookwitness run examples/failing.json --artifacts .tmp/failing
```

That command intentionally exits `1`. The handler returned `202` for all three
requests, but its state probe exposes both a duplicated side effect and stale
state behavior. See [the example walkthrough](examples/README.md).

## Write a contract

A scenario declares one owned service, exact events, an ordered delivery plan,
and one application-owned JSON probe:

```json
{
  "version": 1,
  "name": "payment-webhook-invariant",
  "service": {
    "command": ["{python}", "handler.py", "--port", "8765"],
    "cwd": ".",
    "ready": {"url": "http://127.0.0.1:8765/health"}
  },
  "defaults": {
    "url": "http://127.0.0.1:8765/webhook",
    "headers": {"Content-Type": "application/json"}
  },
  "events": {
    "completed": {
      "body": {"sequence": 2, "status": "completed"},
      "headers": {"X-Event-ID": "evt-2"}
    }
  },
  "deliveries": [
    {"name": "first", "event": "completed", "expect": {"statuses": [202]}},
    {"name": "retry", "event": "completed", "expect": {"statuses": [202]}}
  ],
  "probe": {
    "command": ["{python}", "probe.py"],
    "cwd": ".",
    "expect": {"exit_code": 0, "json": {"effect_count": 1, "status": "completed"}}
  }
}
```

`{python}` is portable only as the first command token and expands to the
interpreter running WebhookWitness. Otherwise commands are literal argv arrays.
The probe must print exactly one JSON value to stdout. Read the complete
[scenario format](docs/scenario-format.md) before adapting it.

## Evidence and exit codes

Each `run` stores the following in its artifact directory:

| File | Purpose |
| --- | --- |
| `report.json` | Stable machine-readable result (`schema_version: 1`) |
| `report.md` | Human review of deliveries and the final invariant |
| `junit.xml` | CI test result for deliveries plus the probe |
| `service.stdout.log`, `service.stderr.log` | Local application diagnostics |
| `probe.stdout.log`, `probe.stderr.log` | Local probe diagnostics |

Exit codes are a stable part of the CLI contract:

- `0`: the scenario is valid, or every delivery and the probe passed.
- `1`: the scenario ran and the contract failed.
- `2`: the scenario, service setup, readiness, probe setup, or report output was invalid.

Use the [repair guide](docs/repair.md) to distinguish setup failures from real
contract failures.

## Scope and safety

- Only `http(s)` loopback URLs are accepted (`localhost`, `127.0.0.1`, `::1`).
- Commands run directly with `shell=False`; scenario working directories and
  body files must stay inside the scenario directory.
- Delivery order is explicit and sequential; `delay_ms` is a bounded pause.
- A run owns the declared service process and terminates it afterward.
- Reports omit webhook request bodies and headers. Application logs remain in
  the local artifact directory and may still contain data written by your app.
- The tool proves only the events and final state you declare. It does not claim
  exactly-once delivery, replace signature verification, or load-test races.

Remote targets, hosted capture, provider adapters, secret/signature helpers,
and concurrent delivery storms are non-goals for v0.1.

## Install a release

Download the wheel and `SHA256SUMS.txt` from the
[latest GitHub Release](https://github.com/KanadeK/webhookwitness/releases/latest),
verify the listed checksum, then install it into an environment:

```console
python -m pip install webhookwitness-0.1.0-py3-none-any.whl
webhookwitness version
```

## Develop and verify

```console
uv sync --locked --extra dev
uv run python scripts/verify_release.py
```

The release gate runs formatting, lint, strict typing, branch coverage, both
examples, distribution builds, and a clean wheel-install smoke test. Architecture
and authority boundaries are documented in [docs/architecture.md](docs/architecture.md).

Contributions are welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md).
Security reports follow [SECURITY.md](SECURITY.md). WebhookWitness is MIT
licensed.
