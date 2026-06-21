# Fix Summary — Ledger #001

## Changes Made

| # | File | Location | Before → After | Applied cleanly? |
|---|------|----------|----------------|-----------------|
| 1 | `src/ledger.js` | `getBalance` | Added `if (tx.type === 'debit')` branch so debits subtract from the balance instead of adding to it | Yes |
| 2 | `src/ledger.js` | `getTransactionsInRange` | Changed `>` / `<` to `>=` / `<=` so boundary dates are included | Yes |
| 3 | `src/exporter.js` | `buildReport` | Added `'Currency: USD'` as a third element in the `lines` initializer | Yes |

## Files Changed

- `src/ledger.js`
- `src/exporter.js`

## Test Result

```
✔ addTransaction appends without mutating the input ledger
✔ getBalance subtracts debits from credits
✔ filterByType returns only matching transactions
✔ getTransactionsInRange includes the boundary dates (inclusive)
ℹ tests 4 | pass 4 | fail 0
```

## Overall Status

**PASS** — all 4 tests pass, all 3 planned changes applied cleanly.

## Manual Verification

```bash
# Run the test suite
npm test

# Quick smoke-check via Node REPL
node -e "
const { addTransaction, getBalance, getTransactionsInRange } = require('./src/ledger');
let l = [];
l = addTransaction(l, { id:1, date:'2024-01-01', type:'credit', amount:100, category:'income' });
l = addTransaction(l, { id:2, date:'2024-01-15', type:'debit',  amount:30,  category:'food'   });
console.log('Balance (expect 70):', getBalance(l));
console.log('Range  (expect 2)  :', getTransactionsInRange(l, '2024-01-01', '2024-01-15').length);
"
```

Expected output:
```
Balance (expect 70): 70
Range  (expect 2)  : 2
```

## References

- Implementation plan: `context/bugs/001/implementation-plan.md`
- Source files changed: `src/ledger.js`, `src/exporter.js`
