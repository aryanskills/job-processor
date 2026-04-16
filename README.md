# Background Job Processor 🚀

A production-ready **asynchronous background job processing service** built with **FastAPI**, **SQLAlchemy (async)**, and **SQLite**. Jobs are submitted via REST API, processed asynchronously in the background, and can be tracked through their full lifecycle.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Async job processing** | Non-blocking background tasks via FastAPI `BackgroundTasks` + `asyncio` |
| **Full lifecycle tracking** | `pending → in_progress → completed / failed / cancelled` |
| **Priority queue** | Jobs with higher priority run first |
| **Graceful error handling** | Random failure simulation (configurable rate), full error capture |
| **Pagination & filtering** | List jobs by status with skip/limit |
| **Statistics endpoint** | Aggregate counts per status |
| **Swagger UI** | Auto-generated docs at `/docs` |
| **ReDoc** | Alternative docs at `/redoc` |
| **Postman collection** | Ready-to-import with pre-written tests |
| **Docker support** | `Dockerfile` + `docker-compose.yml` included |

---

## 📁 Project Structure

```
job_processor/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, CORS, router registration
│   ├── api/
│   │   └── v1/
│   │       └── jobs.py          # All job endpoints (submit, get, list, cancel, stats)
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   └── exceptions.py        # Custom HTTP exceptions
│   ├── db/
│   │   └── database.py          # Async SQLAlchemy engine, session, Base, init_db
│   ├── models/
│   │   └── job.py               # Job ORM model (SQLAlchemy)
│   ├── schemas/
│   │   └── job.py               # Pydantic request/response schemas
│   └── services/
│       └── job_service.py       # CRUD + async background worker logic
├── tests/
│   └── test_jobs.py             # Full pytest-asyncio test suite
├── .env.example                 # Environment variable template
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── postman_collection.json      # Importable Postman collection
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 🔄 Job Lifecycle

```
POST /api/v1/jobs/
        │
        ▼
   ┌─────────┐     background task starts     ┌─────────────┐
   │ PENDING │ ──────────────────────────────► │ IN_PROGRESS │
   └─────────┘                                 └─────────────┘
        │                                             │
        │  cancel requested                    5-10s delay
        │                                             │
        ▼                                    ┌────────┴────────┐
   ┌───────────┐                             │                 │
   │ CANCELLED │                        ┌─────────┐      ┌────────┐
   └───────────┘                        │COMPLETED│      │ FAILED │
                                        └─────────┘      └────────┘
```

---

## 🚀 Quick Start

### Option 1 — Local (Python virtualenv)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/job-processor.git
cd job-processor

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp .env.example .env

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

### Option 2 — Docker Compose

```bash
docker-compose up --build
```

The API will be available at **http://localhost:8000**.

---

## 📖 API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

#### `POST /jobs/` — Submit a Job
```json
// Request body
{
  "name": "generate-report",        // required, 1-255 chars
  "payload": { "year": 2025 },      // optional, any JSON object
  "priority": 3                     // optional, 0-10 (default: 0)
}

// Response 201
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "generate-report",
  "status": "pending",
  "result": null,
  "error": null,
  "priority": 3,
  "created_at": "2025-01-15T10:00:00Z",
  "started_at": null,
  "completed_at": null
}
```

#### `GET /jobs/{job_id}` — Get Job Status
```bash
curl http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

#### `GET /jobs/` — List Jobs
```bash
# All jobs (paginated)
curl "http://localhost:8000/api/v1/jobs/?skip=0&limit=20"

# Filter by status
curl "http://localhost:8000/api/v1/jobs/?status=completed"
```

#### `GET /jobs/stats` — Statistics
```json
{
  "total": 42,
  "pending": 5,
  "in_progress": 3,
  "completed": 30,
  "failed": 2,
  "cancelled": 2
}
```

#### `DELETE /jobs/{job_id}/cancel` — Cancel a Job
```bash
curl -X DELETE http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/cancel
```

### Error Responses

| Status | Scenario |
|--------|----------|
| `404` | Job ID not found |
| `409` | Cancelling an already-terminal job |
| `422` | Invalid request body (e.g. empty name, priority > 10) |

---

## 🧪 Running Tests

```bash
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run the full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

**Test coverage includes:**
- Health endpoints
- Job submission (full, minimal, invalid)
- Get job by ID (found + 404)
- List jobs (all, filtered, paginated)
- Job cancellation (success, 409 conflict, 404)
- Statistics endpoint
- Priority validation

---

## 📬 Postman Collection

1. Open **Postman**
2. Click **Import** → select `postman_collection.json`
3. Set the `base_url` collection variable to `http://localhost:8000`
4. Run **"Submit Job (full payload)"** first — the `job_id` variable is auto-set
5. Poll **"Get Job by ID"** until the status changes to `completed` or `failed`

Each request includes pre-written **test scripts** so you can use the **Collection Runner** to validate the entire API in one click.

---

## ⚙️ Configuration

All settings are controlled via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./jobs.db` | SQLAlchemy async DB URL |
| `JOB_MIN_DELAY` | `5` | Minimum simulated processing delay (seconds) |
| `JOB_MAX_DELAY` | `10` | Maximum simulated processing delay (seconds) |
| `JOB_FAILURE_RATE` | `0.1` | Probability of random job failure (0.0–1.0) |

### Switching to PostgreSQL

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/job_processor
```

Add `asyncpg` to `requirements.txt`:
```
asyncpg>=0.29.0
```

---

## 🏗️ Design Decisions

| Decision | Rationale |
|---|---|
| **FastAPI BackgroundTasks** | Lightweight, no broker needed for this scale. Swap with Celery + Redis for distributed workloads. |
| **SQLAlchemy async** | Future-proof ORM; swap SQLite for PostgreSQL with one env var change. |
| **UUID primary keys** | Globally unique, safe to expose in URLs, no sequential guessing. |
| **Pydantic v2 schemas** | Strict validation, automatic OpenAPI generation, fast serialisation. |
| **Separate DB session per background task** | Request session is closed before the background task runs; the worker opens its own session. |
| **Terminal state guard** | Re-fetch job inside worker after sleep to honour mid-flight cancellations. |

---

## 📝 License

MIT
