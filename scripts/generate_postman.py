"""Script to generate a fully compliant Postman Collection v2.1.0 JSON."""

import json
import uuid

collection = {
    "info": {
        "_postman_id": str(uuid.uuid4()),
        "name": "F3 RVA API",
        "description": "Complete Postman collection for the F3 RVA modern Python serverless REST API (Phases 1 through 6).",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {
            "key": "baseUrl",
            "value": "http://localhost:8000",
            "type": "string",
            "description": "API Base URL (e.g. http://localhost:8000, https://api.dev.f3rva.org, https://api.f3rva.org)"
        },
        {
            "key": "authToken",
            "value": "",
            "type": "string",
            "description": "JWT Bearer token for protected admin endpoints (populated after /v2/admin/login)"
        }
    ],
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
                            "raw": "{{baseUrl}}/health",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/health/db",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/openapi.json",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts?page=1&results=20",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts?year=2026&month=8&day=7",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts/101",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts/2026-08-07/beatdown-at-gridiron",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts/ao/dogpile?page=1&results=20",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/workouts/101",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "workouts", "101"]
                        },
                        "description": "Atomically deletes a workout and cascades all junction associations. Requires admin JWT."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "3. Members & PAX Analytics",
            "item": [
                {
                    "name": "List All Members (Alphabetical)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/members",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "members"]
                        },
                        "description": "Returns all registered F3 members sorted alphabetically by name."
                    },
                    "response": []
                },
                {
                    "name": "Get Member Profile by ID",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/members/1",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "members", "1"]
                        },
                        "description": "Retrieves complete member profile including aliases, statistics, attended workouts, and Q'd workouts."
                    },
                    "response": []
                },
                {
                    "name": "Get Member Statistics by ID",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/members/1/stats",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "members", "1", "stats"]
                        },
                        "description": "Calculates member total attended workouts, total Qs, and computed Q-ratio."
                    },
                    "response": []
                },
                {
                    "name": "Lookup Member by Name or Alias",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/members/lookup?name=dingo",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "members", "lookup"],
                            "query": [
                                {"key": "name", "value": "dingo", "description": "Search query for primary name or registered alias"}
                            ]
                        },
                        "description": "Case-insensitive member search across primary names and aliases."
                    },
                    "response": []
                }
            ]
        },
        {
            "name": "4. Reports, Leaderboards & AO Metrics",
            "item": [
                {
                    "name": "PAX Attendance Leaderboard (Default: Workouts)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/attendance?sortBy=workout&limit=50",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "sortBy", "value": "workout", "description": "Sort criteria: 'workout', 'q', or 'ratio'"},
                                {"key": "limit", "value": "50", "description": "Maximum number of leaderboard results"}
                            ]
                        },
                        "description": "Ranked leaderboard of members by total workout attendances."
                    },
                    "response": []
                },
                {
                    "name": "PAX Attendance Leaderboard (Sorted by Qs)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/attendance?sortBy=q&limit=50",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "sortBy", "value": "q", "description": "Sort by total Q count"},
                                {"key": "limit", "value": "50", "description": "Limit"}
                            ]
                        },
                        "description": "Ranked leaderboard of members by total workouts led as Q."
                    },
                    "response": []
                },
                {
                    "name": "PAX Attendance Leaderboard (Date Range Filter)",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/attendance?startDate=2026-01-01&endDate=2026-12-31&sortBy=workout&limit=50",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "attendance"],
                            "query": [
                                {"key": "startDate", "value": "2026-01-01", "description": "Filter start date (YYYY-MM-DD)"},
                                {"key": "endDate", "value": "2026-12-31", "description": "Filter end date (YYYY-MM-DD)"},
                                {"key": "sortBy", "value": "workout", "description": "Sort criteria"},
                                {"key": "limit", "value": "50", "description": "Limit"}
                            ]
                        },
                        "description": "Calculates member leaderboard within an arbitrary date range."
                    },
                    "response": []
                },
                {
                    "name": "AO Attendance Averages",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/ao",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "ao"]
                        },
                        "description": "Lists all AOs sorted by average PAX attendance per workout."
                    },
                    "response": []
                },
                {
                    "name": "AO Leaderboard & Streakers",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/ao/1/leaderboard?limit=10",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "ao", "1", "leaderboard"],
                            "query": [
                                {"key": "limit", "value": "10", "description": "Leaderboard limit"}
                            ]
                        },
                        "description": "Retrieves Top Qs, Top Attendees, and active consecutive attendance streaks at an AO."
                    },
                    "response": []
                },
                {
                    "name": "Day of Week Attendance Breakdown",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/day-of-week",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "day-of-week"]
                        },
                        "description": "Aggregates workouts and attendee counts across Sunday through Saturday."
                    },
                    "response": []
                },
                {
                    "name": "Member AO Attendance Distribution",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json", "type": "text"}],
                        "url": {
                            "raw": "{{baseUrl}}/v2/reports/members/1/distribution",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "reports", "members", "1", "distribution"]
                        },
                        "description": "Breakdown of workouts attended and Q'd across all AOs for a specific member."
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
                                    "        pm.collectionVariables.set('authToken', jsonData.accessToken);",
                                    "        console.log('Saved authToken:', jsonData.accessToken);",
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
                            "raw": "{{baseUrl}}/v2/admin/login",
                            "host": ["{{baseUrl}}"],
                            "path": ["v2", "admin", "login"]
                        },
                        "description": "Authenticates admin credentials and returns an HS256 JWT Bearer token (auto-saved to {{authToken}} variable)."
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
                            "raw": "{{baseUrl}}/v2/aliases/request",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/aliases/requests",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/admin/aliases/requests",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/admin/aliases/approve/1/2",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/admin/aliases/reject/1/2",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/v2/admin/members/merge",
                            "host": ["{{baseUrl}}"],
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
                            "raw": "{{baseUrl}}/schedule",
                            "host": ["{{baseUrl}}"],
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

with open("/Users/bbischoff/dev/f3/f3rva-api/postman_collection.json", "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)

print("Successfully wrote postman_collection.json")
