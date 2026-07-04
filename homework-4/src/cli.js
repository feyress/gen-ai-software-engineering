'use strict';

const {
  addTransaction,
  getBalance,
  filterByType,
  getTransactionsInRange,
  summarizeByCategory,
} = require('./ledger');
const { buildReport } = require('./exporter');

// A small fixed sample ledger so `npm start` shows the module working end-to-end.
const SAMPLE = [
  { id: 1, date: '2026-01-05', type: 'credit', amount: 1000, category: 'salary' },
  { id: 2, date: '2026-01-10', type: 'debit', amount: 200, category: 'rent' },
  { id: 3, date: '2026-01-15', type: 'debit', amount: 50, category: 'food' },
  { id: 4, date: '2026-01-20', type: 'credit', amount: 300, category: 'refund' },
];

function main() {
  let ledger = [];
  for (const tx of SAMPLE) {
    ledger = addTransaction(ledger, tx);
  }

  console.log(buildReport(ledger));
  console.log('');
  console.log(`Net balance: ${getBalance(ledger)}`);
  console.log(`Debits: ${filterByType(ledger, 'debit').length}`);
  console.log(
    `In range 2026-01-05..2026-01-15: ${
      getTransactionsInRange(ledger, '2026-01-05', '2026-01-15').length
    }`
  );
  console.log('By category:', summarizeByCategory(ledger));
}

if (require.main === module) {
  main();
}

module.exports = { main, SAMPLE };
