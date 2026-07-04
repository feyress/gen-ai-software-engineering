# Bug Context — Ledger #001

## Summary

The `homework-4` sample app (a small Node.js transaction ledger) ships with two
seeded logic bugs and two seeded security issues. This file is the human-authored
brief that kicks off the agent pipeline.

## Application under test

- `src/ledger.js` — pure ledger functions (balance, filtering, range, summary).
- `src/exporter.js` — builds and exports a text report.
- `src/cli.js` — demo entry point (`npm start`).
- `tests/ledger.test.js` — baseline tests (two currently fail, see below).

Run command: `npm test` (Node's built-in `node:test` runner).

## Defects

### Bug 1 — Wrong balance (logic)
- **Where:** `src/ledger.js`, `getBalance`.
- **Symptom:** Debits are *added* to the balance instead of being subtracted, so the
  reported balance is too high. For the sample ledger the function returns `1550`
  but the correct net balance is `1050`.
- **Repro:** `npm start` prints `Net balance: 1550`; the test
  *"getBalance subtracts debits from credits"* expects `1050` and fails.

### Bug 2 — Boundary dates excluded (logic / off-by-one)
- **Where:** `src/ledger.js`, `getTransactionsInRange`.
- **Symptom:** The range is documented as inclusive `[start, end]`, but strict `>`/`<`
  comparisons drop transactions that land exactly on `start` or `end`.
- **Repro:** `getTransactionsInRange(ledger, '2026-01-05', '2026-01-15')` returns 1
  transaction; the inclusive expectation is 3. The test
  *"getTransactionsInRange includes the boundary dates (inclusive)"* fails.

### Security 1 — Command injection (CRITICAL)
- **Where:** `src/exporter.js`, `exportReport`.
- **Symptom:** The report text and destination filename are interpolated into a shell
  string passed to `execSync`. A crafted filename (e.g. `out.txt; rm -rf ~`) executes
  arbitrary commands.

### Security 2 — Hardcoded secret (HIGH)
- **Where:** `src/exporter.js`, top-level `API_KEY` constant.
- **Symptom:** A live-looking API key is committed in source. Secrets must come from
  the environment / a secrets manager.

## Scope for this pipeline run

The implementation plan (`implementation-plan.md`) fixes **Bug 1** and **Bug 2** and
makes a small touch to `exporter.js`. The two security issues are intentionally left in
place so the Security Verifier has real findings to report on the changed code.
