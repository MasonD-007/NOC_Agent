"""
Prometheus tools — query the Prometheus HTTP API.

Inside Docker, Prometheus is reachable at http://prometheus:9090.
Metrics available (from log_aggregator.py):

  security_events_total{event_type, severity, source_ip}
  failed_logins_per_ip_total{source_ip, target_user}
  suspicious_requests_total{source_ip, endpoint}
  traffic_bytes_per_sec{source_ip, destination_ip}
  payload_threat_score{source_ip}
  recent_event_rate_per_minute{source_ip}
"""

import os
import time

import requests as _requests
from mcp.server import Server

PROM_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

_server: Server | None = None


def _query(q: str) -> list:
    r = _requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=8)
    r.raise_for_status()
    return r.json().get("data", {}).get("result", [])


def _query_range(q: str, hours: int) -> list:
    end   = int(time.time())
    start = end - hours * 3600
    step  = max(60, hours * 36)
    r = _requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": q, "start": start, "end": end, "step": f"{step}s"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("result", [])


def _alerts() -> list:
    r = _requests.get(f"{PROM_URL}/api/v1/alerts", timeout=8)
    r.raise_for_status()
    return r.json().get("data", {}).get("alerts", [])


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_top_suspicious_ips(limit: int = 10) -> list[dict]:
        """Return the top N most suspicious IPs ranked by a composite threat score
        derived from failed logins, traffic volume, payload threat score, and event rate."""
        scores: dict[str, dict] = {}

        def _acc(prom_name: str, key: str) -> None:
            for item in _query(prom_name):
                ip = item["metric"].get("source_ip", "unknown")
                if ip == "unknown":
                    continue
                scores.setdefault(ip, {})[key] = float(item["value"][1])

        _acc("failed_logins_per_ip_total",   "failed_logins")
        _acc("traffic_bytes_per_sec",         "traffic_bps")
        _acc("payload_threat_score",          "payload_threat_score")
        _acc("recent_event_rate_per_minute",  "event_rate_per_min")
        _acc("suspicious_requests_total",     "suspicious_requests")

        result = []
        for ip, data in scores.items():
            composite = (
                min(data.get("failed_logins", 0) * 2,         100) +
                min(data.get("traffic_bps",   0) / 1_000_000, 100) +
                    data.get("payload_threat_score", 0)             +
                min(data.get("event_rate_per_min", 0) * 2,    100)
            ) / 4
            result.append({"ip": ip, "composite_score": round(composite, 1), **data})

        result.sort(key=lambda x: x["composite_score"], reverse=True)
        return result[:limit]

    @server.tool()
    def get_traffic_spike_alerts(hours: int = 1) -> dict:
        """Return traffic spike events from the last N hours where bytes/sec exceeded
        10 MB/s, including currently firing Prometheus alerts and historical series."""
        firing = [
            {
                "alertname":   a["labels"].get("alertname"),
                "source_ip":   a["labels"].get("source_ip"),
                "destination": a["labels"].get("destination_ip"),
                "severity":    a["labels"].get("severity"),
                "state":       a["state"],
                "description": a.get("annotations", {}).get("description"),
            }
            for a in _alerts()
            if a["labels"].get("alertname") == "TrafficSpike"
        ]

        historical = []
        for series in _query_range("traffic_bytes_per_sec > 10000000", hours):
            ip   = series["metric"].get("source_ip", "unknown")
            dest = series["metric"].get("destination_ip", "unknown")
            peak = max(float(v[1]) for v in series["values"])
            historical.append({
                "source_ip":          ip,
                "destination_ip":     dest,
                "peak_bytes_per_sec": int(peak),
                "data_points":        len(series["values"]),
            })

        return {"window_hours": hours, "firing_alerts": firing, "historical_spikes": historical}

    @server.tool()
    def get_failed_login_events(hours: int = 1) -> dict:
        """Return failed SSH login events aggregated by source IP and target user
        over the last N hours, sorted by attempt count descending."""
        results = _query(f"increase(failed_logins_per_ip_total[{hours}h])")
        events = [
            {
                "source_ip":   item["metric"].get("source_ip", "unknown"),
                "target_user": item["metric"].get("target_user", "unknown"),
                "attempts":    int(float(item["value"][1])),
            }
            for item in results
            if float(item["value"][1]) > 0
        ]
        events.sort(key=lambda x: x["attempts"], reverse=True)
        return {"window_hours": hours, "events": events, "total_source_ips": len(events)}

    @server.tool()
    def get_ip_event_history(ip: str) -> dict:
        """Return all available Prometheus metrics and recent log-aggregator events
        for a specific IP address — full threat profile for one IP."""
        metric_snapshot: dict = {}
        for prom_name, friendly_name in [
            ("failed_logins_per_ip_total",  "failed_logins_total"),
            ("traffic_bytes_per_sec",        "traffic_bytes_per_sec"),
            ("payload_threat_score",         "payload_threat_score"),
            ("suspicious_requests_total",    "suspicious_requests_total"),
            ("recent_event_rate_per_minute", "event_rate_per_min"),
            ("security_events_total",        "security_events_total"),
        ]:
            for item in _query(f'{prom_name}{{source_ip="{ip}"}}'):
                val    = float(item["value"][1])
                labels = {k: v for k, v in item["metric"].items() if k not in ("__name__", "source_ip")}
                key    = f"{friendly_name}({','.join(f'{k}={v}' for k, v in labels.items())})" if labels else friendly_name
                metric_snapshot[key] = val

        return {"ip": ip, "prometheus_metrics": metric_snapshot}
