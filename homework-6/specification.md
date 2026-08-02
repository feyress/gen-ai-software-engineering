# Multi-Agent Banking Transaction Pipeline Specification

> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that will satisfy the High and Mid-Level Objectives.

This specification is the contract for the code-generation agent, the test agent, and the documentation agent. Every status string, reason string, threshold, and file path used by the implementation is fixed here. Where a value could not be derived from `TASKS.md`, `sample-transactions.json`, or `.claude/CLAUDE.md`, it is marked **[ASSUMED]** and may be challenged in review. Nothing in this document may be substituted by the implementer without amending this document first.

---

## A. High-Level Objective

Build a Python 3 multi-agent pipeline that reads raw banking transactions from `sample-transactions.json` and drives each one through validation, fraud scoring, compliance screening, and settlement by passing JSON message envelopes between five independent agents through shared directories, ending with one terminal result per transaction in `shared/results/` and a machine-readable run summary.

---

## B. Mid-Level Objectives

**B1. Every input record reaches exactly one terminal file.**
A run over the eight records in `sample-transactions.json` writes eight files named `shared/results/<transaction_id>.json`, each with `data.status` in `{rejected, held, blocked, settled}`, plus `shared/results/pipeline-summary.json`. When the run finishes, `shared/input/`, `shared/processing/`, and `shared/output/` contain no `.json` files. No unhandled exception escapes the orchestrator, and the failure of one transaction does not stop the other seven.

**B2. Validation rejects on typed reasons and is terminal.**
A transaction whose currency is not in the ISO 4217 allow-list is written to `shared/results/` with `status: rejected` and `reason: invalid_currency` (exercised by TXN006, currency `XYZ`). A transaction whose amount parses to a value less than or equal to zero is written with `status: rejected` and `reason: non_positive_amount` (exercised by TXN007, amount `-100.00`). A rejected transaction is never passed to `fraud_detector` and never appears in `shared/output/`.

**B3. Fraud scoring is deterministic, additive, and holds high risk.**
The fraud detector assigns an integer `risk_score` in `0..100` and a `risk_level` of `low`, `medium`, or `high` using the fixed weights in section C4. A USD-equivalent amount at or above 10,000 contributes 70 points and therefore always produces `risk_level: high`, `status: held`, and `reason: manual_review_required` written to `shared/results/` (exercised by TXN002 at 25,000.00 USD scoring 70 and TXN005 at 75,000.00 USD scoring 85). An amount in the structuring band 9,000.00 to 9,999.99 contributes 40 points and produces `risk_level: medium` with `status: risk_scored` (exercised by TXN003 at 9,999.99 USD scoring 48). Settlement-hour and cross-border signals together also produce `medium` (exercised by TXN004, 02:47Z from `DE` over the `api` channel, scoring 45).

**B4. Money is converted with `Decimal` and `ROUND_HALF_UP` only.**
A cleared transaction is settled into the USD base currency using the static FX table in section C5, quantized once to the base currency minor unit of two decimal places with `ROUND_HALF_UP`, and written with `status: settled`, a `settlement_reference`, the `fx_rate` applied, and the `settled_amount` as a string. TXN004 at `500.00` EUR and rate `1.080000` settles to exactly `"540.00"` USD. No `float` appears anywhere in the money path.

**B5. Reporting and audit are complete and PII-safe.**
`agents/reporting_agent.py` writes `shared/results/pipeline-summary.json` containing, for the sample data, `counts_by_status` of `{"settled": 4, "held": 2, "rejected": 2, "blocked": 0}`, `settled_totals_by_currency` of `{"USD": "14699.99", "EUR": "500.00"}`, a `settled_total_base` of `"15239.99"` USD, and an `exceptions` array naming TXN002, TXN005, TXN006, and TXN007 with their reasons. Every status change appends exactly one line to `shared/audit-log.jsonl` carrying `timestamp`, `agent`, `transaction_id`, and `outcome`, and no account number appears there in plaintext: `ACC-1001` is written as `ACC-****01`.

---

## C. Implementation Notes

### C1. Stack and layout

Python 3.11 or newer, standard library only for the pipeline itself. `fastmcp>=2.0` is used solely by `mcp/server.py`; `pytest>=8.3` and `pytest-cov>=6.0` are used solely by `tests/`. The pipeline must import nothing outside the standard library, so that `python integrator.py` runs on a bare interpreter. **[ASSUMED]** Python 3.11 as the floor; `pyproject.toml` does not pin a version.

