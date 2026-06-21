# 📖 API Reference

Base URL: `http://localhost:3000`

All request/response bodies are JSON. File uploads use multipart form data.
The `204 Delete` response has no body.

---

## Ticket Model

```jsonc
{
  "id": "550e8400-e29b-41d4-a716-446655440000",  // UUID, server-generated
  "customer_id": "CUST-001",                       // required
  "customer_email": "alice@example.com",           // required, must be valid email
  "customer_name": "Alice Smith",                  // required
  "subject": "Cannot log in",                      // required, 1–200 chars
  "description": "Password reset is broken.",      // required, 10–2000 chars
  "category": "account_access",                    // see enum below
  "priority": "urgent",                            // see enum below
  "status": "new",                                 // see enum below
  "created_at": "2026-06-21T12:00:00+00:00",
  "updated_at": "2026-06-21T12:00:00+00:00",
  "resolved_at": null,                             // set when status → resolved
  "assigned_to": "agent-1",                        // nullable
  "tags": ["login", "urgent"],
  "metadata": {
    "source": "web_form",                          // see enum below
    "browser": null,                               // free-form string, nullable
    "device_type": "desktop"                       // see enum below
  },
  "classification": {                              // null until auto-classified
    "category": "account_access",
    "priority": "urgent",
    "confidence": 0.85,
    "reasoning": "matched 3 'account_access' keyword(s)...",
    "keywords": ["2fa", "cannot access", "critical", "password"]
  }
}
```

### Enumerations

| Field | Allowed values |
|-------|---------------|
| `category` | `account_access` `technical_issue` `billing_question` `feature_request` `bug_report` `other` |
| `priority` | `urgent` `high` `medium` `low` |
| `status` | `new` `in_progress` `waiting_customer` `resolved` `closed` |
| `metadata.source` | `web_form` `email` `api` `chat` `phone` |
| `metadata.device_type` | `desktop` `mobile` `tablet` |

**Server-applied defaults on creation:** `category=other`, `priority=medium`, `status=new`, `tags=[]`, `metadata.source=api`.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tickets` | Create a ticket |
| `POST` | `/tickets/import` | Bulk import (CSV / JSON / XML) |
| `GET` | `/tickets` | List all tickets with optional filters |
| `GET` | `/tickets/:id` | Get one ticket |
| `PUT` | `/tickets/:id` | Partial update |
| `DELETE` | `/tickets/:id` | Delete a ticket |
| `POST` | `/tickets/:id/auto-classify` | Auto-classify and persist result |

---

### POST /tickets

Creates a single support ticket. Pass `?auto_classify=true` to run the
classifier immediately on creation.

**Request body** (required fields marked `*`):

```json
{
  "customer_id": "CUST-001",
  "customer_email": "alice@example.com",
  "customer_name": "Alice Smith",
  "subject": "Cannot log in to my account",
  "description": "I forgot my password and the 2FA reset email never arrives.",
  "category": "account_access",
  "priority": "high",
  "tags": ["login"],
  "metadata": { "source": "web_form", "device_type": "desktop" }
}
```

**cURL examples:**

```bash
# Basic create
curl -X POST http://localhost:3000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-001",
    "customer_email": "alice@example.com",
    "customer_name": "Alice Smith",
    "subject": "Cannot log in to my account",
    "description": "Forgot my password and 2FA reset email never arrives."
  }'

# Create and auto-classify in one step
curl -X POST "http://localhost:3000/tickets?auto_classify=true" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-002",
    "customer_email": "ivan@example.com",
    "customer_name": "Ivan Petrov",
    "subject": "Production down - critical outage",
    "description": "The whole production system is down. This is a critical outage."
  }'
```

**Responses:**

| Status | Body |
|--------|------|
| `201 Created` | Full ticket object |
| `400 Bad Request` | `{ "error": "Validation failed", "details": [{...}] }` |

---

### POST /tickets/import

Imports tickets in bulk from a CSV, JSON, or XML source. The format is
inferred from the file extension or specified via `?format=csv|json|xml`.
Each record is validated individually; failures are collected and returned
alongside successes.

Query parameters:
- `format=csv|json|xml` — required when sending a raw body without a file upload
- `auto_classify=true` — run the classifier on each successfully imported ticket

**Option A — multipart file upload:**

```bash
# Import 50 tickets from CSV
curl -F file=@demo/sample_tickets.csv http://localhost:3000/tickets/import

# Import XML with auto-classification
curl -F file=@demo/sample_tickets.xml \
  "http://localhost:3000/tickets/import?auto_classify=true"
```

**Option B — raw body with explicit format:**

```bash
curl -X POST "http://localhost:3000/tickets/import?format=json" \
  -H "Content-Type: application/json" \
  --data-binary @demo/sample_tickets.json
