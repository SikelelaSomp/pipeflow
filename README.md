# PipeFlow

**Middleware intelligence layer between South African universities, TVET colleges, and NSFAS.**

PipeFlow automates and validates the flow of student funding data that currently moves manually through spreadsheets and portal uploads. Universities connect once. Every registration, result submission, and deregistration flows through PipeFlow automatically — validated, tracked, and forwarded. No spreadsheets. No manual uploads. No avoidable mistakes.

---

## The Problem

Every registration cycle, financial aid staff at every university and TVET college in South Africa manually download a template from the NSFAS portal, fill it in with student data, and upload it back. One wrong ID number, one missing field, one late upload — a student loses their funding. Not because they don't qualify. Because of a human error on a spreadsheet.

PipeFlow removes that human error from the process.

---

## How It Works

```
University / TVET College
        |
        |  POST /api/v1/events
        ↓
    PipeFlow
    ├── Validates (RSA ID, required fields, NQF level, credits, duplicates)
    ├── Logs every status transition with timestamp
    └── Forwards to NSFAS
        |
        ↓
      NSFAS
```

Every event moves through a pipeline:

```
RECEIVED → VALIDATING → VALID → FORWARDED
                      ↘ INVALID (with exact field-level failure reasons)
```

---

## Tech Stack

- **Python 3.13** with **FastAPI**
- **PostgreSQL** via **asyncpg**
- **SQLAlchemy 2.0** (async)
- **Alembic** for migrations
- **Pydantic** for validation
- **bcrypt** for API key hashing
- **Uvicorn** as the ASGI server

---

## Project Structure

```
pipeflow/
├── alembic.ini
├── seed.py
├── requirements.txt
├── .env
├── alembic/
│   └── versions/
│       └── a85dd8b164a9_initial_schema.py
└── app/
    ├── main.py
    ├── api/
    │   └── v1/
    │       ├── router.py
    │       └── endpoints/
    │           ├── auth.py
    │           ├── events.py
    │           ├── institutions.py
    │           └── students.py
    ├── core/
    │   ├── auth.py
    │   ├── config.py
    │   └── security.py
    ├── db/
    │   └── session.py
    ├── models/
    │   └── models.py
    ├── schemas/
    │   └── schemas.py
    ├── services/
    │   └── event_service.py
    └── validators/
        └── event_validator.py
```

---

## Database — 7 Tables

| Table | Purpose |
|---|---|
| `institutions` | Every party in the system — universities, TVETs, NSFAS. API key stored as bcrypt hash. |
| `students` | Identity spine. RSA ID is the universal correlator. |
| `student_institution_enrolments` | Maps a student to an institution per academic year. One active enrolment per student per year enforced at DB level. |
| `events` | Core unit of work. Every data exchange is one row. Payload stored as JSONB. |
| `event_status_log` | Immutable append-only audit trail. Every status transition logged with timestamp. |
| `validation_results` | Per-field, per-rule validation outcomes for every event. |
| `disbursements` | Materialised from DISBURSEMENT_SCHEDULED events. |

---

## Event Types

**Inbound (University → NSFAS):**
- `STUDENT_REGISTRATION_SUBMITTED`
- `STUDENT_RESULTS_SUBMITTED`
- `STUDENT_DEREGISTERED`

**Outbound (NSFAS → University):**
- `FUNDING_DECISION_ISSUED`
- `DISBURSEMENT_SCHEDULED`
- `DISBURSEMENT_STATUS_UPDATED`
- `FUNDING_SUSPENDED`

---

## API Endpoints

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/auth/me` | Resolve institution from API key — use as login check | All |
| GET | `/api/v1/events/stats` | Summary counts by status and event type | All |
| GET | `/api/v1/events` | List events | All (scoped) |
| GET | `/api/v1/events/{event_id}` | Event detail with audit trail and validation results | All |
| POST | `/api/v1/events` | Submit inbound event | University |
| POST | `/api/v1/events/outbound` | Submit outbound event | NSFAS only |
| GET | `/api/v1/institutions` | List all institutions | NSFAS only |
| POST | `/api/v1/institutions` | Register new institution | NSFAS only |
| GET | `/api/v1/students/{rsa_id}` | Look up student by RSA ID | All (scoped) |
| GET | `/health` | Health check | Public |

Interactive docs at `http://localhost:8000/docs`

---

## Authentication

API keys per institution. Every key is prefixed with `pf_`, generated with `secrets.token_urlsafe(32)`, hashed with bcrypt, and never stored raw. Shown once at creation.

Pass in every request as:
```
Authorization: Bearer pf_your_key_here
```

NSFAS holds the master key and is the only institution that can create other institutions and see all events.

---

## Validation Rules

**All inbound events:**
- RSA ID format (13 digits)
- RSA ID Luhn checksum

**STUDENT_REGISTRATION_SUBMITTED:**
- Required fields
- NQF level range (5–8)
- Total credits minimum (120)
- Duplicate active enrolment check across institutions

**STUDENT_RESULTS_SUBMITTED:**
- Required fields
- Credits passed cannot exceed credits attempted
- Pass rate consistency
- Warning if pass rate below 60% (NSFAS funding threshold)

**STUDENT_DEREGISTERED:**
- Required fields
- Reason enum validation

---

## Local Setup

### Prerequisites
- Python 3.13
- PostgreSQL
- pgAdmin (optional, for DB management)

### 1. Clone the repo
```bash
git clone https://github.com/SikelelaSomp/pipeflow.git
cd pipeflow
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the root:
```
DATABASE_URL=postgresql+asyncpg://pipeflow:yourpassword@localhost:5432/pipeflow
SECRET_KEY=your_secret_key
```

### 4. Create the database
In pgAdmin or psql, create a database named `pipeflow`.

### 5. Run migrations
```bash
alembic upgrade head
```

### 6. Seed the database
```bash
python seed.py
```

### 7. Start the server

Open two terminals:

**Terminal 1 — keep running:**
```bash
set PYTHONPATH=C:\Users\Admin\pipeflow
uvicorn app.main:app --reload
```

**Terminal 2 — for commands:**
```bash
cd C:\Users\Admin\pipeflow
```

API is live at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

---

## CORS

The API allows requests from:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

---

## Current Status

- [x] Core event pipeline — RECEIVED → VALIDATING → VALID/INVALID → FORWARDED
- [x] Full validation rule engine
- [x] Immutable audit trail per event
- [x] API key authentication per institution
- [x] NSFAS master key with elevated permissions
- [x] Auth endpoint for frontend login
- [x] Stats endpoint for dashboard summary
- [x] Student lookup endpoint
- [x] CORS configured for frontend development
- [ ] NSFAS portal integration (browser automation — in research)
- [ ] Frontend dashboard (in development)
- [ ] Rate limiting and structured logging
- [ ] Retry logic for failed forwarding

---

## Roadmap

**Now — Pilot**
Universities submit to PipeFlow via API. PipeFlow validates and uses browser automation to submit to the NSFAS institution portal on their behalf, removing the manual upload step entirely.

**Next — Pull Model**
PipeFlow connects directly into university Student Information Systems (ITS, PeopleSoft) and pulls registration data automatically. No human submission required.

**Long term — Source of Truth**
PipeFlow mirrors the NSFAS database and becomes the authoritative source of student funding status per institution per qualification — surfacing delays, flagging anomalies, and creating accountability that does not currently exist in the system.

---

## Contributing

This is an active early-stage project. If you want to contribute or collaborate, reach out directly.

---

## License

Private. All rights reserved.
