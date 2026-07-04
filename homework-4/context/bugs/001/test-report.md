# Test Report — Ledger #001 Changes

## Scope

**File:** `src/ledger.js` and `src/exporter.js`

**Functions tested:**
- `getBalance` (src/ledger.js, lines 32–42): Now correctly subtracts debits from the balance.
- `getTransactionsInRange` (src/ledger.js, lines 62–64): Now uses inclusive boundaries (`>=` and `<=`).
- `buildReport` (src/exporter.js, lines 13–23): Now includes 'Currency: USD' line in report.

## Tests Added

All tests in `tests/ledger.changes.test.js` (14 new tests):

### getBalance Tests (5 tests)

1. **getBalance: only debits returns negative balance**
   - Asserts that a ledger with only debit transactions produces a negative balance.
   - Covers: F (fast in-memory test), I (fresh fixture), R (deterministic), S (exact assertion of -150), T (tests changed debit behavior).

2. **getBalance: only credits returns positive balance**
   - Asserts that a ledger with only credit transactions produces a positive balance.
   - Covers: F, I, R, S (exact assertion of 300), T (tests changed credit behavior).

3. **getBalance: empty ledger returns 0**
   - Asserts that an empty ledger produces a balance of 0.
   - Covers: F, I, R, S (exact assertion of 0), T (boundary case: no transactions).

4. **getBalance: single debit transaction is negative**
   - Asserts that a single debit transaction results in a negative balance equal to the negative of the amount.
   - Covers: F, I, R, S (exact assertion of -75), T (boundary case: single debit).

5. **getBalance: mixed credits and debits calculates correctly**
   - Asserts that mixed transactions calculate the correct net balance (500 - 100 + 50 - 25 = 425).
   - Covers: F, I, R, S (exact assertion of 425), T (happy path with multiple transactions).

### getTransactionsInRange Tests (6 tests)

6. **getTransactionsInRange: start boundary is included**
   - Asserts that the start date is included in the range (inclusive lower bound).
   - Covers: F, I, R, S (checks length and id), T (boundary case: start date included).

7. **getTransactionsInRange: end boundary is included**
   - Asserts that the end date is included in the range (inclusive upper bound).
   - Covers: F, I, R, S (checks length and id), T (boundary case: end date included).

8. **getTransactionsInRange: empty range returns no transactions**
   - Asserts that when no transactions fall within the date range, an empty array is returned.
   - Covers: F, I, R, S (exact assertion of length 0), T (boundary case: no matches).

9. **getTransactionsInRange: single date match returns one transaction**
   - Asserts that when start and end are the same date, only transactions on that date are returned.
   - Covers: F, I, R, S (exact assertion of length 1), T (boundary case: single-day range).

10. **getTransactionsInRange: range spanning all dates includes all**
    - Asserts that a range encompassing all transaction dates returns all transactions.
    - Covers: F, I, R, S (exact assertion of length 3), T (boundary case: full span).

### buildReport Tests (3 tests)

11. **buildReport: includes Currency: USD line**
    - Asserts that the report output contains the string 'Currency: USD'.
    - Covers: F, I, R, S (string containment check), T (tests new currency line).

12. **buildReport: empty ledger still has Currency: USD**
    - Asserts that even an empty ledger report includes the 'Currency: USD' line.
    - Covers: F, I, R, S (string containment check), T (boundary case: empty ledger).

13. **buildReport: contains header and currency in correct order**
    - Asserts that the first three lines are 'Transaction Report', '==================', and 'Currency: USD' in order.
    - Covers: F, I, R, S (exact assertions of each line), T (tests report structure).

14. **buildReport: with multiple categories includes all totals**
    - Asserts that the report includes all category totals and the correct balance.
    - Covers: F, I, R, S (multiple string containment checks and balance calculation), T (happy path with mixed categories).

## FIRST Compliance

- **Fast:** All tests run in-memory with no I/O, network calls, or sleep/timers. Execution averages < 0.1ms per test.
- **Independent:** Each test builds its own fresh fixture array; no mutable state shared between tests or reliance on test execution order.
- **Repeatable:** Tests use fixed, deterministic data with no randomness, wall-clock time, or environment variables. Same result every run.
- **Self-validating:** Each test includes explicit `assert.equal` or `assert.deepEqual` or `assert.ok` checks that pass or fail without manual interpretation.
- **Timely:** Tests target only the three changed functions (`getBalance`, `getTransactionsInRange`, `buildReport`) with both happy-path and boundary/edge cases.

## Test Run Result

```
✔ tests/ledger.changes.test.js: 14 new tests
✔ tests/ledger.test.js: 4 existing tests
───────────────────────────────────────────
✔ Total: 18 tests
✔ Passed: 18
✔ Failed: 0
✔ Duration: 85.582ms
```

All tests pass. No failures.

## References

- Implementation plan: `context/bugs/001/implementation-plan.md`
- Fix summary: `context/bugs/001/fix-summary.md`
- Test source: `tests/ledger.changes.test.js`
- Original tests: `tests/ledger.test.js`
- Source files: `src/ledger.js`, `src/exporter.js`
