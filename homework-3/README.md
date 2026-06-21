# Homework 3 — Specification-Driven Design

## Student & Task Summary

**Author:** Serhii

**Assignment:** Design a **specification package** for a finance-oriented application — documents only, **no implementation**. The graded artifact is the *specification itself*: clarity of decomposition, traceability from goals → tasks, and how well edge cases, verification, and non-functional/performance expectations are baked in.

**Chosen feature:** **Virtual card lifecycle** — issue, freeze/unfreeze, set spending limits, view transactions, and replace a virtual payment card, for a **regulated FinTech** environment serving both **end-users** and **internal ops/compliance**.

### Deliverables in this folder

| File | Purpose |
|------|---------|
| [`specification.md`](./specification.md) | Layered spec: high-level objective → mid-level objectives → non-functional/policy → implementation notes → beginning/ending context → ~16 low-level tasks, with an edge-case table, verification map, and performance budgets integrated throughout. |
| [`agents.md`](./agents.md) | AI agent operating guidelines: stack-agnostic conventions, banking domain rules, code style, testing/verification expectations, security/compliance constraints, edge-case stance. |
| [`.claude/CLAUDE.md`](./.claude/CLAUDE.md) | Editor/AI rules — the short, imperative do/don't checklist (Claude Code format) steering AI work with FinTech-sensitive defaults. |
| `README.md` | This file — rationale and industry best-practice map. |
| `TASKS.md`, `specification-TEMPLATE-example.md` | Provided assignment brief and template (kept unchanged for reference). |

> **Stack choice:** deliberately **stack-agnostic** — the spec describes conventions abstractly (e.g. "the language's arbitrary-precision decimal type for money") so it can be executed in any host stack without re-writing the requirements.

---

## Rationale

### Why the spec is structured this way
I followed the assignment's layered model and made the three cross-cutting concerns — **edge cases, verification, and performance** — *first-class* rather than trailing bullets:

- **Traceability is explicit.** Every mid-level objective has an ID (`MO-1…MO-6`) and every low-level task carries a `Serves: MO-x` tag, so a reader can trace any task up to a business outcome and any objective down to the work that delivers it. Several tasks end with a **Definition of Done** so an implementer (human or agent) can check them off without guessing.
- **Guardrails live in the spec, not just the README.** Money handling, PAN masking, idempotency, the card state machine, and the error taxonomy are in `specification.md` §D and restated as binding rules in `agents.md` / `CLAUDE.md`, so an AI partner can't "work around" them.
- **One feature, decomposed deeply** — I chose virtual cards (the task's primary example) precisely because it yields *many* small, real tasks (state machine, money VO, redaction, idempotency, audit, auth guard, issue, freeze, limits, auth-decision, history, replace, ops view, errors, fixtures) instead of three generic bullets.

### How I chose the performance targets
All numbers are labeled **[ASSUMED]** and justified in `specification.md` §C.5. The reasoning:
- **Authorization decision p99 ≤ 100 ms** is the strictest budget because it sits on the **payment hot path** — card networks impose tight authorization windows, so the state/limit check must be fast and deterministic.
- **Card-state mutations p99 ≤ 300 ms** and **history reads p95 ≤ 200 ms** reflect *self-service UX* expectations (feels instant) for operations that touch a single card / a bounded, paginated list.
- **Pagination cap (≤ 100), per-user rate limit, and ≤ 1 s time-to-consistency** are operational guardrails: they bound resource usage on a live ledger and set a realistic budget for an eventually-consistent read model where a just-posted transaction must still appear quickly.

These are presented as *targets/ranges with justifications*, not "should be fast" — and as assumptions a real program would calibrate against its processor's SLAs.

### How I decided verification depth
Verification is mapped **per objective** (`specification.md` §H.1) and reinforced by two continuously-checked invariants — *audit-event-per-mutation* and *no-PAN-in-logs* — because in a regulated context, "it works" is insufficient; **auditability and data protection must be provable**. I documented unit / integration / e2e categories *as documentation* (no code is written for this homework) and tied edge cases (§G) directly to expected user-visible behavior **and** their compliance implication, since that linkage is exactly what an auditor reviews.

---

## Industry Best Practices — and where they appear

| Best practice | Why it matters in FinTech | Where it appears |
|---------------|---------------------------|------------------|
| **PCI-DSS-aligned PAN handling** (never log/store/return full PAN; tokenization boundary; mask to last-4) | Cardholder data exposure is the highest-severity FinTech risk | `specification.md` §C.1, §D, edge case §G #8; Task 3 (redaction); `agents.md` §2.1; `CLAUDE.md` |
| **Immutable, append-only audit trail** (one event per mutation, actor + before/after, tamper-evident) | Regulatory traceability and insider-threat review | `specification.md` §C.3, Task 5, invariant in §H.2; `agents.md` §2.2 |
| **Idempotent writes** (idempotency keys; safe retries; conflict detection) | Prevents double-issue / double-spend on network retries | `specification.md` §D, Task 4, edge case §G #10; `agents.md` §2.3; `CLAUDE.md` |
| **Decimal money + ISO-4217** (no floats, no currency coercion) | Floating-point rounding errors are unacceptable for money | `specification.md` §D, Task 2; `agents.md` §1, §2.5; `CLAUDE.md` |
| **Least privilege / deny-by-default authZ** (role matrix, owner checks) | Limits blast radius; protects against insider misuse | `specification.md` §C.1, Task 6, Task 13, edge case §G #7; `agents.md` §2.6, §5 |
| **Data minimization & retention** (PII classification; no CVV/PAN stored here; 7-yr retention) | GDPR/CCPA minimization + financial record-keeping (SOX/AML) | `specification.md` §C.2 |
| **Fail-closed under uncertainty** (risk-increasing ops fail closed; never silent-approve) | Safer default when downstreams are degraded | `specification.md` §C.4, edge cases §G #9, #11; `agents.md` §6; `CLAUDE.md` |
| **Explicit, enforced state machine** (documented transitions; terminal states never authorize) | Prevents undefined/unsafe card states | `specification.md` §D, Task 1, edge cases §G #4, #6 |
| **Optimistic concurrency** (versioned cards; no lost updates) | Correctness under concurrent freeze/auth | `specification.md` §D, edge case §G #3 |
| **Typed errors without data leakage** | Clear semantics; no sensitive data in error bodies | `specification.md` §D, Task 14; `agents.md` §3 |
| **Compliance assertions as tests + reconciliation** | Makes controls *provable*, not aspirational | `specification.md` §H.2, Task 15; `agents.md` §4 |

---

## AI Tooling Used

This specification package was authored with **Claude Code** (Opus). The workflow: analyze the assignment brief (`TASKS.md`), confirm scope decisions (feature, AI-rules format, stack), then draft the layered spec and the agent/rules files with traceability tags and a best-practice map. No application code was generated, per the assignment — the deliverable is the specification itself.
