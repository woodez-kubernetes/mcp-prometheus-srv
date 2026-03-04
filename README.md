# MCP Prometheus Server

## What Is This?

This application lets an AI assistant (like Claude) monitor the health of our Kubernetes infrastructure by giving it access to Prometheus — the system that collects performance and health metrics from all of our servers and applications.

Normally, checking on infrastructure health requires an engineer to log into Prometheus, write specialised queries, and interpret the raw data. This app removes that barrier. You can simply ask Claude questions in plain English like:

- "Are all our services healthy?"
- "Which pods are using the most memory?"
- "Are there any alerts firing right now?"
- "What happened to the checkout service in the last hour?"

Claude uses this app behind the scenes to fetch the answers from Prometheus, summarise the data, and report back in a way anyone can understand.

## How Does It Work?

The app sits between Claude and Prometheus as a translator:

```
You ask Claude a question
        ↓
Claude calls this app
        ↓
The app queries Prometheus for the raw data
        ↓
The app summarises the data into a concise format
        ↓
Claude reads the summary and responds in plain English
```

The app provides Claude with **tools** (actions it can take, like running a query or checking alerts), **resources** (background context like cluster status), and **prompts** (step-by-step guides for common tasks like troubleshooting an unhealthy pod or assessing overall cluster health).

## What Can It Do?

- **Run queries** — Ask about any metric Prometheus collects (CPU usage, memory, request rates, error counts, etc.)
- **Check targets** — See which services Prometheus is monitoring and whether they're reachable
- **Review alerts** — List any active alerts that indicate something needs attention
- **Explore metrics** — Discover what data is available without needing to know metric names upfront
- **Troubleshoot** — Walk through structured investigations for common problems (pod crashes, high resource usage, node capacity)

## Useful Commands

```bash
# Port-forward Prometheus for local development
kubectl -n monitoring port-forward service/prometheus-server 9090:80

# Port-forward PostgreSQL for local development
kubectl -n woodez-database port-forward service/postgres-svc 5432:5432
```

## Links

- **Live URL**: http://mcp-monitor.apexkube.xyz
- **Repository**: https://github.com/woodez-kubernetes/mcp-prometheus-srv.git