```
homework-6/
├── integrator.py                  orchestrator
├── agents/
│   ├── envelope.py                shared kernel: constants, envelope, time, masking
│   ├── mailbox.py                 the only module that touches shared/ directly
│   ├── audit.py                   append-only audit trail
│   ├── results_store.py           read-side queries over shared/results/
│   ├── transaction_validator.py
│   ├── fraud_detector.py
│   ├── compliance_checker.py
│   ├── settlement_processor.py
│   └── reporting_agent.py
├── mcp/server.py
├── shared/{input,processing,output,results}/
└── shared/audit-log.jsonl
```

`agents/envelope.py` is the shared kernel. Every constant table that more than one agent needs lives there — the status, reason, and risk-level enumerations, the currency allow-list, the minor-unit map, and the FX table — so that no agent imports a downstream agent to reach a constant. **[ASSUMED]** The audit trail is written to `shared/audit-log.jsonl`; `CLAUDE.md` names the file but not its directory, and placing it under `shared/` keeps every run artefact in one tree while staying out of `shared/results/`.

### C2. Message envelope

Every message on the wire is a single JSON object in this shape, matching the standard format in `TASKS.md`:

```json
{
  "message_id": "3f2c8b1e-9a4d-4f61-8b3a-0d5c7e2a1b44",
  "timestamp": "2026-03-16T10:00:00Z",
  "source_agent": "transaction_validator",
  "target_agent": "fraud_detector",
  "message_type": "transaction",
  "data": { "transaction_id": "TXN001", "amount": "1500.00", "currency": "USD", "status": "validated" }
}
```

| Field | Type | Rule |
|---|---|---|
| `message_id` | string | New UUID4 per envelope. An agent never reuses its input `message_id`. |
| `timestamp` | string | ISO 8601 UTC with a `Z` suffix, produced only by `utc_now_iso()`. |
| `source_agent` | string | Module name of the agent that produced this envelope, or `integrator` for the first one. |
| `target_agent` | string | Module name of the next agent, or `results` when the outcome is terminal. |
| `message_type` | string | Closed set: `transaction`, `result`, `summary`. |
| `data` | object | The transaction payload, carried forward and extended, never replaced. |

`data` always carries the original record fields (`transaction_id`, `timestamp`, `source_account`, `destination_account`, `amount`, `currency`, `transaction_type`, `description`, `metadata`) plus the fields each agent adds. Agents extend `data`; they do not drop keys written by an earlier agent. An agent never mutates its input dict — it builds and returns a new envelope, so a caller may compare the input and output envelopes.

### C3. Closed enumerated sets

The code-generation agent may not introduce any value outside these sets. A condition that does not map to an existing member is a specification gap and must be raised, not invented around.

| Set | Members |
|---|---|
| `status` | `received`, `validated`, `rejected`, `risk_scored`, `held`, `cleared`, `blocked`, `settled` |
| `risk_level` | `low`, `medium`, `high` |
| `reason` | `missing_field`, `invalid_currency`, `non_positive_amount`, `malformed_amount`, `sanctioned_counterparty`, `manual_review_required` |
| `message_type` | `transaction`, `result`, `summary` |

Terminal statuses are `rejected`, `blocked`, `settled`, and `held`. `held` is terminal for the batch: a held transaction is parked for a human reviewer and this system does not resume it, so it is written to `shared/results/` and never reaches `compliance_checker`. Every non-terminal status routes to `shared/output/` addressed to the next agent. Every `reason` is paired with a free-text `reason_detail` intended for a human; `reason` is what tests assert on, `reason_detail` is not.

### C4. Validation and fraud rules

Required fields, all of which must be present and non-empty: `transaction_id`, `timestamp`, `source_account`, `destination_account`, `amount`, `currency`, `transaction_type`. `description` and `metadata` are optional. A required field that is present but unusable as its declared type — an unparseable `timestamp`, an empty string, a non-string identifier — is reported as `missing_field` with the field named in `reason_detail`; amounts are the exception, since they have their own reasons.

Validation checks run in this fixed order and the first failure wins, so exactly one `reason` is ever emitted:

1. Required fields present and usable, else `missing_field`.
2. `amount` is a string matching `^-?\d{1,15}(\.\d{1,6})?$`, else `malformed_amount`. A JSON number is rejected here rather than coerced, because coercion would pass through `float`. **[ASSUMED]** The regex bounds; `TASKS.md` only says amounts are decimal strings.
3. `Decimal(amount) > 0`, else `non_positive_amount` (TXN007, `-100.00`).
4. `currency` is uppercase alpha-3 and a member of the allow-list `{USD, EUR, GBP, JPY}`, else `invalid_currency` (TXN006, `XYZ`). **[ASSUMED]** The allow-list is limited to these four so that every accepted currency has an FX rate and a minor unit; the ISO 4217 register is far larger.
5. The scale of `amount` does not exceed the currency minor unit, else `malformed_amount`.

