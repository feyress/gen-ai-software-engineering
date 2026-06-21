# Verified Research — Ledger #001

> Author: Bug Research Verifier. This document fact-checks every claim in
> `codebase-research.md` against the actual source files and assigns an objective
> research-quality rating per the **research-quality-measurement** skill.

## Verification Summary

- **Result:** PASS
- **Research Quality:** Excellent
- **Counts:**
  - `verified_refs` = 3 / 3 (every claimed snippet found in the cited file)
  - `exact_line_refs` = 3 / 3 (every `file:line` exactly correct)
  - `minor_discrepancies` = 0
  - `major_discrepancies` = 0

## Verified Claims

| Claim | Cited reference | Actual location found | Verdict |
|-------|-----------------|-----------------------|---------|
| **R1** — Balance ignores debit sign | `src/ledger.js:35` (`getBalance`), `balance += tx.amount;` | `src/ledger.js:35`, inside `getBalance` (lines 32–38), snippet matches exactly | ✅ |
| **R2** — Inclusive range uses strict comparisons | `src/ledger.js:59` (`getTransactionsInRange`), `return ledger.filter((tx) => tx.date > start && tx.date < end);` | `src/ledger.js:59`, inside `getTransactionsInRange` (lines 58–60), snippet matches exactly | ✅ |
| **R3** — Report export is shell-built | `src/exporter.js:32` (`exportReport`), `execSync(\`echo "${report}" > ${filename}\`);` | `src/exporter.js:32`, inside `exportReport` (lines 30–34), snippet matches exactly | ✅ |

### Detail per claim

- **R1 — Balance ignores debit sign.** Line 35 reads `balance += tx.amount;`. The
  function docstring (lines 27–28) states "Credits increase the balance, debits
  decrease it," yet the loop adds every `tx.amount` unconditionally, never branching on
  `tx.type`. The defect is genuinely present and correctly diagnosed; the suggested
  direction (subtract when `type === 'debit'`) is sound.
- **R2 — Inclusive range uses strict comparisons.** Line 59 reads
  `return ledger.filter((tx) => tx.date > start && tx.date < end);`. The docstring
  (line 51) documents the range as `[start, end]`, inclusive, but the predicate uses
  strict `>` and `<`, excluding transactions on either boundary. Defect present and
  correctly diagnosed; the suggested fix (`>=` and `<=`) is correct.
- **R3 — Report export is shell-built.** Line 32 reads
  `execSync(\`echo "${report}" > ${filename}\`);`. Both `report` and `filename` are
  interpolated into a shell command passed to `execSync`, a genuine shell-injection
  surface. The claim is correctly scoped as a security-review note rather than part of
  the logic-bug fix, which matches the file contents.

## Discrepancies Found

None.

## Research Quality Assessment

**Level: Excellent.** Per the research-quality-measurement table, the **Excellent** rule
applies: all snippets verified, all line numbers exact, all diagnoses correct, and 0
discrepancies (0 minor, 0 major). Every cited `file:line` points precisely at the
described code, every quoted snippet matches the source character-for-character (ignoring
whitespace), and each described defect is genuinely present and accurately diagnosed.
No worse rule (Good, Adequate, Poor, Unreliable) is triggered. Per the downstream
decision rule, the plan may proceed as-is.

## References

Files inspected:

- `context/bugs/001/research/codebase-research.md` (research under verification)
- `src/ledger.js` (claims R1, R2)
- `src/exporter.js` (claim R3)
