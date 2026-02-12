# MCP Prometheus Server — Implementation Plan

An MCP (Model Context Protocol) server built with Django and Django REST Framework that
exposes Prometheus metrics at `localhost:9090` as tools and resources for LLM agents.

---

## Stage 1: Project Scaffolding & Dependencies

**Goal:** Bootstrap the Django project, virtual environment, and install all dependencies.

### Tasks

1. Create a Python virtual environment and activate it.
2. Install core dependencies:
   - `django` — web framework
   - `djangorestframework` — API layer
   - `django-mcp-server` — MCP protocol integration (wraps the official `mcp` Python SDK and provides Django-native tool/resource decorators)
   - `httpx` — async HTTP client for Prometheus API calls
   - `uvicorn` — ASGI server (required for async MCP transport)
3. Generate the Django project (`mcp_prometheus`) and app (`prometheus_tools`).
4. Configure `settings.py`:
   - Add `rest_framework`, `mcp_server`, and `prometheus_tools` to `INSTALLED_APPS`.
   - Set `DJANGO_MCP_GLOBAL_SERVER_CONFIG` with server name and instructions.
   - Define `PROMETHEUS_URL = "http://localhost:9090"` as a project-level setting.
   - Configure ASGI application for `uvicorn`.
5. Wire up URL config — mount the MCP endpoint at `/mcp`.
6. Add a `requirements.txt` (or `pyproject.toml`) pinning all versions.

### Deliverables

```
mcp_prometheus/
  settings.py
  urls.py
  asgi.py
  wsgi.py
prometheus_tools/
  __init__.py
  apps.py
  mcp.py          # tool definitions (empty scaffold)
  services.py     # Prometheus client (empty scaffold)
requirements.txt
manage.py
```

---

## Stage 2: Prometheus Client Service Layer

**Goal:** Build a reusable async service class that wraps the Prometheus HTTP API.

### Prometheus HTTP API Endpoints to Support

| Capability            | Prometheus Endpoint                        |
|-----------------------|--------------------------------------------|
| Instant query         | `GET /api/v1/query`                        |
| Range query           | `GET /api/v1/query_range`                  |
| List metrics (series) | `GET /api/v1/series`                       |
| Label names           | `GET /api/v1/labels`                       |
| Label values          | `GET /api/v1/label/<name>/values`          |
| Targets               | `GET /api/v1/targets`                      |
| Active alerts         | `GET /api/v1/alerts`                       |
| Alerting/recording rules | `GET /api/v1/rules`                     |
| Metric metadata       | `GET /api/v1/targets/metadata`             |

### Tasks

1. Create `prometheus_tools/services.py` with a `PrometheusClient` class.
2. Use `httpx.AsyncClient` for all HTTP calls to Prometheus.
3. Read `PROMETHEUS_URL` from Django settings.
4. Implement one async method per endpoint above, e.g.:
   - `async def instant_query(query: str, time: str | None = None) -> dict`
   - `async def range_query(query: str, start: str, end: str, step: str) -> dict`
   - `async def list_series(match: list[str], start: str | None, end: str | None) -> dict`
   - `async def get_labels() -> list[str]`
   - `async def get_label_values(label_name: str) -> list[str]`
   - `async def get_targets() -> dict`
   - `async def get_alerts() -> dict`
   - `async def get_rules() -> dict`
   - `async def get_metric_metadata(metric: str | None = None) -> dict`
5. Implement consistent error handling — translate Prometheus error responses (400, 422, 503) into clear error messages the LLM can reason about.
6. Add a connection-check helper (`async def health() -> bool`).

### Deliverables

- `prometheus_tools/services.py` — fully functional async Prometheus client.
- Unit tests with mocked HTTP responses in `prometheus_tools/tests/test_services.py`.

---

## Stage 3: MCP Tool Definitions

**Goal:** Register MCP tools that LLMs can invoke to query Prometheus.

Tools are the primary MCP primitive here — they let the LLM *execute actions* (run queries).
Each tool maps to one or more Prometheus client methods from Stage 2.

### Tool Inventory

| # | Tool Name               | Description                                                        | Key Parameters                              |
|---|-------------------------|--------------------------------------------------------------------|---------------------------------------------|
| 1 | `query_instant`         | Run a PromQL instant query                                         | `query`, `time` (optional)                  |
| 2 | `query_range`           | Run a PromQL range query over a time window                        | `query`, `start`, `end`, `step`             |
| 3 | `list_metrics`          | List all available metric names                                    | —                                           |
| 4 | `get_metric_metadata`   | Get TYPE, HELP, and UNIT for one or all metrics                    | `metric` (optional)                         |
| 5 | `list_labels`           | List all label names present in the data                           | —                                           |
| 6 | `get_label_values`      | Get all values for a specific label                                | `label_name`                                |
| 7 | `find_series`           | Find time series matching label selectors                          | `match` (list of selectors)                 |
| 8 | `get_targets`           | Show all scrape targets and their health status                    | —                                           |
| 9 | `get_alerts`            | List all currently firing alerts                                   | —                                           |
| 10| `get_rules`             | List alerting and recording rules                                  | `type` (optional: `alert` or `record`)      |

