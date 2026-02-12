"""MCP tool and resource definitions for Prometheus."""

from mcp_server import mcp_server as mcp

from .formatters import format_alerts, format_matrix, format_rules, format_targets, format_vector
from .services import PrometheusClient, PrometheusError

client = PrometheusClient()


def _error_response(exc: PrometheusError) -> dict:
    """Convert a PrometheusError into a structured dict the LLM can reason about."""
    return {
        "error": True,
        "error_type": exc.error_type,
        "message": exc.message,
        "status_code": exc.status_code,
    }


# ------------------------------------------------------------------ #
# Tool 1: query_instant
# ------------------------------------------------------------------ #


@mcp.tool()
async def query_instant(query: str, time: str | None = None) -> dict:
    """Execute a PromQL instant query against Prometheus.

    Use this to get the current value of any metric. Returns a vector of
    {metric, value} pairs.

    Common Kubernetes PromQL examples:
      - up                                              — target health (1=up, 0=down)
      - kube_pod_status_phase{phase="Running"}          — running pods
      - rate(container_cpu_usage_seconds_total[5m])     — CPU usage rate
      - container_memory_working_set_bytes              — memory usage

    Args:
        query: A PromQL expression.
        time:  Optional evaluation timestamp (RFC3339 or Unix). Defaults to now.
    """
    try:
        data = await client.instant_query(query=query, time=time)
        return format_vector(data)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 2: query_range
# ------------------------------------------------------------------ #


@mcp.tool()
async def query_range(query: str, start: str, end: str, step: str) -> dict:
    """Execute a PromQL range query over a time window.

    Returns a summarised matrix with statistics per series (num_samples,
    first/last/min/max/avg values). Use this when you need to see how a
    metric changes over time.

    Common Kubernetes PromQL examples:
      - rate(container_cpu_usage_seconds_total[5m])     — CPU trend
      - container_memory_working_set_bytes              — memory trend
      - kube_pod_container_status_restarts_total        — restart history

    Args:
        query: A PromQL expression.
        start: Start timestamp (RFC3339 or Unix), e.g. '2024-01-01T00:00:00Z'.
        end:   End timestamp (RFC3339 or Unix).
        step:  Resolution step width, e.g. '15s', '1m', '5m'.
    """
    try:
        data = await client.range_query(query=query, start=start, end=end, step=step)
        return format_matrix(data)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 3: list_metrics
# ------------------------------------------------------------------ #


@mcp.tool()
async def list_metrics() -> list[str]:
    """List all available metric names in Prometheus.

    Returns a sorted list of metric name strings. Use this to discover
    what metrics are available before querying.
    """
    try:
        return await client.get_label_values("__name__")
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 4: get_metric_metadata
# ------------------------------------------------------------------ #


@mcp.tool()
async def get_metric_metadata(metric: str | None = None) -> dict:
    """Get TYPE, HELP, and UNIT metadata for metrics.

    Use this to understand what a metric measures, its type (counter, gauge,
    histogram, summary), and its unit before writing PromQL queries.

    Args:
        metric: A specific metric name, or omit to get metadata for all metrics.
    """
    try:
        return await client.get_metric_metadata(metric=metric)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 5: list_labels
# ------------------------------------------------------------------ #


@mcp.tool()
async def list_labels() -> list[str]:
    """List all label names present in Prometheus data.

    Returns label names like 'job', 'instance', 'namespace', 'pod', etc.
    Use this to discover available dimensions for filtering queries.
    """
    try:
        return await client.get_labels()
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 6: get_label_values
# ------------------------------------------------------------------ #


@mcp.tool()
async def get_label_values(label_name: str) -> list[str]:
    """Get all values for a specific label.

    Useful for discovering namespaces, pod names, job names, etc.

    Examples:
      - get_label_values('namespace')  — list all Kubernetes namespaces
      - get_label_values('job')        — list all scrape jobs
      - get_label_values('pod')        — list all pod names

    Args:
        label_name: The label to retrieve values for.
    """
    try:
        return await client.get_label_values(label_name=label_name)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 7: find_series
# ------------------------------------------------------------------ #


@mcp.tool()
async def find_series(match: list[str]) -> list[dict]:
    """Find time series matching one or more label selectors.

    Returns the full label set for each matching series. Use this to explore
    which label combinations exist for a given metric.

    Args:
        match: List of series selectors, e.g. ['{job="prometheus"}'] or
               ['up{namespace="default"}'].
    """
    try:
        return await client.list_series(match=match)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 8: get_targets
# ------------------------------------------------------------------ #


@mcp.tool()
async def get_targets() -> dict:
    """Show all Prometheus scrape targets and their health status.

    Returns active and dropped targets with their labels, health state,
    last scrape time, and scrape duration. Use this to check if scrape
    targets are healthy.
    """
    try:
        data = await client.get_targets()
        return format_targets(data)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 9: get_alerts
# ------------------------------------------------------------------ #


