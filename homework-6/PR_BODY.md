# Homework 6: AI-Powered Multi-Agent Banking Pipeline

> **Author**: Serhii Yefanov

## Summary

This submission implements Homework 6 end to end: four **meta-agents** (AI workflows
in `.claude/agents/`) that produced a working **transaction processing pipeline**
(five Python agents in `agents/` plus an orchestrator), together with slash commands,
a coverage-gate hook, two MCP servers, tests, and documentation.

The pipeline reads eight records from `sample-transactions.json`, passes JSON envelopes
through `shared/input` → validator → fraud detector → compliance → settlement →
`shared/results`, and writes a run summary to `pipeline-summary.json`. A clean run
produces **4 settled**, **2 held**, **2 rejected**, **0 blocked**, with a USD base
total of **15239.99**.

## What was built

### Meta-agents (deliverable)

| Agent | Role | Output |
|-------|------|--------|
| `spec-writer` | Specification | `specification.md`, `agents.md`, `/write-spec` |
| `code-generator` | Pipeline code | `agents/*.py`, `integrator.py`, `mcp/server.py`, `research-notes.md` |
| `test-author` | Tests + gate | `tests/` (281 tests, 99% coverage), `scripts/coverage_gate.py`, hooks |
| `doc-writer` | Documentation | `README.md`, `HOWTORUN.md` |

### Pipeline agents (output of meta-agent 2)

`transaction_validator` → `fraud_detector` → `compliance_checker` →
`settlement_processor`, with `reporting_agent` aggregating terminal results.

### Skills & hooks

- `/write-spec`, `/run-pipeline`, `/validate-transactions` in `.claude/commands/`
- Coverage gate blocks `git push` below **80%** via `hooks/pre-push` and Claude Code
  `PreToolUse` in `.claude/settings.json`

### MCP

- **context7** — three library lookups documented in `research-notes.md`
  (`/prefecthq/fastmcp`, `/python/cpython`, `/pytest-dev/pytest`)
- **pipeline-status** — custom FastMCP server with `get_transaction_status`,
  `list_pipeline_results`, and `pipeline://summary`

## How to verify

```bash
cd homework-6
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python integrator.py
.venv/bin/python -m pytest --cov -q
.venv/bin/python scripts/validate_transactions.py --dry-run
```

From the repo root, install the pre-push hook:

```bash
ln -sf ../../homework-6/hooks/pre-push .git/hooks/pre-push
git push --dry-run   # should PASS at 99% coverage
COVERAGE_MIN=100 git push --dry-run   # should BLOCK
```

Full steps: [`homework-6/HOWTORUN.md`](homework-6/HOWTORUN.md).

## AI usage

- Four meta-agents dispatched as Claude Code subagents (Opus), each with a disjoint
  file boundary per `agents.md` section 2.
- **context7** used during code generation for FastMCP 3.4.5 API, `decimal` money
  handling, and pytest `tmp_path` isolation — see `research-notes.md`.
- Test agent found a real config bug: `pyproject.toml` originally used `source` for
  coverage, which silently excluded `integrator.py` and `mcp/server.py`; fixed to
  `include`.

## Screenshots

Five required screenshots are in [`homework-6/docs/screenshots/`](homework-6/docs/screenshots/).
Embedded below for review.

### Pipeline run

Terminal output of `.venv/bin/python integrator.py`: all eight transactions processed,
stage counts (8 → 6 → 4 → 4), outcome table, and settled total **15239.99** USD.

![pipeline-run](homework-6/docs/screenshots/pipeline-run.png)

### Tests and coverage

`pytest --cov` report: **281 passed**, **99%** total coverage across `agents/`,
`integrator.py`, and `mcp/server.py`.

![test-coverage](homework-6/docs/screenshots/test-coverage.png)

### `/run-pipeline` skill

Claude Code executing `/run-pipeline`: pipeline run, summary from
`pipeline-summary.json`, and all four contract verification checks **PASSED**
(eight result files, empty working directories, outcomes match section D, audit log
has no unmasked accounts).

![skill-run-pipeline](homework-6/docs/screenshots/skill-run-pipeline.png)

### Coverage gate blocking a push

`COVERAGE_MIN=100 git push --dry-run` refused by the pre-push hook:
`coverage-gate: BLOCKED — total test coverage is 99.00%, below the required 100.00%`.

![hook-trigger](homework-6/docs/screenshots/hook-trigger.png)

### MCP: context7 + custom tool

Left: context7 `resolve-library-id` for FastMCP → `/prefecthq/fastmcp`, plus
`query-docs` excerpts for `@mcp.tool` and `@mcp.resource`. Right:
`get_transaction_status("TXN004")` on the `pipeline-status` server →
`status: settled`, `settled_amount: "540.00"`.

![mcp-interaction](homework-6/docs/screenshots/mcp-interaction.png)

### Additional evidence (in repo, not screenshot)

| Item | Where to find it |
|------|------------------|
| Specification | [`homework-6/specification.md`](homework-6/specification.md) — all five sections, eleven Low-Level Tasks |
| Author + ASCII diagram | [`homework-6/README.md`](homework-6/README.md) — credits **Serhii Yefanov** |
| context7 research log | [`homework-6/research-notes.md`](homework-6/research-notes.md) — three queries with library IDs |

## Test plan

- [x] `python integrator.py` completes with 8 results and empty working directories
- [x] Outcomes match `specification.md` section D (including TXN004 → `540.00`)
- [x] `pytest --cov` passes with ≥ 90% total coverage (99% observed)
- [x] Coverage gate blocks push when `COVERAGE_MIN=100`
- [x] Coverage gate allows push at the real 80% floor
- [x] `get_transaction_status`, `list_pipeline_results`, `pipeline://summary` respond
- [x] `README.md` credits **Serhii Yefanov** and includes ASCII architecture diagram
- [x] `HOWTORUN.md` has numbered steps from setup to demo
- [x] Five required screenshots captured and embedded above