### Tasks

1. Create `prometheus_tools/mcp.py`.
2. Import `mcp_server.mcp_server as mcp` and define each tool using the `@mcp.tool()` decorator.
3. Each tool function:
   - Is `async`.
   - Has a clear docstring describing what it does and when the LLM should use it (this is surfaced to the LLM via MCP tool descriptions).
   - Uses typed parameters with defaults where sensible.
   - Calls the appropriate `PrometheusClient` method.
   - Returns structured data (dict/list) that `django-mcp-server` serializes to JSON.
4. For `query_instant` and `query_range`, include docstring examples of common PromQL patterns for Kubernetes metrics:
   - `container_cpu_usage_seconds_total`
   - `container_memory_working_set_bytes`
   - `kube_pod_status_phase`
   - `up` (target health)
5. Verify tools are registered via `python manage.py mcp_inspect`.

### Example Tool Definition

```python
from mcp_server import mcp_server as mcp
from .services import PrometheusClient

client = PrometheusClient()

@mcp.tool()
async def query_instant(query: str, time: str | None = None) -> dict:
    """Execute a PromQL instant query against Prometheus.

    Use this tool to get the current value of any Prometheus metric.

    Args:
        query: A PromQL expression, e.g. 'up', 'rate(http_requests_total[5m])'
        time:  Optional RFC3339 or Unix timestamp. Defaults to current time.

    Returns:
        Query result with 'resultType' and 'result' keys.
    """
    return await client.instant_query(query=query, time=time)
```

### Deliverables

- `prometheus_tools/mcp.py` — all 10 tool definitions.
- Tools visible via `manage.py mcp_inspect`.

---

## Stage 4: LLM-Friendly Response Formatting

**Goal:** Post-process Prometheus API responses into concise, LLM-readable formats.

Raw Prometheus responses can be verbose (large result sets, deep nesting). This stage
adds a formatting layer so the LLM gets clean, summarised data.

### Tasks

1. Create `prometheus_tools/formatters.py`.
2. Implement formatters for each result type:
   - **Vector results** — tabulate as `{metric_name, labels, value, timestamp}`.
   - **Matrix results** — summarise with `{metric_name, labels, num_samples, first_value, last_value, min, max, avg}`.
   - **Targets** — flatten to `{job, instance, health, last_scrape, scrape_duration}`.
   - **Alerts** — flatten to `{alertname, state, severity, summary, active_since}`.
   - **Rules** — flatten to `{name, type, query, health, last_evaluation}`.
3. Add a `max_results` cap (default 50) with a note to the LLM about truncation.
4. Integrate formatters into tool functions from Stage 3.
5. For very large responses, return data as an embedded MCP resource (using `output_as_resource`) so the LLM can reference it without blowing up the context window.

### Deliverables

- `prometheus_tools/formatters.py`
- Updated tool functions returning formatted responses.
- Tests in `prometheus_tools/tests/test_formatters.py`.

---

## Stage 5: MCP Resources (Read-Only Context)

**Goal:** Expose Prometheus metadata as MCP resources the LLM can read for context.

Resources are the "read" side of MCP — they give the LLM reference information
without requiring a tool call.

### Resource Inventory

| Resource URI                        | Description                                |
|-------------------------------------|--------------------------------------------|
| `prometheus://status`               | Prometheus build info and runtime status    |
| `prometheus://targets/summary`      | Summary of all scrape targets and health    |
| `prometheus://alerts/active`        | Currently firing alerts                     |
| `prometheus://metrics/catalog`      | Full list of metric names with descriptions |

### Tasks

1. Add resource definitions in `prometheus_tools/mcp.py` using `@mcp.resource()`.
2. Each resource returns a snapshot of the relevant Prometheus state.
3. Resources are refreshed on each read (no caching in this stage).

### Deliverables

- Resource definitions in `prometheus_tools/mcp.py`.
- Verified via `manage.py mcp_inspect`.

---

## Stage 6: Kubernetes-Specific Prompt Templates

**Goal:** Provide pre-built MCP prompts that guide the LLM through common Kubernetes
observability workflows.

### Prompt Inventory

| Prompt Name              | Description                                                  |
|--------------------------|--------------------------------------------------------------|
| `k8s_cluster_health`     | Step-by-step cluster health assessment                       |
| `k8s_pod_troubleshoot`   | Diagnose why a specific pod is unhealthy                     |
| `k8s_resource_usage`     | Analyse CPU/memory usage across namespaces                   |
| `k8s_alert_triage`       | Triage currently firing alerts                               |
| `k8s_node_capacity`      | Evaluate node resource capacity and allocation               |

### Tasks

1. Define prompts using `@mcp.prompt()` in `prometheus_tools/mcp.py`.
2. Each prompt returns a structured list of messages that guide the LLM to use the
   appropriate tools in sequence.
3. Include the relevant PromQL queries as suggestions within the prompt messages.

### Example

