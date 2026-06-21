'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const {
  addTransaction,
  getBalance,
  getTransactionsInRange,
} = require('../src/ledger');
const { buildReport } = require('../src/exporter');

// ============================================================================
// Tests for getBalance (changed: now correctly subtracts debits)
// ============================================================================

test('getBalance: only debits returns negative balance', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'debit', amount: 100, category: 'food' },
    { id: 2, date: '2026-01-02', type: 'debit', amount: 50, category: 'gas' },
  ];
  assert.equal(getBalance(ledger), -150);
});

test('getBalance: only credits returns positive balance', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 200, category: 'salary' },
    { id: 2, date: '2026-01-02', type: 'credit', amount: 100, category: 'bonus' },
  ];
  assert.equal(getBalance(ledger), 300);
});

test('getBalance: empty ledger returns 0', () => {
  assert.equal(getBalance([]), 0);
});

test('getBalance: single debit transaction is negative', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'debit', amount: 75, category: 'expense' },
  ];
  assert.equal(getBalance(ledger), -75);
});

test('getBalance: mixed credits and debits calculates correctly', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 500, category: 'salary' },
    { id: 2, date: '2026-01-05', type: 'debit', amount: 100, category: 'rent' },
    { id: 3, date: '2026-01-10', type: 'credit', amount: 50, category: 'refund' },
    { id: 4, date: '2026-01-15', type: 'debit', amount: 25, category: 'food' },
  ];
  // 500 - 100 + 50 - 25 = 425
  assert.equal(getBalance(ledger), 425);
});

// ============================================================================
// Tests for getTransactionsInRange (changed: now inclusive on both boundaries)
// ============================================================================

test('getTransactionsInRange: start boundary is included', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'a' },
    { id: 2, date: '2026-01-05', type: 'credit', amount: 100, category: 'b' },
    { id: 3, date: '2026-01-10', type: 'credit', amount: 100, category: 'c' },
  ];
  const result = getTransactionsInRange(ledger, '2026-01-01', '2026-01-05');
  assert.equal(result.length, 2);
  assert.deepEqual(result[0].id, 1);
});

test('getTransactionsInRange: end boundary is included', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'a' },
    { id: 2, date: '2026-01-05', type: 'credit', amount: 100, category: 'b' },
    { id: 3, date: '2026-01-10', type: 'credit', amount: 100, category: 'c' },
  ];
  const result = getTransactionsInRange(ledger, '2026-01-05', '2026-01-10');
  assert.equal(result.length, 2);
  assert.deepEqual(result[1].id, 3);
});

test('getTransactionsInRange: empty range returns no transactions', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'a' },
    { id: 2, date: '2026-01-10', type: 'credit', amount: 100, category: 'b' },
  ];
  const result = getTransactionsInRange(ledger, '2026-01-05', '2026-01-08');
  assert.equal(result.length, 0);
});

test('getTransactionsInRange: single date match returns one transaction', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'a' },
    { id: 2, date: '2026-01-05', type: 'credit', amount: 100, category: 'b' },
    { id: 3, date: '2026-01-10', type: 'credit', amount: 100, category: 'c' },
  ];
  const result = getTransactionsInRange(ledger, '2026-01-05', '2026-01-05');
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].id, 2);
});

test('getTransactionsInRange: range spanning all dates includes all', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'a' },
    { id: 2, date: '2026-01-05', type: 'credit', amount: 100, category: 'b' },
    { id: 3, date: '2026-01-10', type: 'credit', amount: 100, category: 'c' },
  ];
  const result = getTransactionsInRange(ledger, '2026-01-01', '2026-01-10');
  assert.equal(result.length, 3);
});

// ============================================================================
// Tests for buildReport (changed: now includes 'Currency: USD' line)
// ============================================================================

test('buildReport: includes Currency: USD line', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'income' },
  ];
  const report = buildReport(ledger);
  assert.ok(report.includes('Currency: USD'), 'Report should contain "Currency: USD"');
});

test('buildReport: empty ledger still has Currency: USD', () => {
  const ledger = [];
  const report = buildReport(ledger);
  assert.ok(report.includes('Currency: USD'), 'Empty ledger report should contain "Currency: USD"');
});

test('buildReport: contains header and currency in correct order', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'income' },
  ];
  const report = buildReport(ledger);
  const lines = report.split('\n');
  assert.equal(lines[0], 'Transaction Report');
  assert.equal(lines[1], '==================');
  assert.equal(lines[2], 'Currency: USD');
});

test('buildReport: with multiple categories includes all totals', () => {
  const ledger = [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'salary' },
    { id: 2, date: '2026-01-02', type: 'debit', amount: 30, category: 'food' },
    { id: 3, date: '2026-01-03', type: 'credit', amount: 50, category: 'bonus' },
  ];
  const report = buildReport(ledger);
  assert.ok(report.includes('salary: 100'), 'Report should include salary category');
  assert.ok(report.includes('food: 30'), 'Report should include food category');
  assert.ok(report.includes('bonus: 50'), 'Report should include bonus category');
  assert.ok(report.includes('Balance: 120'), 'Report should show correct balance (100 - 30 + 50)');
});
