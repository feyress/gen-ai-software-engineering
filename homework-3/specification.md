# Virtual Card Lifecycle — Specification

> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that will satisfy the High- and Mid-Level Objectives.
> This specification is **stack-agnostic**: it describes conventions abstractly (e.g. "the language's arbitrary-precision decimal type", "the framework's schema/validation layer") rather than naming a language or framework. See [`agents.md`](./agents.md) and [`.claude/CLAUDE.md`](./.claude/CLAUDE.md) for the non-negotiable guardrails that bind every task below.

---

## A. High-Level Objective

**Enable end-users to self-manage the full lifecycle of virtual payment cards — issue, freeze/unfreeze, set spending limits, view transactions, and replace — inside a regulated, fully auditable platform that never exposes raw card data.**

**Scope boundary (one sentence):** This feature owns the virtual-card *control plane* (card state, limits, history reads, audit) and is explicitly **out of scope** for physical card production, payment settlement/clearing, KYC/onboarding, fraud scoring models, and the internals of the card network / issuer-processor — all of which are treated as upstream/hypothetical services this feature *calls* but does not *implement*.

**Primary stakeholders:**

| Stakeholder | Needs |
|-------------|-------|
| **End-user (cardholder)** | Self-service: create, freeze/unfreeze, set limits, view their own transactions, replace a compromised card — fast, clear, only their own data. |
| **Internal Ops / Compliance** | Read-only investigative view across cards, full audit trail of every action, ability to perform *audited* administrative actions (e.g. force-freeze) — **never** raw PAN. |
| Support (secondary) | Subset of Ops read view to assist users; strictly least-privilege. |

---

## B. Mid-Level Objectives

Each objective is **observable** (what changes in the world when it succeeds) and tagged so every Low-Level Task in §F can trace back to it.

| ID | Objective | Observable success signal |
|----|-----------|---------------------------|
| **MO-1** | **Card issuance** | A request by an authenticated user creates exactly one virtual card in `active` state; the response returns only *masked* identifiers (`•••• 1234`) and an opaque `card_id`; an `issued` audit event exists. |
| **MO-2** | **Freeze / unfreeze** | Freezing a card causes subsequent authorizations to be declined; unfreezing restores approvals; both transitions are idempotent and audited. |
| **MO-3** | **Spending limits** | A user can set a per-card limit and a per-interval cap (e.g. daily/monthly); an authorization that would breach a cap is declined at decision time. |
| **MO-4** | **Transaction history** | A user retrieves a paginated, chronologically ordered list of *their* card's transactions; a transaction posted by a write is visible within the consistency budget (§C). |
| **MO-5** | **Card replacement** | Replacing a card atomically terminates the old card and issues a new one that inherits limits/config; the old `card_id` can never authorize again; both events are audited and linked. |
| **MO-6** | **Ops/Compliance view & actions** | An authorized Ops/Compliance user can read card state and the full audit trail (with PAN redacted) and perform administrative actions that are themselves audited with actor identity. |

---

## C. Non-Functional & Policy Requirements

> Stated as **targets/ranges**. Hypothetical numbers are labeled **[ASSUMED]** with a one-line justification anchored in FinTech UX/ops reality.

### C.1 Security
- **PAN handling (PCI-DSS-aligned):** The full Primary Account Number (PAN) is **never** logged, never returned by any read API, and never stored outside the dedicated vault/tokenization boundary. All surfaces use either an opaque `card_id` or a masked form (first-6/last-4 at most, default last-4: `•••• 1234`).
- **Tokenization boundary:** This feature stores a vault **token reference**, not card data. Detokenization is delegated to the issuer-processor adapter and is out of scope.
- **Encryption:** All sensitive fields encrypted at rest; all transport over TLS 1.2+ . Secrets (vault credentials, signing keys) sourced from a secrets manager, never from code or config files.
- **Authorization model — least privilege, deny-by-default:**
  - `cardholder` → may act **only** on cards they own.
  - `ops_read` → read-only across cards, PAN redacted.
  - `compliance` → `ops_read` + audit export.
  - `ops_admin` → may force-freeze/terminate; every action audited with actor.
  - Any request lacking an explicit grant is **denied** (no implicit allow).

