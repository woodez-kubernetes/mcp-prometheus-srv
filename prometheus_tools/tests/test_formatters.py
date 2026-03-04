"""Unit tests for Prometheus response formatters."""

import pytest

from prometheus_tools.formatters import (
    MAX_RESULTS,
    format_alerts,
    format_matrix,
    format_rules,
    format_targets,
    format_vector,
)


# ------------------------------------------------------------------ #
# format_vector
# ------------------------------------------------------------------ #


class TestFormatVector:
    def test_basic_vector(self):
        data = {
            "resultType": "vector",
            "result": [
                {"metric": {"__name__": "up", "job": "prometheus"}, "value": [1700000000, "1"]},
                {"metric": {"__name__": "up", "job": "node"}, "value": [1700000000, "0"]},
            ],
        }
        out = format_vector(data)
        assert out["resultType"] == "vector"
        assert len(out["results"]) == 2
        assert out["results"][0]["metric_name"] == "up"
        assert out["results"][0]["labels"] == {"job": "prometheus"}
        assert out["results"][0]["value"] == "1"
        assert out["results"][0]["timestamp"] == 1700000000
        assert "truncation" not in out

    def test_empty_vector(self):
        data = {"resultType": "vector", "result": []}
        out = format_vector(data)
        assert out["results"] == []

    def test_truncation(self):
        result = [
            {"metric": {"__name__": f"m{i}"}, "value": [1700000000, str(i)]}
            for i in range(60)
        ]
        data = {"resultType": "vector", "result": result}
        out = format_vector(data, max_results=10)
        assert len(out["results"]) == 10
        assert out["truncation"]["truncated"] is True
        assert out["truncation"]["total"] == 60
        assert out["truncation"]["showing"] == 10

    def test_missing_name(self):
        data = {
            "resultType": "vector",
            "result": [{"metric": {"job": "test"}, "value": [1700000000, "42"]}],
        }
        out = format_vector(data)
        assert out["results"][0]["metric_name"] == ""
        assert out["results"][0]["labels"] == {"job": "test"}


# ------------------------------------------------------------------ #
# format_matrix
# ------------------------------------------------------------------ #


class TestFormatMatrix:
    def test_basic_matrix(self):
        data = {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"__name__": "cpu", "pod": "app-1"},
                    "values": [
                        [1700000000, "0.1"],
                        [1700000060, "0.5"],
                        [1700000120, "0.3"],
                    ],
                }
            ],
        }
        out = format_matrix(data)
        assert out["resultType"] == "matrix"
        assert len(out["results"]) == 1
        r = out["results"][0]
        assert r["metric_name"] == "cpu"
        assert r["labels"] == {"pod": "app-1"}
        assert r["num_samples"] == 3
        assert r["first_value"] == 0.1
        assert r["last_value"] == 0.3
        assert r["min"] == 0.1
        assert r["max"] == 0.5
        assert r["avg"] == pytest.approx(0.3, abs=0.001)
        assert r["time_range"]["start"] == 1700000000
        assert r["time_range"]["end"] == 1700000120

    def test_empty_values(self):
        data = {
            "resultType": "matrix",
            "result": [{"metric": {"__name__": "x"}, "values": []}],
        }
        out = format_matrix(data)
        r = out["results"][0]
        assert r["num_samples"] == 0
        assert "first_value" not in r

    def test_truncation(self):
        result = [
            {"metric": {"__name__": f"m{i}"}, "values": [[1700000000, "1"]]}
            for i in range(55)
        ]
        data = {"resultType": "matrix", "result": result}
        out = format_matrix(data, max_results=MAX_RESULTS)
        assert len(out["results"]) == MAX_RESULTS
        assert out["truncation"]["total"] == 55


# ------------------------------------------------------------------ #
# format_targets
# ------------------------------------------------------------------ #


