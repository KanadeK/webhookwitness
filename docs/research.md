# Differentiation Research

Research performed on 2026-08-30 used multiple public web and GitHub queries.
The selected problem is deliberately narrower than nearby projects.

## Representative Prior Art

- HookRadar and PomeloHook receive, inspect, persist, forward, and replay
  webhook traffic. WebhookWitness is not a receiver service or relay.
  <https://github.com/aniketmishra-0/Hookradar>
  <https://github.com/Pomelo-Studios/PomeloHook>
- Resonate's example demonstrates one implementation of exactly-once webhook
  processing. WebhookWitness tests an already-existing handler as a black box.
  <https://github.com/resonatehq-examples/example-webhook-handler-ts>
- Carbon Layer has provider-specific payment chaos flags. WebhookWitness owns no
  payment model or provider adapter; the scenario and probe define the contract.
  <https://github.com/Pritom14/carbon-layer>
- GitHub documents delivery signature validation. WebhookWitness accepts exact
  fixture headers and bytes but does not replace provider verification code.
  <https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries>

## Product Difference

The missing slice is a small, generic CI runner that combines all four actions:

1. start an arbitrary local handler with an argv array;
2. deliver a declared sequence, including duplicates and stale events;
3. run an application-owned state probe; and
4. fail CI on the final business invariant with portable evidence.

This avoids competing with hosted webhook inboxes and avoids embedding another
idempotency implementation that users would have to trust in production.