### C.2 Privacy & Data Handling
- **PII classification:**

  | Data element | Class | Rule |
  |--------------|-------|------|
  | Full PAN, CVV | **Prohibited** (out of this store) | Never persisted/logged here; vault only. |
  | Masked PAN, `card_id`, card state | Restricted | Returned only to authorized owner/ops. |
  | Transaction amount, merchant, timestamp | Restricted | Owner + ops; retained per below. |
  | Audit events | Restricted, immutable | Append-only; compliance-readable. |

- **Data minimization:** Store only what the control plane needs; no CVV, no full PAN.
- **Retention [ASSUMED]:** Transaction & audit records retained **7 years** — justification: aligns with common financial record-keeping obligations (e.g. SOX/AML retention norms); configurable per jurisdiction. Terminated-card metadata retained for the same window for dispute/audit traceability.

### C.3 Audit & Logging
- **Every state-changing action emits exactly one immutable audit event** containing: `event_id`, `actor` (user/ops/system id + role), `action`, `card_id`, `before_state`, `after_state`, `timestamp` (UTC), `correlation_id` (request id), and `idempotency_key` where applicable.
- Audit store is **append-only and tamper-evident** (e.g. hash-chained or WORM-backed). No update or delete path exists.
- Application logs are **structured** and pass through a redaction filter; a log line containing a full PAN is treated as a **P1 incident**, not a warning.
- **Invariant:** *audit-event-per-mutation* — for every successful mutation there is exactly one audit event; reconciliation (§H) checks this continuously.

### C.4 Reliability
- **Availability [ASSUMED]:** 99.9% monthly for control-plane reads/writes — justification: standard "three-nines" baseline for non-life-critical financial self-service; the authorization decision path may warrant higher and is called out separately.
- **Idempotency:** All mutating operations are idempotent via a client-supplied `idempotency_key` (§D).
- **Graceful degradation:** If the issuer-processor/authorization downstream is unavailable, mutations that *increase risk* (e.g. unfreeze, raise limit) **fail closed** with a typed `downstream_unavailable` error; risk-reducing actions (freeze) should still succeed locally and reconcile. An in-flight authorization with an unknown downstream outcome resolves to a `pending` state, never a silent approval.

### C.5 Performance — measurable targets **[ASSUMED]**

| Operation | Target | Why reasonable for FinTech |
|-----------|--------|----------------------------|
| Card-state mutation (freeze/unfreeze/limit/replace) | **p99 ≤ 300 ms** | Self-service UX feels instant; mutations are single-card, single-row. |
| Authorization decision (limit/state check) | **p99 ≤ 100 ms** | On the payment hot path; networks impose tight auth windows — must be fast and deterministic. |
| Transaction-history read | **p95 ≤ 200 ms** | List view; bounded by pagination cap below. |
| Pagination | **page size ≤ 100**, cursor-based | Prevents unbounded scans; cursor avoids offset drift on a live ledger. |
| Per-user write rate limit | **≤ 10 mutations / 10 s** | Throttles abuse/automation while allowing normal correction flows. |
| Time-to-consistency (history read after a posting write) | **≤ 1 s** | Users expect a just-made transaction to appear; 1 s is acceptable for an eventually-consistent read model. |

---

## D. Implementation Notes (guardrails builders must not violate)