Fraud signals are additive, evaluated on the USD-equivalent amount, and the total is clamped to `0..100`:

| Signal | Condition | Points | Sample record |
|---|---|---:|---|
| High value | USD equivalent ≥ 10,000.00 | 70 | TXN002 (25,000.00), TXN005 (75,000.00) |
| Very high value | USD equivalent ≥ 50,000.00, in addition to the above | 15 | TXN005 (75,000.00) |
| Structuring | 9,000.00 ≤ USD equivalent < 10,000.00 | 40 | TXN003 (9,999.99, one cent under the reporting threshold) |
| Unusual timing | Envelope `data.timestamp` hour in `00:00:00`–`04:59:59` UTC | 20 | TXN004 (02:47Z) |
| Cross-border | `metadata.country` differs from the domestic country `US`, or is absent | 15 | TXN004 (`DE`) |
| Channel: `api` | `metadata.channel == "api"`, or `metadata` absent | 10 | TXN004 |
| Channel: `online` | `metadata.channel == "online"` | 8 | TXN001, TXN003 |
| Channel: `mobile` | `metadata.channel == "mobile"` | 5 | TXN008 |
| Channel: `branch` | `metadata.channel == "branch"` | 0 | TXN002, TXN005 |

Bands: `low` is `0..29`, `medium` is `30..69`, `high` is `70..100`. The high-value weight of 70 is set exactly at the `high` boundary so that any transaction at or above the 10,000 reporting threshold is held regardless of channel — TXN002 comes through the lowest-risk channel, `branch`, and must still be held. The structuring weight of 40 places a lone structuring hit in the middle of the `medium` band, which is what TXN003 requires: suspicious enough to score, not enough to stop. **[ASSUMED]** All nine weights and the two band edges; the sample data fixes their relative order and the outcomes in section D, not the exact integers. Missing `metadata` is scored as the worst case on both country and channel, per the fail-closed rule in `CLAUDE.md`, and a channel outside the four named above is scored at 10 for the same reason. All four channels present in the sample data are named in the table, so an unrecognised channel is covered by a synthetic fixture in `tests/`.

### C5. Money handling

Amounts are `decimal.Decimal` parsed from the JSON string, never `float` and never integer cents. The base currency is `USD`. Conversion multiplies by the source currency rate and quantizes once, at settlement, with `ROUND_HALF_UP`.

| Currency | Rate to USD | Minor unit |
|---|---|---:|
| USD | `1.000000` | 2 |
| EUR | `1.080000` | 2 |
| GBP | `1.270000` | 2 |
| JPY | `0.006700` | 0 |

**[ASSUMED]** All four rates and the `FX_RATES_AS_OF` date of `2026-03-16`. No rate source is supplied with the assignment; these are static test rates and must be replaced before any real use. The rate actually applied is recorded on the settled result, so a reviewer can recompute the figure. Currencies are never mixed inside one arithmetic expression: convert first, then add.

### C6. Audit trail

`agents/audit.py` appends one JSON object per line to `shared/audit-log.jsonl`. The file is opened in append mode and never rewritten. Every status change emits exactly one record with these fields:

| Field | Example |
|---|---|
| `timestamp` | `"2026-03-16T10:00:00Z"`, from `utc_now_iso()` |
| `agent` | `"fraud_detector"` |
| `transaction_id` | `"TXN002"` |
| `outcome` | the new `status`, e.g. `"held"` |
| `message_id` | the envelope that carried the change |
| `detail` | optional short string, PII-masked |

### C7. PII

`source_account` and `destination_account` are sensitive, as is `description`, which is free text a customer may have written. `mask_account("ACC-1001")` returns `"ACC-****01"`: everything up to and including the last hyphen is kept, the final two characters are kept, and the characters between are replaced with exactly four asterisks regardless of how many were masked, so the mask does not leak the original length. An account number shorter than two characters after the prefix is fully masked as `"ACC-****"`. Masked values are what appear in `shared/audit-log.jsonl`, in `shared/results/pipeline-summary.json`, in every exception message, and on stdout. The unmasked value stays in the envelope `data` payload under `shared/`, which is the pipeline's working state.

### C8. File-based transport

`agents/mailbox.py` is the only module that touches `shared/` directly. Every agent module is a decision function that does no file I/O.

