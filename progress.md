# MCP Prometheus Server — Progress

## Stage 1: Project Scaffolding & Dependencies — COMPLETED

**Status:** Done

### What was done

1. **Virtual environment** — Created `venv/` with Python 3.
2. **Dependencies installed:**
   - Django 6.0.2
   - djangorestframework 3.16.1
   - django-mcp-server 0.5.7
   - httpx 0.28.1
   - uvicorn 0.40.0
   - python-dotenv 1.2.1
3. **Django project generated** — `mcp_prometheus/` (project) and `prometheus_tools/` (app).
4. **`settings.py` configured:**
   - Added `rest_framework`, `mcp_server`, `prometheus_tools` to `INSTALLED_APPS`.
   - `PROMETHEUS_URL` setting (default `http://localhost:9090`, env-overridable).
   - `DJANGO_MCP_GLOBAL_SERVER_CONFIG` with server name and instructions.
   - `ASGI_APPLICATION` set for async support.
   - `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` all read from environment with safe defaults.
5. **URL config** — MCP endpoint mounted at `/mcp` via `mcp_server.urls`.
6. **`requirements.txt`** — Pinned top-level dependency versions.
7. **Scaffold files created:**
   - `prometheus_tools/services.py` — `PrometheusClient` class stub.
   - `prometheus_tools/mcp.py` — MCP tool/resource/prompt import scaffold.
8. **`.env.example`** — Template for environment variables.

### Verification

- `manage.py check` — 0 issues.
- `manage.py mcp_inspect` — MCP server operational, base `get_server_instructions` tool registered.

---

## Stage 2: Prometheus Client Service Layer — COMPLETED

**Status:** Done

### What was done

1. **`PrometheusClient` class** (`prometheus_tools/services.py`):
   - Async HTTP client using `httpx.AsyncClient` for all Prometheus API calls.
   - Reads `PROMETHEUS_URL` from Django settings (configured in Stage 1).
   - Central `_get()` helper that handles all GET requests, parses the Prometheus JSON
     envelope, extracts the `data` field, and raises `PrometheusError` on failures.

2. **9 async methods implemented**, one per Prometheus API endpoint:
   - `instant_query(query, time?, timeout?)` — `GET /api/v1/query`
   - `range_query(query, start, end, step, timeout?)` — `GET /api/v1/query_range`
   - `list_series(match, start?, end?)` — `GET /api/v1/series`
   - `get_labels(match?)` — `GET /api/v1/labels`
   - `get_label_values(label_name, match?)` — `GET /api/v1/label/<name>/values`
   - `get_targets(state?)` — `GET /api/v1/targets`
   - `get_alerts()` — `GET /api/v1/alerts`
   - `get_rules(type?)` — `GET /api/v1/rules`
   - `get_metric_metadata(metric?, limit?)` — `GET /api/v1/targets/metadata`

3. **`PrometheusError` exception class** — carries `status_code`, `error_type`, and
   `message` for LLM-readable error reporting.

4. **`health()` method** — connection check via `GET /-/healthy`.

5. **Unit tests** (`prometheus_tools/tests/test_services.py`):
   - 18 tests covering all methods, success paths, HTTP errors, and Prometheus-level errors.
   - All tests use mocked `httpx` responses (no live Prometheus required).

6. **Test infrastructure added:**
   - `pytest`, `pytest-django`, `pytest-asyncio` installed.
   - `pytest.ini` configured with `DJANGO_SETTINGS_MODULE` and `asyncio_mode = auto`.

### Verification

- `pytest prometheus_tools/tests/test_services.py -v` — **18 passed** in 0.05s.

---

## Stage 3: MCP Tool Definitions — COMPLETED

**Status:** Done

### What was done

1. **10 MCP tools defined** in `prometheus_tools/mcp.py` using `@mcp.tool()` decorators:

   | # | Tool | Calls | Parameters |
   |---|------|-------|------------|
   | 1 | `query_instant` | `client.instant_query` | `query`, `time?` |
   | 2 | `query_range` | `client.range_query` | `query`, `start`, `end`, `step` |
   | 3 | `list_metrics` | `client.get_label_values("__name__")` | — |
   | 4 | `get_metric_metadata` | `client.get_metric_metadata` | `metric?` |
   | 5 | `list_labels` | `client.get_labels` | — |
   | 6 | `get_label_values` | `client.get_label_values` | `label_name` |
   | 7 | `find_series` | `client.list_series` | `match` (list) |
   | 8 | `get_targets` | `client.get_targets` | — |
   | 9 | `get_alerts` | `client.get_alerts` | — |
   | 10 | `get_rules` | `client.get_rules` | `type?` |