- **Money:** Use the language's **arbitrary-precision decimal** type — **never floating point**. Represent amounts as `{ minor_units: integer, currency: ISO-4217 }` internally; apply a single, documented rounding rule (banker's rounding) only at presentation. Mixed-currency comparisons are an error, not a coercion.
- **Identifiers:** Card identity surfaced externally is an **opaque, non-guessable `card_id`** — never the PAN, never a sequential integer. Masked display format default: `•••• 1234`.
- **Idempotency:** Every mutating operation accepts an `idempotency_key`. A repeat with the **same key + same payload** returns the original result (no double effect). A repeat with the **same key + different payload** is rejected with `idempotency_conflict`.
- **Error semantics — typed categories** (no leaking sensitive data in messages):
  - `validation_error` — bad input (e.g. negative limit).
  - `state_conflict` — illegal transition (e.g. unfreeze a terminated card).
  - `authorization_error` — caller lacks permission / not card owner.
  - `idempotency_conflict` — key reuse with differing payload.
  - `downstream_unavailable` — issuer/processor unreachable (fail closed where risk-increasing).
- **Card state machine** — enumerated states and the **only** legal transitions:

  ```
  (none) --issue--> active
  active --freeze--> frozen
  frozen --unfreeze--> active
  active|frozen --replace--> replaced   (and a new active card is issued)
  active|frozen --terminate--> terminated
  ```
  - `terminated` and `replaced` are **terminal**: no outbound transitions, no authorizations ever.
  - Any transition not listed is rejected deterministically with `state_conflict` and audited as a rejected attempt.

- **Concurrency:** State transitions use optimistic concurrency (version/`etag` per card). Conflicting concurrent writes → one wins, the other gets `state_conflict`; never a lost update.

---

## E. Context

### E.1 Beginning context (hypothetical — exists before work starts)
- **Identity/Auth service** — issues authenticated principals with roles (`cardholder`, `ops_read`, `compliance`, `ops_admin`).
- **Issuer-processor / card-network adapter** — external service that actually provisions card tokens and renders authorization decisions; this feature calls it through a thin adapter interface.
- **Vault / tokenization service** — holds PAN; returns token references and masked display values.
- **Transaction event stream** — emits posted-transaction events that feed the read model for MO-4.
- **Append-only audit store** — WORM/hash-chained sink for audit events.
- **Empty feature module** — the directory where the virtual-card control plane will be built; no domain code yet.

### E.2 Ending context (exists after the tasks are done)
- A **virtual-card feature module** implementing MO-1…MO-6.
- **Data models:** `Card`, `SpendingLimit`, `Transaction` (read model), `AuditEvent`, `IdempotencyRecord`.
- A **documented, enforced state machine** (§D) as a pure, unit-tested component.
- **Verification suites as documentation:** unit, integration, and e2e categories described in §H, plus reusable **fixtures** (cards in each state, limit edge values).
- A **compliance review checklist** mapping each control in §C to its enforcing code path.

---

## F. Low-Level Tasks

> Each task uses the template's prompt-style shape **plus** a `Serves:` traceability tag and, where it makes sense, an explicit **Definition of Done (DoD)** / acceptance criteria. Edge cases relevant to a task are listed inline; the consolidated table is §G.

### 1. Card domain model & state machine
- **Serves:** MO-1, MO-2, MO-5
- **Prompt:** "Create the `Card` aggregate and a pure state-machine function enforcing the legal transitions in spec §D. Reject illegal transitions with a typed `state_conflict`."
- **Create/Update:** `card/model`, `card/state_machine`
- **Function/Component:** `Card`, `transition(card, action) -> Card | StateConflict`
- **Details:** States `active|frozen|terminated|replaced`; optimistic version field; no float fields; `card_id` opaque. Pure & side-effect-free so it is trivially unit-testable.
- **DoD:** Unit tests cover every legal transition and a representative illegal transition for each state; illegal transitions return `state_conflict` and never mutate input.

### 2. Money value object
- **Serves:** MO-3 (and all amount handling)
- **Prompt:** "Implement a `Money` value object using the arbitrary-precision decimal type with `{minor_units, currency}`; forbid float construction and cross-currency arithmetic."
- **Create/Update:** `shared/money`
- **Function/Component:** `Money`, `add/compare`, `from_minor_units`
- **Details:** ISO-4217 currency; banker's rounding only at presentation; cross-currency op → `validation_error`.
- **DoD:** Tests prove float input is rejected and `0.1 + 0.2` style precision bugs are impossible.

