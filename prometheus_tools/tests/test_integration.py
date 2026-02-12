"""Integration tests that require a running Prometheus at localhost:9090.

These tests are skipped by default. Run them with:
    pytest prometheus_tools/tests/test_integration.py -v --run-integration

They exercise the full stack: MCP tool → PrometheusClient → real Prometheus HTTP API.
"""

import os

import pytest

# Skip the entire module unless --run-integration is passed or PROMETHEUS_INTEGRATION env is set
pytestmark = pytest.mark.skipif(
    not os.getenv("PROMETHEUS_INTEGRATION") and "--run-integration" not in " ".join(os.sys.argv),
    reason="Integration tests require --run-integration flag or PROMETHEUS_INTEGRATION=1 env var",
)


# ------------------------------------------------------------------ #
# PrometheusClient integration
# ------------------------------------------------------------------ #


class TestClientIntegration:
    """Direct PrometheusClient calls against a live Prometheus."""

    @pytest.fixture
    def client(self):
        from prometheus_tools.services import PrometheusClient

        return PrometheusClient()

    async def test_health(self, client):
        result = await client.health()
        assert result is True

    async def test_instant_query_up(self, client):
        result = await client.instant_query(query="up")
        assert result["resultType"] == "vector"
        assert len(result["result"]) > 0

    async def test_range_query(self, client):
        result = await client.range_query(
            query="up",
            start="2024-01-01T00:00:00Z",
            end="2099-01-01T00:00:00Z",
            step="3600s",
        )
        assert result["resultType"] == "matrix"

    async def test_get_labels(self, client):
        result = await client.get_labels()
        assert "__name__" in result

    async def test_get_label_values(self, client):
        result = await client.get_label_values("__name__")
        assert isinstance(result, list)
        assert len(result) > 0

    async def test_get_targets(self, client):
        result = await client.get_targets()
        assert "activeTargets" in result

    async def test_get_alerts(self, client):
        result = await client.get_alerts()
        assert "alerts" in result

    async def test_get_rules(self, client):
        result = await client.get_rules()
        assert "groups" in result

    async def test_get_build_info(self, client):
        result = await client.get_build_info()
        assert "version" in result

    async def test_bad_promql_raises(self, client):
        from prometheus_tools.services import PrometheusError

        with pytest.raises(PrometheusError) as exc_info:
            await client.instant_query(query="invalid{{{")
        assert exc_info.value.status_code in (400, 422)


# ------------------------------------------------------------------ #
# MCP tool integration
# ------------------------------------------------------------------ #


class TestToolIntegration:
    """MCP tool functions against a live Prometheus."""

    async def test_query_instant(self):
        from prometheus_tools.mcp import query_instant

        result = await query_instant(query="up")
        assert result["resultType"] == "vector"
        assert "results" in result  # formatted output

    async def test_query_instant_error_handling(self):
        from prometheus_tools.mcp import query_instant

        result = await query_instant(query="invalid{{{")
        assert result.get("error") is True

    async def test_list_metrics(self):
        from prometheus_tools.mcp import list_metrics

        result = await list_metrics()
        assert isinstance(result, list)
        assert len(result) > 0

    async def test_list_labels(self):
        from prometheus_tools.mcp import list_labels

        result = await list_labels()
        assert "__name__" in result

    async def test_get_targets(self):
        from prometheus_tools.mcp import get_targets

        result = await get_targets()
        assert "active_targets" in result
        assert "summary" in result

    async def test_get_alerts(self):
        from prometheus_tools.mcp import get_alerts

        result = await get_alerts()
        assert "summary" in result
        assert "alerts" in result

    async def test_get_rules(self):
        from prometheus_tools.mcp import get_rules

        result = await get_rules()
        assert "summary" in result
        assert "rules" in result
