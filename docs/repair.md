# Repair guide

Start with the CLI exit code; it identifies which layer failed.

## Exit 2: scenario or setup failure

Run validation alone first:

```console
webhookwitness validate path/to/scenario.json
```

Fix the reported field rather than adding a fallback. If validation passes,
inspect `service.stderr.log` in the artifact directory and run the declared
service argv from its declared `cwd`. Confirm that it remains in the foreground
and that its health URL reaches a 2xx response before the readiness deadline.

Probe setup failures mean its executable, working directory, output encoding,
or timeout is wrong. The probe must print exactly one JSON value to stdout; put
diagnostic messages on stderr.

## Exit 1: delivery mismatch

Open `report.md` or `report.json` and locate the first failed delivery. A
received status outside `expect.statuses` is application behavior. A missing
status is a request/network error. Service logs stay beside the report.

Update expected statuses only when the handler's documented acknowledgement
contract is actually different. Do not make a real error status “pass” merely
to green the test.

## Exit 1: final probe mismatch

Compare `probe.actual_json` with `probe.expected_json` in the report. Common
root causes are:

- the idempotency key is recorded after the irreversible side effect;
- duplicate detection and the side effect are not in the same transaction;
- a stale event overwrites state without comparing sequence/version/time; or
- the probe observes a different isolated store than the service uses.

Repair the authority path in the handler, then rerun the same scenario. The
checked-in `examples/failing.json` is expected to fail and demonstrates this
case; `examples/passing.json` is its known-good counterpart.

## Windows development notes

If a machine-wide uv cache is unavailable, choose a repository-local cache for
the command:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync --locked --extra dev
```

The release verifier already places pytest and build scratch data under the
repository's ignored `.tmp` directory.