### 3. Masking / redaction utility
- **Serves:** MO-1, MO-6, §C.1
- **Prompt:** "Create a redaction utility that masks PAN to `•••• 1234` and scrubs prohibited fields from any object before it reaches logs or API responses."
- **Create/Update:** `shared/redaction`
- **Function/Component:** `mask_pan(pan)`, `redact(obj)`
- **Details:** Default last-4 only; used by the logging filter and all serializers.
- **DoD:** A test feeds an object containing a full PAN through `redact` and asserts no full PAN remains; a log-filter test asserts a PAN-bearing line is masked.

### 4. Idempotency layer
- **Serves:** MO-1, MO-2, MO-3, MO-5
- **Prompt:** "Implement an idempotency store so every mutation is replay-safe: same key+payload returns the stored result; same key+different payload returns `idempotency_conflict`."
- **Create/Update:** `shared/idempotency`
- **Function/Component:** `IdempotencyRecord`, `with_idempotency(key, payload, fn)`
- **Details:** Persist request hash + result; TTL aligned to retry window.
- **DoD:** Tests cover (a) duplicate key+payload → single effect, (b) duplicate key+different payload → `idempotency_conflict`.

### 5. Audit event emitter
- **Serves:** MO-1…MO-6, §C.3
- **Prompt:** "Create an audit emitter that writes one immutable event per mutation with actor, before/after state, correlation id, and idempotency key to the append-only store."
- **Create/Update:** `audit/emitter`, `audit/model`
- **Function/Component:** `AuditEvent`, `emit(action, actor, before, after, ctx)`
- **Details:** Append-only; no update/delete API; tamper-evident chaining.
- **DoD:** Integration test asserts exactly one event per successful mutation (audit-event-per-mutation invariant) and that the store rejects updates.

### 6. Authorization / access-control guard
- **Serves:** MO-6, §C.1
- **Prompt:** "Implement a deny-by-default access guard: cardholders act only on owned cards; ops roles per the matrix in §C.1."
- **Create/Update:** `auth/guard`
- **Function/Component:** `authorize(actor, action, resource)`
- **Details:** No implicit allow; ownership check for cardholders; PAN redacted for ops.
- **DoD:** Tests cover owner-allowed, non-owner-denied, ops-read-allowed, cardholder-admin-denied.

### 7. Issue card
- **Serves:** MO-1
- **Prompt:** "Implement card issuance: call the issuer adapter, store a token reference (never PAN), create a `Card` in `active`, return masked identifiers, emit an `issued` audit event."
- **Create/Update:** `card/issue`
- **Function/Component:** `issue_card(actor, request, idempotency_key)`
- **Details:** Response contains `card_id` + masked PAN only; wrapped in idempotency layer.
- **DoD:** e2e: issuing returns no full PAN; an audit `issued` event exists; replay with same key creates no second card.

### 8. Freeze / unfreeze
- **Serves:** MO-2
- **Prompt:** "Implement freeze and unfreeze using the state machine; both idempotent; unfreeze fails closed if downstream is unavailable."
- **Create/Update:** `card/freeze`
- **Function/Component:** `freeze(card_id, key)`, `unfreeze(card_id, key)`
- **Details:** Freezing an already-frozen card is a successful **no-op** (idempotent), still audited as a no-op; unfreeze of a terminated card → `state_conflict`.
- **DoD:** Tests cover freeze→frozen, double-freeze no-op, unfreeze→active, unfreeze-terminated→`state_conflict`, downstream-unavailable on unfreeze → `downstream_unavailable`.

### 9. Set & validate spending limits
- **Serves:** MO-3
- **Prompt:** "Implement setting a per-card limit and a per-interval cap with validation; reject non-positive or over-maximum values."
- **Create/Update:** `card/limits`
- **Function/Component:** `set_limit(card_id, limit, key)`
- **Details:** Uses `Money`; interval ∈ {daily, monthly}; limit must be `> 0` and `≤ program max`.
- **DoD:** Tests reject `0`, negative, and over-max with `validation_error`; accept a valid limit and audit it.

