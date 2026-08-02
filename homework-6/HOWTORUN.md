# ▶️ How to Run — Homework 6 Multi-Agent Banking Pipeline

Everything below was run against this repository on **Python 3.14.4** in a local
`.venv`. Commands are copy-pasteable from the **`homework-6/`** directory unless a
step says otherwise.

> **Claude Code**: launch it from `homework-6/` so it picks up
> [`.mcp.json`](.mcp.json) and [`.claude/settings.json`](.claude/settings.json).
> The assignment calls the file `mcp.json`; Claude Code actually reads **`.mcp.json`**
> (with the leading dot), which is what this folder ships.

---

## 0. Prerequisites

| Tool | Needed for | Version observed |
|------|-----------|------------------|
| Python 3.11+ | Pipeline, tests, custom MCP server | **3.14.4** |
| `git` | Pre-push coverage gate | **2.50.1** |
| Node.js + `npx` | context7 MCP server | Node **v25.9.0**, npx **11.12.1** |
| Claude Code | Slash commands, meta-agents, hooks | current release |

No database, no Docker, no cloud account. The pipeline is a single-process Python
batch that reads JSON files from disk.

---

## 1. Create the virtual environment and install dependencies

```bash
cd homework-6
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Installed versions on the machine this guide was verified against:

| Package | Version |
|---------|---------|
| `fastmcp` | 3.4.5 |
| `pytest` | 9.1.1 |
| `pytest-cov` | 7.1.0 |

The pipeline itself (`agents/`, `integrator.py`) uses **only the Python standard
library**. `fastmcp` is imported solely by `mcp/server.py`.

---

## 2. Run the pipeline

```bash
.venv/bin/python integrator.py
```

Expected output (abridged):

```
seeded 8 transaction(s) into shared/input/
  transaction_validator  processed 8
  fraud_detector         processed 6
  compliance_checker     processed 4
  settlement_processor   processed 4

  id      status    score risk            amount      settled USD  reason
  TXN001  settled       8 low        1500.00 USD          1500.00  -
  TXN002  held         70 high      25000.00 USD                -  manual_review_required
  TXN003  settled      48 medium     9999.99 USD          9999.99  -
  TXN004  settled      45 medium      500.00 EUR           540.00  -
  TXN005  held         85 high      75000.00 USD                -  manual_review_required
  TXN006  rejected      - -           200.00 XYZ                -  invalid_currency
  TXN007  rejected      - -          -100.00 GBP                -  non_positive_amount
  TXN008  settled       5 low        3200.00 USD          3200.00  -

totals by status: blocked 0, held 2, rejected 2, settled 4
settled total in USD base: 15239.99
```

After a successful run:

- `shared/results/` holds eight `<transaction_id>.json` files plus
  `pipeline-summary.json`
- `shared/audit-log.jsonl` holds one line per status change (30 lines for eight
  records)
- `shared/input/`, `shared/processing/` and `shared/output/` contain **no** `.json`
  files

---

## 3. Inspect the results

```bash
# One transaction
.venv/bin/python -c "
import json, pathlib
d = json.loads(pathlib.Path('shared/results/TXN004.json').read_text())['data']
print(d['status'], d['risk_score'], d['settled_amount'])
"
# -> settled 45 540.00

# Run summary
.venv/bin/python -c "
import json, pathlib
s = json.loads(pathlib.Path('shared/results/pipeline-summary.json').read_text())
s = s.get('data', s)
print(s['counts_by_status'])
print('base total:', s['settled_total_base'])
"
# -> {'rejected': 2, 'held': 2, 'blocked': 0, 'settled': 4}
# -> base total: 15239.99

