# ▶️ How to Run the Application

## Requirements

- Python 3.10+ (developed on 3.14)
- `pip` / `venv`

## 1. Set up a virtual environment & install dependencies

```bash
cd homework-1
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run the API

```bash
python -m src.app
```

The server starts on **http://localhost:3000**.

> Shortcut: `bash demo/run.sh` does all of the above (venv + install + start).

## 3. Try it out

With the server running, send a request:

```bash
curl -X POST http://localhost:3000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "fromAccount": "ACC-12345",
    "toAccount": "ACC-67890",
    "amount": 100.50,
    "currency": "USD",
    "type": "transfer"
  }'

curl http://localhost:3000/transactions
curl http://localhost:3000/accounts/ACC-12345/balance
curl http://localhost:3000/accounts/ACC-12345/summary
```

More examples live in [`demo/sample-requests.http`](./demo/sample-requests.http)
(open in VS Code with the REST Client extension) and
[`demo/sample-data.json`](./demo/sample-data.json).

## 4. Run the tests

```bash
python -m pytest -q
```

Expected: `34 passed`.
