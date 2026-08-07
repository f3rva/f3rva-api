# Gemini Agent Instructions for `f3rva-api`

This document provides comprehensive instructions, architectural guardrails, coding conventions, and **OWASP API Security Best Practices** for developing and maintaining the **`f3rva-api`** repository.

---

## 1. Project Overview

**`f3rva-api`** is the centralized Python 3.13+ serverless REST and HTTP API service for the F3 RVA community (`f3rva.org` and `f3-rva-workspace.slack.com`).
It replaces the legacy monolithic PHP backend, serving backblast archives, member analytics, leaderboards, alias claims, admin mutations, and the schedule proxy.

---

## 2. Technology Stack & Modern Tooling

- **Language:** Python 3.13+ (Strict static typing enforced)
- **Web Framework:** FastAPI 0.115+
- **ASGI Serverless Adapter:** Mangum 0.19+ (`lifespan="off"`)
- **Validation & Serialization:** Pydantic v2 (Strict BaseModel schemas with `ConfigDict`)
- **Database Engine:** SQLAlchemy 2.0+ with PyMySQL connection pooling & `pool_pre_ping=True`
- **Security & Crypto:** PyJWT (HS256), Cryptography, `python-multipart`
- **Testing:** `pytest`, `pytest-mock`, `pytest-cov`, and HTTPX `TestClient`
- **Linting & Type Checking:** `ruff` and `mypy` (strict mode)

---

## 3. Directory & Package Structure

AI agents must preserve and respect the following package hierarchy:

```text
src/
├── __init__.py
├── main.py                     # Central FastAPI application & Mangum handler
├── config/                     # Configuration, settings & database session pool
│   ├── __init__.py
│   ├── settings.py             # Parses env vars & reads AWS SSM Parameter Store
│   ├── database.py             # SQLAlchemy 2.0 engine, SessionLocal & get_db dependency
│   └── version.py              # Dynamic Git tag and package version resolution
├── models/                     # Data definitions
│   ├── __init__.py
│   ├── workout.py              # WORKOUT, WORKOUT_AO, WORKOUT_Q, WORKOUT_PAX, WORKOUT_DETAILS
│   ├── member.py               # MEMBER, MEMBER_ALIAS, ALIAS_REQUEST
│   └── schemas.py              # Pydantic v2 request & response schemas
├── routers/                    # Controller layer (Thin Routers)
│   ├── __init__.py
│   ├── workouts.py             # /v2/workouts (paginated, by-date, by-ao, by-slug)
│   ├── members.py              # /v2/members (profiles, stats, workout history)
│   ├── reports.py              # /v2/reports (attendance, AO averages, day-of-week, streakers)
│   ├── self_service.py         # /v2/aliases (claim alias requests)
│   ├── admin.py                # /v2/admin (login, approve, reject, merge pax)
│   └── schedule.py             # /schedule (F3 Nation proxy)
└── services/                   # Business Logic Layer (Free of transport details)
    ├── __init__.py
    ├── workout_service.py      # Workout query composition & pagination math
    ├── member_service.py       # Atomic multi-table alias merger & stats calculations
    ├── report_service.py       # Attendance aggregations & recursive streakers algorithm
    ├── admin_service.py        # Password hashing & JWT token verification
    └── scraper_service.py      # Backblast HTML parser (BeautifulSoup4)
tests/                          # Pytest suite
    ├── conftest.py             # SQLite in-memory fixtures & TestClient instance
    ├── test_health.py
    ├── test_workouts.py
    ├── test_members.py
    ├── test_reports.py
    ├── test_alias_transactions.py
    └── test_admin_auth.py
```

---

## 4. OWASP API Security & Hardening Guardrails

AI agents MUST adhere unconditionally to the **OWASP API Security Top 10** standards across all modules:

### A. OWASP API1: Broken Object-Level Authorization (BOLA / IDOR)
* All mutating endpoints (e.g. approving alias requests, merging member IDs, updating/deleting workouts) **MUST require explicit admin authentication** via the `get_current_admin` dependency.
* Never allow public clients to modify records belonging to other users without authorization.

