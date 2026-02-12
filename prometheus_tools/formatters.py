"""LLM-friendly formatters for Prometheus API responses.

Each formatter takes raw Prometheus data and returns a concise, structured
representation that is easy for an LLM to reason about.
"""

from __future__ import annotations

MAX_RESULTS = 50


def _truncation_note(total: int, limit: int) -> dict | None:
    """Return a truncation warning dict if results were capped."""
    if total > limit:
        return {
            "truncated": True,
            "showing": limit,
            "total": total,
            "note": f"Results truncated to {limit} of {total}. Narrow your query for complete data.",
        }
    return None


# ------------------------------------------------------------------ #
# Vector (instant query) results
# ------------------------------------------------------------------ #


def format_vector(data: dict, max_results: int = MAX_RESULTS) -> dict:
    """Format an instant-query vector result.

    Input shape:  {"resultType": "vector", "result": [{metric: {...}, value: [ts, val]}, ...]}
    Output shape: {"resultType": "vector", "results": [{metric_name, labels, value, timestamp}, ...]}
    """
    raw_results = data.get("result", [])
    total = len(raw_results)
    formatted = []
    for item in raw_results[:max_results]:
        metric = item.get("metric", {})
        value = item.get("value", [None, None])
        labels = {k: v for k, v in metric.items() if k != "__name__"}
        formatted.append({
            "metric_name": metric.get("__name__", ""),
            "labels": labels,
            "value": value[1] if len(value) > 1 else None,
            "timestamp": value[0] if len(value) > 0 else None,
        })

    result = {"resultType": "vector", "results": formatted}
    note = _truncation_note(total, max_results)
    if note:
        result["truncation"] = note
    return result


# ------------------------------------------------------------------ #
# Matrix (range query) results
# ------------------------------------------------------------------ #


def format_matrix(data: dict, max_results: int = MAX_RESULTS) -> dict:
    """Format a range-query matrix result with summary statistics.

    Input shape:  {"resultType": "matrix", "result": [{metric: {...}, values: [[ts,val], ...]}, ...]}
    Output shape: {"resultType": "matrix", "results": [{metric_name, labels, num_samples,
                   first_value, last_value, min, max, avg}, ...]}
    """
    raw_results = data.get("result", [])
    total = len(raw_results)
    formatted = []
    for item in raw_results[:max_results]:
        metric = item.get("metric", {})
        values = item.get("values", [])
        labels = {k: v for k, v in metric.items() if k != "__name__"}

        float_vals = []
        for pair in values:
            try:
                float_vals.append(float(pair[1]))
            except (ValueError, IndexError, TypeError):
                continue

        summary = {
            "metric_name": metric.get("__name__", ""),
            "labels": labels,
            "num_samples": len(values),
        }
        if float_vals:
            summary.update({
                "first_value": float_vals[0],
                "last_value": float_vals[-1],
                "min": min(float_vals),
                "max": max(float_vals),
                "avg": round(sum(float_vals) / len(float_vals), 6),
            })
        if values:
            summary["time_range"] = {
                "start": values[0][0],
                "end": values[-1][0],
            }

        formatted.append(summary)

    result = {"resultType": "matrix", "results": formatted}
    note = _truncation_note(total, max_results)
    if note:
        result["truncation"] = note
    return result


# ------------------------------------------------------------------ #
# Targets
# ------------------------------------------------------------------ #


def format_targets(data: dict, max_results: int = MAX_RESULTS) -> dict:
    """Flatten target data into an LLM-friendly summary.

    Input shape:  {"activeTargets": [...], "droppedTargets": [...]}
    Output shape: {"active_targets": [{job, instance, health, last_scrape, scrape_duration}, ...],
                   "summary": {total_active, healthy, unhealthy}}
    """
    active = data.get("activeTargets", [])
    total = len(active)
    formatted = []
    healthy_count = 0
    for t in active[:max_results]:
        labels = t.get("labels", {})
        health = t.get("health", "unknown")
        if health == "up":
            healthy_count += 1
        formatted.append({
            "job": labels.get("job", ""),
            "instance": labels.get("instance", ""),
            "health": health,
            "last_scrape": t.get("lastScrape", ""),
            "scrape_duration": t.get("lastScrapeDuration", None),
        })

    result = {
        "active_targets": formatted,
        "summary": {
            "total_active": total,
            "healthy": healthy_count,
            "unhealthy": total - healthy_count,
        },
        "dropped_targets_count": len(data.get("droppedTargets", [])),
    }
    note = _truncation_note(total, max_results)
    if note:
        result["truncation"] = note
    return result


# ------------------------------------------------------------------ #
# Alerts
# ------------------------------------------------------------------ #


def format_alerts(data: dict, max_results: int = MAX_RESULTS) -> dict:
    """Flatten alert data into an LLM-friendly summary.

    Input shape:  {"alerts": [{labels: {...}, state, activeAt, ...}, ...]}
    Output shape: {"alerts": [{alertname, state, severity, summary, active_since}, ...],
                   "summary": {total, firing, pending}}
    """
    raw_alerts = data.get("alerts", [])
    total = len(raw_alerts)
    firing = sum(1 for a in raw_alerts if a.get("state") == "firing")
    pending = sum(1 for a in raw_alerts if a.get("state") == "pending")

    formatted = []
    for a in raw_alerts[:max_results]:
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})
        formatted.append({
            "alertname": labels.get("alertname", ""),
            "state": a.get("state", ""),
            "severity": labels.get("severity", ""),
            "summary": annotations.get("summary", annotations.get("description", "")),
            "active_since": a.get("activeAt", ""),
        })

    result = {
        "alerts": formatted,
        "summary": {"total": total, "firing": firing, "pending": pending},
    }
    note = _truncation_note(total, max_results)
    if note:
        result["truncation"] = note
    return result


# ------------------------------------------------------------------ #
# Rules
# ------------------------------------------------------------------ #


def format_rules(data: dict, max_results: int = MAX_RESULTS) -> dict:
    """Flatten rule groups into a flat list of rules.

    Input shape:  {"groups": [{name, rules: [{name, type, query, health, lastEvaluation}, ...]}, ...]}
    Output shape: {"rules": [{name, group, type, query, health, last_evaluation}, ...],
                   "summary": {total, alerting, recording}}
    """
    groups = data.get("groups", [])
    flat_rules = []
    for group in groups:
        group_name = group.get("name", "")
        for rule in group.get("rules", []):
            flat_rules.append({
                "name": rule.get("name", ""),
                "group": group_name,
                "type": rule.get("type", ""),
                "query": rule.get("query", ""),
                "health": rule.get("health", ""),
                "last_evaluation": rule.get("lastEvaluation", ""),
            })

    total = len(flat_rules)
    alerting = sum(1 for r in flat_rules if r["type"] == "alerting")
    recording = sum(1 for r in flat_rules if r["type"] == "recording")

    result = {
        "rules": flat_rules[:max_results],
        "summary": {"total": total, "alerting": alerting, "recording": recording},
    }
    note = _truncation_note(total, max_results)
    if note:
        result["truncation"] = note
    return result
