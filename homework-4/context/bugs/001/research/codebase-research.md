# Codebase Research — Ledger #001

> Author: Bug Researcher (upstream agent). This document records the researcher's
> findings about the seeded defects, with `file:line` references and code snippets.
> It is the **input** to the Bug Research Verifier.

## Claim R1 — Balance ignores debit sign

- **File:line:** `src/ledger.js:35`
- **Function:** `getBalance`
- **Observed code:**
  ```js
  balance += tx.amount;
  ```
- **Finding:** Inside the `getBalance` loop every transaction amount is added,
  regardless of `tx.type`. Debits must be subtracted. This is the cause of the
  inflated balance (`1550` instead of `1050`) seen in `npm start`.
- **Suggested direction:** branch on `tx.type` and subtract when `type === 'debit'`.

## Claim R2 — Inclusive range uses strict comparisons

- **File:line:** `src/ledger.js:59`
- **Function:** `getTransactionsInRange`
- **Observed code:**
  ```js
  return ledger.filter((tx) => tx.date > start && tx.date < end);
  ```
- **Finding:** The function is documented as an inclusive range `[start, end]` but
  uses `>` and `<`, dropping transactions exactly on the boundaries. For
  `('2026-01-05', '2026-01-15')` it returns 1 transaction instead of 3.
- **Suggested direction:** use `>=` and `<=`.

## Claim R3 — Report export is shell-built (noted, out of fix scope)

- **File:line:** `src/exporter.js:32`
- **Function:** `exportReport`
- **Observed code:**
  ```js
  execSync(`echo "${report}" > ${filename}`);
  ```
- **Finding:** The destination filename is interpolated into a shell command. Flagged
  for the security review; not part of the logic-bug fix scope.

## Test command

`npm test`
