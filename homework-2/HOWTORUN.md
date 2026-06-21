# ▶️ How to Run the Application

## Requirements

- Python 3.10+ (developed on 3.14)
- `pip` / `venv`

## Quick start

```bash
cd homework-2
bash demo/run.sh
```

This creates a venv, installs dependencies, and starts the server on **http://localhost:3000**.

## Manual setup (if you prefer)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.app
```

## Try the API

With the server running, test a few endpoints:

```bash
# Create a ticket
curl -X POST http://localhost:3000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-001",
    "customer_email": "alice@example.com",
    "customer_name": "Alice Smith",
    "subject": "Cannot log in to my account",
    "description": "I forgot my password and the 2FA reset email never arrives."
  }'

# List all tickets
curl http://localhost:3000/tickets

# Filter by category and priority
curl "http://localhost:3000/tickets?category=account_access&priority=urgent"

# Get one ticket (replace ID)
curl http://localhost:3000/tickets/<ID>

# Update a ticket
curl -X PUT http://localhost:3000/tickets/<ID> \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "assigned_to": "agent-1"}'

# Auto-classify a ticket
curl -X POST http://localhost:3000/tickets/<ID>/auto-classify

# Delete a ticket
curl -X DELETE http://localhost:3000/tickets/<ID>
```

## Bulk import

```bash
# CSV (50 sample tickets)
curl -F file=@demo/sample_tickets.csv http://localhost:3000/tickets/import

# JSON (20 tickets, with auto-classification)
curl -X POST "http://localhost:3000/tickets/import?format=json&auto_classify=true" \
  -H "Content-Type: application/json" --data-binary @demo/sample_tickets.json

# XML (30 tickets)
curl -F file=@demo/sample_tickets.xml http://localhost:3000/tickets/import

# Negative test (mixed valid/invalid rows)
curl -F file=@demo/invalid_tickets.csv http://localhost:3000/tickets/import
```

More examples in [`demo/sample-requests.http`](./demo/sample-requests.http)
(open in VS Code with the REST Client extension).

## Run the tests

```bash
python -m pytest -q --cov=src --cov-report=term-missing
```

Expected: **56 passed**, coverage **~93%**.

See **[TESTING_GUIDE.md](./TESTING_GUIDE.md)** for details.

## Regenerate sample data (optional)

```bash
python demo/generate_samples.py
```

This overwrites `demo/sample_tickets.{csv,json,xml}` with fresh random data
(deterministically seeded for consistency).
