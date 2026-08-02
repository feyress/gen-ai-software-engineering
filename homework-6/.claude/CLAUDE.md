# CLAUDE.md — Project Rules (Multi-Agent Banking Pipeline)

Short, imperative rules that steer AI work in this project. Sources of truth:
[`../specification.md`](../specification.md) (what to build) and [`../agents.md`](../agents.md) (how to behave). When in doubt, those win; this file is the fast checklist.

## Money — always

- **Amounts are `decimal.Decimal`, parsed from the JSON string.** Never `float`, never `int` cents. `Decimal("1500.00")`, not `Decimal(1500.00)`.
- **Quantize with `ROUND_HALF_UP` to the currency's minor unit** (2 places for USD/EUR/GBP, 0 for JPY). Quantize once, at settlement, not on every intermediate step.
- **Currency codes are ISO 4217 uppercase alpha-3** and validated against an explicit allow-list. An unknown code is a validation failure, not a warning.
- **Never mix currencies in an arithmetic expression.** Convert through the FX table first, and record the rate used.

## PII — always

- **Account numbers and names never appear in plaintext** in logs, audit records, summaries, or error messages. Mask through `mask_account()` before anything is written.
- Masked form keeps the prefix and the last two characters: `ACC-1001` becomes `ACC-****01`.
- The full account number may live in the message `data` payload under `shared/`, because that is the pipeline's working state. It may not live in `audit-log.jsonl` or on stdout.

## Agent contract — always

- **Every agent is a pure-ish function of one envelope to one envelope**: `process_message(message: dict) -> dict`. Decision logic does no file I/O. File movement is the caller's job, in `mailbox.py`.
- **Every envelope carries** `message_id`, `timestamp` (ISO 8601, UTC, `Z` suffix), `source_agent`, `target_agent`, `message_type`, and `data`.
- **Every state change emits exactly one audit event** with timestamp, agent name, transaction id, and outcome. The audit log is append-only.
- **An agent never mutates its input dict.** Build and return a new envelope.
- **A terminal outcome goes to `shared/results/`**; anything still in flight goes to `shared/output/` addressed to the next agent.

## When unsure

- **Fail closed.** A transaction we cannot evaluate is `rejected` or `held`, never `settled`.
- An unparseable amount, an unknown currency, or a missing required field stops that transaction and records a reason. It never crashes the run or halts the other transactions.
- Ambiguity touching money, status, or PII → stop and ask, do not guess.

## Naming & patterns

- Statuses are lowercase snake_case from a closed set: `received`, `validated`, `rejected`, `risk_scored`, `held`, `cleared`, `blocked`, `settled`.
- Risk levels: `low`, `medium`, `high`. Risk score is an `int` in `0..100`.
- Rejection and hold reasons are typed strings (`invalid_currency`, `non_positive_amount`, `missing_field`, `sanctioned_counterparty`, `manual_review_required`), each paired with a human-readable `reason_detail`.
- Timestamps are produced by one helper, `utc_now_iso()`. No scattered `datetime.now()` calls, and no naive datetimes.

## What to avoid (red flags)

- Floats for money.
- Unmasked account numbers in logs or audit records.
- A status change with no audit event.
- Bare `except:` or a swallowed exception.
- `datetime.now()` without a timezone.
- An agent that reads or writes `shared/` directly instead of going through `mailbox.py`.
- Tests that touch the real `shared/` directory instead of `tmp_path`.

## Done means

A change maps to a Low-Level Task in `specification.md` and satisfies it, has unit tests for the happy path and the failure path, keeps total coverage at or above 90 percent, and leaves `python integrator.py` running clean end to end.
