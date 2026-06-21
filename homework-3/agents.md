# agents.md — AI Agent Guidelines (Virtual Card Lifecycle)

These guidelines tell an AI coding partner how to behave when implementing the [`specification.md`](./specification.md) in this **regulated FinTech** domain. They are **binding**: a generated change that violates a rule below should be treated as a defect, even if it "works."

The companion [`.claude/CLAUDE.md`](./.claude/CLAUDE.md) is the short, imperative do/don't list; this file is the fuller rationale. Where they overlap, neither relaxes the other.

---

## 1. Stack assumptions (stack-agnostic)

This project does not commit to a language or framework. Translate every rule into the host stack's idiom:

- **Money** → the language's **arbitrary-precision decimal** type (e.g. `BigDecimal`/`Decimal`), **never** binary floating point.
- **Validation** → the framework's schema/validation layer at every trust boundary (API input, downstream responses).
- **Persistence** → migrations are versioned and reviewed; no ad-hoc schema drift.
- **Logging** → structured logs through a redaction filter (see §4).
- **Config/secrets** → from a secrets manager / environment, never hard-coded.

When the host stack is later chosen, keep these properties; do not "simplify" them away.

## 2. Domain (banking) rules — non-negotiable

1. **Never log, return, or store the full PAN or CVV.** Mask to `•••• 1234` by default. The control plane stores a **vault token reference**, not card data.
2. **Every state-changing action emits exactly one audit event** (actor, action, before/after state, correlation id, idempotency key). No mutation is "too small" to audit.
3. **Prefer idempotent writes.** Every mutating operation takes an `idempotency_key`; retries must be safe. Same key + different payload → `idempotency_conflict`.
4. **Use the documented card state machine** (`active|frozen|terminated|replaced`). Never invent a state or an undocumented transition; illegal transitions return `state_conflict`.
5. **Money is decimal + ISO-4217 currency.** No float math, no cross-currency coercion, rounding only at presentation (banker's rounding).
6. **Deny-by-default authorization.** Cardholders act only on owned cards; ops roles follow the `specification.md` §C.1 matrix. No implicit allow.

## 3. Code style & structure

- **State transitions are pure functions** — input card + action → new card or typed error; no I/O inside the transition. This keeps them trivially unit-testable.
- **Typed errors over generic exceptions:** `validation_error`, `state_conflict`, `authorization_error`, `idempotency_conflict`, `downstream_unavailable`. Error bodies carry **no** sensitive data.
- **Naming:** `card_id` (opaque, never PAN); money variables carry currency in the type, not the name; states use the canonical enum names.
- **Small units:** prefer small, composable functions over large procedures; isolate downstream-adapter calls behind interfaces so they can be faked in tests.

## 4. Testing & verification expectations

- **Test happy path *and* the §G edge cases** of the spec — at minimum: double-freeze no-op, invalid limit, concurrent freeze+auth, auth on frozen/terminated, stale read, double-replace, unauthorized ops action, PAN-exposure attempt, downstream timeout, idempotency conflict.
- **Compliance assertions are tests, not hopes:**
  - *audit-event-per-mutation* — every successful mutation produces exactly one audit event.
  - *no-PAN-in-logs* — feeding a PAN-bearing object through redaction/log filter leaves no full PAN.
- **Fixtures:** provide cards in each state and limit edge values (0, negative, at-max, over-max) for reuse.
- **Performance budgets** from spec §C.5 are verified by load tests; the authorization decision (p99 ≤ 100 ms) is the strictest.
- A change is **not done** until its task's Definition of Done in `specification.md` §F is demonstrably met.

## 5. Security & compliance constraints

- **Least privilege everywhere** — request only the scopes/roles needed; default to the narrowest.
- **Secrets** never in code, logs, fixtures, or test snapshots.
- **Respect the PII classification** table (spec §C.2): Prohibited data never enters this store; Restricted data only reaches authorized actors.
- **Tamper-evident, append-only audit** — never generate code that updates or deletes audit events.

## 6. How to treat edge cases & uncertainty

- **When unsure, fail closed** — prefer declining/erroring over approving/exposing. A risk-increasing action (unfreeze, raise limit) under downstream uncertainty must **not** silently succeed.
- **Never silently approve** an authorization with an unknown downstream outcome — resolve to `pending` and reconcile.
- **Surface, don't swallow** — no empty catch blocks; every handled failure is typed and, if it mutated state, audited.
- If the spec is ambiguous, **stop and ask** rather than guessing a behavior that touches money, state, or PII.

## 7. Definition of Done for any agent-produced change

- [ ] Matches a Low-Level Task and its DoD in `specification.md` §F.
- [ ] No full PAN/CVV anywhere; identifiers masked/opaque.
- [ ] Mutation emits exactly one audit event.
- [ ] Idempotent where it writes.
- [ ] Money uses decimal + currency.
- [ ] Authorization is deny-by-default and owner/role-checked.
- [ ] Tests cover happy path + relevant §G edge cases and the compliance assertions.