2. **Error handling** — all tools catch `PrometheusError` and return a structured
   `{error, error_type, message, status_code}` dict so the LLM can reason about failures.

3. **LLM-oriented docstrings** — each tool has a clear description surfaced to the LLM
   via MCP, including common K8s PromQL examples for `query_instant` and `query_range`.

4. **`list_metrics` implementation** — uses `get_label_values("__name__")` which is the
   idiomatic Prometheus way to list all metric names.

### Verification

- `manage.py mcp_inspect` — 11 tools registered (10 custom + `get_server_instructions`).
- All tool parameters, types, and descriptions correctly exposed.
- Stage 2 tests still pass — **18 passed**.

---

## Stage 4: LLM-Friendly Response Formatting — COMPLETED

**Status:** Done

### What was done

1. **`formatters.py`** (`prometheus_tools/formatters.py`) — 5 formatter functions:

   | Formatter | Input | Output |
   |-----------|-------|--------|
   | `format_vector` | Instant query result | `{metric_name, labels, value, timestamp}` per series |
   | `format_matrix` | Range query result | `{metric_name, labels, num_samples, first_value, last_value, min, max, avg, time_range}` per series |
   | `format_targets` | Targets response | `{job, instance, health, last_scrape, scrape_duration}` + summary counts |
   | `format_alerts` | Alerts response | `{alertname, state, severity, summary, active_since}` + firing/pending counts |
   | `format_rules` | Rules response | Flattened `{name, group, type, query, health, last_evaluation}` + alerting/recording counts |

2. **Truncation** — all formatters accept `max_results` (default 50) and attach a
   `truncation` object when results are capped, telling the LLM how many results
   exist and suggesting to narrow the query.

3. **Integrated into MCP tools** — `query_instant`, `query_range`, `get_targets`,
   `get_alerts`, and `get_rules` now return formatted responses.

4. **14 new formatter tests** in `prometheus_tools/tests/test_formatters.py`:
   - Basic formatting, empty data, truncation, missing fields, summary counts.

### Verification

- `pytest prometheus_tools/tests/ -v` — **32 passed** (18 services + 14 formatters).

---

## Stage 5: MCP Resources (Read-Only Context) — COMPLETED

**Status:** Done

### What was done

1. **`get_build_info()` method** added to `PrometheusClient` — calls
   `GET /api/v1/status/buildinfo` to retrieve Prometheus version/build details.

2. **4 MCP resources defined** in `prometheus_tools/mcp.py` using `@mcp.resource()`:

   | Resource URI | Description | Data Source |
   |-------------|-------------|-------------|
   | `prometheus://status` | Prometheus build info + health | `get_build_info()` + `health()` |
   | `prometheus://targets/summary` | Scrape targets with health summary | `get_targets()` → `format_targets()` |
   | `prometheus://alerts/active` | Currently firing alerts | `get_alerts()` → `format_alerts()` |
   | `prometheus://metrics/catalog` | All metric names with TYPE/HELP/UNIT metadata | `get_label_values("__name__")` + `get_metric_metadata()` |

3. **Resources return JSON strings** — each resource function returns `json.dumps()`
   with `indent=2` for readability. All resources gracefully handle `PrometheusError`.

4. **`prometheus://metrics/catalog`** joins metric names with their metadata to produce
   a unified catalog with `{name, type, help, unit}` per metric.

### Verification

- `manage.py mcp_inspect` — 4 resources registered alongside 11 tools.
- All 32 existing tests still pass.

---

## Stage 6: Kubernetes-Specific Prompt Templates — COMPLETED

**Status:** Done

### What was done