### B. OWASP API2: Broken Authentication & Token Security
* **JWT Signing**: Use **HS256** with high-entropy (256-bit) signing secrets stored in AWS SSM Parameter Store / `.env`.
* **Token Transport**: Tokens must only be accepted via the `Authorization: Bearer <token>` HTTP header. Never accept tokens via URL query parameters (preventing token leakage in logs and browser history).
* **Token Expiration**: Enforce strict expiration timestamps (`exp` claim) with clock skew validation.
* **Safe Password Verification**: Compare admin password hashes using constant-time comparison (`secrets.compare_digest`) to prevent timing attacks.

### C. OWASP API3: Broken Object Property Level Authorization & Mass Assignment
* Always use explicit **Pydantic v2 DTOs** for request bodies.
* Never pass raw unvalidated dictionaries directly into SQLAlchemy models.
* Use `extra="forbid"` on sensitive request models to reject unexpected payload injection.

### D. OWASP API4: Unrestricted Resource Consumption (DoS / Rate Limiting / Pagination)
* **Mandatory Pagination Caps**: All list endpoints (`/v2/workouts`, `/v2/members`) must enforce strict upper limits (`limit <= 100`, default `20`) to prevent memory exhaustion attacks.
* **Database Connection Limits**: Enforce `pool_size=5`, `max_overflow=2`, and `pool_timeout=10` on database engine connections.
* **Request Timeout Protection**: External HTTP requests (e.g., F3 Nation API proxy or backblast scraper) must enforce explicit timeouts (`timeout=10`).

### E. OWASP API5: Broken Function Level Authorization
* Clearly delineate public read endpoints (`GET /v2/workouts/*`, `GET /v2/members/*`, `GET /v2/reports/*`, `POST /v2/aliases/request`) from protected administrative operations (`POST /v2/admin/*`).
* The admin router must be guarded by dependency-injected authentication at the router level.

### F. OWASP API6: Unrestricted Access to Sensitive Business Flows
* **Duplicate Submission Prevention**: Enforce database uniqueness checks and duplicate request guards on alias claim workflows.
* **Atomic Multi-Table Safety**: Any multi-table update (such as `assign_alias` or `merge_pax`) must use atomic transactions with guaranteed rollback on exceptions to prevent corrupted state.

### G. OWASP API7: Server-Side Request Forgery (SSRF) Protection
* When scraping backblast URLs:
  * Only allow HTTP/HTTPS URLs targeting approved domains (`f3rva.org`, `dev.f3rva.org`, or explicit F3 sites).
  * Block internal network IP ranges, private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback addresses (`127.0.0.1`, `localhost`), and the AWS metadata endpoint (`169.254.169.254`).

### H. OWASP API8: Security Misconfiguration & Information Leakage
* **Zero Credential & Stack Trace Leakage**:
  * Exception handlers must return sanitized, structured error responses (`{"errorCode": ..., "errorMessage": "..."}`).
  * **NEVER return raw database exception strings, connection URLs, hostnames, or passwords to the client in HTTP responses.**
* **Safe URL Construction**: Always use `sqlalchemy.engine.URL.create(...)` to escape special characters in passwords and prevent connection string corruption.
* **Security Headers**: CORS is restricted to authorized origins; `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` are enforced.

### I. OWASP API9: Improper Inventory & Version Management
* All REST endpoints must reside under explicit API version prefixes (`/v2/`).
* OpenAPI specification (`/openapi.json`) and Swagger docs (`/docs`) must accurately reflect all request and response contracts.

### J. OWASP API10: Unsafe Consumption of APIs & Injection Prevention
* **100% Parameterized Queries**: All database interactions must use SQLAlchemy 2.0 ORM mappings or parameterized `text("... :param")` queries. Never use f-strings or raw string concatenation to build SQL statements.
* **Input Sanitization**: Clean and strip all text inputs for member names, backblast titles, and search queries.

---

## 5. Architectural & Code Quality Guardrails

1. **The "Thin Routers, Fat Services" Rule**:
   * Controllers in `src/routers/` only handle HTTP status codes, query validation, and serialization.
   * All database queries, recursive algorithms, and transactions belong in `src/services/`.
2. **Strict Python 3.13 Typing**:
   * Use built-in generic types (`list[T]`, `dict[K, V]`, `str | None`).
   * Use `Annotated` for all FastAPI dependencies.
3. **Deterministic Pytest Suite**:
   * Every router and service component must have a corresponding test suite in `tests/`.
   * Tests run against in-memory SQLite fixtures (`tests/conftest.py`) without requiring live network access.