- **Write** is atomic: serialise to `<target>.tmp` in the destination directory, `os.replace()` onto the final name. A reader therefore never observes a partial JSON file.
- **Claim** moves `shared/input/<id>.json` or `shared/output/<id>.json` to `shared/processing/<id>.json` before the agent runs, so an interrupted run leaves visible evidence of which transaction was in flight.
- **Deliver** writes the returned envelope to `shared/output/<transaction_id>.json` for a non-terminal status, or `shared/results/<transaction_id>.json` for a terminal one, then removes the claimed file from `shared/processing/`.
- File names are `<transaction_id>.json`. `pipeline-summary.json` is the one file in `shared/results/` that is not a transaction result, and every reader of that directory must skip it by name.

### C9. Compliance

`SANCTIONS_DENY_LIST` is a module-level frozen set in `agents/compliance_checker.py` holding destination account numbers: `{"ACC-4242", "ACC-6666", "ACC-7000"}`. **[ASSUMED]** These three values are invented test-only data. No real sanctions list is supplied with the assignment, and by design none of the eight sample destination accounts appears in it, so no sample record is blocked. The `sanctioned_counterparty` path is therefore covered by a synthetic fixture in `tests/`, not by the sample run, and a reviewer should read the empty `blocked` count in the summary as expected rather than as a gap.

A currency transaction report flag, `ctr_required: true`, is set when the USD equivalent is at or above 10,000.00. In the sample run this flag is never `true`, because the only two records above the threshold, TXN002 and TXN005, are held by the fraud detector before compliance sees them. TXN003 exercises the negative boundary at 9,999.99, one cent below; the positive branch is covered by a synthetic fixture.

### C10. Testing

`pytest` with `pytest-cov`, coverage measured over `agents`, `integrator.py`, and `mcp/server.py` as configured in `pyproject.toml`. Total coverage must be at or above 90 percent; the push hook blocks below 80 percent. Every test writes under `tmp_path` and no test reads or writes the real `shared/` tree. Each agent needs at least one happy-path and one failure-path test, and one integration test runs all eight sample records end to end and asserts the outcome table in section D against the resulting files.

---

## D. Context

### Beginning context

- `sample-transactions.json` — eight raw records, each with `transaction_id`, `timestamp`, `source_account`, `destination_account`, `amount` as a decimal string, `currency`, `transaction_type`, `description`, and a `metadata` object holding `channel` and `country`.
- `TASKS.md` — the assignment, fixing the shared-directory protocol and the envelope shape.
- `.claude/CLAUDE.md` — the project rules on money, PII, the agent contract, and fail-closed behaviour.
- `pyproject.toml`, `requirements.txt` — test and coverage configuration, `fastmcp` dependency.
- `agents/`, `mcp/`, `tests/`, `shared/` exist as empty directories. No source file exists yet.

### Ending context

- `integrator.py` and the nine modules under `agents/` listed in section C1.
- `mcp/server.py` exposing `get_transaction_status`, `list_pipeline_results`, and `pipeline://summary`.
- `tests/` with per-agent unit tests and one end-to-end integration test, total coverage at or above 90 percent.
- `shared/results/` holding eight transaction results and `pipeline-summary.json`; `shared/audit-log.jsonl` holding one line per state change; `shared/input/`, `shared/processing/`, and `shared/output/` empty.

### Expected outcome for each sample record

These eight rows are the acceptance criteria for the integration test. They were read off the data, not assumed.

| ID | Amount | Channel / Country / Time | Signals that fire | Score | Risk | Terminal status | Reason |
|---|---|---|---|---:|---|---|---|
| TXN001 | 1500.00 USD | online / US / 09:00Z | channel `online` | 8 | low | `settled` | — |
| TXN002 | 25000.00 USD | branch / US / 09:15Z | high value | 70 | high | `held` | `manual_review_required` |
| TXN003 | 9999.99 USD | online / US / 09:30Z | structuring, channel `online` | 48 | medium | `settled` | — |
| TXN004 | 500.00 EUR | api / DE / 02:47Z | unusual timing, cross-border, channel `api` | 45 | medium | `settled` | — |
| TXN005 | 75000.00 USD | branch / US / 10:00Z | high value, very high value | 85 | high | `held` | `manual_review_required` |
| TXN006 | 200.00 XYZ | online / US / 10:05Z | none — stopped at validation | — | — | `rejected` | `invalid_currency` |
| TXN007 | -100.00 GBP | online / GB / 10:10Z | none — stopped at validation | — | — | `rejected` | `non_positive_amount` |
| TXN008 | 3200.00 USD | mobile / US / 10:15Z | channel `mobile` | 5 | low | `settled` | — |

TXN004 settles at `500.00 × 1.080000 = 540.00` USD. The four settled records total `15239.99` USD in base currency. TXN007 originates in `GB` and would score as cross-border, but validation is terminal and it never reaches the fraud detector — TXN004 is the only record that exercises the cross-border signal end to end. No sample record reaches the sanctions deny-list or trips the currency-transaction-report flag; see section C9.

