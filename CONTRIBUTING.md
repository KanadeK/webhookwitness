# Contributing

Bug reports and focused pull requests are welcome. Please describe the observed
behavior, the smallest scenario that reproduces it, and the expected contract.
Do not include production webhook bodies, credentials, or personal data.

## Development

```console
uv sync --locked --extra dev
uv run python scripts/verify_release.py
```

Behavior changes should begin with a failing test and update the format or
architecture documentation when they change a public contract. Keep the runtime
dependency-free unless a concrete requirement cannot be met by the standard
library. Do not add provider-specific paths to the generic core.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