@mcp.tool()
async def get_alerts() -> dict:
    """List all currently firing alerts from Prometheus.

    Returns alerts with alertname, state, severity, summary, and when
    they became active, plus a summary count of firing/pending. Use this
    to check for active problems.
    """
    try:
        data = await client.get_alerts()
        return format_alerts(data)
    except PrometheusError as exc:
        return _error_response(exc)


# ------------------------------------------------------------------ #
# Tool 10: get_rules
# ------------------------------------------------------------------ #


@mcp.tool()
async def get_rules(type: str | None = None) -> dict:
    """List alerting and recording rules configured in Prometheus.

    Returns a flat list of rules with name, group, type, query, health,
    and last evaluation, plus a summary count of alerting/recording rules.

    Args:
        type: Optional filter — 'alert' for alerting rules only,
              'record' for recording rules only. Omit for all rules.
    """
    try:
        data = await client.get_rules(type=type)
        return format_rules(data)
    except PrometheusError as exc:
        return _error_response(exc)


# ================================================================== #
# MCP Resources (read-only context)
# ================================================================== #


@mcp.resource("prometheus://status", description="Prometheus build info and runtime status")
async def prometheus_status() -> str:
    """Return Prometheus server build information and health status."""
    import json

    try:
        build_info = await client.get_build_info()
        healthy = await client.health()
    except PrometheusError:
        build_info = {}
        healthy = False

    return json.dumps({
        "healthy": healthy,
        "build_info": build_info,
        "prometheus_url": client.base_url,
    }, indent=2)


@mcp.resource("prometheus://targets/summary", description="Summary of all scrape targets and their health")
async def prometheus_targets_summary() -> str:
    """Return a formatted summary of all Prometheus scrape targets."""
    import json

    try:
        data = await client.get_targets()
        return json.dumps(format_targets(data), indent=2)
    except PrometheusError as exc:
        return json.dumps(_error_response(exc), indent=2)


@mcp.resource("prometheus://alerts/active", description="Currently firing alerts from Prometheus")
async def prometheus_active_alerts() -> str:
    """Return a formatted summary of all currently firing alerts."""
    import json

    try:
        data = await client.get_alerts()
        return json.dumps(format_alerts(data), indent=2)
    except PrometheusError as exc:
        return json.dumps(_error_response(exc), indent=2)


@mcp.resource("prometheus://metrics/catalog", description="Full list of available metric names with metadata")
async def prometheus_metrics_catalog() -> str:
    """Return all metric names paired with their TYPE and HELP metadata."""
    import json

    try:
        names = await client.get_label_values("__name__")
        metadata = await client.get_metric_metadata()
    except PrometheusError:
        names = []
        metadata = {}

    catalog = []
    for name in names:
        meta_entries = metadata.get(name, [])
        entry = {"name": name}
        if meta_entries:
            entry["type"] = meta_entries[0].get("type", "")
            entry["help"] = meta_entries[0].get("help", "")
            entry["unit"] = meta_entries[0].get("unit", "")
        catalog.append(entry)

    return json.dumps({"total_metrics": len(catalog), "metrics": catalog}, indent=2)


# ================================================================== #
# MCP Prompts (K8s observability workflows)
# ================================================================== #


@mcp.prompt(description="Step-by-step Kubernetes cluster health assessment")
def k8s_cluster_health() -> list[dict]:
    """Guide the LLM through a full cluster health check."""
    return [
        {
            "role": "user",
            "content": """Perform a comprehensive Kubernetes cluster health assessment using these steps:

1. **Target health** — call `get_targets()` to check all scrape targets are up.
2. **Firing alerts** — call `get_alerts()` to see if any alerts are currently firing.
3. **Node readiness** — run `query_instant('kube_node_status_condition{condition="Ready",status="true"}')`.
4. **Pod phases** — run `query_instant('sum by (phase) (kube_pod_status_phase)')` to see how many pods are in each phase (Running, Pending, Failed, etc.).
5. **Restart storms** — run `query_instant('sum by (namespace, pod) (increase(kube_pod_container_status_restarts_total[1h])) > 3')` to find pods restarting frequently.
6. **CPU pressure** — run `query_instant('1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))')` for overall cluster CPU utilisation.
7. **Memory pressure** — run `query_instant('1 - sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes)')` for overall memory utilisation.

Summarise findings, highlight any issues, and recommend actions.""",
        }
    ]


