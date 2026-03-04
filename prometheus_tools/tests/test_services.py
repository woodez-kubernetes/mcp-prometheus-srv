"""Unit tests for PrometheusClient with mocked HTTP responses."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from prometheus_tools.services import PrometheusClient, PrometheusError


@pytest.fixture
def client():
    """PrometheusClient pointed at a fake base URL."""
    return PrometheusClient(base_url="http://prometheus:9090")


def _mock_response(status_code=200, json_data=None, text="", content_type="application/json"):
    """Build a fake httpx.Response with proper body content."""
    if json_data is not None:
        content = json.dumps(json_data).encode()
    else:
        content = text.encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": content_type},
        request=httpx.Request("GET", "http://prometheus:9090"),
    )


# ------------------------------------------------------------------ #
# _get — success & error paths
# ------------------------------------------------------------------ #


class TestGetHelper:
    async def test_success_returns_data(self, client):
        payload = {"status": "success", "data": {"resultType": "vector", "result": []}}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client._get("/query", {"query": "up"})
        assert result == {"resultType": "vector", "result": []}

    async def test_http_error_raises(self, client):
        error_payload = {"status": "error", "errorType": "bad_data", "error": "invalid expression"}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(status_code=400, json_data=error_payload))
            with pytest.raises(PrometheusError) as exc_info:
                await client._get("/query", {"query": "bad{"})
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_type == "bad_data"
        assert "invalid expression" in exc_info.value.message

    async def test_non_success_status_raises(self, client):
        payload = {"status": "error", "errorType": "execution", "error": "query timed out"}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            with pytest.raises(PrometheusError) as exc_info:
                await client._get("/query", {"query": "slow_query"})
        assert exc_info.value.error_type == "execution"


# ------------------------------------------------------------------ #
# instant_query
# ------------------------------------------------------------------ #


class TestInstantQuery:
    async def test_basic_query(self, client):
        data = {"resultType": "vector", "result": [{"metric": {"__name__": "up"}, "value": [1700000000, "1"]}]}
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.instant_query(query="up")
        assert result["resultType"] == "vector"
        assert len(result["result"]) == 1
        # Verify the correct URL and params were passed
        instance.get.assert_called_once()
        call_args = instance.get.call_args
        assert "/api/v1/query" in call_args[0][0]
        assert call_args[1]["params"]["query"] == "up"

    async def test_query_with_time(self, client):
        payload = {"status": "success", "data": {"resultType": "vector", "result": []}}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            await client.instant_query(query="up", time="2024-01-01T00:00:00Z")
        call_params = instance.get.call_args[1]["params"]
        assert call_params["time"] == "2024-01-01T00:00:00Z"


# ------------------------------------------------------------------ #
# range_query
# ------------------------------------------------------------------ #


class TestRangeQuery:
    async def test_basic_range(self, client):
        data = {
            "resultType": "matrix",
            "result": [{"metric": {"__name__": "up"}, "values": [[1700000000, "1"], [1700000060, "1"]]}],
        }
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.range_query(
                query="up",
                start="2024-01-01T00:00:00Z",
                end="2024-01-01T01:00:00Z",
                step="60s",
            )
        assert result["resultType"] == "matrix"
        call_params = instance.get.call_args[1]["params"]
        assert call_params["start"] == "2024-01-01T00:00:00Z"
        assert call_params["step"] == "60s"


# ------------------------------------------------------------------ #
# list_series
# ------------------------------------------------------------------ #


class TestListSeries:
    async def test_series_lookup(self, client):
        data = [{"__name__": "up", "job": "prometheus"}, {"__name__": "up", "job": "node"}]
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.list_series(match=['{job="prometheus"}'])
        assert len(result) == 2
        call_params = instance.get.call_args[1]["params"]
        assert call_params["match[]"] == ['{job="prometheus"}']


# ------------------------------------------------------------------ #
# get_labels / get_label_values
# ------------------------------------------------------------------ #


class TestLabels:
    async def test_get_labels(self, client):
        payload = {"status": "success", "data": ["__name__", "instance", "job"]}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_labels()
        assert result == ["__name__", "instance", "job"]

    async def test_get_label_values(self, client):
        payload = {"status": "success", "data": ["prometheus", "node-exporter"]}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_label_values("job")
        assert "prometheus" in result
        assert "/api/v1/label/job/values" in instance.get.call_args[0][0]


# ------------------------------------------------------------------ #
# get_targets
# ------------------------------------------------------------------ #


class TestTargets:
    async def test_get_targets(self, client):
        data = {
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
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_targets()
        assert len(result["activeTargets"]) == 1
        assert result["activeTargets"][0]["health"] == "up"


# ------------------------------------------------------------------ #
# get_alerts
# ------------------------------------------------------------------ #


class TestAlerts:
    async def test_get_alerts_empty(self, client):
        payload = {"status": "success", "data": {"alerts": []}}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_alerts()
        assert result["alerts"] == []

    async def test_get_alerts_firing(self, client):
        data = {
            "alerts": [
                {
                    "labels": {"alertname": "HighMemory", "severity": "critical"},
                    "state": "firing",
                    "activeAt": "2024-01-01T00:00:00Z",
                }
            ]
        }
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_alerts()
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["state"] == "firing"


# ------------------------------------------------------------------ #
# get_rules
# ------------------------------------------------------------------ #


class TestRules:
    async def test_get_rules(self, client):
        data = {
            "groups": [
                {
                    "name": "test-group",
                    "rules": [{"name": "HighMemory", "type": "alerting", "query": "node_memory_Active_bytes > 1e9"}],
                }
            ]
        }
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_rules()
        assert len(result["groups"]) == 1

    async def test_get_rules_filtered(self, client):
        payload = {"status": "success", "data": {"groups": []}}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            await client.get_rules(type="alert")
        call_params = instance.get.call_args[1]["params"]
        assert call_params["type"] == "alert"


# ------------------------------------------------------------------ #
# get_metric_metadata
# ------------------------------------------------------------------ #


class TestMetricMetadata:
    async def test_get_all_metadata(self, client):
        data = {
            "up": [{"type": "gauge", "help": "Target is up", "unit": ""}],
            "process_cpu_seconds_total": [{"type": "counter", "help": "CPU time", "unit": "seconds"}],
        }
        payload = {"status": "success", "data": data}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            result = await client.get_metric_metadata()
        assert "up" in result

    async def test_get_single_metric_metadata(self, client):
        payload = {"status": "success", "data": {"up": [{"type": "gauge", "help": "Target is up", "unit": ""}]}}
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=_mock_response(json_data=payload))
            await client.get_metric_metadata(metric="up")
        call_params = instance.get.call_args[1]["params"]
        assert call_params["metric"] == "up"


# ------------------------------------------------------------------ #
# health
# ------------------------------------------------------------------ #


class TestHealth:
    async def test_healthy(self, client):
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(
                return_value=_mock_response(status_code=200, text="Prometheus Server is Healthy.", content_type="text/plain")
            )
            result = await client.health()
        assert result is True

    async def test_unhealthy(self, client):
        with patch("prometheus_tools.services.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            result = await client.health()
        assert result is False
