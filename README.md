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
│   │   ├── workout.py                 # SQLAlchemy 2.0 ORM models (WORKOUT, AO, MEMBER, MEMBER_SLACK, etc.)
│   │   └── schemas.py                 # Pydantic v2 request & response DTOs
│   ├── routers/                       # Controller layer (thin routers)
│   │   ├── schedule.py                # /schedule (live F3 Nation schedule proxy)
│   │   ├── auth.py                    # /v2/auth (Slack OAuth login, link confirmation, user profile)
│   │   ├── workouts.py                # /v2/workouts (read, filter, structured add/edit, delete, aos list)
│   │   ├── members.py                 # /v2/members (alphabetical list, profiles, stats, lookup)
│   │   ├── reports.py                 # /v2/reports (attendance, AO averages, day-of-week, streakers)
│   │   ├── aliases.py                 # /v2/aliases (self-service claim requests)
│   │   └── admin.py                   # /v2/admin (JWT login, approve, reject, merge records)
│   ├── services/                      # Core business logic layer
│   │   ├── schedule_service.py        # Upstream F3 Nation API integration & event transformations
│   │   ├── slack_auth_service.py      # Slack OAuth OIDC exchange, team ID verification & member linking
│   │   ├── slack_notification_service.py# Block Kit backblast summaries dispatched to #backblasts
│   │   ├── workout_service.py         # Derived table pagination & backblast queries (<15ms)
│   │   ├── workout_mutation_service.py# Structured workout additions, author updates & transactional deletions
│   │   ├── member_service.py          # Member profiles, attendance stats & search
│   │   ├── report_service.py          # Streaker calculation & attendance aggregations
│   │   └── alias_service.py           # Multi-table atomic alias merger, audit & MEMBER_SLACK reconciliation
│   └── utils/
│       ├── logging.py                 # Structured latency tracing decorator (@timed_service)
│       └── security.py                # JWT creation, decoding, and Bearer token dependency
└── tests/                             # Automated Pytest suite (100% test coverage)
    ├── conftest.py                    # SQLite in-memory fixtures & TestClient setup
    ├── test_health.py                 # Health checks, docs, CORS & Mangum Lambda adapter
    ├── test_schedule.py               # Schedule API transformation, caching, and error handling
    ├── test_slack_auth.py             # Slack OAuth exchange, workspace enforcement & link confirmation
    ├── test_slack_notifications.py    # Block Kit message formatting & Slack WebClient dispatch
    ├── test_workouts.py               # Workouts filtering, pagination & 404 handling
    ├── test_members.py                # Member stats, alias lookups & Q-ratio math
    ├── test_reports.py                # Streaker recursive algorithm & attendance reports
    ├── test_workout_mutations.py      # Structured workout additions, author permissions & deletions
    ├── test_admin.py                  # JWT authentication, alias approvals, MEMBER_SLACK merges
    ├── test_database.py               # Database engine, session lifecycle & version tests
    ├── test_utils.py                  # Service latency tracking & logging decorator tests
    └── run_tests.py                   # Standalone test runner script (104 tests)
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

### Environment Variables (.env)
The API strictly reads configuration from OS environment variables, local `.env`, or AWS SSM Parameter Store without hardcoded defaults. The following variables must be configured:

| Variable | Required | Description | Example / Default Value |
| :--- | :--- | :--- | :--- |
| `BACKBLAST_URL_PREFIX` | **Yes** | Base URL prefix for constructing backblast permalinks | `https://dev.f3rva.org` (dev) / `https://f3rva.org` (prod) |
| `DATABASE_URL` | **Yes** | MySQL connection URL with URL-encoded password | `mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4` |
| `JWT_SECRET_KEY` | **Yes** | Secret key for signing admin and member JWT tokens | 32+ character random secret |
| `ADMIN_USERNAME` | **Yes** | Admin authentication username | `admin` |
| `ADMIN_PASSWORD` | **Yes** | Admin authentication password | High-entropy password |
| `F3_NATION_API_KEY` | Optional | API key for upstream F3 Nation schedule sync | `f3_...` |
| `SLACK_CLIENT_ID` | Optional | Slack App Client ID for Sign in with Slack | OAuth client ID |
| `SLACK_CLIENT_SECRET` | Optional | Slack App Client Secret for Sign in with Slack | OAuth client secret |
| `SLACK_BOT_TOKEN` | Optional | Slack Bot Token for backblast channel notifications | `xoxb-...` |
| `SLACK_BACKBLAST_CHANNEL_ID` | Optional | Channel ID for backblast notification cards | `C0123456789` |

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

---

## 7. Slack OAuth & Notification Configuration

### Slack App Permissions & Redirect URLs (api.slack.com/apps)
1. **OAuth & Permissions > Redirect URLs**:
   - Add frontend callback URLs:
     - `http://localhost:3000/auth/slack/callback` (or your local frontend dev port)
     - `https://dev.f3rva.org/auth/slack/callback`
     - `https://f3rva.org/auth/slack/callback`
   - Click **Save URLs**.
2. **OAuth & Permissions > Scopes**:
   - **Bot Token Scopes**:
     - `chat:write` (dispatches Block Kit backblast summaries to the backblast channel)
     - `users:read`
     - `users:read.email`
     - `users.profile:read`
   - **User Token Scopes**:
     - Leave **empty**.
   > [!IMPORTANT]
   > Do **NOT** add `openid`, `profile`, or `email` to Bot Token Scopes or User Token Scopes under Workspace Scopes. OpenID Connect scopes are requested dynamically during user sign-in via the authorize URL. Adding them to workspace token scopes will cause Slack to reject installation with `"Invalid permissions requested"`.
3. **Reinstall App**:
   - Click **Reinstall to Workspace** and authorize the updated bot scopes.

### AWS SSM Parameter Store Variables
Store the following parameters under `/f3rva/dev/` and `/f3rva/prod/`:

| Parameter Name | Description | Example Dev | Example Prod |
| :--- | :--- | :--- | :--- |
| `slack_client_id` | Slack App Client ID | `123456.dev...` | `123456.prod...` |
| `slack_client_secret` | Slack App Client Secret | `secret_dev...` | `secret_prod...` |
| `slack_bot_token` | Bot User OAuth Token (`xoxb-...`) | `xoxb-dev...` | `xoxb-prod...` |
| `slack_allowed_team_id` | Enforced Workspace Team ID | `T_DEV_123` | `T_PROD_456` |
| `slack_backblast_channel_id` | Slack Channel ID for Backblasts | `C_DEV_TEST` | `C_PROD_BACKBLASTS` |
| `backblast_url_prefix` | Base URL prefix for backblast permalinks | `https://dev.f3rva.org` | `https://f3rva.org` |

### Database DDL: `MEMBER_SLACK`
```sql
CREATE TABLE IF NOT EXISTS MEMBER_SLACK (
    MEMBER_ID INT NOT NULL,
    SLACK_TEAM_ID VARCHAR(32) NOT NULL,
    SLACK_USER_ID VARCHAR(32) NOT NULL,
    SLACK_DISPLAY_NAME VARCHAR(255) NULL,
    SLACK_REAL_NAME VARCHAR(255) NULL,
    SLACK_EMAIL VARCHAR(255) NULL,
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (SLACK_TEAM_ID, SLACK_USER_ID),
    KEY idx_member_slack_member_id (MEMBER_ID),
    CONSTRAINT fk_member_slack_member FOREIGN KEY (MEMBER_ID) REFERENCES MEMBER (MEMBER_ID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```