```python
@mcp.prompt()
async def k8s_pod_troubleshoot(namespace: str, pod: str) -> list[dict]:
    """Diagnose why a specific Kubernetes pod is unhealthy."""
    return [
        {"role": "user", "content": f"""Diagnose pod {pod} in namespace {namespace}:
1. Check pod phase: query_instant('kube_pod_status_phase{{namespace="{namespace}",pod="{pod}"}} == 1')
2. Check restarts: query_instant('kube_pod_container_status_restarts_total{{namespace="{namespace}",pod="{pod}"}}')
3. Check CPU: query_range('rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod="{pod}"}}[5m])', ...)
4. Check memory: query_instant('container_memory_working_set_bytes{{namespace="{namespace}",pod="{pod}"}}')
5. Check OOMKilled: query_instant('kube_pod_container_status_last_terminated_reason{{namespace="{namespace}",pod="{pod}",reason="OOMKilled"}}')
Summarise findings and recommend actions."""}
    ]
```

### Deliverables

- Prompt definitions in `prometheus_tools/mcp.py`.
- Verified via `manage.py mcp_inspect`.

---

## Stage 7: Testing & Validation

**Goal:** End-to-end testing of the MCP server with a real Prometheus instance.

### Tasks

1. **Unit tests** (mocked Prometheus):
   - All `PrometheusClient` methods with mocked `httpx` responses.
   - All formatters with sample Prometheus JSON payloads.
   - All tool functions returning expected output shapes.
2. **Integration tests** (requires Prometheus at `localhost:9090`):
   - Django test client hitting the MCP endpoint.
   - Verify tool invocations return valid data.
   - Verify resources return valid data.
   - Test error handling (bad PromQL, unreachable Prometheus).
3. **MCP client test** — script using `mcp` Python SDK to:
   - Connect to `http://localhost:8000/mcp`.
   - List tools, resources, and prompts.
   - Call each tool and verify the response.
4. **Claude Desktop manual test**:
   - Configure Claude Desktop to connect to the server.
   - Verify tools appear and can be invoked conversationally.

### Deliverables

- `prometheus_tools/tests/test_services.py`
- `prometheus_tools/tests/test_formatters.py`
- `prometheus_tools/tests/test_tools.py`
- `prometheus_tools/tests/test_integration.py`
- `scripts/mcp_client_test.py`

---

## Stage 8: Configuration, Security & Deployment Hardening

**Goal:** Make the server production-ready and configurable.

### Tasks

1. **Environment-based configuration**:
   - `PROMETHEUS_URL` from env var (default `http://localhost:9090`).
   - `MCP_MAX_RESULTS` — configurable result truncation limit.
   - `MCP_ALLOWED_ORIGINS` — CORS settings for the MCP endpoint.
   - Django `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` from env.
2. **Authentication** (optional, off by default):
   - Token authentication via DRF `TokenAuthentication`.
   - Configure via `DJANGO_MCP_AUTHENTICATION_CLASSES`.
3. **Rate limiting**:
   - Add `django-ratelimit` or DRF throttling to prevent LLM query loops.
4. **Query safety**:
   - Optional PromQL allowlist/blocklist to prevent expensive queries.
   - Query timeout enforcement (pass `timeout` param to Prometheus).
5. **Docker setup**:
   - `Dockerfile` for the MCP server.
   - `docker-compose.yml` including both Prometheus and the MCP server.
6. **Documentation**:
   - Update `README.md` with setup, configuration, and usage instructions.
   - Document all available tools, resources, and prompts.

### Deliverables

- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- Updated `README.md`
- Security middleware configuration in `settings.py`.

---

## Final Project Structure

```
mcp-prometheus-srv/
├── manage.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── mcp_prometheus/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── prometheus_tools/
    ├── __init__.py
    ├── apps.py
    ├── mcp.py              # MCP tools, resources, and prompts
    ├── services.py          # Async Prometheus HTTP client
    ├── formatters.py        # LLM-friendly response formatters
    └── tests/
        ├── __init__.py
        ├── test_services.py
        ├── test_formatters.py
        ├── test_tools.py
        └── test_integration.py
```

---

## Dependency Summary

| Package                | Purpose                                    |
|------------------------|--------------------------------------------|
| `django`               | Web framework                              |
| `djangorestframework`  | API layer, serializers, authentication     |
| `django-mcp-server`    | MCP protocol integration for Django        |
| `httpx`                | Async HTTP client for Prometheus API       |
| `uvicorn`              | ASGI server for async MCP transport        |
| `python-dotenv`        | Environment variable management            |
| `pytest` / `pytest-django` / `pytest-asyncio` | Testing framework   |

---

## Implementation Order & Dependencies

```
Stage 1 (Scaffolding)
  └─> Stage 2 (Prometheus Client)
        └─> Stage 3 (MCP Tools)
              ├─> Stage 4 (Response Formatting)
              ├─> Stage 5 (MCP Resources)
              └─> Stage 6 (K8s Prompts)
                    └─> Stage 7 (Testing)
                          └─> Stage 8 (Hardening & Deployment)
```

Stages 4, 5, and 6 can be developed in parallel once Stage 3 is complete.