### 10. Authorization-time limit & state enforcement
- **Serves:** MO-2, MO-3
- **Prompt:** "Implement the authorization decision: deny if card not `active`, or if the transaction would breach the per-interval cap; meet the p99 ≤ 100 ms budget."
- **Create/Update:** `card/authorize_decision`
- **Function/Component:** `decide(card_id, amount) -> Approve | Decline(reason)`
- **Details:** Reads current state + interval spend; deterministic; concurrency-safe against simultaneous freeze (§G race row).
- **DoD:** Tests: frozen → decline; over-cap → decline; within-cap active → approve; decision is deterministic for identical inputs.

### 11. Transaction history read model & pagination
- **Serves:** MO-4
- **Prompt:** "Build a read model fed by the transaction event stream and a cursor-paginated history endpoint (page ≤ 100), owner-scoped."
- **Create/Update:** `transaction/read_model`, `transaction/history`
- **Function/Component:** `get_history(card_id, cursor, limit)`
- **Details:** Chronological order; cursor-based; respects time-to-consistency ≤ 1 s.
- **DoD:** Tests: a posted transaction appears within budget; pagination cap enforced; a non-owner cannot read.

### 11b. Stale-read handling
- **Serves:** MO-4, §C.5
- **Prompt:** "Expose a freshness signal (e.g. read-model watermark) so a client can detect a read older than the consistency budget."
- **Create/Update:** `transaction/history`
- **Details:** Return a `consistent_as_of` timestamp; document that a just-written txn may take ≤ 1 s.

### 12. Replace card (atomic terminate + reissue)
- **Serves:** MO-5
- **Prompt:** "Implement replacement that atomically terminates the old card and issues a new `active` card inheriting limits/config; link both via audit events; old `card_id` can never authorize again."
- **Create/Update:** `card/replace`
- **Function/Component:** `replace_card(card_id, key)`
- **Details:** Transactional/saga so a partial failure leaves no orphan; replacing an already-`replaced` card → `state_conflict`.
- **DoD:** Tests: old card → `replaced` & cannot authorize; new card active with inherited limits; double-replace → `state_conflict`; failure injection leaves a consistent state (no card in limbo).

### 13. Ops/Compliance read & admin view
- **Serves:** MO-6
- **Prompt:** "Implement an ops view to read card state and the full audit trail (PAN redacted) and an audited `ops_admin` force-freeze action."
- **Create/Update:** `ops/view`, `ops/admin_actions`
- **Function/Component:** `ops_read_card`, `ops_force_freeze`
- **Details:** Deny-by-default; every ops action audited with the ops actor identity, not the cardholder's.
- **DoD:** Tests: `ops_read` sees redacted data; `ops_admin` force-freeze is audited with ops actor; `support` role cannot force-freeze.

### 14. Error taxonomy & API error mapping
- **Serves:** all
- **Prompt:** "Define the typed error categories from §D and a mapper that returns safe, sensitive-data-free error responses."
- **Create/Update:** `shared/errors`
- **Details:** No card data in any error body; stable error codes.
- **DoD:** Test asserts no error response includes PAN or token reference.

### 15. Verification fixtures & reconciliation job
- **Serves:** MO-1…MO-6, §H
- **Prompt:** "Provide reusable fixtures (cards in each state, limit edge values) and a reconciliation check enforcing audit-event-per-mutation."
- **Create/Update:** `tests/fixtures`, `jobs/audit_reconciliation`
- **Details:** Reconciliation flags any mutation without a matching audit event.
- **DoD:** Reconciliation job fails the build if the invariant is violated in a seeded dataset.

---

## G. Edge Cases & Failure Modes

