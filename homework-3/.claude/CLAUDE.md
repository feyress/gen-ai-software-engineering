# CLAUDE.md — Project Rules (Virtual Card Lifecycle)

Short, imperative rules that steer AI work in this project. Sources of truth:
[`../specification.md`](../specification.md) (what to build) and [`../agents.md`](../agents.md) (how to behave). When in doubt, those win; this file is the fast checklist.

## FinTech-sensitive defaults — always

- **Never** print, log, return, or store a full PAN or CVV. Mask to `•••• 1234`. Store a vault **token reference**, not card data.
- **Money is decimal + ISO-4217 currency.** Never floats. Round (banker's) only at presentation. Never mix currencies.
- **Every mutating operation takes an `idempotency_key`** and is replay-safe. Same key + different payload → `idempotency_conflict`.
- **Every state change emits exactly one audit event** (actor, action, before/after, correlation id). Audit is append-only — never update or delete it.
- **Authorization is deny-by-default.** Cardholders touch only their own cards; ops roles per spec §C.1.
- **Use the card state machine** `active|frozen|terminated|replaced`. Illegal transition → `state_conflict`. `terminated`/`replaced` are terminal — they never authorize.

## When unsure

- **Fail closed.** Prefer decline/error over approve/expose. Risk-increasing actions under downstream uncertainty must not silently succeed.
- **Never silently approve** an authorization with an unknown outcome — mark `pending` and reconcile.
- Ambiguity touching money, state, or PII → **stop and ask**, don't guess.

## Naming & patterns

- Identifiers: opaque `card_id`, never PAN, never sequential.
- State transitions: **pure functions**, no I/O inside.
- Errors: typed (`validation_error`, `state_conflict`, `authorization_error`, `idempotency_conflict`, `downstream_unavailable`); **no sensitive data in error bodies**.
- Downstream calls go through an adapter interface so they can be faked in tests.

## What to avoid (red flags)

- ❌ Floats for money.
- ❌ Logging or returning raw card data.
- ❌ Mutations with no audit event.
- ❌ Empty `catch` / swallowed errors.
- ❌ Implicit "allow" in access checks.
- ❌ Undocumented states or transitions.
- ❌ Secrets in code, logs, or fixtures.

## Done means

A change maps to a Low-Level Task and meets its **Definition of Done** in spec §F, with tests for the happy path **and** the relevant §G edge cases, plus the compliance assertions (*audit-event-per-mutation*, *no-PAN-in-logs*).
