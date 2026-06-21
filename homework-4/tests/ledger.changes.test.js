const { test } = require('node:test');
const assert = require('node:assert/strict');
const { getBalance, getTransactionsInRange } = require('../src/ledger');
const { buildReport } = require('../src/exporter');

// Helper: fixture factory for getBalance tests
function balanceFixture() {
  return [
    { id: 1, date: '2026-01-05', type: 'credit', amount: 1000, category: 'salary' },
    { id: 2, date: '2026-01-10', type: 'debit', amount: 200, category: 'food' },
    { id: 3, date: '2026-01-15', type: 'credit', amount: 500, category: 'bonus' },
  ];
}

// Helper: fixture factory for getTransactionsInRange tests
function rangeFixture() {
  return [
    { id: 1, date: '2026-01-01', type: 'credit', amount: 100, category: 'income' },
    { id: 2, date: '2026-01-05', type: 'debit', amount: 30, category: 'food' },
    { id: 3, date: '2026-01-15', type: 'credit', amount: 50, category: 'income' },
    { id: 4, date: '2026-02-01', type: 'debit', amount: 20, category: 'food' },
  ];
}

// Helper: fixture factory for buildReport tests
function reportFixture() {
  return [
    { id: 1, date: '2026-01-05', type: 'credit', amount: 1000, category: 'salary' },
    { id: 2, date: '2026-01-10', type: 'debit', amount: 200, category: 'food' },
  ];
}

// ============================================================================
// getBalance tests
// ============================================================================

test('getBalance: subtracts debits from credits (happy path)', () => {
  const ledger = balanceFixture();
  // 1000 (credit) - 200 (debit) + 500 (credit) = 1300
  assert.equal(getBalance(ledger), 1300);
});

test('getBalance: handles empty ledger (boundary case)', () => {
  assert.equal(getBalance([]), 0);
});

test('getBalance: debit-only ledger produces negative balance (edge case)', () => {
  const ledger = [
    { id: 1, date: '2026-01-05', type: 'debit', amount: 100, category: 'food' },
    { id: 2, date: '2026-01-10', type: 'debit', amount: 50, category: 'rent' },
  ];
  assert.equal(getBalance(ledger), -150);
});

// ============================================================================
// getTransactionsInRange tests
// ============================================================================

test('getTransactionsInRange: includes transactions on boundary dates (happy path)', () => {
  const ledger = rangeFixture();
  const result = getTransactionsInRange(ledger, '2026-01-01', '2026-01-15');
  // Should include 4 tx: id 1 (2026-01-01), id 2 (2026-01-05), id 3 (2026-01-15), but not id 4 (2026-02-01)
  assert.equal(result.length, 3);
  assert.deepEqual(
    result.map((tx) => tx.id),
    [1, 2, 3]
  );
});

test('getTransactionsInRange: returns empty array when no transactions in range (boundary case)', () => {
  const ledger = rangeFixture();
  const result = getTransactionsInRange(ledger, '2026-06-01', '2026-06-30');
  assert.equal(result.length, 0);
});

test('getTransactionsInRange: single-day range includes only that day (edge case)', () => {
  const ledger = rangeFixture();
  const result = getTransactionsInRange(ledger, '2026-01-05', '2026-01-05');
  assert.equal(result.length, 1);
  assert.equal(result[0].id, 2);
});

// ============================================================================
// buildReport tests
// ============================================================================

test('buildReport: includes "Currency: USD" header (happy path)', () => {
  const ledger = reportFixture();
  const report = buildReport(ledger);
  assert(report.includes('Currency: USD'), 'Report should include Currency: USD');
});

test('buildReport: correct order of headers (boundary case)', () => {
  const ledger = reportFixture();
  const report = buildReport(ledger);
  const lines = report.split('\n');
  assert.equal(lines[0], 'Transaction Report');
  assert.equal(lines[1], '==================');
  assert.equal(lines[2], 'Currency: USD');
});

test('buildReport: includes balance calculation (edge case)', () => {
  const ledger = reportFixture();
  // 1000 (credit) - 200 (debit) = 800
  const report = buildReport(ledger);
  assert(report.includes('Balance: 800'), 'Report should show correct balance of 800');
});
