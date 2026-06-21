# HOWTORUN — Homework 4 Pipeline

## Prerequisites

- **Node.js** ≥ 18 (uses the built-in `node:test` runner). Verified on Node 25.
  - Check: `node --version`
- **Claude Code CLI** on your `PATH` (provides the `claude` command), signed in.
  - Check: `claude --version`
- No `npm install` needed — the sample app has **zero runtime dependencies**.

## 1. See the seeded bugs (before)

```bash
cd homework-4
npm test
```

Expected: **2 of 4** baseline tests fail —
*"getBalance subtracts debits from credits"* and
*"getTransactionsInRange includes the boundary dates (inclusive)"* — because of the two
seeded logic bugs. `npm start` prints an inflated `Net balance: 1550`.

## 2. Run the pipeline (one command)

```bash
npm run pipeline      # or: ./run-pipeline.sh
```

This runs the four agents **in order**, each with the model declared in its
`agents/*.agent.md` frontmatter and with its skill auto-loaded:

1. **Research Verifier** (opus, read-only) → `context/bugs/001/research/verified-research.md`
2. **Bug Fixer** (sonnet) → edits source, runs tests → `context/bugs/001/fix-summary.md`
3. **Security Verifier** (opus, read-only) → `context/bugs/001/security-report.md`
4. **Unit Test Generator** (haiku) → `tests/ledger.changes.test.js` + `context/bugs/001/test-report.md`

Each stage prints a banner with its model and output path. The opus stages can run for a
minute or two **with no streaming output** — that is normal (`claude -p` prints only when
the stage finishes), not a hang.

### Permission model (why it doesn't prompt)

Headless agents can't answer interactive permission prompts, so each is launched with
`--permission-mode bypassPermissions` and scoped tools:

- **Read-only agents** (Research Verifier, Security Verifier) are additionally launched with
  `--disallowedTools "Edit" "Bash"` — a hard block, so they **cannot modify source or run
  shell commands**; they only read code and write their one report file.
- **Mutating agents** (Bug Fixer, Unit Test Generator) may edit files and run `npm test`.

This is a deliberate, scoped choice for unattended execution. Run it only on a repo you
trust (it is operating on this homework's own `src/`).

### Resuming / re-running

- The script is **resumable**: a stage whose output file already exists is **skipped**, so
  if a stage fails (e.g. a transient `API Error: Overloaded`), just run `npm run pipeline`
  again and it continues from the failed stage. Transient failures are also **retried**
  automatically (up to `MAX_ATTEMPTS`, default 3).
- To **re-run the whole pipeline from scratch**, reset the sample app and clear the
  generated artifacts first (the Bug Fixer is not idempotent — its before/after blocks only
  match the original buggy source):

  ```bash
  git checkout -- src/ledger.js src/exporter.js
  rm -f context/bugs/001/research/verified-research.md \
        context/bugs/001/fix-summary.md \
        context/bugs/001/security-report.md \
        context/bugs/001/test-report.md \
        tests/ledger.changes.test.js
  FORCE=1 npm run pipeline    # FORCE=1 also re-runs stages even if outputs exist
  ```

## 3. Confirm the result (after)

```bash
npm test     # all tests pass (4 baseline + 9 generated = 13)
npm start    # Net balance: 1050 ; In range 2026-01-05..2026-01-15: 3
```

Then read the four artifacts under `context/bugs/001/` (and `tests/ledger.changes.test.js`).

## Screenshots

Capture these into `docs/screenshots/` for the PR:

1. `npm run pipeline` — the four stage banners and "PIPELINE COMPLETE".
2. The applied fix (e.g. `git diff src/ledger.js`) or `fix-summary.md`.
3. `security-report.md` — the CRITICAL/HIGH findings.
4. `npm test` after — 13/13 passing.