---

## E. Low-Level Tasks

Tasks are ordered by dependency. Tasks 1 to 3 build the kernel every agent imports; tasks 4 to 8 are the five pipeline agents; tasks 9 to 11 are the read side, the orchestrator, and the MCP server. Each `Prompt` is written to be pasted verbatim into the code-generation agent together with this file.

### 1. Shared kernel

```
Task: Message Envelope and Constants
Prompt: "Read specification.md sections C1, C2, C3, C5, and C7. Create agents/envelope.py, the shared kernel that every other module imports. Define the closed constant sets exactly as specified and nothing more: STATUS, REASON, RISK_LEVEL, and MESSAGE_TYPE as str-valued Enums or frozensets; TERMINAL_STATUSES; CURRENCY_ALLOW_LIST as the frozenset {USD, EUR, GBP, JPY}; MINOR_UNITS mapping each of those to 2, 2, 2, 0; BASE_CURRENCY as 'USD'; DOMESTIC_COUNTRY as 'US'; FX_TABLE mapping each allow-listed currency to a Decimal rate built from a string literal, with USD 1.000000, EUR 1.080000, GBP 1.270000, JPY 0.006700; and FX_RATES_AS_OF as '2026-03-16'. Implement utc_now_iso() returning the current UTC time as an ISO 8601 string with a Z suffix and second precision, using timezone-aware datetime only. Implement mask_account(account: str) -> str returning ACC-****01 for ACC-1001, keeping everything through the final hyphen and the last two characters and always using exactly four asterisks in between, and returning a fully masked value when fewer than two characters follow the prefix. Implement usd_equivalent(amount: Decimal, currency: str) -> Decimal multiplying by the FX rate without quantizing. Implement build_envelope(source_agent, target_agent, message_type, data, message_id=None) -> dict returning a new dict with a fresh uuid4 message_id when none is given, a utc_now_iso() timestamp, and a deep copy of data so callers cannot alias it. Use decimal.Decimal everywhere money appears and never float. Add type hints and a short module docstring. Do not import any other project module."
File to CREATE: agents/envelope.py
Function to CREATE: build_envelope(source_agent: str, target_agent: str, message_type: str, data: dict, message_id: str | None = None) -> dict, utc_now_iso() -> str, mask_account(account: str) -> str, usd_equivalent(amount: Decimal, currency: str) -> Decimal
Details: Single source of truth for every closed set, the currency allow-list, the minor-unit map, and the FX table. No file I/O, no logging, no dependency on any other agents module, so that the import graph stays acyclic.
```

### 2. Mailbox

```
Task: File-Based Mailbox
Prompt: "Read specification.md section C8. Create agents/mailbox.py, the only module in the project permitted to touch the shared/ directory tree. Implement ensure_directories(root: Path) -> None creating shared/input, shared/processing, shared/output and shared/results under the given root. Implement write_message(directory: Path, name: str, message: dict) -> Path writing UTF-8 JSON with indent=2 atomically: serialise to name + '.tmp' in the same directory, flush, then os.replace onto the final path, so a reader never sees a partial file. Implement read_message(path: Path) -> dict. Implement list_messages(directory: Path) -> list[Path] returning .json files sorted by name and always skipping pipeline-summary.json. Implement claim(source_dir: Path, processing_dir: Path, name: str) -> Path moving a message into shared/processing before an agent runs. Implement deliver(root: Path, envelope: dict, claimed: Path) -> Path writing the envelope to shared/results/<transaction_id>.json when envelope['data']['status'] is terminal and to shared/output/<transaction_id>.json otherwise, then removing the claimed file from shared/processing. Take the terminal status set from agents.envelope; do not redefine it. Raise a named exception on a missing file rather than returning None, and never use a bare except. Add type hints and pathlib throughout."
File to CREATE: agents/mailbox.py
Function to CREATE: ensure_directories(root: Path) -> None, write_message(directory: Path, name: str, message: dict) -> Path, read_message(path: Path) -> dict, list_messages(directory: Path) -> list[Path], claim(source_dir: Path, processing_dir: Path, name: str) -> Path, deliver(root: Path, envelope: dict, claimed: Path) -> Path
Details: Atomic write through a temporary file and os.replace. Routing by terminal status is decided here so no agent needs to know the directory layout. Skipping pipeline-summary.json is enforced in one place.
```

### 3. Audit trail

