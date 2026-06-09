# 🏦 Homework 1: Banking Transactions API

> **AI Tools Used**: Claude Code

---

## 📋 Project Overview

A minimal REST API for banking transactions, built with **Python + Flask** and
**in-memory storage** (no database). It supports creating and listing transactions,
fetching a transaction by id, querying account balances, and an account summary.

## ✨ Features Implemented

| Task | Feature | Status |
|------|---------|--------|
| 1 | Core CRUD endpoints (create, list, get-by-id, balance) | ✅ |
| 2 | Validation (positive amount ≤ 2 decimals, `ACC-XXXXX` accounts, ISO 4217 currency) | ✅ |
| 3 | History filtering by account / type / date range (combinable) | ✅ |
| 4 | **Option A** — account summary endpoint | ✅ |

## 🔌 Endpoints

| Method | Endpoint | Description | Codes |
|--------|----------|-------------|-------|
| `POST` | `/transactions` | Create a transaction | `201`, `400` |
| `GET` | `/transactions` | List all (supports `?accountId=&type=&from=&to=`) | `200`, `400` |
| `GET` | `/transactions/<id>` | Get one transaction by id | `200`, `404` |
| `GET` | `/accounts/<accountId>/balance` | Account balance | `200` |
| `GET` | `/accounts/<accountId>/summary` | Account summary (totals, count, last activity) | `200` |

## 🧾 Transaction Model

```json
{
  "id": "auto-generated uuid",
  "fromAccount": "ACC-12345",
  "toAccount": "ACC-67890",
  "amount": 100.50,
  "currency": "USD",
  "type": "deposit | withdrawal | transfer",
  "timestamp": "ISO 8601 (auto-generated, UTC)",
  "status": "pending | completed | failed (default: completed)"
}
```

## ✅ Validation Rules

- **amount** — required, numeric, `> 0`, at most 2 decimal places.
- **accounts** — `transfer` needs both accounts; `deposit` needs `toAccount`;
  `withdrawal` needs `fromAccount`. Any account given must match `ACC-XXXXX`
  (5 alphanumerics).
- **currency** — required, valid ISO 4217 code (USD, EUR, GBP, JPY, …).
- **type** — required, one of `deposit | withdrawal | transfer`.
- **status** — optional; if given, one of `pending | completed | failed`.

Invalid requests return `400` with a structured body:

```json
{
  "error": "Validation failed",
  "details": [
    {"field": "amount", "message": "Amount must be a positive number"},
    {"field": "currency", "message": "Invalid currency code (must be a valid ISO 4217 code)"}
  ]
}
```

## 🏗️ Architecture Decisions

- **No account entity.** Accounts exist only as IDs referenced on transactions.
  Balances and summaries are computed on the fly. Querying an account with no
  transactions returns a zero balance with `currency: null` (not a 404).
- **One currency per account.** An account is bound to the currency of its first
  transaction; later transactions in a different currency are rejected with `400`.
  This keeps a balance a single, meaningful number rather than a mix of currencies.
- **Only `completed` transactions affect balances/summary totals.** `pending` and
  `failed` are recorded and listed but don't move money.
- **No overdraft checks.** Withdrawals/transfers are accepted even if the balance
  goes negative (out of scope for this assignment).
- **Layered modules** — `routes` (HTTP) → `store` (state) → `validators`/`models`
  (pure functions). The app factory (`create_app`) gives each instance a fresh
  store, which also makes tests independent.

## 📁 Project Structure

```
homework-1/
├── README.md
├── HOWTORUN.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── app.py          # Flask app factory + JSON error handlers + entry point
│   ├── routes.py       # the 5 endpoints (thin)
│   ├── store.py        # in-memory store: filter / balance / summary
│   ├── models.py       # build a transaction from a validated payload
│   └── validators.py   # validation + filter parsing + constants
├── tests/
│   └── test_api.py     # 34 tests via Flask's test client
└── demo/
    ├── run.sh
    ├── sample-requests.http
    └── sample-data.json
```

## 🧪 Tests

```bash
.venv/bin/python -m pytest -q   # 34 passing
```

See [HOWTORUN.md](./HOWTORUN.md) for setup and run instructions.