```

**CSV format** — columns:

```
customer_id, customer_email, customer_name, subject, description,
tags, metadata_source, metadata_device_type
```

Multiple tags are separated by `|` (e.g. `login|urgent`).

**JSON format** — array of ticket objects or `{ "tickets": [...] }`.

**XML format** — root element containing `<ticket>` children:

```xml
<tickets>
  <ticket>
    <customer_id>CUST-400</customer_id>
    <customer_email>judy@example.com</customer_email>
    <customer_name>Judy Walsh</customer_name>
    <subject>Refund not processed</subject>
    <description>My refund has not appeared yet.</description>
    <tags><tag>billing</tag><tag>refund</tag></tags>
    <metadata>
      <source>email</source>
      <device_type>desktop</device_type>
    </metadata>
  </ticket>
</tickets>
```

**Response** (`201` if at least one succeeded, `400` if none):

```json
{
  "format": "csv",
  "total": 50,
  "successful": 48,
  "failed": 2,
  "errors": [
    {
      "index": 7,
      "messages": [
        { "field": "customer_email", "message": "customer_email must be a valid email address" }
      ]
    }
  ],
  "created_ids": ["uuid-1", "uuid-2", "..."]
}
```

A whole-file parse failure returns `400` with `{ "error": "Invalid JSON: ... (line 3)" }`.

---

### GET /tickets

Returns all tickets. Optionally filter by one or more fields (AND-ed together).

**Query parameters:** `category`, `priority`, `status`, `assigned_to`

```bash
# All tickets
curl http://localhost:3000/tickets

# Filter by category and priority
curl "http://localhost:3000/tickets?category=billing_question&priority=high"

# Filter by assignee
curl "http://localhost:3000/tickets?assigned_to=agent-1&status=in_progress"
```

**Response:** `200 OK` → JSON array of ticket objects (empty array if none match).

---

### GET /tickets/:id

```bash
curl http://localhost:3000/tickets/550e8400-e29b-41d4-a716-446655440000
```

| Status | Body |
|--------|------|
| `200 OK` | Ticket object |
| `404 Not Found` | `{ "error": "Ticket not found" }` |

---

### PUT /tickets/:id

Partial update — include only the fields you want to change. Setting
`status` to `resolved` automatically stamps `resolved_at`.

```bash
# Assign and move to in_progress
curl -X PUT http://localhost:3000/tickets/<ID> \
  -H "Content-Type: application/json" \
  -d '{ "status": "in_progress", "assigned_to": "agent-1" }'

# Manual category/priority override
curl -X PUT http://localhost:3000/tickets/<ID> \
  -H "Content-Type: application/json" \
  -d '{ "category": "billing_question", "priority": "high" }'

# Resolve
curl -X PUT http://localhost:3000/tickets/<ID> \
  -H "Content-Type: application/json" \
  -d '{ "status": "resolved" }'
```

| Status | Body |
|--------|------|
| `200 OK` | Updated ticket object |
| `400 Bad Request` | Validation error with `details` |
| `404 Not Found` | `{ "error": "Ticket not found" }` |

---

### DELETE /tickets/:id

```bash
curl -X DELETE http://localhost:3000/tickets/<ID>
```

| Status | Body |
|--------|------|
| `204 No Content` | (empty) |
| `404 Not Found` | `{ "error": "Ticket not found" }` |

---

### POST /tickets/:id/auto-classify

Runs the rule-based classifier on the ticket's `subject` and `description`,
stores the result (updating `category`, `priority`, and `classification`),
and logs the decision.

```bash
curl -X POST http://localhost:3000/tickets/<ID>/auto-classify
```

**`200 OK` response:**

```json
{
  "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
  "category": "account_access",
  "priority": "urgent",
  "confidence": 0.85,
  "reasoning": "matched 3 'account_access' keyword(s): password, 2fa, cannot access; priority 'urgent' from keyword(s): cannot access, critical.",
  "keywords": ["2fa", "cannot access", "critical", "password"]
}
```

`confidence` is a score in `[0, 1]`. A value below `0.5` typically indicates
weak signal — the ticket may belong to `other` or warrant manual review.

| Status | Body |
|--------|------|
| `200 OK` | Classification result (also persisted on the ticket) |
| `404 Not Found` | `{ "error": "Ticket not found" }` |

---

## Error reference

| Status | When |
|--------|------|
| `400` | Missing/invalid JSON body, field validation failure, malformed import file, empty import body |
| `404` | Ticket not found, or unknown route |
| `405` | Wrong HTTP method for a valid route |
| `500` | Unexpected server error |

All error responses follow the same shape:

```json
{ "error": "Human-readable message" }
```

Validation failures include a `details` array:

```json
{
  "error": "Validation failed",
  "details": [
    { "field": "customer_email", "message": "customer_email must be a valid email address" },
    { "field": "subject", "message": "subject must be between 1 and 200 characters" }
  ]
}
```
