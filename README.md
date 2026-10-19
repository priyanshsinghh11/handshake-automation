# Recruitment Assessment Automation

Automatically sends a personalised assessment link to every candidate who applies for a job via Handshake.

---

## What it does

```
Candidate applies via Handshake
        ↓
POST /webhooks/handshake  (our endpoint)
        ↓
Handshake Adapter  (normalises the payload)
        ↓
Application Service
  • find/create candidate
  • find/create job
  • create application (idempotent)
  • find assessment mapping
  • generate secure token + URL
  • send assessment email
  • store status
        ↓
Database (SQLite / PostgreSQL)
```

The same webhook received twice **never** sends a second email.

---

## Architecture

```
app/
├── adapters/handshake.py   ← Handshake-specific conversion (isolated)
├── services/
│   ├── application.py      ← Core processing pipeline
│   ├── assessment.py       ← Token generation, session creation
│   └── email.py            ← Provider-agnostic email sending
├── routes/
│   ├── webhook.py          ← POST /webhooks/handshake
│   ├── applications.py     ← GET /applications, retry
│   └── mappings.py         ← CRUD for job→assessment mappings
├── models.py               ← SQLAlchemy ORM
├── schemas.py              ← Pydantic v2 validation
├── config.py               ← All config via Pydantic Settings
├── database.py             ← Engine + session factory
└── main.py                 ← App startup, table creation, seed data
```

---

## Project Structure

```
handshake-assessment-automation/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routes/
│   │   ├── webhook.py
│   │   ├── applications.py
│   │   └── mappings.py
│   ├── services/
│   │   ├── application.py
│   │   ├── assessment.py
│   │   └── email.py
│   └── adapters/
│       └── handshake.py
├── tests/
│   ├── conftest.py
│   ├── test_webhook.py
│   └── test_application.py
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── README.md
```

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust:

| Variable              | Default                            | Description                          |
|-----------------------|------------------------------------|--------------------------------------|
| `DATABASE_URL`        | `sqlite:///./app.db`               | SQLite for dev, PostgreSQL for prod  |
| `WEBHOOK_SECRET`      | `change-me`                        | Required in `X-Webhook-Secret` header|
| `ASSESSMENT_BASE_URL` | `http://localhost:8000/assessment` | Prefix for generated assessment URLs |
| `EMAIL_PROVIDER`      | `mock`                             | `mock` or `brevo`                    |
| `EMAIL_FROM`          | `noreply@example.com`              | Sender address                       |
| `BREVO_API_KEY`       | *(empty)*                          | Required if `EMAIL_PROVIDER=brevo`   |
| `SENDGRID_API_KEY`    | *(empty)*                          | Future use                           |

---

## How to Run

```bash
cp .env.example .env
# edit .env as needed

uvicorn app.main:app --reload
```

Or:

```bash
python run.py
```

On startup the application:
1. Creates all database tables.
2. Seeds two demo jobs, two assessments, and two mappings automatically.

Web UI available at http://localhost:8000 (plain HTML/CSS/JS in `app/static/`):
view applications and retry failed ones, manage job → assessment mappings, and send a test application.

API docs available at:
- http://localhost:8000/docs  (Swagger)
- http://localhost:8000/redoc

---

## How to Test

```bash
pytest
```

All tests use an in-memory SQLite database. No real email credentials or Handshake access needed.

---

## Example Webhook Request

```bash
curl -X POST http://localhost:8000/webhooks/handshake \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "candidate_id": "hs_candidate_123",
    "candidate_name": "Rahul Sharma",
    "candidate_email": "rahul@example.com",
    "job_id": "seed_job_ai",
    "job_title": "AI Engineer Intern"
  }'
```

Expected response:

```json
{
  "success": true,
  "application_id": 1,
  "status": "EMAIL_SENT"
}
```

Send the exact same request again → response is identical but **no second email is sent**.

---

## Example Complete Workflow

```
1. Start server:      uvicorn app.main:app --reload
2. Demo data seeded automatically (AI Engineer Intern, Full Stack Engineer)
3. POST /webhooks/handshake with candidate payload
4. System: validates secret → creates candidate → creates application
         → finds mapping → creates assessment session → sends mock email
         → status = EMAIL_SENT
5. POST same payload again → duplicate detected → no second email
6. GET /applications → see all applications with status
7. To retry a failed application: POST /applications/{id}/retry
```

---

## Connecting Real Handshake Integration

> **Note**: As of this writing, Handshake does not offer a verified outbound webhook.  
> The MVP exposes its own endpoint and uses a normalised payload.

When Handshake adds webhook support:

1. Open `app/adapters/handshake.py`.
2. Update `parse_handshake_payload()` to map Handshake's actual field names to `InternalApplicationInput`.
3. Add signature verification (HMAC-SHA256 or similar) in the webhook route dependency.
4. Nothing else in the application changes.

Future integrations (Workable, Greenhouse, CSV import) follow the same pattern:
- Add a new adapter in `app/adapters/`
- Map to `InternalApplicationInput`
- Call `process_application()` from the service layer

---

## Known Limitations (MVP)

- No authentication for recruiter-facing APIs (mappings, applications).
- No pagination on list endpoints.
- Email retry is manual (POST /applications/{id}/retry).
- SQLite is not suitable for concurrent production load; switch to PostgreSQL.
- Brevo/SendGrid email providers are stubs – not yet implemented.

---

## Recommended Next Step (Production Path)

```
Handshake (real webhook)
        ↓
FastAPI  (this service)
        ↓
PostgreSQL
        ↓
Redis Queue  (async email jobs)
        ↓
Worker
        ↓
Brevo / SendGrid
        ↓
Assessment Portal
```
