'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const {
  addTransaction,
  getBalance,
  filterByType,
  getTransactionsInRange,
} = require('../src/ledger');

// A reusable, deterministic fixture (no shared mutable state between tests).
function fixture() {
  return [
    { id: 1, date: '2026-01-05', type: 'credit', amount: 1000, category: 'salary' },
    { id: 2, date: '2026-01-10', type: 'debit', amount: 200, category: 'rent' },
    { id: 3, date: '2026-01-15', type: 'debit', amount: 50, category: 'food' },
    { id: 4, date: '2026-01-20', type: 'credit', amount: 300, category: 'refund' },
  ];
}

test('addTransaction appends without mutating the input ledger', () => {
  const ledger = [];
  const next = addTransaction(ledger, fixture()[0]);
  assert.equal(ledger.length, 0);
  assert.equal(next.length, 1);
});

test('getBalance subtracts debits from credits', () => {
  // 1000 (credit) - 200 (debit) - 50 (debit) + 300 (credit) = 1050
  assert.equal(getBalance(fixture()), 1050);
});

test('filterByType returns only matching transactions', () => {
  assert.equal(filterByType(fixture(), 'debit').length, 2);
  assert.equal(filterByType(fixture(), 'credit').length, 2);
});

test('getTransactionsInRange includes the boundary dates (inclusive)', () => {
  const inRange = getTransactionsInRange(fixture(), '2026-01-05', '2026-01-15');
  // Inclusive range should contain the 05, 10 and 15 transactions => 3.
  assert.equal(inRange.length, 3);
});
