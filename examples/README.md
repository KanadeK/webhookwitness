# Examples

`passing.json` starts a handler that deduplicates event IDs before applying the
side effect and refuses to let an older event overwrite newer state.

`failing.json` starts the same handler in an intentionally broken mode. Every
delivery applies the side effect and an older event may regress state. All HTTP
responses still look successful, so only the final probe exposes the defect.

Both scenarios send a newer event, then an older event, then retry the newer
event. Runtime state is written below `examples/runtime/`, which is ignored by
Git.
