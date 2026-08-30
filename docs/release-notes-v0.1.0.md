# WebhookWitness v0.1.0

The first public release turns webhook idempotency and ordering claims into a
black-box CI contract. WebhookWitness starts an existing local handler, sends a
declared sequence of duplicate and out-of-order events, and compares an
application-owned final state probe.

## Included

- dependency-free Python runtime and `webhookwitness` CLI;
- strict loopback-only scenarios with exact JSON or file-backed bodies;
- stable pass (`0`), contract-fail (`1`), and setup-fail (`2`) exits;
- JSON, Markdown, and JUnit evidence plus local process logs;
- known-good and intentionally broken runnable examples; and
- wheel, source distribution, portable examples bundle, and SHA-256 manifest.

## Limits

This release executes deliveries sequentially. It does not test concurrent
races, remote targets, provider signatures, hosted capture, or production load.
It proves only the events and final state declared in a scenario.

See the README quick start and `docs/scenario-format.md` for the complete
contract.
