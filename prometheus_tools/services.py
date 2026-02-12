"""Async client for the Prometheus HTTP API."""

import httpx
from django.conf import settings


class PrometheusError(Exception):
    """Raised when a Prometheus API call fails."""

    def __init__(self, status_code: int, error_type: str, message: str):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        super().__init__(f"Prometheus {error_type} ({status_code}): {message}")


class PrometheusClient:
    """Wraps the Prometheus /api/v1 endpoints using httpx.AsyncClient."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.PROMETHEUS_URL).rstrip('/')
        self._api = f"{self.base_url}/api/v1"

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request to a Prometheus API endpoint.

        Returns the 'data' portion of a successful response.
        Raises PrometheusError with an LLM-readable message on failure.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._api}{path}", params=params, timeout=30.0)

        if resp.status_code != 200:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            raise PrometheusError(
                status_code=resp.status_code,
                error_type=body.get("errorType", "unknown"),
                message=body.get("error", resp.text),
            )

        body = resp.json()
        if body.get("status") != "success":
            raise PrometheusError(
                status_code=resp.status_code,
                error_type=body.get("errorType", "unknown"),
                message=body.get("error", "Unknown error from Prometheus"),
            )

        return body["data"]

    # ------------------------------------------------------------------ #
    # Expression queries
    # ------------------------------------------------------------------ #

    async def instant_query(self, query: str, time: str | None = None, timeout: str | None = None) -> dict:
        """Execute a PromQL instant query (GET /api/v1/query).

        Args:
            query:   PromQL expression.
            time:    Evaluation timestamp (RFC3339 or Unix). Defaults to now.
            timeout: Evaluation timeout, e.g. '30s'.

        Returns:
            Dict with 'resultType' and 'result' keys.
        """
        params: dict[str, str] = {"query": query}
        if time:
            params["time"] = time
        if timeout:
            params["timeout"] = timeout
        return await self._get("/query", params)

    async def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
        timeout: str | None = None,
    ) -> dict:
        """Execute a PromQL range query (GET /api/v1/query_range).

        Args:
            query:   PromQL expression.
            start:   Start timestamp (RFC3339 or Unix).
            end:     End timestamp (RFC3339 or Unix).
            step:    Query resolution step, e.g. '15s', '1m'.
            timeout: Evaluation timeout.

        Returns:
            Dict with 'resultType' and 'result' keys.
        """
        params: dict[str, str] = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        if timeout:
            params["timeout"] = timeout
        return await self._get("/query_range", params)

    # ------------------------------------------------------------------ #
    # Series & label discovery
    # ------------------------------------------------------------------ #

    async def list_series(
        self,
        match: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Find time series matching label selectors (GET /api/v1/series).

        Args:
            match: List of series selectors, e.g. ['{job="prometheus"}'].
            start: Start timestamp.
            end:   End timestamp.

        Returns:
            List of label-set dicts for matching series.
        """
        params: dict[str, str | list[str]] = {"match[]": match}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self._get("/series", params)

    async def get_labels(self, match: list[str] | None = None) -> list[str]:
        """List all label names (GET /api/v1/labels).

        Args:
            match: Optional series selectors to scope the label listing.

        Returns:
            Sorted list of label name strings.
        """
        params: dict[str, str | list[str]] = {}
        if match:
            params["match[]"] = match
        return await self._get("/labels", params)

    async def get_label_values(self, label_name: str, match: list[str] | None = None) -> list[str]:
        """Get all values for a specific label (GET /api/v1/label/<name>/values).

        Args:
            label_name: The label to retrieve values for, e.g. 'job', 'instance'.
            match:      Optional series selectors to scope the values.

        Returns:
            Sorted list of label value strings.
        """
        params: dict[str, str | list[str]] = {}
        if match:
            params["match[]"] = match
        return await self._get(f"/label/{label_name}/values", params)

    # ------------------------------------------------------------------ #
    # Targets, alerts, rules
    # ------------------------------------------------------------------ #

    async def get_targets(self, state: str | None = None) -> dict:
        """Get scrape targets (GET /api/v1/targets).

        Args:
            state: Filter by target state — 'active', 'dropped', or 'any'.

        Returns:
            Dict with 'activeTargets' and 'droppedTargets' lists.
        """
        params: dict[str, str] = {}
        if state:
            params["state"] = state
        return await self._get("/targets", params)

    async def get_alerts(self) -> dict:
        """Get currently firing alerts (GET /api/v1/alerts).

        Returns:
            Dict with 'alerts' list.
        """
        return await self._get("/alerts")

    async def get_rules(self, type: str | None = None) -> dict:
        """Get alerting and recording rules (GET /api/v1/rules).

        Args:
            type: Filter by rule type — 'alert' or 'record'.

        Returns:
            Dict with 'groups' list.
        """
        params: dict[str, str] = {}
        if type:
            params["type"] = type
        return await self._get("/rules", params)

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    async def get_metric_metadata(self, metric: str | None = None, limit: int | None = None) -> dict:
        """Get metric metadata — TYPE, HELP, UNIT (GET /api/v1/targets/metadata).

        Args:
            metric: Filter to a single metric name.
            limit:  Max number of metrics to return.

        Returns:
            Dict mapping metric names to lists of metadata entries.
        """
        params: dict[str, str] = {}
        if metric:
            params["metric"] = metric
        if limit is not None:
            params["limit"] = str(limit)
        return await self._get("/targets/metadata", params)

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    async def get_build_info(self) -> dict:
        """Get Prometheus build information (GET /api/v1/status/buildinfo).

        Returns:
            Dict with version, revision, branch, buildUser, buildDate, goVersion.
        """
        return await self._get("/status/buildinfo")

    # ------------------------------------------------------------------ #
    # Health check
    # ------------------------------------------------------------------ #

    async def health(self) -> bool:
        """Check if Prometheus is reachable (GET /-/healthy).

        Returns:
            True if Prometheus responds with 200.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/-/healthy", timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
