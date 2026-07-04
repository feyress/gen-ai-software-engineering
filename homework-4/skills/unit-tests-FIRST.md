---
name: unit-tests-FIRST
description: Use when generating unit tests so every test satisfies the FIRST principles (Fast, Independent, Repeatable, Self-validating, Timely).
---

# Unit Tests — FIRST

This skill defines the **FIRST** principles the **Unit Test Generator** must follow for
every test it writes. The project uses Node's built-in `node:test` runner with
`node:assert/strict`. Run tests with `npm test`.

## The five principles

- **F — Fast.** Tests run in milliseconds. No network, no disk, no `sleep`, no real
  child processes. Exercise pure functions directly with in-memory fixtures.
- **I — Independent.** No test depends on another's order or leftover state. Build a
  *fresh* fixture inside each test (a factory function), never a shared mutable array.
- **R — Repeatable.** Same result every run, on any machine. No reliance on `Date.now()`,
  randomness, locale, timezone, or environment. If time is needed, inject a fixed value.
- **S — Self-validating.** Each test asserts a concrete expected value and passes or fails
  with no human interpretation. Never just `console.log`; always `assert`.
- **T — Timely.** Tests are written alongside the code change they cover, targeting the
  **changed** behavior (and its edge cases), not unrelated code.

## Checklist (every generated test must pass all of these)

- [ ] Uses `node:test` (`test(...)`) and `node:assert/strict`.
- [ ] Builds its own fixture; shares no mutable state with other tests.
- [ ] No I/O, timers, randomness, or wall-clock dependence.
- [ ] Asserts an exact expected value (equality / deep-equality / throws).
- [ ] Has a descriptive name stating the behavior under test.
- [ ] Covers the happy path **and** at least one boundary/edge case for the changed code.

## Example (good)

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { getBalance } = require('../src/ledger');

function fixture() {
  return [
    { id: 1, date: '2026-01-05', type: 'credit', amount: 1000, category: 'salary' },
    { id: 2, date: '2026-01-10', type: 'debit', amount: 200, category: 'rent' },
  ];
}

test('getBalance subtracts debits from credits', () => {
  assert.equal(getBalance(fixture()), 800); // 1000 - 200
});

test('getBalance of an empty ledger is 0', () => {
  assert.equal(getBalance([]), 0); // boundary case
});
```

## Anti-patterns to avoid

- A module-level `const ledger = [...]` mutated across tests (breaks **I**).
- Asserting against `new Date()` / `Math.random()` output (breaks **R**).
- `console.log` "checks" with no assertion (breaks **S**).
- Spawning real shells or writing real files (breaks **F**); stub or assert on
  arguments instead.
