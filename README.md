# F3 RVA API (`f3rva-api`)

Modern, serverless Python REST and HTTP API service for the **F3 RVA** community. This service consolidates all backend endpoints for workout backblasts, live schedules, PAX attendance analytics, AO leaderboards, alias management, and admin workflows.

---

## 1. Technology Stack

- **Runtime**: Python 3.13+ (strict static typing enforced)
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) 0.115+
- **ASGI / Serverless Adapter**: [Mangum](https://mangum.io/) for AWS Lambda execution
- **Validation & Serialization**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **Database ORM & Query Engine**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with PyMySQL connection pooling
- **Security & Tokens**: [PyJWT](https://pyjwt.readthedocs.io/) for HS256 JWT Bearer authorization
- **Configuration & Secrets**: Pydantic BaseSettings + AWS SSM Parameter Store (`boto3`)
- **Testing**: [pytest](https://docs.pytest.org/), pytest-mock, pytest-cov, and HTTPX `TestClient`
- **Linting & Code Quality**: `ruff` and `mypy`

---

## 2. Architecture & Project Layout

```text
f3rva-api/
├── .github/
│   └── workflows/
│       ├── deploy.yml                 # CI/CD deployment to Dev (on push to main) and Prod (on release)
│       └── release-tag.yml            # Dispatch action to create versioned release tags
├── scripts/
│   ├── package_lambda.sh              # Local shell script to build ARM64 deployment zip
│   └── generate_postman.py            # Generates strictly compliant Postman v2.1.0 JSON
├── pyproject.toml                     # Build configuration, ruff, mypy & pytest settings
├── requirements.txt                   # Production dependencies (FastAPI, SQLAlchemy, PyMySQL, etc.)
├── requirements-dev.txt               # Development dependencies (pytest, mypy, ruff, httpx)
├── .env.example                       # Local environment variable template
├── postman_collection.json            # Pre-configured Postman v2.1.0 collection (Phases 1-6)
├── README.md                          # Operator and developer guide
├── GEMINI.md                          # AI agent instructions, OWASP rules & guardrails
├── src/
│   ├── main.py                        # FastAPI application instance & AWS Lambda handler
│   ├── config/
│   │   ├── settings.py                # 12-factor environment parser with AWS SSM Parameter resolution
│   │   ├── database.py                # SQLAlchemy engine pool and session lifecycle management
│   │   └── version.py                 # Dynamic Git tag and package version resolution
│   ├── models/
│   │   ├── workout.py                 # SQLAlchemy 2.0 ORM models (WORKOUT, AO, MEMBER, ALIAS, etc.)
│   │   └── schemas.py                 # Pydantic v2 request & response DTOs
│   ├── routers/                       # Controller layer (thin routers)
│   │   ├── schedule.py                # /schedule (live F3 Nation schedule proxy)
│   │   ├── workouts.py                # /v2/workouts (read, filter, structured add, delete)
│   │   ├── members.py                 # /v2/members (alphabetical list, profiles, stats, lookup)
│   │   ├── reports.py                 # /v2/reports (attendance, AO averages, day-of-week, streakers)
│   │   ├── aliases.py                 # /v2/aliases (self-service claim requests)
│   │   └── admin.py                   # /v2/admin (JWT login, approve, reject, merge records)
│   ├── services/                      # Core business logic layer
│   │   ├── schedule_service.py        # Upstream F3 Nation API integration & event transformations
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
    ├── test_schedule.py               # Schedule API transformation, caching, and error handling
    ├── test_workouts.py               # Workouts filtering, pagination & 404 handling
    ├── test_members.py                # Member stats, alias lookups & Q-ratio math
    ├── test_reports.py                # Streaker recursive algorithm & attendance reports
    ├── test_workout_mutations.py      # Structured workout additions & protected deletions
    ├── test_admin.py                  # JWT authentication, alias approvals & merger tests
    ├── test_database.py               # Database engine, session lifecycle & version tests
    ├── test_utils.py                  # Service latency tracking & logging decorator tests
    └── run_tests.py                   # Standalone test runner script (75 tests)
```

---

## 3. Local Development Quickstart

### Prerequisites
* Python 3.13 or higher (`python3 --version`)
* Access to MySQL database or local test database

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
```

### Running the API Locally
Start the development server with live auto-reload:
```bash
python -m uvicorn src.main:app --reload --port 8000
```

* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Raw OpenAPI JSON Spec**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
* **Schedule API**: [http://localhost:8000/schedule](http://localhost:8000/schedule)

---

## 4. Running the Test Suite & Coverage

The repository maintains **100% test coverage** across all routes, services, schemas, and configurations.

```bash
# Run pytest with code coverage validation
pytest -v --cov=src --cov-fail-under=80

# Or execute the standalone test runner
python tests/run_tests.py
```

---

## 5. CI/CD & AWS Deployment

The deployment pipeline is modeled directly after `f3rva-website` using GitHub Actions and AWS OIDC role assumption.

### Deployment Triggers
1. **Development (`development` environment)**:
   * **Trigger**: Push to `main` branch.
   * **Actions**: Runs linter, static type checker, pytest suite, packages an ARM64 Linux zip bundle, updates the `f3rva-dev-api-lambda` Lambda function, and invalidates the CloudFront distribution.
2. **Production (`production` environment)**:
   * **Trigger**: Published GitHub Release.
   * **Actions**: Runs tests, packages locked version, deploys to `f3rva-prod-api-lambda`, and invalidates CloudFront.

---

## 6. GitHub Repository Setup: Environments & Secrets

Before pushing code to trigger the GitHub Actions workflow, configure the GitHub repository environments and secrets in GitHub (**Settings > Environments**):

### Environment: `development`
Create a GitHub Environment named **`development`** and add the following Environment Secrets:

| Secret Name | Description | Example / Default Value |
| :--- | :--- | :--- |
| `DEV_AWS_ROLE_ARN` | **(Required)** ARN of the AWS IAM OIDC Role that GitHub Actions assumes to deploy to AWS. | `arn:aws:iam::123456789012:role/GitHubActionsRole` |
| `DEV_CLOUDFRONT_DISTRIBUTION_ID` | **(Required)** CloudFront Distribution ID created by CDK for `F3RVA-api-dev` (used for cache invalidations). | `E1A2B3C4D5E6F7` |
| `DEV_AWS_REGION` | *(Optional)* AWS region for deployment. | `us-east-1` (default if omitted) |
| `DEV_LAMBDA_FUNCTION_NAME` | *(Optional)* Target Lambda function name. | `f3rva-dev-api-lambda` (default if omitted) |

---

### Environment: `production`
Create a GitHub Environment named **`production`** and add the following Environment Secrets:

| Secret Name | Description | Example / Default Value |
| :--- | :--- | :--- |
| `PROD_AWS_ROLE_ARN` | **(Required)** ARN of the AWS IAM OIDC Role for production deployment. | `arn:aws:iam::123456789012:role/GitHubActionsRole` |
| `PROD_CLOUDFRONT_DISTRIBUTION_ID` | **(Required)** CloudFront Distribution ID created by CDK for `F3RVA-api-prod`. | `E7F6E5D4C3B2A1` |
| `PROD_AWS_REGION` | *(Optional)* AWS region for deployment. | `us-east-1` (default if omitted) |
| `PROD_LAMBDA_FUNCTION_NAME` | *(Optional)* Target Lambda function name. | `f3rva-prod-api-lambda` (default if omitted) |

---

### How to Find Your CloudFront Distribution ID
After deploying `F3RVA-api-dev` via CDK (`npx cdk deploy F3RVA-api-dev`), the Distribution ID is displayed in the CloudFormation outputs:
```text
Outputs:
F3RVA-api-dev.CloudFrontDistributionId = E1A2B3C4D5E6F7
```
Alternatively, in the AWS Console: Navigate to **CloudFront > Distributions** and look for the distribution with alternate domain name `api.dev.f3rva.org` (or origin `f3rva-dev-api-lambda`).
