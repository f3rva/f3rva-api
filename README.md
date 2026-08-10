# F3 RVA API (`f3rva-api`)

Modern, serverless Python REST and HTTP API service for the **F3 RVA** community. This service replaces the legacy monolithic PHP backend, providing high-performance, type-safe endpoints for workout backblasts, PAX attendance analytics, AO leaderboards, web scraping ingestion, alias management, and admin workflows.

---

## 1. Technology Stack

- **Runtime**: Python 3.13+ (strict static typing enforced)
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) 0.115+
- **ASGI / Serverless Adapter**: [Mangum](https://mangum.io/) for AWS Lambda execution
- **Validation & Serialization**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **Database ORM & Query Engine**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with PyMySQL connection pooling
- **Security & Tokens**: [PyJWT](https://pyjwt.readthedocs.io/) for HS256 JWT Bearer authorization
- **HTML Parsing & Scraping**: [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) and [HTTPX](https://www.python-httpx.org/)
- **Testing**: [pytest](https://docs.pytest.org/), pytest-mock, pytest-cov, and HTTPX `TestClient`
- **Linting & Code Quality**: `ruff` and `mypy`

---

## 2. Architecture & Project Layout

```text
f3rva-api/
├── pyproject.toml                     # Build configuration, ruff, mypy & pytest settings
├── requirements.txt                   # Production dependencies (FastAPI, SQLAlchemy, PyMySQL, etc.)
├── requirements-dev.txt               # Development dependencies (pytest, mypy, ruff, httpx)
├── .env.example                       # Local environment variable template
├── postman_collection.json            # Pre-configured Postman v2.1.0 collection (Phases 1-5)
├── README.md                          # Operator and developer guide
├── GEMINI.md                          # AI agent instructions, OWASP rules & guardrails
├── src/
│   ├── main.py                        # FastAPI application instance & AWS Lambda handler
│   ├── config/
│   │   ├── settings.py                # 12-factor environment parser with Pydantic BaseSettings
│   │   ├── database.py                # SQLAlchemy engine pool and session lifecycle management
│   │   └── version.py                 # Dynamic Git tag and package version resolution
│   ├── models/
│   │   ├── workout.py                 # SQLAlchemy 2.0 ORM models (WORKOUT, AO, MEMBER, ALIAS, etc.)
│   │   └── schemas.py                 # Pydantic v2 request & response DTOs
│   ├── routers/                       # Controller layer (thin routers)
│   │   ├── workouts.py                # /v2/workouts (read, filter, ingest, refresh)
│   │   ├── members.py                 # /v2/members (alphabetical list, profiles, stats, lookup)
│   │   ├── reports.py                 # /v2/reports (attendance, AO averages, day-of-week, streakers)
│   │   ├── aliases.py                 # /v2/aliases (self-service claim requests)
│   │   └── admin.py                   # /v2/admin (JWT login, approve, reject, merge records)
│   ├── services/                      # Core business logic layer
│   │   ├── workout_service.py         # Derived table pagination & backblast queries (<15ms)
│   │   ├── workout_mutation_service.py# Structured workout additions & transactional deletions
│   │   ├── member_service.py          # Member profiles, attendance stats & search
│   │   ├── report_service.py          # Streaker calculation & attendance aggregations
│   │   └── alias_service.py           # Multi-table atomic alias merger & audit transactions
│   └── utils/
│       ├── logging.py                 # Structured latency tracing decorator (@timed_service)
│       └── security.py                # JWT creation, decoding, and Bearer token dependency
└── tests/                             # Automated Pytest suite (100% test coverage)
    ├── conftest.py                    # SQLite in-memory fixtures & TestClient setup
    ├── test_health.py                 # Health checks, docs, CORS & Mangum Lambda adapter
    ├── test_workouts.py               # Workouts filtering, pagination & 404 handling
    ├── test_members.py                # Member stats, alias lookups & Q-ratio math
    ├── test_reports.py                # Streaker recursive algorithm & attendance reports
    ├── test_workout_mutations.py      # Structured workout additions & protected deletions
    ├── test_admin.py                  # JWT authentication, alias approvals & merger tests
    ├── test_database.py               # Database engine, session lifecycle & version tests
    ├── test_utils.py                  # Service latency tracking & logging decorator tests
    └── run_tests.py                   # Standalone test runner script
```

---

## 3. Local Development Quickstart

### Prerequisites
* Python 3.13 or higher (`python3 --version`)
* Access to the MySQL database or local SQLite test database

### Setup Virtual Environment
```bash
# 1. Clone repository and navigate to directory
cd /Users/bbischoff/dev/f3/f3rva-api

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Create local environment file
cp .env.example .env
# Edit .env with your database connection credentials and admin secret
```

### Running the API Locally
Start the development server with live auto-reload:
```bash
python -m uvicorn src.main:app --reload --port 8000
```

* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
* **Postman Collection**: Import [`postman_collection.json`](file:///Users/bbischoff/dev/f3/f3rva-api/postman_collection.json) directly into Postman for pre-configured requests across all endpoints.

---

## 4. Authentication & Security (JWT)

Protected administrative endpoints require an **HTTP Bearer JWT Token**.

1. **Obtain Token via `POST /v2/admin/login`**:
   ```bash
   curl -X POST http://localhost:8000/v2/admin/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "change-me-admin-password"}'
   ```
   Returns:
   ```json
   {
     "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "tokenType": "bearer",
     "expiresIn": 86400
   }
   ```
2. **Access Protected Endpoints**:
   Include the token in the `Authorization` header:
   ```text
   Authorization: Bearer <accessToken>
   ```
3. **Automated Postman Capture**:
   Executing the `Admin Login` request in Postman automatically saves the token to the `{{authToken}}` collection variable for all subsequent requests.

---

## 5. Running Tests & Quality Checks

The repository enforces a **strict minimum of 80% test coverage** via `pytest-cov` (`--cov-fail-under=80`). The current test suite operates at **100% coverage** across all modules.

```bash
# Run all 64 unit and integration tests with coverage enforcement (>= 80%)
pytest

# Run tests with verbose per-file line-by-line coverage report
pytest -v --cov=src --cov-report=term-missing

# Run linting with Ruff
ruff check src tests

# Run strict type checking with MyPy
mypy src

# Run standalone test runner
python tests/run_tests.py
```

---

## 6. Versioning & Release Strategy

The application version is dynamically tied to Git tags via `setuptools_scm` and resolved at runtime:

### A. Environment Resolution Matrix

| Event / Trigger | Target Environment | Version Displayed in Swagger UI & `/health` |
| :--- | :--- | :--- |
| **Local Dev (uncommitted edits)** | `localhost:8000` | `<commit_sha>-dirty` (e.g. `59185fc-dirty`) |
| **Local Dev (clean working tree)** | `localhost:8000` | `<commit_sha>` or exact tag if tagged |
| **PR Merge to `main`** | `api.dev.f3rva.org` | `<tag>-<count>-g<sha>` (e.g. `0.1.0-2-ga1b2c3d`) |
| **Publish Release / Tag `v*`** | `api.f3rva.org` (Prod) | `0.2.0` (clean Semantic Versioning release) |

### B. CI/CD Release Flow

1. **Development (`dev.f3rva.org`)**:
   * Pushes/merges to the `main` branch trigger automated GitHub Actions testing and deployment to the `dev` Lambda function.
   * Version reflects the base release plus the exact commit hash for full audit traceability.
2. **Production (`f3rva.org`)**:
   * Creating a release/tag in GitHub (e.g. `v0.2.0`) triggers the production release workflow.
   * `setuptools_scm` locks the version statically to `0.2.0` in `src/_version.py`.
   * Deploys the artifact to the production AWS Lambda function (`f3rva-prod-api`).
   * `https://api.f3rva.org/health` and `https://api.f3rva.org/docs` display `0.2.0`.

---

## 7. Deployment & AWS Integration

When deployed to AWS Lambda:
1. `src/main.py` exposes `handler = Mangum(app, lifespan="off")` as the Lambda entrypoint.
2. In production, database credentials and the admin secret key are dynamically read from **AWS SSM Parameter Store** (`/f3rva/prod/*`) with in-memory caching.
3. Traffic is routed via **CloudFront** and **AWS Lambda Function URL / API Gateway** under `https://api.f3rva.org`.
