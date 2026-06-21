# Test Report — Ledger #001

## Scope

**File:** `tests/ledger.changes.test.js` (new file)

**Changed functions tested:**
1. `getBalance` (src/ledger.js:32–42) — balance calculation with debit subtraction logic
2. `getTransactionsInRange` (src/ledger.js:62–64) — inclusive boundary date filtering
3. `buildReport` (src/exporter.js:13–23) — report header with "Currency: USD"

## Tests Added

| Test Name | What It Asserts | FIRST Cases Covered |
|-----------|-----------------|---------------------|
| `getBalance: subtracts debits from credits (happy path)` | Credits add and debits subtract correctly (1000 - 200 + 500 = 1300) | **F, I, R, S, T** — mixed credits/debits verify the core fix |
| `getBalance: handles empty ledger (boundary case)` | Empty ledger returns balance of 0 | **F, I, R, S, T** — boundary: no transactions |
| `getBalance: debit-only ledger produces negative balance (edge case)` | All-debit ledger correctly produces negative balance (-150) | **F, I, R, S, T** — edge: only debits, negative result |
| `getTransactionsInRange: includes transactions on boundary dates (happy path)` | Start and end dates are inclusive; filters correctly to 3 of 4 transactions | **F, I, R, S, T** — core fix: `>=` / `<=` boundaries work |
| `getTransactionsInRange: returns empty array when no transactions in range (boundary case)` | Out-of-range query returns empty array (not null, not error) | **F, I, R, S, T** — boundary: no matches |
| `getTransactionsInRange: single-day range includes only that day (edge case)` | Same start/end date returns exactly 1 matching transaction | **F, I, R, S, T** — edge: tight range, single match |
| `buildReport: includes "Currency: USD" header (happy path)` | Report text contains "Currency: USD" | **F, I, R, S, T** — core fix: header is present |
| `buildReport: correct order of headers (boundary case)` | Headers appear in correct order: "Transaction Report", "==================", "Currency: USD" | **F, I, R, S, T** — verifies position as 3rd line |
| `buildReport: includes balance calculation (edge case)` | Report correctly shows "Balance: 800" based on ledger (1000 - 200 = 800) | **F, I, R, S, T** — validates integration: balance + report |

## FIRST Compliance

- **Fast:** All tests complete in <1 ms; no I/O, no network, no sleep; pure in-memory fixture evaluation.
- **Independent:** Each test constructs its own fresh fixture via factory function; no shared mutable state; tests run in any order.
- **Repeatable:** No reliance on `Date.now()`, `Math.random()`, locale, or timezone; all transaction dates are fixed strings; same result every run on any machine.
- **Self-validating:** Each test uses `assert.equal()` or `assert.deepEqual()` with concrete expected values (1300, 0, -150, 3, 1, presence/order checks); tests pass or fail with no human interpretation.
- **Timely:** Tests written alongside the fix; target only the three changed functions; cover happy path and 2 additional cases (boundary + edge) for each function.

## Test Run Result

```
✔ getBalance: subtracts debits from credits (happy path)
✔ getBalance: handles empty ledger (boundary case)
✔ getBalance: debit-only ledger produces negative balance (edge case)
✔ getTransactionsInRange: includes transactions on boundary dates (happy path)
✔ getTransactionsInRange: returns empty array when no transactions in range (boundary case)
✔ getTransactionsInRange: single-day range includes only that day (edge case)
✔ buildReport: includes "Currency: USD" header (happy path)
✔ buildReport: correct order of headers (boundary case)
✔ buildReport: includes balance calculation (edge case)
✔ addTransaction appends without mutating the input ledger (existing test)
✔ getBalance subtracts debits from credits (existing test)
✔ filterByType returns only matching transactions (existing test)
✔ getTransactionsInRange includes the boundary dates (inclusive) (existing test)

ℹ tests 13 | pass 13 | fail 0 | duration 90.1 ms
```

**Result:** ✅ **PASS** — All 9 new tests pass; all 4 existing tests pass; 100% success rate.

## References

- Fix summary: `context/bugs/001/fix-summary.md`
- Implementation plan: `context/bugs/001/implementation-plan.md`
- Source files: `src/ledger.js`, `src/exporter.js`
- Test file: `tests/ledger.changes.test.js`
- Unit test framework: Node.js built-in `node:test` with `node:assert/strict`
- FIRST principles reference: `skills/unit-tests-FIRST.md`