```
Task: Audit Trail
Prompt: "Read specification.md sections C6 and C7. Create agents/audit.py writing an append-only audit trail to shared/audit-log.jsonl, one JSON object per line. Implement record_event(root: Path, agent: str, transaction_id: str, outcome: str, message_id: str, detail: str | None = None) -> dict building the event with a utc_now_iso() timestamp from agents.envelope, appending it to shared/audit-log.jsonl in append mode with a trailing newline, and returning the event. Implement read_events(root: Path) -> list[dict] parsing the file back, returning an empty list when it does not exist. No account number, customer name, or transaction description may reach this file: pass any account value through mask_account() from agents.envelope before writing, and assert in the docstring that callers must not put raw PII into detail. Never truncate or rewrite the file. Add type hints."
File to CREATE: agents/audit.py
Function to CREATE: record_event(root: Path, agent: str, transaction_id: str, outcome: str, message_id: str, detail: str | None = None) -> dict, read_events(root: Path) -> list[dict]
Details: One event per status change, fields timestamp, agent, transaction_id, outcome, message_id, detail. Append-only. Masked accounts only.
```

### 4. Transaction Validator

```
Task: Transaction Validator
Prompt: "Read specification.md sections C3 and C4 and the outcome table in section D. Create agents/transaction_validator.py with process_message(message: dict) -> dict. It receives an envelope whose data.status is 'received' and returns a new envelope; it must not mutate the input. Run the five validation checks in exactly the specified order and stop at the first failure so only one reason is ever emitted: (1) the seven required fields transaction_id, timestamp, source_account, destination_account, amount, currency, transaction_type are present, non-empty and usable, with an unparseable ISO 8601 timestamp or an empty string reported as missing_field naming the field in reason_detail; (2) amount is a string matching ^-?\\d{1,15}(\\.\\d{1,6})?$, otherwise malformed_amount, and a JSON number is rejected here rather than coerced; (3) Decimal(amount) is greater than zero, otherwise non_positive_amount; (4) currency is uppercase alpha-3 and in CURRENCY_ALLOW_LIST from agents.envelope, otherwise invalid_currency; (5) the scale of amount does not exceed MINOR_UNITS for that currency, otherwise malformed_amount. On success return an envelope targeting fraud_detector with data.status 'validated' and data.amount left as the original string. On failure return an envelope targeting 'results' with data.status 'rejected', data.reason set to the failing member of the reason set, and a human-readable data.reason_detail. Use only status and reason values from the closed sets in section C3. Do no file I/O and no printing. Use decimal.Decimal, never float, and never a bare except: catch decimal.InvalidOperation explicitly. Add type hints and a docstring naming TXN006 and TXN007 as the sample records this agent stops."
File to CREATE: agents/transaction_validator.py
Function to CREATE: process_message(message: dict) -> dict
Details: Checks required fields, amount format, positivity, ISO 4217 membership, and decimal scale, in that order. Rejection is terminal and routes to shared/results/. TXN006 must come out rejected/invalid_currency and TXN007 rejected/non_positive_amount; the other six must come out validated.
```

### 5. Fraud Detector

```
Task: Fraud Detector
Prompt: "Read specification.md section C4 and the outcome table in section D. Create agents/fraud_detector.py with process_message(message: dict) -> dict, receiving a validated envelope and returning a new one without mutating the input. Compute the USD equivalent of data.amount with usd_equivalent() from agents.envelope, then sum these additive signals into an integer risk_score clamped to 0..100: 70 when the USD equivalent is at or above 10000; a further 15 when it is at or above 50000; 40 when it is at or above 9000 and below 10000; 20 when the hour of data.timestamp is between 00:00:00 and 04:59:59 UTC; 15 when metadata.country differs from DOMESTIC_COUNTRY or metadata is absent; and a channel weight of 10 for api or absent metadata, 8 for online, 5 for mobile, 0 for branch, 10 for any unrecognised channel. Map the score to a risk_level of low for 0..29, medium for 30..69, high for 70..100. Record the signals that fired as a sorted list of strings in data.risk_signals using the identifiers high_value, very_high_value, structuring, unusual_timing, cross_border, channel_risk. When risk_level is high, return an envelope targeting 'results' with data.status 'held', data.reason 'manual_review_required' and a reason_detail naming the signals. Otherwise return an envelope targeting compliance_checker with data.status 'risk_scored'. Always set data.risk_score and data.risk_level. Use decimal.Decimal for all comparisons and never float. Use only values from the closed sets in section C3. Do no file I/O. Add type hints and a docstring stating the expected scores for the sample records: TXN001 8, TXN002 70, TXN003 48, TXN004 45, TXN005 85, TXN008 5."
File to CREATE: agents/fraud_detector.py
Function to CREATE: process_message(message: dict) -> dict
Details: Deterministic additive scoring over high value, structuring, unusual timing, cross-border, and channel. High risk means held for manual review and is terminal for this run; everything else continues to compliance as risk_scored. Missing metadata scores as the worst case on both country and channel.
```

