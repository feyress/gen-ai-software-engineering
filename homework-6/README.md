# 🏦 Homework 6: AI-Powered Multi-Agent Banking Pipeline

> **Author**: Serhii Yefanov
> **AI Tools Used**: Claude Code (Opus), context7 MCP

---

## 📋 Overview

This project reads eight raw banking transactions out of
[`sample-transactions.json`](sample-transactions.json) and drives each one through
validation, fraud scoring, sanctions screening and settlement. The five processing
stages never call each other. Instead they hand JSON message envelopes to one another
by writing files into shared directories, so every hop a transaction makes is a real
artefact on disk that you can open and read afterwards. Each transaction ends in
exactly one terminal file under `shared/results/`, with a status of `settled`,
`held`, `rejected` or `blocked`, and the run finishes by writing a machine-readable
tally to `shared/results/pipeline-summary.json`.

The pipeline is the *output* of the assignment, not the whole of it. The deliverable
is also the four AI workflows that produced it: one wrote the specification, one wrote
the pipeline code, one wrote the tests, and one wrote the documentation you are
reading. Each of those four was given a disjoint set of files it was allowed to touch,
which is what makes the exercise meaningful: the agent that wrote the tests could not
quietly edit the code to make a failing assertion go green. The whole system is
Python standard library only, apart from `fastmcp` in the MCP server and `pytest` in
the test suite, so `python integrator.py` runs on a bare interpreter.

