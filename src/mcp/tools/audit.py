"""
Audit & explanation tools.

explain_threat(ip) aggregates evidence from:
  1. Prometheus metrics (all series for the IP)
  2. Active Prometheus alerts involving the IP
  3. Recent events from the log aggregator (/recent_events)
  4. Current iptables block status on core-router

Returns a single structured dict the frontend can render directly.
"""

import os
import time

import requests as _requests
from mcp.server import Server

PROM_URL    = os.getenv("PROMETHEUS_URL",     "http://prometheus:9090")
LOG_AGG_URL = os.getenv("LOG_AGGREGATOR_URL", "http://log-aggregator:8000")

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def explain_threat(ip: str) -> dict:
        """Aggregate all available evidence for an IP into a single structured threat report:
        Prometheus metrics, active alerts, recent log events, and firewall block status."""
        from tools.ssh import _connect

        report: dict = {
            "ip":         ip,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # ── 1. Prometheus metrics snapshot ────────────────────────────────────
        def _snap(prom_name: str, key: str) -> None:
            try:
                r = _requests.get(
                    f"{PROM_URL}/api/v1/query",
                    params={"query": f'{prom_name}{{source_ip="{ip}"}}'},
                    timeout=8,
                )
                rows = r.json().get("data", {}).get("result", [])
                if rows:
                    report.setdefault("metrics", {})[key] = float(rows[0]["value"][1])
            except Exception:
                pass

        report["metrics"] = {}
        _snap("failed_logins_per_ip_total",  "failed_logins_total")
        _snap("traffic_bytes_per_sec",        "traffic_bytes_per_sec")
        _snap("payload_threat_score",         "payload_threat_score")
        _snap("recent_event_rate_per_minute", "event_rate_per_min")
        _snap("suspicious_requests_total",    "suspicious_requests_total")

        # ── 2. Active Prometheus alerts for this IP ────────────────────────────
        report["active_alerts"] = []
        try:
            r       = _requests.get(f"{PROM_URL}/api/v1/alerts", timeout=8)
            alerts  = r.json().get("data", {}).get("alerts", [])
            report["active_alerts"] = [
                {
                    "name":        a["labels"].get("alertname"),
                    "severity":    a["labels"].get("severity"),
                    "state":       a["state"],
                    "description": a.get("annotations", {}).get("description"),
                }
                for a in alerts
                if a["labels"].get("source_ip") == ip
            ]
        except Exception:
            pass

        # ── 3. Recent log-aggregator events ───────────────────────────────────
        report["recent_events"] = []
        try:
            r = _requests.get(f"{LOG_AGG_URL}/recent_events", timeout=5)
            report["recent_events"] = [
                e for e in r.json() if e.get("source_ip") == ip
            ][-20:]
        except Exception:
            pass

        # ── 4. Firewall block status (iptables on core-router) ─────────────
        report["firewall_status"] = "unknown"
        try:
            conn   = _connect("core-router")
            rules  = conn.send_command(f"iptables -L INPUT -n 2>&1 | grep -w '{ip}' || echo NOT_FOUND")
            conn.disconnect()
            report["firewall_status"] = "blocked" if "DROP" in rules else "not_blocked"
            report["firewall_rules"]  = rules.strip()
        except Exception:
            pass

        # ── 5. Composite threat level ─────────────────────────────────────────
        m          = report["metrics"]
        composite  = (
            min(m.get("failed_logins_total",   0) * 2,         100) +
            min(m.get("traffic_bytes_per_sec", 0) / 1_000_000, 100) +
                m.get("payload_threat_score",  0)                   +
            min(m.get("event_rate_per_min",    0) * 2,         100)
        ) / 4

        num_alerts = len(report["active_alerts"])
        if   composite >= 60 or num_alerts >= 2: level = "critical"
        elif composite >= 30 or num_alerts >= 1: level = "high"
        elif composite >= 10:                    level = "medium"
        else:                                    level = "low"

        report["threat_level"]    = level
        report["composite_score"] = round(composite, 1)
        report["is_blocked"]      = report["firewall_status"] == "blocked"
        return report