### 6. Compliance Checker

```
Task: Compliance Checker
Prompt: "Read specification.md sections C3 and C9. Create agents/compliance_checker.py with process_message(message: dict) -> dict, receiving a risk_scored envelope and returning a new one without mutating the input. Define the module-level frozenset SANCTIONS_DENY_LIST = {'ACC-4242', 'ACC-6666', 'ACC-7000'} and document in the docstring that these are invented test-only values that no sample transaction matches. Screen data.destination_account against the deny-list: on a hit return an envelope targeting 'results' with data.status 'blocked', data.reason 'sanctioned_counterparty', and a reason_detail that names the counterparty only through mask_account() from agents.envelope. On a miss return an envelope targeting settlement_processor with data.status 'cleared' and data.ctr_required set to True when the USD equivalent of the amount is at or above 10000 and False otherwise, plus data.screened_at from utc_now_iso(). Never write an unmasked account number into any reason_detail or message. Use decimal.Decimal for the threshold comparison and only values from the closed sets in section C3. Do no file I/O. Add type hints."
File to CREATE: agents/compliance_checker.py
Function to CREATE: process_message(message: dict) -> dict
Details: Sanctions screening on the destination account plus a currency-transaction-report flag at 10000 USD equivalent. Blocked is terminal; cleared continues to settlement. No sample record is blocked, and TXN003 at 9999.99 exercises the negative boundary of the report flag; both positive branches are covered by synthetic fixtures in tests.
```

### 7. Settlement Processor

```
Task: Settlement Processor
Prompt: "Read specification.md sections C5 and D. Create agents/settlement_processor.py with process_message(message: dict) -> dict, receiving a cleared envelope and returning a new terminal one without mutating the input. Parse data.amount into a Decimal from its string form. Look up the rate in FX_TABLE from agents.envelope, multiply, then quantize exactly once to the BASE_CURRENCY minor unit of two decimal places using ROUND_HALF_UP. Write these fields into data: status 'settled', base_currency 'USD', fx_rate as the rate string, fx_rate_as_of from FX_RATES_AS_OF, settled_amount as the quantized value converted with str(), settled_at from utc_now_iso(), and settlement_reference formatted as 'SET-' + transaction_id + '-' + the first eight hexadecimal characters of the envelope message_id with hyphens removed and uppercased, so the reference is deterministic for a given envelope and a test can reproduce it. Target 'results'. Never use float, never call round(), and never mix two currencies in one expression. Use only values from the closed sets in section C3. Do no file I/O. Add type hints and a docstring stating that TXN004 at 500.00 EUR and rate 1.080000 must settle to exactly '540.00' USD."
File to CREATE: agents/settlement_processor.py
Function to CREATE: process_message(message: dict) -> dict
Details: Converts to the USD base currency through the static FX table with Decimal and ROUND_HALF_UP, quantizes once to the minor unit, and emits a deterministic settlement reference. Settled is terminal.
```

### 8. Reporting Agent

```
Task: Reporting Agent
Prompt: "Read specification.md sections B5, C7 and D. Create agents/reporting_agent.py with process_message(message: dict) -> dict and build_summary(results: list[dict]) -> dict. build_summary takes the list of terminal envelopes read from shared/results/ and returns the summary payload: generated_at from utc_now_iso(); total_transactions; counts_by_status as a dict with the keys rejected, held, blocked and settled always present and defaulting to 0; settled_totals_by_currency mapping each original currency to the summed original amount as a string, computed with Decimal; settled_total_base as the summed settled_amount in USD as a string; and exceptions as a list of objects with transaction_id, status, reason and reason_detail for every rejected, held or blocked transaction, sorted by transaction_id. No account number or description may appear in the summary; pass anything account-shaped through mask_account() from agents.envelope. process_message wraps build_summary in an envelope with message_type 'summary', source_agent 'reporting_agent', target_agent 'results', and data set to the summary payload; it receives the collected results under message['data']['results'] and does no file I/O itself, leaving the write of shared/results/pipeline-summary.json to the caller. Use Decimal for every total and never float. Add type hints and a docstring stating the expected sample-run figures: 8 transactions, counts settled 4, held 2, rejected 2, blocked 0, settled_total_base '15239.99'."
File to CREATE: agents/reporting_agent.py
Function to CREATE: process_message(message: dict) -> dict, build_summary(results: list[dict]) -> dict
Details: Aggregates everything in shared/results/ excluding pipeline-summary.json itself into counts by status, settled totals by currency, a base-currency total, and an exception list with reasons. The caller writes the file through mailbox so this module stays free of file I/O.
```

### 9. Results Store

