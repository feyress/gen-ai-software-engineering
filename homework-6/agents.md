# agents.md — Behavioural Contract (Multi-Agent Banking Pipeline)

How an AI agent must behave while working in this repository. [`specification.md`](specification.md) says what to build; this file says how to build it and when to stop and ask. [`.claude/CLAUDE.md`](.claude/CLAUDE.md) is the short checklist version of the same rules; where this file and that file overlap they agree, and where either conflicts with `specification.md`, the specification wins.

The word "agent" is used in two senses here. A **meta-agent** is one of the four AI workflows that produce this project: the spec writer, the code generator, the test writer, and the documentation writer. A **pipeline agent** is one of the five Python modules under `agents/` that process a transaction. Section 2 governs meta-agents; sections 3 onward govern the code they emit.

---

## 1. Stack assumptions

| Item | Value |
|---|---|
| Language | Python 3.11 or newer |
| Pipeline dependencies | Standard library only. `python integrator.py` must run on a bare interpreter. |
| Tooling dependencies | `fastmcp>=2.0` for `mcp/server.py`, `pytest>=8.3` and `pytest-cov>=6.0` for `tests/` |
| Money | `decimal.Decimal` with `ROUND_HALF_UP` |
| Transport | JSON files under `shared/`, one object per file, UTF-8, `indent=2` |
| Test runner | `pytest`, configured in `pyproject.toml`, coverage over `agents`, `integrator.py`, `mcp/server.py` |
| MCP | `context7` for library lookups during code generation, `pipeline-status` for querying results |

Do not add a dependency to the pipeline. If a task looks like it needs one, that is a signal the task is being over-built: say so instead of installing it.

## 2. Meta-agent boundaries

Each meta-agent owns a disjoint set of files and does not write outside it.

| Meta-agent | Writes | Never writes |
|---|---|---|
| 1 — Specification | `specification.md`, `agents.md` | Any `.py` file, tests, README |
| 2 — Code generation | `integrator.py`, `agents/*.py`, `mcp/server.py`, `research-notes.md` | Tests, README, the specification |
| 3 — Unit tests | `tests/*.py`, the coverage-gate hook configuration | Production code. A failing test means the code is wrong or the spec is wrong. |
| 4 — Documentation | `README.md`, `HOWTORUN.md`, `docs/` | Code, tests, the specification |

Meta-agent 3 may not edit production code to make a test pass. If a test fails, either the implementation deviates from `specification.md`, in which case meta-agent 2 fixes it, or the specification is wrong, in which case meta-agent 1 amends it and everything downstream follows. Silently changing the expected value in an assertion is the one thing that invalidates the whole exercise.

## 3. Non-negotiable banking rules

1. **Money is `Decimal`, parsed from the JSON string.** `Decimal("1500.00")`, never `Decimal(1500.00)`, never `float`, never integer cents. A `float` anywhere in the money path is a defect regardless of whether a test catches it.
2. **Quantize once, at settlement, with `ROUND_HALF_UP`,** to the currency minor unit: two places for USD, EUR and GBP, zero for JPY. Intermediate products stay unquantized.
3. **Never mix currencies in one arithmetic expression.** Convert through `FX_TABLE` first and record the applied `fx_rate` on the result so a reviewer can recompute it.
4. **Currency codes are ISO 4217 uppercase alpha-3 and are checked against the allow-list.** An unknown code is a validation failure with `reason: invalid_currency`, not a warning and not a pass-through.
5. **Every status change emits exactly one audit event.** A status that changes without a line appearing in `shared/audit-log.jsonl` is a defect.
6. **Thresholds are constants, not literals scattered through branches.** 10,000 for high value and the currency transaction report, 50,000 for very high value, 9,000 for the structuring band, 05:00 UTC for the timing window. Each is named once, in the module that owns it.
7. **A terminal outcome goes to `shared/results/`; anything in flight goes to `shared/output/`** addressed to the next agent. `held` counts as terminal for this batch.

## 4. The shared message envelope

Every message is one JSON object with exactly these six top-level keys:

```json
{
  "message_id": "uuid4-string",
  "timestamp": "2026-03-16T10:00:00Z",
  "source_agent": "transaction_validator",
  "target_agent": "fraud_detector",
  "message_type": "transaction",
  "data": { "transaction_id": "TXN001", "amount": "1500.00", "currency": "USD", "status": "validated" }
}
```

- A pipeline agent is a function of one envelope to one envelope: `process_message(message: dict) -> dict`.
- **An agent never mutates its input.** Build a new envelope with a fresh `message_id` and a fresh `utc_now_iso()` timestamp. A caller must be able to diff the input against the output.
- **An agent extends `data`, it does not replace it.** Keys written by an upstream agent survive to the terminal result, which is what makes the result files auditable.
- **Decision logic does no file I/O.** No `open()`, no `Path.write_text()`, no `print()` inside a pipeline agent. File movement belongs to `mailbox.py` and stdout belongs to `integrator.py`. This is what lets every agent be unit-tested on a plain dict with no filesystem at all.
- Statuses, reasons, risk levels and message types come from the closed sets in `specification.md` section C3. Inventing a new member is out of scope for the code generator; raise it instead.