@mcp.prompt(description="Diagnose why a specific Kubernetes pod is unhealthy")
def k8s_pod_troubleshoot(namespace: str, pod: str) -> list[dict]:
    """Guide the LLM through diagnosing an unhealthy pod."""
    return [
        {
            "role": "user",
            "content": f"""Diagnose pod **{pod}** in namespace **{namespace}** using these steps:

1. **Pod phase** — run `query_instant('kube_pod_status_phase{{namespace="{namespace}",pod="{pod}"}} == 1')` to see the current phase.
2. **Container readiness** — run `query_instant('kube_pod_container_status_ready{{namespace="{namespace}",pod="{pod}"}}')`.
3. **Restarts** — run `query_instant('kube_pod_container_status_restarts_total{{namespace="{namespace}",pod="{pod}"}}')` to check restart count.
4. **OOMKilled** — run `query_instant('kube_pod_container_status_last_terminated_reason{{namespace="{namespace}",pod="{pod}",reason="OOMKilled"}}')`.
5. **CPU usage** — run `query_range('rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod="{pod}"}}[5m])', <start>, <end>, '1m')` for recent CPU trend (use last 30 minutes).
6. **Memory usage** — run `query_instant('container_memory_working_set_bytes{{namespace="{namespace}",pod="{pod}"}}')`.
7. **CPU throttling** — run `query_instant('rate(container_cpu_cfs_throttled_periods_total{{namespace="{namespace}",pod="{pod}"}}[5m]) / rate(container_cpu_cfs_periods_total{{namespace="{namespace}",pod="{pod}"}}[5m])')`.

Summarise findings, identify the root cause, and recommend actions.""",
        }
    ]


@mcp.prompt(description="Analyse CPU and memory usage across Kubernetes namespaces")
def k8s_resource_usage(namespace: str | None = None) -> list[dict]:
    """Guide the LLM through resource usage analysis."""
    ns_filter = f'namespace="{namespace}"' if namespace else ""
    ns_label = f" for namespace **{namespace}**" if namespace else " across all namespaces"
    return [
        {
            "role": "user",
            "content": f"""Analyse CPU and memory resource usage{ns_label}:

1. **CPU usage by namespace** — run `query_instant('sum by (namespace) (rate(container_cpu_usage_seconds_total{{{ns_filter}}}[5m]))')`.
2. **CPU requests vs usage** — run `query_instant('sum by (namespace) (kube_pod_container_resource_requests{{resource="cpu",{ns_filter}}})')` and compare with actual usage from step 1.
3. **Memory usage by namespace** — run `query_instant('sum by (namespace) (container_memory_working_set_bytes{{{ns_filter}}})')`.
4. **Memory requests vs usage** — run `query_instant('sum by (namespace) (kube_pod_container_resource_requests{{resource="memory",{ns_filter}}})')` and compare with actual usage from step 3.
5. **Top CPU pods** — run `query_instant('topk(10, sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{ns_filter}}}[5m])))')`.
6. **Top memory pods** — run `query_instant('topk(10, sum by (namespace, pod) (container_memory_working_set_bytes{{{ns_filter}}}))')`.

Summarise resource utilisation, identify over/under-provisioned workloads, and recommend right-sizing actions.""",
        }
    ]


@mcp.prompt(description="Triage currently firing Prometheus alerts")
def k8s_alert_triage() -> list[dict]:
    """Guide the LLM through triaging active alerts."""
    return [
        {
            "role": "user",
            "content": """Triage all currently firing Prometheus alerts:

1. **Get all alerts** — call `get_alerts()` to retrieve active alerts.
2. **Get alert rules** — call `get_rules(type='alert')` to understand the alerting conditions.
3. For each firing alert:
   a. Note the **alertname**, **severity**, and **summary**.
   b. Run the alert's PromQL expression using `query_instant()` to see the current value.
   c. Check the **trend** using `query_range()` over the last hour to see if the situation is improving or worsening.
4. **Prioritise** alerts by severity (critical > warning > info).
5. For each critical alert, investigate related metrics to identify root cause.

Present a triage report: list each alert with severity, current status, trend direction, and recommended action.""",
        }
    ]


@mcp.prompt(description="Evaluate Kubernetes node resource capacity and allocation")
def k8s_node_capacity() -> list[dict]:
    """Guide the LLM through node capacity analysis."""
    return [
        {
            "role": "user",
            "content": """Evaluate Kubernetes node resource capacity and allocation:

1. **Node list** — run `get_label_values('node')` or `query_instant('kube_node_info')` to list all nodes.
2. **Node conditions** — run `query_instant('kube_node_status_condition{condition="Ready",status="true"}')` to check readiness.
3. **CPU capacity vs allocatable** — run `query_instant('kube_node_status_capacity{resource="cpu"}')` and `query_instant('kube_node_status_allocatable{resource="cpu"}')`.
4. **Memory capacity vs allocatable** — run `query_instant('kube_node_status_capacity{resource="memory"}')` and `query_instant('kube_node_status_allocatable{resource="memory"}')`.
5. **CPU allocation ratio** — run `query_instant('sum by (node) (kube_pod_container_resource_requests{resource="cpu"}) / on(node) kube_node_status_allocatable{resource="cpu"}')`.
6. **Memory allocation ratio** — run `query_instant('sum by (node) (kube_pod_container_resource_requests{resource="memory"}) / on(node) kube_node_status_allocatable{resource="memory"}')`.
7. **Actual CPU usage per node** — run `query_instant('1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))')`.
8. **Actual memory usage per node** — run `query_instant('1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)')`.

Summarise: for each node, show capacity, allocation, and actual usage. Flag nodes that are over-committed or under-utilised. Recommend scheduling or scaling actions.""",
        }
    ]