class TestFormatTargets:
    def test_basic_targets(self):
        data = {
            "activeTargets": [
                {
                    "labels": {"job": "prometheus", "instance": "localhost:9090"},
                    "health": "up",
                    "lastScrape": "2024-01-01T00:00:00Z",
                    "lastScrapeDuration": 0.005,
                },
                {
                    "labels": {"job": "node", "instance": "node1:9100"},
                    "health": "down",
                    "lastScrape": "2024-01-01T00:00:00Z",
                    "lastScrapeDuration": 0.0,
                },
            ],
            "droppedTargets": [{"labels": {"job": "dropped"}}],
        }
        out = format_targets(data)
        assert len(out["active_targets"]) == 2
        assert out["active_targets"][0]["job"] == "prometheus"
        assert out["active_targets"][0]["health"] == "up"
        assert out["summary"]["total_active"] == 2
        assert out["summary"]["healthy"] == 1
        assert out["summary"]["unhealthy"] == 1
        assert out["dropped_targets_count"] == 1

    def test_empty_targets(self):
        data = {"activeTargets": [], "droppedTargets": []}
        out = format_targets(data)
        assert out["summary"]["total_active"] == 0
        assert out["dropped_targets_count"] == 0


# ------------------------------------------------------------------ #
# format_alerts
# ------------------------------------------------------------------ #


class TestFormatAlerts:
    def test_firing_alerts(self):
        data = {
            "alerts": [
                {
                    "labels": {"alertname": "HighCPU", "severity": "critical"},
                    "annotations": {"summary": "CPU is above 90%"},
                    "state": "firing",
                    "activeAt": "2024-01-01T00:00:00Z",
                },
                {
                    "labels": {"alertname": "DiskFull", "severity": "warning"},
                    "annotations": {"description": "Disk usage above 80%"},
                    "state": "pending",
                    "activeAt": "2024-01-01T01:00:00Z",
                },
            ]
        }
        out = format_alerts(data)
        assert len(out["alerts"]) == 2
        assert out["alerts"][0]["alertname"] == "HighCPU"
        assert out["alerts"][0]["severity"] == "critical"
        assert out["alerts"][0]["summary"] == "CPU is above 90%"
        # Falls back to description when summary is absent
        assert out["alerts"][1]["summary"] == "Disk usage above 80%"
        assert out["summary"]["total"] == 2
        assert out["summary"]["firing"] == 1
        assert out["summary"]["pending"] == 1

    def test_empty_alerts(self):
        data = {"alerts": []}
        out = format_alerts(data)
        assert out["alerts"] == []
        assert out["summary"]["total"] == 0


# ------------------------------------------------------------------ #
# format_rules
# ------------------------------------------------------------------ #


class TestFormatRules:
    def test_mixed_rules(self):
        data = {
            "groups": [
                {
                    "name": "cpu-rules",
                    "rules": [
                        {
                            "name": "HighCPU",
                            "type": "alerting",
                            "query": "rate(cpu[5m]) > 0.9",
                            "health": "ok",
                            "lastEvaluation": "2024-01-01T00:00:00Z",
                        },
                        {
                            "name": "cpu:avg5m",
                            "type": "recording",
                            "query": "avg(rate(cpu[5m]))",
                            "health": "ok",
                            "lastEvaluation": "2024-01-01T00:00:00Z",
                        },
                    ],
                },
                {
                    "name": "memory-rules",
                    "rules": [
                        {
                            "name": "HighMemory",
                            "type": "alerting",
                            "query": "mem > 1e9",
                            "health": "ok",
                            "lastEvaluation": "2024-01-01T00:00:00Z",
                        },
                    ],
                },
            ]
        }
        out = format_rules(data)
        assert len(out["rules"]) == 3
        assert out["rules"][0]["group"] == "cpu-rules"
        assert out["rules"][2]["group"] == "memory-rules"
        assert out["summary"]["total"] == 3
        assert out["summary"]["alerting"] == 2
        assert out["summary"]["recording"] == 1

    def test_empty_groups(self):
        data = {"groups": []}
        out = format_rules(data)
        assert out["rules"] == []
        assert out["summary"]["total"] == 0

    def test_truncation(self):
        rules = [{"name": f"r{i}", "type": "alerting", "query": "x", "health": "ok", "lastEvaluation": ""} for i in range(60)]
        data = {"groups": [{"name": "big", "rules": rules}]}
        out = format_rules(data, max_results=10)
        assert len(out["rules"]) == 10
        assert out["truncation"]["total"] == 60