Everything here is a teaching exercise. The exchange rates and the sanctions list are
invented, so no figure this pipeline settles means anything financially. See
[Honest caveats](#️-honest-caveats).

---

## 🧠 The word "agent" means two different things here

This is the single most confusing thing about the project, so it is worth being blunt
about it before anything else. There are **nine** things in this repository called an
agent, and they belong to two completely separate groups that never interact at
runtime.

| | **Meta-agents** | **Pipeline agents** |
|---|---|---|
| How many | 4 | 5 |
| What they are | AI workflows, Markdown files | Python modules |
| Where they live | [`.claude/agents/`](.claude/agents/) | [`agents/`](agents/) |
| What they act on | This repository | One transaction |
| When they run | Once, at build time, in Claude Code | Every time `integrator.py` runs |
| Written in | English prompts | Python |

A meta-agent **built** this project. A pipeline agent **processes a payment**. The
distinction is spelled out in [`agents.md`](agents.md) section 5 as well.

### 🤖 The four meta-agents (they built the project)

These are Claude Code subagent definitions. Each names the files it owns and, just as
importantly, the files it must never write.

- **[`spec-writer`](.claude/agents/spec-writer.agent.md)** decides *what gets built*.
  It reads `TASKS.md` and the sample data and produces
  [`specification.md`](specification.md) and [`agents.md`](agents.md), including the
  closed sets of every legal status and reason. It writes no Python at all. Its slash
  command is [`/write-spec`](.claude/commands/write-spec.md).
- **[`code-generator`](.claude/agents/code-generator.agent.md)** decides *how the
  specification becomes code*. It implements the eleven numbered Low-Level Tasks in
  dependency order and produces `agents/*.py`, `integrator.py`, `mcp/server.py` and
  [`research-notes.md`](research-notes.md). It is required to look up any library API
  through context7 rather than recalling it, and it may not amend the specification or
  write tests.
- **[`test-author`](.claude/agents/test-author.agent.md)** decides *whether the code
  matches the specification*. It produces `tests/*.py` and the coverage gate
  configuration. Its one hard rule is that a failing test is never fixed by editing
  the test: either the code deviates from the spec, or the spec is wrong, and either
  way it stops and reports rather than moving the goalposts.
- **[`doc-writer`](.claude/agents/doc-writer.agent.md)** decides *how the finished
  system is explained*. It produces this `README.md` and
  [`HOWTORUN.md`](HOWTORUN.md), must credit the author by name, and must verify every
  number it quotes against a real run rather than copying it out of the specification.

### ⚙️ The five pipeline agents (they process transactions)

Each one is a pure function of a single envelope to a single envelope,
`process_message(message: dict) -> dict`. None of them opens a file, prints anything,
or mutates its input, which is what lets all five be tested on a plain dictionary with
no filesystem involved. The bullets below say what each one *decides*.

- **[`transaction_validator`](agents/transaction_validator.py)** decides whether a
  record is well formed enough to be scored at all. It runs five checks in a fixed
  order and stops at the first failure, so exactly one reason is ever emitted: the
  seven required fields are present and usable (`missing_field`), the amount is a
  decimal string and not a JSON number (`malformed_amount`), the amount is greater
  than zero (`non_positive_amount`), the currency is uppercase alpha-3 and on the
  allow-list of USD, EUR, GBP and JPY (`invalid_currency`), and the amount's scale
  fits the currency's minor unit (`malformed_amount`). Rejection is terminal: it stops
  TXN006 and TXN007, and neither reaches the fraud detector.
- **[`fraud_detector`](agents/fraud_detector.py)** decides a risk score and whether a
  human has to look at the transaction. Six signals add up into an integer clamped to
  0 through 100: high value at or above 10,000 USD equivalent (70 points), very high
  value at or above 50,000 (a further 15), structuring in the 9,000 to 9,999.99 band
  (40), an unusual hour between 00:00 and 04:59 UTC (20), a counterparty country other
  than `US` (15), and the origination channel (10 for `api`, 8 for `online`, 5 for
  `mobile`, 0 for `branch`). A score of 70 or more is `high` risk and becomes `held`
  with reason `manual_review_required`, which is terminal for this batch. The
  high-value weight sits exactly on the band edge on purpose, so anything at or above
  the reporting threshold is held no matter how safe its channel looks.
- **[`compliance_checker`](agents/compliance_checker.py)** decides whether a scored
  transaction may proceed to settlement. It screens the destination account against
  `SANCTIONS_DENY_LIST` and returns `blocked` with reason `sanctioned_counterparty` on
  a hit, naming the counterparty only in masked form. On a miss it returns `cleared`
  and sets the currency-transaction-report flag `ctr_required` when the USD equivalent
  reaches 10,000.
- **[`settlement_processor`](agents/settlement_processor.py)** decides the final
  base-currency figure and closes the transaction. It multiplies the `Decimal` amount
  by the currency's rate from the static FX table and quantizes exactly once, with
  `ROUND_HALF_UP`, to two places. It records the rate it applied and the date the
  rates claim to be from, so a reviewer can recompute the number, and it emits a
  settlement reference derived from the envelope's `message_id` so the reference is
  reproducible for a given envelope.
- **[`reporting_agent`](agents/reporting_agent.py)** decides what the run as a whole
  says. It aggregates the terminal envelopes into counts by status, settled totals per
  original currency, one settled total in the USD base currency, and an exception list
  naming every transaction that did not settle along with its reason. It sums each
  currency separately before any conversion, so two currencies never meet inside one
  arithmetic expression, and it does no file I/O of its own.

### 🧩 Four supporting modules

Not agents, and they decide nothing about a transaction. They exist so that no agent
has to know about the filesystem or import a downstream agent to reach a constant.

| Module | Responsibility |
|---|---|
| [`agents/envelope.py`](agents/envelope.py) | The shared kernel: the closed status, reason, risk-level and message-type sets, the currency allow-list, the minor-unit map, the FX table, `utc_now_iso()`, `mask_account()` and `build_envelope()`. Imports no other project module, so the import graph stays acyclic. |
| [`agents/mailbox.py`](agents/mailbox.py) | The only module permitted to touch `shared/`. Writes atomically through a `.tmp` file and `os.replace`, claims a message into `shared/processing/` before an agent runs, and routes a delivered envelope to `shared/results/` or `shared/output/` by whether its status is terminal. |
| [`agents/audit.py`](agents/audit.py) | The append-only trail. One JSON line per status change in `shared/audit-log.jsonl`, with any account-shaped token masked on the way in. |
| [`agents/results_store.py`](agents/results_store.py) | The read side over `shared/results/`, used by the reporting agent, the orchestrator and the MCP server, so account masking cannot drift between them. A transaction that was never processed comes back as `None`, never as an invented status. |

[`integrator.py`](integrator.py) is the orchestrator. It is the only module that knows
the pipeline order and the only one that writes to stdout. Every transaction is
processed inside its own guard, so one unreadable record can never stop the other
seven.

---

## 🗺️ Architecture

```
                      sample-transactions.json  (8 raw records)
                                   │
                     integrator.py: one envelope per record
                                   ▼
                         ┌─────────────────────┐
                         │    shared/input/    │  status: received
                         └──────────┬──────────┘
                                    │  claim ▸ shared/processing/
                                    ▼
                    ┌───────────────────────────────┐
                    │     transaction_validator     │      rejected
                    │  7 fields · amount · ISO 4217 │──┐   invalid_currency
                    └───────────────┬───────────────┘  │   non_positive_amount
                                    │ validated        │   malformed_amount
                                    ▼                  │   missing_field
                         ┌─────────────────────┐       │
                         │    shared/output/   │       │
                         └──────────┬──────────┘       │
                                    ▼                  │
                    ┌───────────────────────────────┐  │
                    │         fraud_detector        │  │   held
                    │   additive score, 0 .. 100    │──┤   manual_review_required
                    └───────────────┬───────────────┘  │
                                    │ risk_scored      │
                                    ▼                  │
                         ┌─────────────────────┐       │
                         │    shared/output/   │       │
                         └──────────┬──────────┘       │
                                    ▼                  │
                    ┌───────────────────────────────┐  │
                    │       compliance_checker      │  │   blocked
                    │  sanctions screen · CTR flag  │──┤   sanctioned_counterparty
                    └───────────────┬───────────────┘  │
                                    │ cleared          │
                                    ▼                  │
                         ┌─────────────────────┐       │
                         │    shared/output/   │       │
                         └──────────┬──────────┘       │
                                    ▼                  │
                    ┌───────────────────────────────┐  │
                    │      settlement_processor     │  │   settled
                    │  Decimal × FX, ROUND_HALF_UP  │──┤
                    └───────────────────────────────┘  │
                                                       ▼
                                        ┌──────────────────────────────┐
                                        │       shared/results/        │
                                        │  <transaction_id>.json  × 8  │
                                        └───────────────┬──────────────┘
                                                        │ read back
                                                        ▼
                                                 reporting_agent
                                                        │
                                                        ▼
                                     shared/results/pipeline-summary.json

   every status change above also appends one line to shared/audit-log.jsonl
   (30 lines for a clean 8-record run), with account numbers masked as ACC-****01
```

The three branches on the right are the terminal exits. A transaction that is
rejected at validation, held at fraud scoring, or blocked at compliance goes straight
to `shared/results/` and is never handed to the next stage. Only a transaction that
survives all three reaches settlement.

---

## 🛠️ Tech stack

Every version below was read from the environment this README was written against,
not from the requirements file.

| Layer | Choice | Version |
|---|---|---|
| Language | Python (`.venv`) | **3.14.4** (`specification.md` sets the floor at 3.11) |
| Pipeline runtime | Python standard library only | no third-party import in `agents/` or `integrator.py` |
| Money | `decimal.Decimal` with `ROUND_HALF_UP` | stdlib |
| Transport | JSON files under `shared/`, UTF-8, `indent=2` | stdlib `json` + `os.replace` |
| Custom MCP server | [`fastmcp`](mcp/server.py) | **3.4.5** |
| External MCP server | `@upstash/context7-mcp@latest` over `npx` | Node **v25.9.0**, npx **11.12.1** |
| Test runner | `pytest` | **9.1.1** |
| Coverage | `pytest-cov` / `coverage` | **7.1.0** / **7.15.2** |
| Coverage gate | bash `pre-push` + Claude Code `PreToolUse` hook | git **2.50.1** |

The `fastmcp>=2.0` pin in [`requirements.txt`](requirements.txt) resolves to 3.4.5, a
whole major version above the one used in homework 5. That gap is exactly why the
code-generation agent was required to check the decorator API through context7 instead
of recalling it; see [Query 1 in `research-notes.md`](research-notes.md).

Roughly 1,340 lines of production Python across `agents/`, `integrator.py` and
`mcp/server.py`, against roughly 2,360 lines of tests, plus about 450 lines of
supporting CLI and hook scripts in `scripts/`.

---

## 📊 What the eight sample transactions actually do

Observed by running `.venv/bin/python integrator.py`, not copied from the
specification.

| ID | Amount | Channel / country / time | Score | Risk | Terminal status | Reason | Settled USD |
|---|---|---|---:|---|---|---|---:|
| TXN001 | 1500.00 USD | online / US / 09:00Z | 8 | low | `settled` | | 1500.00 |
| TXN002 | 25000.00 USD | branch / US / 09:15Z | 70 | high | `held` | `manual_review_required` | |
| TXN003 | 9999.99 USD | online / US / 09:30Z | 48 | medium | `settled` | | 9999.99 |
| TXN004 | 500.00 EUR | api / DE / 02:47Z | 45 | medium | `settled` | | 540.00 |
| TXN005 | 75000.00 USD | branch / US / 10:00Z | 85 | high | `held` | `manual_review_required` | |
| TXN006 | 200.00 XYZ | online / US / 10:05Z | | | `rejected` | `invalid_currency` | |
| TXN007 | -100.00 GBP | online / GB / 10:10Z | | | `rejected` | `non_positive_amount` | |
| TXN008 | 3200.00 USD | mobile / US / 10:15Z | 5 | low | `settled` | | 3200.00 |

The run tally, straight from `shared/results/pipeline-summary.json`:

- **Counts by status**: settled 4, held 2, rejected 2, blocked 0
- **Settled per original currency**: USD `14699.99`, EUR `500.00`
- **Settled total in USD base**: `15239.99`
- **Exceptions**: 4, naming TXN002, TXN005, TXN006 and TXN007 with their reasons

Stage throughput drops as transactions exit: the validator handles all 8, the fraud
detector 6, compliance 4 and settlement 4. TXN004 is the only record that converts a
currency, at `500.00 × 1.080000 = 540.00`. Two things a reader might mistake for gaps
are expected: `blocked` is 0 because no sample destination account is on the deny-list,
and `ctr_required` is never `true` because the only two records above the 10,000
threshold are held by the fraud detector before compliance ever sees them. Both paths
are covered by synthetic fixtures in the test suite instead.

---

## 🧪 Tests and the coverage gate

`.venv/bin/python -m pytest --cov -q` gives **281 passing tests** and **99% total
coverage** over 551 statements and 112 branches:

```
Name                              Stmts   Miss Branch BrPart  Cover   Missing
-----------------------------------------------------------------------------
agents/__init__.py                    0      0      0      0   100%
agents/audit.py                      25      0      6      0   100%
agents/compliance_checker.py         20      0      2      0   100%
agents/envelope.py                   66      0      6      0   100%
agents/fraud_detector.py             84      0     26      0   100%
agents/mailbox.py                    56      0      8      0   100%
agents/reporting_agent.py            28      0      6      0   100%
agents/results_store.py              34      0     10      0   100%
agents/settlement_processor.py       22      0      0      0   100%
agents/transaction_validator.py      65      2     24      0    98%   76-77
integrator.py                       125      0     18      0   100%
mcp/server.py                        26      0      6      0   100%
-----------------------------------------------------------------------------
TOTAL                               551      2    112      0    99%
281 passed in 0.83s
```

The two uncovered lines are the `except decimal.InvalidOperation` arm in the
validator. The amount regex runs first and already guarantees the string parses, so
that arm is defence in depth that no input can currently reach. Deleting it to buy
100% would remove a safety net, so it stays.

The suite is spread across eleven files: 57 tests on the validator, 53 on the fraud
detector, 34 end-to-end integration tests, 33 on the kernel, 24 on the mailbox, 18 on
compliance, 17 on the results store, 15 on settlement, 12 on reporting, 10 on the MCP
server and 8 on the audit trail. Every test that writes anything writes under
`tmp_path`, so no test can reach the real `shared/` tree. That isolation is a design
consequence, not a testing trick: every function that touches the filesystem takes an
explicit `root: Path`, which is what makes `root=tmp_path` sufficient.

### 🚧 The coverage gate hook

The gate is one implementation, [`scripts/coverage_gate.py`](scripts/coverage_gate.py),
with two callers, so it cannot pass in one place and fail in the other:

| Caller | Wiring | Effect when coverage is short |
|---|---|---|
| git `pre-push` | [`hooks/pre-push`](hooks/pre-push), symlinked into `.git/hooks/` | exits 1, aborting the push |
| Claude Code `PreToolUse` | [`.claude/settings.json`](.claude/settings.json) on the `Bash` matcher | exits 2, denying the tool call |

The Claude Code caller inspects the tool payload and ignores every Bash command that
is not a `git push`, catching `git push`, `git -C dir push` and a push chained after
`&&`. **The floor is 80%**, and a push below it is refused. Both paths were exercised
against this repository:

```
$ git push --dry-run
coverage-gate: measuring homework-6 test coverage before push...
coverage-gate: PASS — total test coverage is 99.00%, at or above the required 80.00%.

$ COVERAGE_MIN=100 git push --dry-run
coverage-gate: measuring homework-6 test coverage before push...
coverage-gate: BLOCKED — total test coverage is 99.00%, below the required 100.00%.
Push refused. Add tests for the uncovered lines below, then push again.
```

To demonstrate the block without weakening the real gate, raise the floor for one
command with the `COVERAGE_MIN` environment variable. **Use `COVERAGE_MIN=100`.**

---

## 🔌 MCP servers

Two servers are declared in [`.mcp.json`](.mcp.json), which Claude Code loads when it
is started from this directory.

### context7, used while the code was being written

The code-generation meta-agent was forbidden from writing against a library API it had
only recalled. Three lookups went through context7 and each one changed a specific
line of code. They are written up in full in
[**`research-notes.md`**](research-notes.md):

| Query | Library ID returned | What changed as a result |
|---|---|---|
| FastMCP tool and resource declaration | `/prefecthq/fastmcp` | `mcp/server.py` uses the bare `@mcp.tool` decorator, a custom `pipeline://summary` resource URI, and a plain `mcp.run()` that still defaults to stdio, which is why `.mcp.json` needs no transport configuration |
| `Decimal` quantization for money | `/python/cpython` | `agents/envelope.py` derives the exponent as `Decimal(10) ** -places` from the minor-unit table rather than hard-coding `Decimal("0.01")`, and passes `ROUND_HALF_UP` explicitly because the context default is `ROUND_HALF_EVEN` |
| Isolating filesystem tests with `tmp_path` | `/pytest-dev/pytest` | every filesystem function takes an explicit `root: Path`, so tests pass `tmp_path` and no test needs `monkeypatch.chdir` |

[`scripts/context7_query.py`](scripts/context7_query.py) is a small JSON-RPC client
that makes those lookups reproducible from a terminal, without Claude Code in the
loop.

### pipeline-status, the custom FastMCP server

[`mcp/server.py`](mcp/server.py) makes a finished run queryable. It reads only through
`agents/results_store.py`, the same layer the reporting agent uses, so account masking
cannot drift between the two.

| Endpoint | Kind | Answers |
|---|---|---|
| `get_transaction_status(transaction_id)` | tool | status, risk score, risk level, reason and settled amount for one transaction, with `null` for anything it never acquired |
| `list_pipeline_results()` | tool | the total count and one compact record per processed transaction |
| `pipeline://summary` | resource | the latest run summary as formatted text, or a clear message when no run has completed |

An unknown transaction returns `{"found": false}` rather than a guessed status,
because `status` is a closed set. Verified against the current run: `TXN004` comes
back `found: true, status: settled, risk_score: 45, settled_amount: "540.00"`,
`TXN999` comes back `found: false`, and `list_pipeline_results` reports a total of 8.

---

## ⌨️ Slash commands

Three Claude Code commands wrap the workflow. Setup and example prompts are in
[`HOWTORUN.md`](HOWTORUN.md).

| Command | Does |
|---|---|
| [`/write-spec`](.claude/commands/write-spec.md) | Regenerates `specification.md` and `agents.md` from the template, tracing every rule to a sample record |
| [`/run-pipeline`](.claude/commands/run-pipeline.md) | Clears `shared/`, runs the pipeline, reports the summary, then checks the outcomes against section D of the specification and greps the audit log for unmasked accounts |
| [`/validate-transactions`](.claude/commands/validate-transactions.md) | Runs validation only, with no pipeline and no files written, and prints the verdict table |

---

## 📸 Screenshots

These eleven images are planned for `docs/screenshots/` and are captured by hand after
a run. The first five are the ones [`TASKS.md`](TASKS.md) requires; the rest cover the
remaining steps the pull request description has to evidence.

| File | Will show |
|---|---|
| `pipeline-run.png` | The full terminal output of `.venv/bin/python integrator.py`: the four stage counts, the eight-row outcome table, and the tally ending in `settled total in USD base: 15239.99` |
| `test-coverage.png` | The `pytest --cov` report: the per-module table, `TOTAL ... 99%`, and `281 passed` |
| `skill-run-pipeline.png` | `/run-pipeline` executing inside Claude Code, including its verification that the outcomes match section D and that the audit log holds no unmasked account |
| `hook-trigger.png` | The coverage gate refusing a push: the `coverage-gate: BLOCKED` message from `COVERAGE_MIN=100 git push`, with the coverage table beneath it |
| `mcp-interaction.png` | A context7 query result next to a call to a custom tool, for instance `get_transaction_status("TXN004")` returning `settled` and `"540.00"` |
| `spec-generated.png` | `/write-spec` producing `specification.md`, with the closed sets and the Low-Level Tasks visible |
| `agent-2-code-generation.png` | The code-generation meta-agent at work, with a context7 call visible in the transcript so the lookup is evidenced rather than asserted |
| `readme-author.png` | A rendered preview of this README showing the author line and the ASCII architecture diagram |
| `mcp-servers-connected.png` | The `/mcp` listing with both `context7` and `pipeline-status` connected |
| `validate-transactions.png` | `/validate-transactions` printing the verdict table: 8 total, 6 valid, 2 invalid, with the two reasons |
| `hook-pass.png` | The gate allowing a push at the real threshold: `coverage-gate: PASS — total test coverage is 99.00%, at or above the required 80.00%` |

---

## 🤖 How AI was used

- The four meta-agents in [`.claude/agents/`](.claude/agents/) were dispatched as
  Claude Code subagents on **Claude Opus**, in stage order: `spec-writer` produced the
  specification and the behavioural contract, `code-generator` produced the pipeline
  and the MCP server, `test-author` produced the test suite and the coverage gate, and
  `doc-writer` produced this README and `HOWTORUN.md`. Each was handed only the files
  its role definition lists as inputs and was held to the file boundaries in
  [`agents.md`](agents.md) section 2.
- **context7** supplied the library facts rather than memory: the FastMCP 3.4.5
  decorator API, the `decimal` module's own currency guidance on `quantize` and
  `ROUND_HALF_UP`, and the pytest `tmp_path` fixture. All three queries, the library
  IDs they resolved to, and the code each one changed are recorded in
  [`research-notes.md`](research-notes.md).
- Worth reporting honestly: the test agent found a real defect in the project's own
  configuration rather than in the pipeline. `pyproject.toml` originally measured
  coverage with `[tool.coverage.run] source`, which accepts packages and directories
  only and silently discards file paths. `integrator.py` and `mcp/server.py` were
  therefore not being measured at all, and the headline percentage was flattering. The
  option was changed to `include`, which does accept file paths, and both files are now
  in the report at 100%. The bug produced no error message of any kind, which is why it
  is called out here.
- A separate `PostToolUse` hook, [`scripts/audit_hook.py`](scripts/audit_hook.py),
  logs every file the meta-agents wrote to `docs/meta-agent-runs/tool-audit.jsonl`,
  mirroring for the AI workflows what the audit trail does for transactions. It never
  blocks: a hook that can fail a session over its own logging is worse than no hook.
- The screenshots and the git history were produced by hand.

---

## ⚠️ Honest caveats

- **The FX rates are invented.** The `FX_TABLE` in
  [`agents/envelope.py`](agents/envelope.py) carries USD 1.000000, EUR 1.080000, GBP
  1.270000 and JPY 0.006700, marked `[ASSUMED]` in the source and dated
  `2026-03-16`. No rate source ships with the assignment. The `settled_total_base` of
  `15239.99` is therefore arithmetic over made-up numbers and means nothing
  financially. The applied rate is recorded on every settled result so a reviewer can
  at least recompute the figure from the inputs.
- **The sanctions deny-list is invented.** `SANCTIONS_DENY_LIST` in
  [`agents/compliance_checker.py`](agents/compliance_checker.py) holds three fabricated
  account numbers and no real screening list. By design none of the eight sample
  destination accounts matches, which is why `blocked` is 0. It was deliberately not
  extended to make a sample transaction fail.
- The transaction data itself is synthetic, and the account numbers, descriptions and
  counterparties are all fictional. Account numbers are nonetheless masked everywhere
  a human or a log reader sees them, because the point is to practise the discipline.
- The pipeline is a single-process, sequential batch. It has no retries, no
  concurrency, no resumption of a held transaction, and no persistence beyond JSON
  files on a local disk.

---

## 📚 Further reading in this folder

| File | Contents |
|---|---|
| [`HOWTORUN.md`](HOWTORUN.md) | Numbered steps from a clean checkout to a working demo |
| [`specification.md`](specification.md) | The full technical specification: closed sets, thresholds, FX table, and the eleven Low-Level Tasks |
| [`agents.md`](agents.md) | The behavioural contract: banking rules, the envelope, PII, and the definition of done |
| [`research-notes.md`](research-notes.md) | The three context7 queries in full, with the code each one changed |
| [`.claude/CLAUDE.md`](.claude/CLAUDE.md) | The short checklist version of the project rules |
| [`TASKS.md`](TASKS.md) | The original assignment |

---

<div align="center">

*Completed as part of the AI-Assisted Development course.*

</div>