1. **5 MCP prompts defined** in `prometheus_tools/mcp.py` using `@mcp.prompt()`:

   | Prompt | Parameters | Workflow |
   |--------|-----------|----------|
   | `k8s_cluster_health` | — | Targets, alerts, node readiness, pod phases, restart storms, CPU/memory pressure |
   | `k8s_pod_troubleshoot` | `namespace`, `pod` | Pod phase, readiness, restarts, OOMKilled, CPU/memory usage, throttling |
   | `k8s_resource_usage` | `namespace?` | CPU/memory usage vs requests by namespace, top 10 pods |
   | `k8s_alert_triage` | — | Get alerts + rules, evaluate each alert's expression, check trends, prioritise |
   | `k8s_node_capacity` | — | Node conditions, capacity vs allocatable, allocation ratios, actual usage |

2. Each prompt returns a structured message with **numbered steps** guiding the LLM to:
   - Call the appropriate MCP tools in sequence.
   - Use specific PromQL queries tailored to common K8s metrics.
   - Summarise findings and recommend actions.

3. `k8s_pod_troubleshoot` and `k8s_resource_usage` accept parameters to scope queries
   to a specific namespace/pod, injecting the values into PromQL selectors.

### Verification

- `manage.py mcp_inspect` — 5 prompts registered alongside 11 tools and 4 resources.
- All 32 existing tests still pass.

---

## Stage 7: Testing & Validation — COMPLETED

**Status:** Done

### What was done

1. **Tool unit tests** (`prometheus_tools/tests/test_tools.py`) — 14 new tests:
   - Tests all 10 MCP tool functions with mocked `PrometheusClient`.
   - Verifies formatted output shapes (vector → `results[]`, matrix → `results[]` with stats,
     targets/alerts/rules → `summary` + formatted lists).
   - Verifies error handling returns structured `{error, error_type, message}` dicts.
   - Verifies correct arguments are forwarded to the client.

2. **Integration tests** (`prometheus_tools/tests/test_integration.py`) — 17 tests:
   - Skipped by default — run with `--run-integration` flag or `PROMETHEUS_INTEGRATION=1` env var.
   - `TestClientIntegration` — exercises all `PrometheusClient` methods against a live
     Prometheus (health, instant/range queries, labels, targets, alerts, rules, build info,
     bad PromQL error handling).
   - `TestToolIntegration` — exercises MCP tool functions end-to-end against live Prometheus.

3. **MCP client test script** (`scripts/mcp_client_test.py`):
   - Standalone async script using the `mcp` Python SDK.
   - Connects to `http://localhost:8000/mcp` via streamable HTTP transport.
   - Lists all tools, resources, and prompts.
   - Calls each tool and reads each resource, printing pass/fail status.
   - Usage: start the server with `uvicorn`, then `python scripts/mcp_client_test.py`.

### Test Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_services.py` | 18 | All pass |
| `test_formatters.py` | 14 | All pass |
| `test_tools.py` | 14 | All pass |
| `test_integration.py` | 17 | Skipped (no live Prometheus) |
| **Total** | **63** | **46 passed, 17 skipped** |

### Verification

- `pytest prometheus_tools/tests/ -v` — **46 passed, 17 skipped** in 0.08s.

---

## PostgreSQL Database Migration — COMPLETED

**Status:** Done

### What was done

1. **Created PostgreSQL user and database** (connecting as `postgres` on `localhost:5432`):
   - `CREATE USER mcp_prometheus WITH PASSWORD 'mcp_prometheus'`
   - `CREATE DATABASE mcp_prometheus OWNER mcp_prometheus`
   - `GRANT ALL PRIVILEGES ON DATABASE mcp_prometheus TO mcp_prometheus`

2. **Installed `psycopg2-binary` 2.9.11** — PostgreSQL adapter for Python.

3. **Updated `settings.py`** — switched `DATABASES['default']` from SQLite to PostgreSQL:
   - Engine: `django.db.backends.postgresql`
   - All connection params configurable via env vars (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) with defaults matching the newly created database.

4. **Updated `.env.example`** — added `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

5. **Updated `requirements.txt`** — added `psycopg2-binary==2.9.11`.

6. **Ran all Django migrations** against PostgreSQL — 18 migrations applied successfully.

### Verification

- `manage.py check` — 0 issues.
- `pytest` — **46 passed, 17 skipped** (all existing tests still pass).

---

## Stage 8: Configuration, Security & Deployment Hardening — PENDING
