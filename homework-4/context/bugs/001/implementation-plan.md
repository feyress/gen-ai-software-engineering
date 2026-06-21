# Implementation Plan — Ledger #001

> Author: Bug Planner (upstream agent). This is the **input** to the Bug Fixer.
> Apply each change exactly, then run the test command and record results.

**Test command:** `npm test`

---

## Change 1 — Fix balance sign (`src/ledger.js`, `getBalance`)

Subtract debit amounts instead of adding them.

**Before:**
```js
  let balance = 0;
  for (const tx of ledger) {
    // BUG 1: debits are added instead of subtracted, so any debit inflates the
    // balance instead of reducing it.
    balance += tx.amount;
  }
  return balance;
```

**After:**
```js
  let balance = 0;
  for (const tx of ledger) {
    if (tx.type === 'debit') {
      balance -= tx.amount;
    } else {
      balance += tx.amount;
    }
  }
  return balance;
```

---

## Change 2 — Make range inclusive (`src/ledger.js`, `getTransactionsInRange`)

Use `>=` / `<=` so boundary dates are included.

**Before:**
```js
  // BUG 2: strict comparisons exclude transactions that fall exactly on the
  // start or end boundary, even though the range is documented as inclusive.
  return ledger.filter((tx) => tx.date > start && tx.date < end);
```

**After:**
```js
  return ledger.filter((tx) => tx.date >= start && tx.date <= end);
```

---

## Change 3 — Add currency line to report (`src/exporter.js`, `buildReport`)

Minor, non-functional improvement so reports state their currency.

**Before:**
```js
  const lines = ['Transaction Report', '=================='];
```

**After:**
```js
  const lines = ['Transaction Report', '==================', 'Currency: USD'];
```

---

## Expected result

After all three changes, `npm test` should pass all tests (the two previously failing
balance/range tests now pass). No test should regress.
