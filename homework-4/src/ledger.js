'use strict';

/**
 * Tiny transaction ledger.
 *
 * A transaction is a plain object:
 *   { id, date: 'YYYY-MM-DD', type: 'credit' | 'debit', amount: number, category: string }
 *
 * NOTE: This module is the subject of the homework-4 agent pipeline. It ships
 * with intentionally seeded defects (see context/bugs/001/bug-context.md) that
 * the pipeline is expected to research, fix, security-review and test.
 */

/**
 * Append a transaction to a ledger array (returns a new array, does not mutate).
 * @param {Array} ledger
 * @param {{id:(string|number), date:string, type:string, amount:number, category:string}} tx
 * @returns {Array}
 */
function addTransaction(ledger, tx) {
  if (!tx || typeof tx.amount !== 'number' || Number.isNaN(tx.amount)) {
    throw new Error('Invalid transaction: amount must be a number');
  }
  if (tx.type !== 'credit' && tx.type !== 'debit') {
    throw new Error("Invalid transaction: type must be 'credit' or 'debit'");
  }
  return ledger.concat([tx]);
}

/**
 * Compute the net balance of a ledger.
 * Credits increase the balance, debits decrease it.
 * @param {Array} ledger
 * @returns {number}
 */
function getBalance(ledger) {
  let balance = 0;
  for (const tx of ledger) {
    // BUG 1: debits are added instead of subtracted, so any debit inflates the
    // balance instead of reducing it.
    balance += tx.amount;
  }
  return balance;
}

/**
 * Return all transactions of a given type.
 * @param {Array} ledger
 * @param {string} type 'credit' | 'debit'
 * @returns {Array}
 */
function filterByType(ledger, type) {
  return ledger.filter((tx) => tx.type === type);
}

/**
 * Return all transactions whose date falls within [start, end], inclusive.
 * Dates are ISO 'YYYY-MM-DD' strings, which compare lexicographically.
 * @param {Array} ledger
 * @param {string} start inclusive lower bound
 * @param {string} end   inclusive upper bound
 * @returns {Array}
 */
function getTransactionsInRange(ledger, start, end) {
  // BUG 2: strict comparisons exclude transactions that fall exactly on the
  // start or end boundary, even though the range is documented as inclusive.
  return ledger.filter((tx) => tx.date > start && tx.date < end);
}

/**
 * Sum amounts grouped by category.
 * @param {Array} ledger
 * @returns {Object<string, number>}
 */
function summarizeByCategory(ledger) {
  const summary = {};
  for (const tx of ledger) {
    const key = tx.category || 'uncategorized';
    summary[key] = (summary[key] || 0) + tx.amount;
  }
  return summary;
}

module.exports = {
  addTransaction,
  getBalance,
  filterByType,
  getTransactionsInRange,
  summarizeByCategory,
};
