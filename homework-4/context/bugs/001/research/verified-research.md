# Verified Research — Ledger #001

> Author: Bug Research Verifier. This document fact-checks the upstream
> `codebase-research.md` against the actual source files and assigns an objective
> research-quality rating per the **research-quality-measurement** skill.

## Verification Summary

- **Result:** ✅ **PASS**
- **Research Quality:** **Excellent**
- **Counts:**
  - `verified_refs` = 3 / 3 (every cited snippet found in the cited file)
  - `exact_line_refs` = 3 / 3 (every `file:line` exactly correct)
  - `minor_discrepancies` = 0
  - `major_discrepancies` = 0

## Verified Claims

| Claim | Cited reference | Actual location found | Verdict |
|-------|-----------------|-----------------------|---------|
| **R1** — Balance ignores debit sign | `src/ledger.js:35` — `balance += tx.amount;` | `src/ledger.js:35` — `balance += tx.amount;` (inside `getBalance` loop, lines 32–38) | ✅ |
| **R2** — Inclusive range uses strict comparisons | `src/ledger.js:59` — `return ledger.filter((tx) => tx.date > start && tx.date < end);` | `src/ledger.js:59` — identical (function `getTransactionsInRange`, lines 58–60) | ✅ |
| **R3** — Report export is shell-built | `src/exporter.js:32` — `execSync(\`echo "${report}" > ${filename}\`);` | `src/exporter.js:32` — identical (function `exportReport`, lines 30–34) | ✅ |

### Notes per claim

- **R1:** Line 35 is `balance += tx.amount;` exactly as quoted. The enclosing
  `getBalance` (lines 32–38) loops over every transaction and adds `tx.amount`
  unconditionally, never branching on `tx.type`. The function's own docstring
  (lines 27–28) states "Credits increase the balance, debits decrease it," so the
  defect is genuinely present and correctly diagnosed: debits are added rather than
  subtracted, inflating the balance. The researcher's suggested direction (branch on
  `tx.type`, subtract when `type === 'debit'`) is the correct fix.
- **R2:** Line 59 matches the quoted snippet character-for-character (modulo leading
  indentation). The docstring (lines 50–56) documents the range as `[start, end]`
  inclusive on both bounds, but the filter uses strict `>` and `<`, which drops
  transactions falling exactly on `start` or `end`. Defect present and correctly
  diagnosed; `>=` / `<=` is the right direction.
- **R3:** Line 32 matches the quoted snippet exactly. The destination `filename`
  (and `report`) are interpolated directly into a shell string passed to `execSync`,
  a classic command-injection sink. Correctly diagnosed and appropriately scoped to
  the security review rather than the logic-bug fix.

## Discrepancies Found

None.

## Research Quality Assessment

**Level: Excellent.** All three cited snippets were located in their cited files,
every `file:line` reference was exactly correct (no line-number drift), every quoted
snippet matched the source character-for-character ignoring leading/trailing
whitespace, and every diagnosis was confirmed against the surrounding code and the
functions' own docstrings. With **0 minor and 0 major discrepancies**, this satisfies
the table's top rule — *"All snippets verified, all line numbers exact, all diagnoses
correct, 0 discrepancies"* — and none of the capping rules (a single major caps at
Adequate; two or more cap at Poor) apply. Per the downstream decision rule, an
**Excellent** rating means the plan may proceed as-is.

## References

Files inspected during verification:

- `context/bugs/001/research/codebase-research.md` (the research document under review)
- `src/ledger.js` (claims R1, R2)
- `src/exporter.js` (claim R3)
