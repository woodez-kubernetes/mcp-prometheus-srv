# Local Testing Guide

How to run the MCP Prometheus server locally and connect Claude Desktop to it.

## Prerequisites

- Python 3.14+ with the project's virtual environment set up (Stage 1)
- Prometheus running at `http://localhost:9090` (or set `PROMETHEUS_URL` in `.env`)

## 1. Start the MCP Server

```bash
# Activate the virtual environment
source venv/bin/activate

# Run database migrations (first time only)
python manage.py migrate

# Start the ASGI server
uvicorn mcp_prometheus.asgi:application --host 127.0.0.1 --port 8000
```

The MCP endpoint will be available at `http://localhost:8000/mcp`.

### Verify it's running

```bash
# In another terminal — check the endpoint responds
curl -s http://localhost:8000/mcp | head -c 200
```

### Inspect registered tools/resources/prompts

```bash
source venv/bin/activate
python manage.py mcp_inspect
```

## 2. Configure Claude Desktop

Open Claude Desktop settings:

**Settings > Developer > Edit Config**

This opens `claude_desktop_config.json`. Add the MCP server entry:

### Option A: Streamable HTTP (recommended)

Connect Claude Desktop directly to the running server over HTTP:

```json
{
  "mcpServers": {
    "mcp-prometheus": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

> Requires the server to be running (`uvicorn` from step 1).

### Option B: stdio transport

Claude Desktop launches the server itself via `manage.py stdio_server`:

```json
{
  "mcpServers": {
    "mcp-prometheus": {
      "command": "/Users/kwood/projects/coding-repos/mcp-prometheus-srv/venv/bin/python",
      "args": [
        "/Users/kwood/projects/coding-repos/mcp-prometheus-srv/manage.py",
        "stdio_server"
      ],
      "env": {
        "PROMETHEUS_URL": "http://localhost:9090"
      }
    }
  }
}
```

> No need to start `uvicorn` manually — Claude Desktop manages the process.

### After editing config

1. Save the file.
2. Restart Claude Desktop.
3. The MCP server should appear in the tools list. You should see tools like `query_instant`, `list_metrics`, `get_alerts`, etc.

## 3. Test with Claude Desktop

Try these prompts to verify everything works:

- "What Prometheus targets are currently being scraped?"
- "List all available metrics"
- "Run the query `up` and tell me which targets are healthy"
- "Check if any alerts are firing"

Or use one of the built-in prompts:

- Select the `k8s_cluster_health` prompt for a full cluster health assessment.
- Select `k8s_alert_triage` to triage any firing alerts.

## 4. Run the MCP Client Test Script

As an alternative to Claude Desktop, use the standalone test script:

```bash
# Terminal 1: start the server
source venv/bin/activate
uvicorn mcp_prometheus.asgi:application --host 127.0.0.1 --port 8000

# Terminal 2: run the client test
source venv/bin/activate
python scripts/mcp_client_test.py
```

This connects to `http://localhost:8000/mcp`, lists all tools/resources/prompts,
calls each tool, and reads each resource.

## 5. Run Integration Tests

If Prometheus is running locally:

```bash
source venv/bin/activate
PROMETHEUS_INTEGRATION=1 python -m pytest prometheus_tools/tests/test_integration.py -v
```

## 6. Docker

### Build the image

```bash
docker build -t mcp-prometheus .
```

### Run the container

```bash
docker run --rm \
  -e PROMETHEUS_URL=http://host.docker.internal:9090 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=mcp_prometheus \
  -e DB_USER=mcp_prometheus \
  -e DB_PASSWORD=mcp_prometheus \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -p 8000:8000 \
  mcp-prometheus
```

> `host.docker.internal` lets the container reach services on the host machine (Prometheus, PostgreSQL).

### Tag and push to DockerHub

```bash
docker tag mcp-prometheus <your-dockerhub-user>/mcp-prometheus:latest
docker push <your-dockerhub-user>/mcp-prometheus:latest
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Connection refused` on port 8000 | Make sure `uvicorn` is running (step 1) |
| `Connection refused` on port 9090 | Start Prometheus or update `PROMETHEUS_URL` in `.env` |
| Tools don't appear in Claude Desktop | Restart Claude Desktop after editing config |
| `ModuleNotFoundError` | Activate the virtual environment: `source venv/bin/activate` |
| Server starts but tools return errors | Verify Prometheus is reachable: `curl http://localhost:9090/-/healthy` |