| # | Scenario | Trigger | Expected behavior (user-visible) | Audit / compliance implication |
|---|----------|---------|----------------------------------|--------------------------------|
| 1 | Freeze already-frozen card | User freezes a `frozen` card | Success **no-op**; state stays `frozen` | Audit logs a no-op freeze (idempotent), preserving intent trail |
| 2 | Invalid limit | Limit `≤ 0` or `> program max` | `validation_error` with reason | Rejected attempt audited; no state change |
| 3 | Concurrent freeze + authorization | Freeze and an auth arrive together | Deterministic: optimistic version decides order; auth sees committed state — if freeze won, auth **declines** | Both actions audited with correlation ids; no lost update |
| 4 | Authorize on frozen/terminated card | Payment attempted | **Decline** with state reason | Decline audited; terminated card auth is a red flag worth monitoring |
| 5 | Stale history read | Read within consistency window of a write | Returns slightly stale list + `consistent_as_of` timestamp | None; documented eventual-consistency budget (≤ 1 s) |
| 6 | Replace already-replaced card | Replace a `replaced` card | `state_conflict` | Rejected attempt audited |
| 7 | Ops action without permission | `support`/cardholder attempts admin action | `authorization_error` (deny-by-default) | Denied attempt audited with actor — supports insider-threat review |
| 8 | PAN exposure attempt | Any code path tries to log/return full PAN | Redaction strips it; full PAN never emitted | **P1 incident** if a raw PAN ever reaches a log; control verified by test #3/#14 |
| 9 | Downstream issuer timeout | Issuer adapter unreachable on a risk-increasing op | Risk-increasing op `fails closed` (`downstream_unavailable`); freeze still succeeds locally | Pending/failed state audited; auto-reconcile when downstream recovers |
| 10 | Duplicate idempotency key, different payload | Client reuses key with changed body | `idempotency_conflict`; no second effect | Conflict audited; protects against double-spend/double-issue |
| 11 | Authorization with unknown downstream outcome | Auth sent, response lost | Resolve to `pending`, **never silent approve** | Pending auth tracked until reconciled |

---

## H. Verification

### H.1 Objective → how we know it's met

| Objective | Verification method |
|-----------|---------------------|
| **MO-1** Issuance | Unit (state init) + e2e (no PAN in response, `issued` audit event present); idempotent replay test. |
| **MO-2** Freeze/unfreeze | Unit (state machine) + integration (auth declined while frozen); double-freeze no-op test. |
| **MO-3** Limits | Unit (validation rejects bad limits) + integration (over-cap auth declined). |
| **MO-4** History | Integration (posted txn visible ≤ 1 s) + pagination cap + owner-scoping tests. |
| **MO-5** Replacement | Integration/saga (atomic terminate+reissue; failure injection leaves no orphan); old card cannot authorize. |
| **MO-6** Ops/Compliance | Integration (redacted reads; admin action audited with ops actor); deny-by-default access tests. |

### H.2 Cross-cutting verification
- **Audit-event-per-mutation invariant** — enforced continuously by the reconciliation job (Task 15); any mutation lacking a matching audit event fails the build / raises an alert.
- **No-PAN-in-logs** — a redaction test (Task 3) and a log-filter test assert full PAN never appears in logs or error bodies.
- **Performance** — load tests assert the §C.5 percentile budgets; the authorization-decision path (p99 ≤ 100 ms) is the strictest gate.
- **Manual compliance review** — the §C controls map 1:1 to enforcing code paths via the compliance checklist (ending context §E.2); reviewers sign off before release.

### H.3 Test categories (as documentation)
- **Unit:** state machine, `Money`, redaction, idempotency, limit validation.
- **Integration:** issuance↔vault, auth-decision↔state/limits, history↔event stream, audit emission.
- **End-to-end:** full user journeys (issue → set limit → transact → freeze → replace) asserting both user outcome **and** audit trail.

> Edge cases (§G), verification (§H), and performance (§C.5) are **first-class, integrated** parts of this spec — not afterthoughts — as required by the assignment.
