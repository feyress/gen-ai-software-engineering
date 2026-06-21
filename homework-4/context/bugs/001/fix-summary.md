# Fix Summary — Ledger #001

## Changes Made

### Change 1 — `src/ledger.js`, `getBalance`
Before: unconditionally added every `tx.amount` to the balance (debits increased balance instead of decreasing it).  
After: subtracts `tx.amount` when `tx.type === 'debit'`, adds otherwise.  
Applied cleanly: yes.

### Change 2 — `src/ledger.js`, `getTransactionsInRange`
Before: `tx.date > start && tx.date < end` (exclusive on both boundaries).  
After: `tx.date >= start && tx.date <= end` (inclusive on both boundaries).  
Applied cleanly: yes.

### Change 3 — `src/exporter.js`, `buildReport`
Before: `const lines = ['Transaction Report', '=================='];`  
After: `const lines = ['Transaction Report', '==================', 'Currency: USD'];`  
Applied cleanly: yes.

---

## Files Changed

- `src/ledger.js`
- `src/exporter.js`

---

## Test Result

```
✔ addTransaction appends without mutating the input ledger (0.498417ms)
✔ getBalance subtracts debits from credits (0.050834ms)
✔ filterByType returns only matching transactions (0.042667ms)
✔ getTransactionsInRange includes the boundary dates (inclusive) (0.042834ms)
ℹ tests 4
ℹ pass 4
ℹ fail 0
```

4 passed, 0 failed.

---

## Overall Status

**PASS** — all planned changes applied cleanly and all 4 tests pass.

---

## Manual Verification

```bash
# From the homework-4 directory:
node -e "
const { addTransaction, getBalance } = require('./src/ledger');
let l = [];
l = addTransaction(l, { id:1, date:'2024-01-01', type:'credit', amount:100, category:'income' });
l = addTransaction(l, { id:2, date:'2024-01-02', type:'debit',  amount:30,  category:'food'   });
console.log('Balance (expect 70):', getBalance(l));
"

node -e "
const { addTransaction, getTransactionsInRange } = require('./src/ledger');
let l = [];
l = addTransaction(l, { id:1, date:'2024-01-01', type:'credit', amount:10, category:'a' });
l = addTransaction(l, { id:2, date:'2024-01-05', type:'credit', amount:20, category:'b' });
l = addTransaction(l, { id:3, date:'2024-01-10', type:'credit', amount:30, category:'c' });
console.log('Range [2024-01-01..2024-01-05] (expect 2 txns):', getTransactionsInRange(l, '2024-01-01', '2024-01-05').length);
"

node -e "
const { addTransaction } = require('./src/ledger');
const { buildReport } = require('./src/exporter');
let l = addTransaction([], { id:1, date:'2024-01-01', type:'credit', amount:50, category:'misc' });
console.log(buildReport(l));
// Expect 'Currency: USD' to appear in output
"
```

---

## References

- Plan: `context/bugs/001/implementation-plan.md`
- Source files modified: `src/ledger.js`, `src/exporter.js`
- Test suite: `tests/*.test.js`
