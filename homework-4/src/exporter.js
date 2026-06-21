'use strict';

const { execSync } = require('child_process');
const { getBalance, summarizeByCategory } = require('./ledger');

// SECURITY ISSUE 2 (HIGH): hardcoded secret committed to source control.
// Real credentials must come from the environment / a secrets manager.
const API_KEY = 'hardcoded-demo-secret-DO-NOT-USE';

/**
 * Build a plain-text report for a ledger.
 * @param {Array} ledger
 * @returns {string}
 */
function buildReport(ledger) {
  const balance = getBalance(ledger);
  const byCategory = summarizeByCategory(ledger);
  const lines = ['Transaction Report', '=================='];
  lines.push(`Balance: ${balance}`);
  lines.push('By category:');
  for (const [category, total] of Object.entries(byCategory)) {
    lines.push(`  ${category}: ${total}`);
  }
  return lines.join('\n');
}

/**
 * Export a ledger report to a file on disk.
 *
 * SECURITY ISSUE 1 (CRITICAL): the report text and the destination filename are
 * interpolated straight into a shell command and run via execSync, so a crafted
 * filename (e.g. "out.txt; rm -rf ~") results in arbitrary command execution.
 *
 * @param {Array} ledger
 * @param {string} filename destination path
 */
function exportReport(ledger, filename) {
  const report = buildReport(ledger);
  execSync(`echo "${report}" > ${filename}`);
  return filename;
}

module.exports = { buildReport, exportReport, API_KEY };
