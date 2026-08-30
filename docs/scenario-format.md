# Scenario format

WebhookWitness v0.1 accepts one strict UTF-8 JSON object. Unknown fields are
errors. Relative paths resolve from the scenario file's directory and may not
escape it.

## Top level

| Field | Required | Meaning |
| --- | --- | --- |
| `version` | yes | Must be integer `1` |
| `name` | yes | Non-empty report name |
| `service` | yes | Owned foreground service process |
| `defaults` | yes | Shared delivery URL, headers, and timeout |
| `events` | yes | Named request fixtures; at least one |
| `deliveries` | yes | Ordered uses of named events; 1-100 |
| `probe` | yes | Read-only final state observation |

## `service`

`command` is a non-empty argv array. If its first token is exactly `{python}` it
expands to the interpreter running WebhookWitness. No other substitution occurs
and no shell is involved.

`cwd` defaults to `.` and must be an existing directory inside the scenario
directory. The service must stay in the foreground. WebhookWitness considers it
ready after `ready.url` returns a 2xx response and fails setup if the process
exits first.

| Field | Default | Bounds |
| --- | ---: | ---: |
| `ready.timeout_seconds` | `5` | 0.1-60 |
| `ready.interval_ms` | `100` | 10-5000 |
| `shutdown_timeout_seconds` | `3` | 0.1-30 |

`ready.url` must be an HTTP or HTTPS loopback URL.

## `defaults`

`url` is the loopback endpoint used for every POST. `headers` is an optional
string-to-string object. `timeout_seconds` defaults to `5` and is bounded from
0.1 to 30 seconds.

`Host`, `Content-Length`, `Connection`, and `Transfer-Encoding` are transport
headers and cannot be authored. Header names and values cannot contain newlines.

## `events`

Each named event contains exactly one of:

- `body`: any JSON value, encoded as compact UTF-8 JSON; or
- `body_file`: a relative file path whose bytes are sent unchanged.

An event may add `headers`, which override same-named default headers during
delivery. Each body is limited to 1 MiB. WebhookWitness does not infer a content
type or signature; declare the exact headers your fixture needs.

## `deliveries`

Deliveries run in array order. Each item has a unique non-empty `name`, the
name of an `event`, and `expect.statuses`, a non-empty unique list of HTTP status
codes from 100 through 599. Optional `delay_ms` pauses for 0-10000 milliseconds
before that delivery.

HTTP error responses are still compared with `expect.statuses`. A network error
is a contract failure with no received status. Later deliveries and the state
probe still run so the reports show the whole authored sequence.

## `probe`

The probe is an argv `command` plus optional `cwd` and `timeout_seconds`
(default `10`, bounds 0.1-60). It runs once, after all deliveries, while the
service is still available.

The command must print exactly one UTF-8 JSON value to stdout, no labels or log
lines. Its exit code and parsed JSON are compared exactly with
`expect.exit_code` (default `0`, bounds 0-255) and required `expect.json`.
Probe stdout is limited to 1 MiB. Send diagnostics to stderr.

## Lifecycle

1. Parse and validate the entire scenario.
2. Create the artifact directory and start the service.
3. Poll readiness until a 2xx response, early exit, or timeout.
4. Send every declared delivery in order.
5. Run the final state probe and compare exact JSON.
6. Terminate the owned service and write all reports.

Invalid input or setup exits `2`. A completed run with any delivery or probe
mismatch exits `1`. A completed matching run exits `0`.