# Audit log: no unmasked account numbers
grep -c 'ACC-[0-9]' shared/audit-log.jsonl    # must be 0
grep -c 'ACC-\*\*\*\*' shared/audit-log.jsonl # positive
```

---

## 4. Run the tests with coverage

```bash
.venv/bin/python -m pytest --cov --cov-report=term-missing -q
```

Expected on this branch:

```
TOTAL                               551      2    112      0    99%
281 passed in ~0.8s
```

The gate floor is **80%**; this project targets **90%+** and currently reports **99%**.
Coverage is measured over `agents/*.py`, `integrator.py` and `mcp/server.py` via
`include` in [`pyproject.toml`](pyproject.toml) (not `source`, which silently drops
file paths).

---

## 5. Validate transactions without running the pipeline

[`TASKS.md`](TASKS.md) suggests `python agents/transaction_validator.py --dry-run`.
This project puts the CLI in [`scripts/validate_transactions.py`](scripts/validate_transactions.py)
instead, because [`agents.md`](agents.md) section 4 forbids file I/O and printing
inside a pipeline agent. The validator stays a pure function; the script is the thin
shell around it.

```bash
.venv/bin/python scripts/validate_transactions.py --dry-run
```

Expected:

```
total:   8
valid:   6
invalid: 2

rejection reasons:
  TXN006  invalid_currency  (currency 'XYZ' is not in the ISO 4217 allow-list)
  TXN007  non_positive_amount  (amount must be greater than zero)
```

Exit code is **1** when any record is invalid (expected here).

---

## 6. Install and exercise the coverage gate hook

The gate is one script, [`scripts/coverage_gate.py`](scripts/coverage_gate.py), wired
two ways:

| Caller | File |
|--------|------|
| git `pre-push` | [`hooks/pre-push`](hooks/pre-push) |
| Claude Code `PreToolUse` on `Bash` | [`.claude/settings.json`](.claude/settings.json) |

### Install the git hook (from the **repository root**)

```bash
cd /path/to/gen-ai-software-engineering
ln -sf ../../homework-6/hooks/pre-push .git/hooks/pre-push
```

The hook resolves the project root with `git rev-parse --show-toplevel` rather than
`$BASH_SOURCE`, because git invokes it through the `.git/hooks/pre-push` symlink.

### Demonstrate the gate allowing a push (real 80% floor)

```bash
git push --dry-run
```

Expected stderr:

```
coverage-gate: measuring homework-6 test coverage before push...
coverage-gate: PASS — total test coverage is 99.00%, at or above the required 80.00%.
```

### Demonstrate the gate blocking a push

Raise the floor for one command only:

```bash
COVERAGE_MIN=100 git push --dry-run
```

Expected stderr:

```
coverage-gate: BLOCKED — total test coverage is 99.00%, below the required 100.00%.
Push refused. Add tests for the uncovered lines below, then push again.
```

Use **`COVERAGE_MIN=100`**, not `99`: the gate refuses only when coverage is
**strictly below** the floor, and 99.00% is not below 99.

### Claude Code hook (no git involved)

Inside Claude Code, ask it to run `git push`. With `COVERAGE_MIN=100` set in the
environment, the `PreToolUse` hook denies the Bash call with exit code **2** and prints
the same `coverage-gate: BLOCKED` message. Non-push Bash commands (`ls`, `pytest`, …)
are ignored.

---

## 7. Configure and verify the two MCP servers

Both servers are declared in [`.mcp.json`](.mcp.json):

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "pipeline-status": {
      "command": "/…/homework-6/.venv/bin/python",
      "args": ["/…/homework-6/mcp/server.py"]
    }
  }
}
```

Edit the absolute paths for `pipeline-status` to match your machine (same pattern as
homework 5).

### In Claude Code

1. `cd homework-6` and start Claude Code.
2. Approve both servers when prompted.
3. Run `/mcp` and confirm **`context7`** and **`pipeline-status`** are connected.

### Example prompts after a pipeline run

| Server | Prompt |
|--------|--------|
| `pipeline-status` | *"Call `get_transaction_status` for TXN004 and tell me the settled amount."* → `status: settled`, `settled_amount: "540.00"` |
| `pipeline-status` | *"Call `list_pipeline_results` and give me the total count."* → `8` |
| `pipeline-status` | *"Read the `pipeline://summary` resource."* → JSON with `settled_total_base: "15239.99"` |
| `context7` | *"Resolve the library ID for FastMCP, then query how to declare a tool and a resource."* |

### Reproduce context7 from the terminal (no Claude Code)

[`scripts/context7_query.py`](scripts/context7_query.py) speaks JSON-RPC to context7
over stdio:

```bash
# List available tools
python3 scripts/context7_query.py list

# Resolve a library name to a Context7-compatible ID
python3 scripts/context7_query.py resolve "fastmcp" "declaring tools and resources"

# Query documentation for a specific library ID
python3 scripts/context7_query.py docs "/prefecthq/fastmcp" "declare a tool and a resource with a custom URI"
```

The three lookups recorded in [`research-notes.md`](research-notes.md) were made with
this client.

### Smoke-test the custom server without Claude Code

```bash
.venv/bin/python - <<'PY'
import asyncio, importlib.util, sys
from pathlib import Path
sys.path.insert(0, ".")
spec = importlib.util.spec_from_file_location("pipeline_mcp_server", "mcp/server.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
from fastmcp import Client
async def main():
    async with Client(mod.mcp) as c:
        print("tools:", [t.name for t in await c.list_tools()])
        r = await c.call_tool("get_transaction_status", {"transaction_id": "TXN005"})
        print("TXN005:", r.data)
asyncio.run(main())
PY
```

---

## 8. Use the three slash commands

Launch Claude Code from `homework-6/`:

| Command | What it does |
|---------|--------------|
| `/write-spec` | Regenerates [`specification.md`](specification.md) and [`agents.md`](agents.md) from the banking template |
| `/run-pipeline` | Clears `shared/`, runs `integrator.py`, reports the summary, verifies outcomes against section D |
| `/validate-transactions` | Runs [`scripts/validate_transactions.py --dry-run`](scripts/validate_transactions.py) and prints the verdict table |

Command definitions live in [`.claude/commands/`](.claude/commands/).

---

## 9. Troubleshooting

### `mcp/` has no `__init__.py` on purpose

Do **not** add one. A regular Python package named `mcp` in this tree would shadow the
installed `mcp` dependency of `fastmcp`. Tests load `mcp/server.py` with
`importlib.util.spec_from_file_location` for the same reason. With the project root on
`sys.path`, `import mcp` must still resolve to
`.venv/lib/.../site-packages/mcp/__init__.py`.

### `integrator.py` or `mcp/server.py` missing from the coverage report

`[tool.coverage.run] source` accepts packages and directories only and silently drops
file paths. Use `include` instead, as in this project's [`pyproject.toml`](pyproject.toml).

### Pre-push hook cannot find `coverage_gate.py`

The hook must be installed from the **repository root** with the symlink shown in
section 6. If you copied the script into `.git/hooks/` instead of symlinking, recreate
the symlink.

### context7 fails on first run

`npx -y @upstash/context7-mcp@latest` needs network access to download the package.
Subsequent runs use the npm cache.

### Held transactions never settle

`held` is terminal for this batch by design. TXN002 and TXN005 are parked for manual
review and do not reach compliance or settlement.

### `blocked` count is zero

Expected for the sample data. No destination account in `sample-transactions.json` is
on `SANCTIONS_DENY_LIST`. The `sanctioned_counterparty` path is covered by a synthetic
fixture in the test suite instead.

---

## 📸 Screenshots

Capture these after a successful run and save them in [`docs/screenshots/`](docs/screenshots/).
Embed the same images in your pull request description.

| File | Capture |
|------|---------|
| `pipeline-run.png` | Full terminal output of `.venv/bin/python integrator.py` |
| `test-coverage.png` | `pytest --cov` showing **99%** and **281 passed** |
| `skill-run-pipeline.png` | `/run-pipeline` in Claude Code with verification output |
| `hook-trigger.png` | `COVERAGE_MIN=100 git push --dry-run` showing `coverage-gate: BLOCKED` |
| `hook-pass.png` | `git push --dry-run` showing `coverage-gate: PASS` at the 80% floor |
| `mcp-interaction.png` | A context7 query result **and** `get_transaction_status("TXN004")` |
| `mcp-servers-connected.png` | `/mcp` listing both servers connected |
| `spec-generated.png` | `/write-spec` with `specification.md` visible |
| `validate-transactions.png` | `/validate-transactions` verdict table (6 valid, 2 invalid) |
| `readme-author.png` | Rendered README showing **Serhii Yefanov** and the ASCII diagram |
| `agent-2-code-generation.png` | Code-generation meta-agent with a context7 call in the transcript |

See also the screenshot table in [`README.md`](README.md).
