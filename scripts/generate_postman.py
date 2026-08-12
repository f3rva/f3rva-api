"""Script to generate Postman Collection v2.1.0 JSON and Environment JSON files using apiBaseUrl."""

import json
import uuid

# Base collection structure
collection = {
    "info": {
        "_postman_id": str(uuid.uuid4()),
        "name": "F3 API",
        "description": "Complete Postman collection for the F3 modern Python serverless REST API (Phases 1 through 6). Configured to use Postman Environments (apiBaseUrl, authToken).",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [],
    "item": [
        {
            "name": "1. System & Health",
            "item": [
                {
                    "name": "Health Check",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/health",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["health"]
                        },
                        "description": "Returns operational status, API version, and runtime environment."
                    },
                    "response": []
                },
                {
                    "name": "Database Health Check",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/health/db",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["health", "db"]
                        },
                        "description": "Executes SELECT 1 against MySQL/SQLite database to verify connection health."
                    },
                    "response": []
                },
                {
                    "name": "OpenAPI JSON Specification",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/openapi.json",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["openapi.json"]
                        },
                        "description": "Retrieves the OpenAPI 3.1 JSON specification."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "2. Workouts & Backblasts",
            "item": [
                {
                    "name": "Get Recent Workouts (Paginated)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts?page=1&results=20",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts"],
                            "query": [
                                {"key": "page", "value": "1", "description": "Page number (1-indexed)"},
                                {"key": "results", "value": "20", "description": "Page size limit"}
                            ]
                        },
                        "description": "Returns recent workouts ordered by date descending with multiple AOs and Qs preserved."
                    },
                    "response": []
                },
                {
                    "name": "Filter Workouts by Date (Year, Month, Day)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts?year=2026&month=8&day=7",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts"],
                            "query": [
                                {"key": "year", "value": "2026", "description": "Filter by 4-digit year"},
                                {"key": "month", "value": "8", "description": "Filter by month (1-12)"},
                                {"key": "day", "value": "7", "description": "Filter by day (1-31, requires month)"}
                            ]
                        },
                        "description": "Filters workouts by hierarchical year, month, and exact day."
                    },
                    "response": []
                },
                {
                    "name": "Get Workout by ID",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts/101",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts", "101"]
                        },
                        "description": "Retrieves workout detail with full PAX roster and HTML content."
                    },
                    "response": []
                },
                {
                    "name": "Get Workout by Date and Slug",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts/2026-08-07/beatdown-at-gridiron",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts", "2026-08-07", "beatdown-at-gridiron"]
                        },
                        "description": "Retrieves workout by exact date (YYYY-MM-DD) and backblast slug."
                    },
                    "response": []
                },
                {
                    "name": "Get Workouts by AO Slug",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts/ao/dogpile?page=1&results=20",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts", "ao", "dogpile"],
                            "query": [
                                {"key": "page", "value": "1", "description": "Page number"},
                                {"key": "results", "value": "20", "description": "Results per page"}
                            ]
                        },
                        "description": "Retrieves workouts held at a specific AO slug (e.g. dogpile, gridiron, the-bridge)."
                    },
                    "response": []
                },
                {
                    "name": "Add Workout (Structured AO Objects)",
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "Content-Type", "value": "application/json", "type": "text"},
                            {"key": "Accept", "value": "application/json", "type": "text"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": "{\n  \"title\": \"Beatdown at First Watch\",\n  \"workoutDate\": \"2026-08-07\",\n  \"qic\": [\"Dingo\", \"Lab Rat\"],\n  \"pax\": [\"Dingo\", \"Lab Rat\", \"Splinter\", \"Swag\"],\n  \"aos\": [\n    {\n      \"name\": \"First Watch\",\n      \"slug\": \"first-watch\"\n    },\n    {\n      \"name\": \"Spider Run\",\n      \"slug\": \"spider-run\"\n    }\n  ],\n  \"body\": \"<p>100 burpees and 5 miles.</p>\",\n  \"url\": \"https://f3rva.org/2026/08/07/beatdown-at-first-watch\",\n  \"author\": \"Dingo\",\n  \"slug\": \"beatdown-at-first-watch\"\n}",
                            "options": {
                                "raw": {
                                    "language": "json"
                                }
                            }
                        },
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts"]
                        },
                        "description": "Creates a new workout record with structured AO objects (name + slug)."
                    },
                    "response": []
                },
                {
                    "name": "Delete Workout (Protected)",
                    "request": {
                        "method": "DELETE",
                        "auth": {
                            "type": "bearer",
                            "bearer": [
                                {"key": "token", "value": "{{authToken}}", "type": "string"}
                            ]
                        },
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/workouts/101",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "workouts", "101"]
                        },
                        "description": "Deletes a workout and all associated attendee and leader records. Requires admin JWT."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "3. Members & PAX Analytics",
            "item": [
                {
                    "name": "Get All Members",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/members",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "members"]
                        },
                        "description": "Returns full list of all F3 RVA members sorted alphabetically."
                    },
                    "response": []
                },
                {
                    "name": "Get Member Profile & Workout History",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/members/1",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "members", "1"]
                        },
                        "description": "Returns member profile with aliases, lifetime stats, attended workouts, and Q'd workouts."
                    },
                    "response": []
                },
                {
                    "name": "Get Member Lifetime Stats",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/members/1/stats",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "members", "1", "stats"]
                        },
                        "description": "Returns total workouts attended, total Qs, and computed Q-ratio."
                    },
                    "response": []
                },
                {
                    "name": "Lookup Member by Name or Alias",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/members/lookup?name=dingo",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "members", "lookup"],
                            "query": [
                                {"key": "name", "value": "dingo", "description": "Search query"}
                            ]
                        },
                        "description": "Performs case-insensitive member search across primary names and registered aliases."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "4. Reports, Leaderboards & AO Metrics",
            "item": [
                {
                    "name": "Attendance Leaderboard (Sorted by Workouts)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/attendance?sortBy=workouts&page=1&results=50",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "sortBy", "value": "workouts", "description": "Sort field (workouts, q, ratio)"},
                                {"key": "page", "value": "1", "description": "Page number"},
                                {"key": "results", "value": "50", "description": "Page size"}
                            ]
                        },
                        "description": "Leaderboard ranking all members by total workout attendance."
                    },
                    "response": []
                },
                {
                    "name": "Attendance Leaderboard (Sorted by Qs)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/attendance?sortBy=q&page=1&results=50",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "sortBy", "value": "q", "description": "Sort by Q count"},
                                {"key": "page", "value": "1", "description": "Page number"},
                                {"key": "results", "value": "50", "description": "Page size"}
                            ]
                        },
                        "description": "Leaderboard ranking members by number of workouts led as Q."
                    },
                    "response": []
                },
                {
                    "name": "Attendance Leaderboard (Date Range Filtered)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/attendance?startDate=2026-08-01&endDate=2026-08-31",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "startDate", "value": "2026-08-01", "description": "Start date (YYYY-MM-DD)"},
                                {"key": "endDate", "value": "2026-08-31", "description": "End date (YYYY-MM-DD)"}
                            ]
                        },
                        "description": "Leaderboard filtered to a custom date window."
                    },
                    "response": []
                },
                {
                    "name": "AO Attendance Summary",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/ao",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "ao"]
                        },
                        "description": "Summary of total workouts held and total attendee count across all AOs."
                    },
                    "response": []
                },
                {
                    "name": "AO Leaderboard with Streak Calculations",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/ao/1/leaderboard",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "ao", "1", "leaderboard"]
                        },
                        "description": "Member attendance leaderboard and active streaks for a specific AO."
                    },
                    "response": []
                },
                {
                    "name": "Day of Week Attendance Breakdown",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/day-of-week",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "day-of-week"]
                        },
                        "description": "Workouts and attendance distribution mapped by day of the week (Sunday through Saturday)."
                    },
                    "response": []
                },
                {
                    "name": "Member AO Attendance Distribution",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/reports/members/1/distribution",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "reports", "members", "1", "distribution"]
                        },
                        "description": "Attendance breakdown across different AOs for a specific member."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "5. Self-Service & Admin Workflows",
            "item": [
                {
                    "name": "Admin Login (Obtain JWT)",
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "exec": [
                                    "if (pm.response.code === 200) {",
                                    "    var jsonData = pm.response.json();",
                                    "    if (jsonData.accessToken) {",
                                    "        pm.environment.set('authToken', jsonData.accessToken);",
                                    "        console.log('Saved authToken to environment:', jsonData.accessToken);",
                                    "    }",
                                    "}"
                                ],
                                "type": "text/javascript"
                            }
                        }
                    ],
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "Content-Type", "value": "application/json", "type": "text"},
                            {"key": "Accept", "value": "application/json", "type": "text"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": "{\n  \"username\": \"admin\",\n  \"password\": \"change-me-admin-password\"\n}",
                            "options": {
                                "raw": {
                                    "language": "json"
                                }
                            }
                        },
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/admin/login",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "admin", "login"]
                        },
                        "description": "Authenticates admin credentials and returns an HS256 JWT Bearer token (auto-saved to {{authToken}} environment variable)."
                    },
                    "response": []
                },
                {
                    "name": "Submit Alias Claim Request (Self-Service)",
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "Content-Type", "value": "application/json", "type": "text"},
                            {"key": "Accept", "value": "application/json", "type": "text"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": "{\n  \"primaryMemberId\": 1,\n  \"aliasMemberId\": 2\n}",
                            "options": {
                                "raw": {
                                    "language": "json"
                                }
                            }
                        },
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/aliases/request",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "aliases", "request"]
                        },
                        "description": "Submits a request to merge an alias/duplicate member record into a primary member record."
                    },
                    "response": []
                },
                {
                    "name": "List Public Pending Alias Requests",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/aliases/requests",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "aliases", "requests"]
                        },
                        "description": "Public list of pending alias merge requests."
                    },
                    "response": []
                },
                {
                    "name": "List Admin Pending Alias Requests (Protected)",
                    "request": {
                        "method": "GET",
                        "auth": {
                            "type": "bearer",
                            "bearer": [
                                {"key": "token", "value": "{{authToken}}", "type": "string"}
                            ]
                        },
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/admin/aliases/requests",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "admin", "aliases", "requests"]
                        },
                        "description": "Admin review queue for pending alias claims. Requires admin JWT."
                    },
                    "response": []
                },
                {
                    "name": "Approve Alias Request & Merge (Protected)",
                    "request": {
                        "method": "POST",
                        "auth": {
                            "type": "bearer",
                            "bearer": [
                                {"key": "token", "value": "{{authToken}}", "type": "string"}
                            ]
                        },
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/admin/aliases/approve/1/2",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "admin", "aliases", "approve", "1", "2"]
                        },
                        "description": "Approves an alias claim request: moves workout history, creates alias, and audits merger."
                    },
                    "response": []
                },
                {
                    "name": "Reject Alias Request (Protected)",
                    "request": {
                        "method": "POST",
                        "auth": {
                            "type": "bearer",
                            "bearer": [
                                {"key": "token", "value": "{{authToken}}", "type": "string"}
                            ]
                        },
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/admin/aliases/reject/1/2",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "admin", "aliases", "reject", "1", "2"]
                        },
                        "description": "Rejects a pending alias claim request. Requires admin JWT."
                    },
                    "response": []
                },
                {
                    "name": "Direct Member Merge (Protected)",
                    "request": {
                        "method": "POST",
                        "auth": {
                            "type": "bearer",
                            "bearer": [
                                {"key": "token", "value": "{{authToken}}", "type": "string"}
                            ]
                        },
                        "header": [
                            {"key": "Content-Type", "value": "application/json", "type": "text"},
                            {"key": "Accept", "value": "application/json", "type": "text"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": "{\n  \"primaryMemberId\": 1,\n  \"aliasMemberId\": 2\n}",
                            "options": {
                                "raw": {
                                    "language": "json"
                                }
                            }
                        },
                        "url": {
                            "raw": "{{apiBaseUrl}}/v2/admin/members/merge",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["v2", "admin", "members", "merge"]
                        },
                        "description": "Directly merges duplicate member record into primary without prior self-service request. Requires admin JWT."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "6. Workout Schedule",
            "item": [
                {
                    "name": "Get Workout Schedule",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{apiBaseUrl}}/schedule",
                            "host": ["{{apiBaseUrl}}"],
                            "path": ["schedule"]
                        },
                        "description": "Fetches, transforms, and caches live F3 Nation workouts into the standard 1stF schedule format for f3rva-website."
                    },
                    "response": []
                }
            ]
        }
    ]
}

# Write postman_collection.json
with open("/Users/bbischoff/dev/f3/f3rva-api/postman_collection.json", "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)
print("Successfully generated postman_collection.json")

# Define Environment generator
def create_environment(name: str, base_url: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "values": [
            {
                "key": "apiBaseUrl",
                "value": base_url,
                "type": "default",
                "enabled": True
            },
            {
                "key": "authToken",
                "value": "",
                "type": "secret",
                "enabled": True
            }
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_using": "Postman/11.0.0"
    }

# Write Local, Dev, and Prod Environment JSON files
environments = {
    "/Users/bbischoff/dev/f3/f3rva-api/postman_environment_dev.json": ("F3 API - Development", "https://api.dev.f3rva.org"),
    "/Users/bbischoff/dev/f3/f3rva-api/postman_environment_prod.json": ("F3 API - Production", "https://api.f3rva.org"),
    "/Users/bbischoff/dev/f3/f3rva-api/postman_environment_local.json": ("F3 API - Local", "http://localhost:8000"),
}

for path, (env_name, url) in environments.items():
    with open(path, "w", encoding="utf-8") as f:
        json.dump(create_environment(env_name, url), f, indent=2)
    print(f"Successfully generated {path.split('/')[-1]}")