## 5. Code style

- Type hints on every public function. `from __future__ import annotations` where it keeps signatures readable.
- A module docstring on every file saying what the module decides and which specification section governs it. Docstrings on public functions state the contract, not the mechanics.
- `pathlib.Path`, never string concatenation on paths. `os.replace` for the atomic rename.
- Timestamps come from `utc_now_iso()` alone. No scattered `datetime.now()`, no naive datetimes.
- No bare `except:` and no swallowed exception. Catch the specific class — `decimal.InvalidOperation`, `json.JSONDecodeError`, `OSError` — and either handle it into a typed `reason` or let it propagate to the orchestrator's per-transaction guard.
- Functions stay small enough to read whole. A scoring function that needs comments to explain its branches needs to be split instead.
- Comments explain a constraint the code cannot show, such as why a threshold sits exactly at a band edge. They do not narrate the next line.
- Prefer a plain `dict` for the envelope over a dataclass: the envelope is serialised on every hop, and the JSON shape in `TASKS.md` is the contract.

## 6. Testing expectations

- `pytest`, tests in `tests/`, one file per module under test, named `test_<module>.py`.
- **Total coverage at or above 90 percent.** The push hook blocks below 80 percent; 80 is the floor, not the target.
- Each pipeline agent needs at least a happy path and a failure path. Each closed-set `reason` needs a test that produces it, including the three that no sample record reaches: `missing_field`, `malformed_amount`, and `sanctioned_counterparty`, which are covered by synthetic fixtures built by mutating a copy of a sample record.
- One integration test runs all eight sample records end to end and asserts the outcome table in `specification.md` section D file by file, including the exact settled amount `"540.00"` for TXN004 and the exact base total `"15239.99"`.
- **No test touches the real `shared/` tree.** Every test uses `tmp_path` and, where a run needs input, a copy of `sample-transactions.json` written into that temporary root.
- Assert on `status`, `reason`, `risk_score`, `risk_level` and amounts as strings. Do not assert on `reason_detail`, which is human-facing prose and free to change.
- Money assertions compare `Decimal` values or exact strings, never floats and never `pytest.approx`.
- A test that needs the current time must control it, not sleep. Assert the shape of a timestamp, not its value.

## 7. Security and PII

- `source_account`, `destination_account` and `description` are sensitive. `description` is customer-authored free text and is treated as PII even though it looks harmless.
- **Anything account-shaped passes through `mask_account()` before it is written anywhere a human or a log reader will see it**: `shared/audit-log.jsonl`, `shared/results/pipeline-summary.json`, every `reason_detail`, every exception message, every line printed by the integrator, and every value returned by the MCP server. `ACC-1001` becomes `ACC-****01`.
- The unmasked value may live in the envelope `data` payload under `shared/`, because that is the pipeline's working state, and nowhere else.
- The sanctions deny-list is invented test data. Do not present it as real, and do not extend it to make a sample transaction fail — the empty `blocked` count in the summary is the correct result for this dataset.
- FX rates are static test values. Any documentation that shows a settled amount says so.
- No secrets, tokens, or real account data enter this repository. `shared/` run artefacts and `audit-log.jsonl` stay out of version control.

## 8. Handling uncertainty

- **Fail closed.** A transaction that cannot be evaluated is `rejected` or `held`, never `settled`. Missing `metadata` scores as the worst case on both country and channel for exactly this reason.
- **One bad record never stops the run.** An unparseable amount, an unknown currency, or a missing field stops that transaction with a typed reason and leaves the other seven to finish.
- **Ambiguity about money, status, or PII means stop and ask.** Do not guess a rate, a threshold, a rounding mode, or a new status string.
- When a gap must be filled to make progress, mark the choice **[ASSUMED]** in the file where it lands and state what would change if the assumption is wrong. An unmarked guess is worse than a marked one.
- If the implementation cannot satisfy `specification.md` as written, stop and report the conflict. Do not quietly implement something adjacent and do not weaken a test to match.
- Use `context7` before guessing at a library API, and log the query in `research-notes.md` with the library id it returned and the pattern actually applied.

## 9. Definition of done

A change is done when all of the following hold:

1. It maps to a numbered Low-Level Task in `specification.md` and satisfies that task as written.
2. `python integrator.py` runs clean end to end and the eight results match the outcome table in section D, with `shared/input/`, `shared/processing/` and `shared/output/` empty afterwards.
3. `pytest --cov` passes with total coverage at or above 90 percent, and every new branch has both a happy-path and a failure-path test.
4. No `float` in the money path, no unmasked account number outside `shared/`, no status change without an audit line, no bare `except`, no naive datetime.
5. Every status, reason, risk level and message type in the diff is a member of a closed set in `specification.md` section C3.
6. Every assumption introduced by the change is marked **[ASSUMED]** where a reviewer will find it.
7. The MCP server answers `get_transaction_status`, `list_pipeline_results`, and `pipeline://summary` against the results of that run.
