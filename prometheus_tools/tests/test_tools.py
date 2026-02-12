"""Unit tests for MCP tool functions with mocked PrometheusClient."""

from unittest.mock import AsyncMock, patch

import pytest

from prometheus_tools.services import PrometheusError


MOCK_CLIENT = "prometheus_tools.mcp.client"


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _prom_error(message="test error"):
    return PrometheusError(status_code=400, error_type="bad_data", message=message)


# ------------------------------------------------------------------ #
# query_instant
# ------------------------------------------------------------------ #


class TestQueryInstant:
    async def test_returns_formatted_vector(self):
        from prometheus_tools.mcp import query_instant

        raw = {
            "resultType": "vector",
            "result": [{"metric": {"__name__": "up", "job": "prom"}, "value": [1700000000, "1"]}],
        }
        with patch(MOCK_CLIENT) as mock:
            mock.instant_query = AsyncMock(return_value=raw)
            result = await query_instant(query="up")
        assert result["resultType"] == "vector"
        assert result["results"][0]["metric_name"] == "up"
        assert result["results"][0]["value"] == "1"

    async def test_error_returns_error_dict(self):
        from prometheus_tools.mcp import query_instant

        with patch(MOCK_CLIENT) as mock:
            mock.instant_query = AsyncMock(side_effect=_prom_error("invalid expression"))
            result = await query_instant(query="bad{")
        assert result["error"] is True
        assert result["error_type"] == "bad_data"
        assert "invalid expression" in result["message"]


# ------------------------------------------------------------------ #
# query_range
# ------------------------------------------------------------------ #


class TestQueryRange:
    async def test_returns_formatted_matrix(self):
        from prometheus_tools.mcp import query_range

        raw = {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"__name__": "cpu", "pod": "app-1"},
                    "values": [[1700000000, "0.1"], [1700000060, "0.5"]],
                }
            ],
        }
        with patch(MOCK_CLIENT) as mock:
            mock.range_query = AsyncMock(return_value=raw)
            result = await query_range(query="cpu", start="0", end="1", step="60s")
        assert result["resultType"] == "matrix"
        assert result["results"][0]["num_samples"] == 2
        assert result["results"][0]["avg"] == pytest.approx(0.3, abs=0.001)

    async def test_error_returns_error_dict(self):
        from prometheus_tools.mcp import query_range

        with patch(MOCK_CLIENT) as mock:
            mock.range_query = AsyncMock(side_effect=_prom_error())
            result = await query_range(query="x", start="0", end="1", step="1s")
        assert result["error"] is True


# ------------------------------------------------------------------ #
# list_metrics
# ------------------------------------------------------------------ #


class TestListMetrics:
    async def test_returns_metric_names(self):
        from prometheus_tools.mcp import list_metrics

        with patch(MOCK_CLIENT) as mock:
            mock.get_label_values = AsyncMock(return_value=["up", "node_cpu_seconds_total"])
            result = await list_metrics()
        assert result == ["up", "node_cpu_seconds_total"]
        mock.get_label_values.assert_called_once_with("__name__")


# ------------------------------------------------------------------ #
# get_metric_metadata
# ------------------------------------------------------------------ #


class TestGetMetricMetadata:
    async def test_returns_metadata(self):
        from prometheus_tools.mcp import get_metric_metadata

        raw = {"up": [{"type": "gauge", "help": "Target is up", "unit": ""}]}
        with patch(MOCK_CLIENT) as mock:
            mock.get_metric_metadata = AsyncMock(return_value=raw)
            result = await get_metric_metadata(metric="up")
        assert "up" in result


# ------------------------------------------------------------------ #
# list_labels
# ------------------------------------------------------------------ #


class TestListLabels:
    async def test_returns_labels(self):
        from prometheus_tools.mcp import list_labels

        with patch(MOCK_CLIENT) as mock:
            mock.get_labels = AsyncMock(return_value=["__name__", "job", "instance"])
            result = await list_labels()
        assert "job" in result


# ------------------------------------------------------------------ #
# get_label_values
# ------------------------------------------------------------------ #


class TestGetLabelValues:
    async def test_returns_values(self):
        from prometheus_tools.mcp import get_label_values

        with patch(MOCK_CLIENT) as mock:
            mock.get_label_values = AsyncMock(return_value=["prometheus", "node"])
            result = await get_label_values(label_name="job")
        assert "prometheus" in result


# ------------------------------------------------------------------ #
# find_series
# ------------------------------------------------------------------ #


class TestFindSeries:
    async def test_returns_series(self):
        from prometheus_tools.mcp import find_series

        raw = [{"__name__": "up", "job": "prometheus"}]
        with patch(MOCK_CLIENT) as mock:
            mock.list_series = AsyncMock(return_value=raw)
            result = await find_series(match=['{job="prometheus"}'])
        assert len(result) == 1
        assert result[0]["job"] == "prometheus"


# ------------------------------------------------------------------ #
# get_targets
# ------------------------------------------------------------------ #


class TestGetTargets:
    async def test_returns_formatted_targets(self):
        from prometheus_tools.mcp import get_targets

        raw = {
            "activeTargets": [
                {
                    "labels": {"job": "prometheus", "instance": "localhost:9090"},
                    "health": "up",
                    "lastScrape": "2024-01-01T00:00:00Z",
                    "lastScrapeDuration": 0.005,
                }
            ],
            "droppedTargets": [],
        }
        with patch(MOCK_CLIENT) as mock:
            mock.get_targets = AsyncMock(return_value=raw)
            result = await get_targets()
        assert result["summary"]["total_active"] == 1
        assert result["summary"]["healthy"] == 1


# ------------------------------------------------------------------ #
# get_alerts
# ------------------------------------------------------------------ #


class TestGetAlerts:
    async def test_returns_formatted_alerts(self):
        from prometheus_tools.mcp import get_alerts

        raw = {
            "alerts": [
                {
                    "labels": {"alertname": "HighCPU", "severity": "critical"},
                    "annotations": {"summary": "CPU > 90%"},
                    "state": "firing",
                    "activeAt": "2024-01-01T00:00:00Z",
                }
            ]
        }
        with patch(MOCK_CLIENT) as mock:
            mock.get_alerts = AsyncMock(return_value=raw)
            result = await get_alerts()
        assert result["summary"]["firing"] == 1
        assert result["alerts"][0]["alertname"] == "HighCPU"

    async def test_empty_alerts(self):
        from prometheus_tools.mcp import get_alerts

        with patch(MOCK_CLIENT) as mock:
            mock.get_alerts = AsyncMock(return_value={"alerts": []})
            result = await get_alerts()
        assert result["summary"]["total"] == 0


# ------------------------------------------------------------------ #
# get_rules
# ------------------------------------------------------------------ #


class TestGetRules:
    async def test_returns_formatted_rules(self):
        from prometheus_tools.mcp import get_rules

        raw = {
            "groups": [
                {
                    "name": "test",
                    "rules": [
                        {"name": "HighCPU", "type": "alerting", "query": "cpu > 0.9", "health": "ok", "lastEvaluation": ""},
                    ],
                }
            ]
        }
        with patch(MOCK_CLIENT) as mock:
            mock.get_rules = AsyncMock(return_value=raw)
            result = await get_rules()
        assert result["summary"]["alerting"] == 1
        assert result["rules"][0]["name"] == "HighCPU"

    async def test_filtered_by_type(self):
        from prometheus_tools.mcp import get_rules

        with patch(MOCK_CLIENT) as mock:
            mock.get_rules = AsyncMock(return_value={"groups": []})
            await get_rules(type="alert")
        mock.get_rules.assert_called_once_with(type="alert")
