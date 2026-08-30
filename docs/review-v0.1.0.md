# v0.1.0 release review

Review completed on 2026-08-30 against the specification and executable release
gate. No blocking findings remain.

## Correctness

- One strict parser produces immutable scenario models; unknown fields and
  ambiguous event bodies fail before execution.
- One `RunResult` is authoritative for JSON, Markdown, JUnit, and CLI status.
- Real subprocess tests prove the passing invariant and prove that a handler can
  return HTTP 202 throughout while still failing final business state.
- Input/setup failures remain exit 2 and do not masquerade as contract failures.

Evidence: 50 tests passed with 97.05% branch coverage. The release gate also
ran both checked-in examples through a clean wheel installation.

## Security and privacy

- Targets are HTTP(S) loopback only and proxy discovery is disabled.
- Service and probe commands are argv arrays executed without a shell.
- Scenario working directories and fixture files cannot escape the scenario
  directory; bodies, delivery counts, delays, and probe output are bounded.
- Request bodies and headers are absent from the result model and reports.
- Locked dependencies returned no known OSV vulnerability or adverse status;
  tracked credential-pattern scanning passed.

Application-owned stdout/stderr logs may still contain data logged by the
application and must be handled as local test artifacts.

## Maintainability

- The installed runtime has no third-party dependencies.
- Parsing, execution, reporting, and CLI exit mapping are separate modules with
  one-way data flow and no compatibility paths or duplicate sources of truth.
- The scenario format, architecture, repair flow, limitations, and release
  process are documented alongside executable examples.

## Performance and resource bounds

- v0.1 deliberately sends at most 100 deliveries sequentially.
- Request and readiness timeouts are bounded, request bodies and probe stdout
  are limited to 1 MiB, and the owned service is terminated after every run.
- Concurrent race and load testing remain explicit non-goals rather than hidden
  promises.

## Portability and release

- Local verification passed on Windows with Python 3.13.
- CI declares Python 3.11 and 3.13 on Linux plus Python 3.12 on Windows.
- The release workflow repeats the full gate, builds wheel/sdist/examples and
  checksums, verifies tag/version agreement, and publishes only after success.

Remote CI remains an external acceptance gate and must be green before the
GitHub Release is considered delivered.

## Known operational limits

- Delivery order is sequential; `delay_ms` does not model concurrent races.
- Scenarios should reserve a dedicated local port for their owned service.
- The probe is application-owned and must be read-only for a meaningful result.
- A pass proves only the authored events and exact expected final JSON.