```
Task: Results Store
Prompt: "Read specification.md sections C8 and D. Create agents/results_store.py, the read side over shared/results/, shared by the reporting agent, the integrator and the MCP server so none of them re-implements directory scanning. Implement get_transaction(root: Path, transaction_id: str) -> dict | None returning the parsed result envelope for that id or None when no file exists. Implement list_results(root: Path) -> list[dict] returning every result envelope sorted by transaction_id, always skipping pipeline-summary.json. Implement latest_summary(root: Path) -> dict | None returning the parsed pipeline-summary.json or None when the pipeline has not run. Implement status_of(root: Path, transaction_id: str) -> dict | None returning a small projection with transaction_id, status, risk_score, risk_level, reason and settled_amount, using None for fields the transaction never acquired, and masking any account field through mask_account(). Read through agents.mailbox rather than opening files directly. Never invent a status value for a missing transaction: return None and let the caller decide how to report it. Add type hints."
File to CREATE: agents/results_store.py
Function to CREATE: get_transaction(root: Path, transaction_id: str) -> dict | None, list_results(root: Path) -> list[dict], latest_summary(root: Path) -> dict | None, status_of(root: Path, transaction_id: str) -> dict | None
Details: Query layer over the results directory, reused verbatim by mcp/server.py. A missing transaction is None, never a fabricated status, because status is a closed set.
```

### 10. Orchestrator

```
Task: Pipeline Orchestrator
Prompt: "Read specification.md sections B1, C1, C8 and D. Create integrator.py driving the whole pipeline. On run: call mailbox.ensure_directories(); load sample-transactions.json; for each record build an envelope with build_envelope(source_agent='integrator', target_agent='transaction_validator', message_type='transaction', data=record plus status 'received') and write it to shared/input/<transaction_id>.json; then drive the four decision agents in order transaction_validator, fraud_detector, compliance_checker, settlement_processor, and for each transaction still in flight claim its message into shared/processing/, call that agent's process_message, record one audit event with audit.record_event, and deliver the returned envelope through mailbox.deliver. Finally read every result with results_store.list_results, call reporting_agent.process_message, and write the summary payload to shared/results/pipeline-summary.json. Print a per-transaction line and a final tally to stdout using masked account numbers only. Wrap each transaction in its own try/except that catches Exception, records an audit event, and writes a rejected result with reason missing_field and an explanatory reason_detail, so one bad record can never stop the other seven; never use a bare except and never let an exception escape run(). Expose run(root: Path = Path('.'), source: Path = Path('sample-transactions.json')) -> dict returning the summary payload, and guard the CLI entry point with if __name__ == '__main__'. The eight sample records must end as in the section D table: TXN001, TXN003, TXN004 and TXN008 settled, TXN002 and TXN005 held, TXN006 and TXN007 rejected, with shared/input/, shared/processing/ and shared/output/ empty when the run ends."
File to CREATE: integrator.py
Function to CREATE: run(root: Path = Path('.'), source: Path = Path('sample-transactions.json')) -> dict, main() -> int
Details: Sets up the shared directories, seeds shared/input/ from sample-transactions.json, drives the agents in order, isolates per-transaction failures, and writes the run summary. It is the only place that knows the pipeline order.
```

### 11. MCP Server

```
Task: Pipeline Status MCP Server
Prompt: "Read specification.md section C10 and TASKS.md Task 4. Create mcp/server.py, a FastMCP server named 'pipeline-status' that makes the pipeline queryable. Use the fastmcp package. Expose the tool get_transaction_status(transaction_id: str) -> dict returning the projection from results_store.status_of, and returning {'found': False, 'transaction_id': transaction_id} when the transaction is unknown rather than inventing a status value, because status is a closed set. Expose the tool list_pipeline_results() -> dict returning the total count and one compact record per processed transaction from results_store.list_results. Expose the resource pipeline://summary returning the latest pipeline run summary from results_store.latest_summary as formatted text, and a clear message when no run has completed yet. Resolve the project root from the module location so the server works regardless of the working directory it is launched from. All read access goes through agents.results_store; do not open files in shared/ directly. Account numbers must already be masked by results_store and must not be unmasked here. Guard the run call with if __name__ == '__main__' so the module can be imported by tests without starting a server. Add type hints and docstrings on every tool, since the docstrings are what the MCP client shows the user."
File to CREATE: mcp/server.py
Function to CREATE: get_transaction_status(transaction_id: str) -> dict, list_pipeline_results() -> dict, pipeline_summary() -> str
Details: FastMCP tools and one resource over the same read layer the reporting agent uses. Returns a found flag rather than a fabricated status for unknown ids, and never widens the PII exposure of the results store.
```
