# Architecture

WebhookWitness has one authority path from authored contract to evidence:

```text
strict JSON -> immutable Scenario -> owned service -> ordered POSTs
                                              -> application probe -> RunResult
                                                                    -> 3 reports
```

## Boundaries

`scenario.py` is the only input boundary. It rejects unknown fields, remote
URLs, escaping paths, shell-shaped command strings, unsafe transport headers,
and unbounded inputs before execution. The rest of the package receives frozen,
validated dataclasses.

`runner.py` owns one subprocess. It disables URL proxy discovery, waits for a
loopback health endpoint, preserves event bytes, applies the declared ordering,
runs one read-only probe, and always stops the service. Delivery failures are
evidence, while invalid setup raises a distinct error.

`report.py` is the only evidence serializer. JSON, Markdown, and JUnit are
derived from one immutable `RunResult`; there is no second result calculation.
Request headers and bodies are deliberately absent from that model, so a report
cannot accidentally serialize them.

`cli.py` maps the model to stable process outcomes: pass `0`, contract failure
`1`, input/setup failure `2`.

## Business invariant ownership

WebhookWitness does not know what “processed once” means for a user's database.
The application-owned probe is authoritative. It can query a test database,
read an isolated state file, or call a local diagnostic endpoint, but it should
not repair or mutate state. Exact JSON equality keeps the contract visible and
reviewable.

The service HTTP status and final probe answer different questions. A status
mismatch says transport/application acknowledgement was wrong. A probe mismatch
says the observable business outcome was wrong. Both remain in the same result.

## Deliberate limits

The v0.1 execution model is sequential. It covers duplicate, retry, delayed,
and explicitly out-of-order deliveries, not concurrent races or throughput.
Loopback-only execution and direct argv invocation keep untrusted remote access,
provider credentials, and shell interpretation outside the product.
