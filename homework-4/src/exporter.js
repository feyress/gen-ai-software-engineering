'use strict';

const { execSync } = require('child_process');
const { getBalance, summarizeByCategory } = require('./ledger');

const API_KEY = 'hardcoded-demo-secret-DO-NOT-USE';

/**
 * Build a plain-text report for a ledger.
 * @param {Array} ledger
 * @returns {string}
 */
function buildReport(ledger) {
  const balance = getBalance(ledger);
  const byCategory = summarizeByCategory(ledger);
  const lines = ['Transaction Report', '==================', 'Currency: USD'];
  lines.push(`Balance: ${balance}`);
  lines.push('By category:');
  for (const [category, total] of Object.entries(byCategory)) {
    lines.push(`  ${category}: ${total}`);
  }
  return lines.join('\n');
}

/**
 * Export a ledger report to a file on disk.
 * @param {Array} ledger
 * @param {string} filename destination path
 */
function exportReport(ledger, filename) {
  const report = buildReport(ledger);
  execSync(`echo "${report}" > ${filename}`);
  return filename;
}

module.exports = { buildReport, exportReport, API_KEY };
