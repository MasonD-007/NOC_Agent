import json
import requests
from mcp.server import Server
from mcp.types import TextContent

LOG_AGG = "http://log-aggregator:8000"
PROMETHEUS = "http://prometheus:9090"

_server: Server | None = None


def _query_prometheus(query: str) -> list[dict]:
    """Run an instant PromQL query and return the result vector."""
    try:
        resp = requests.get(f"{PROMETHEUS}/api/v1/query", params={"query": query}, timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return data["data"]["result"]
    except Exception:
        pass
    return []


def register(server: Server) -> None:
    global _server
    _server = server

    @server.call_tool()
    async def _handle(name: str, arguments: dict) -> list[TextContent]:
        if name == "get_top_suspicious_ips":
            return _get_top_suspicious_ips(arguments.get("limit", 5))
        elif name == "get_traffic_spike_alerts":
            return _get_traffic_spike_alerts(arguments.get("hours", 1))
        elif name == "get_failed_login_events":
            return _get_failed_login_events(arguments.get("hours", 1))
        elif name == "get_ip_event_history":
            return _get_ip_event_history(arguments.get("ip", ""))
        return None  # not our tool, pass through


def _get_top_suspicious_ips(limit: int) -> list[TextContent]:
    """Rank IPs by combining traffic volume, failed logins, and event rate."""
    scores: dict[str, dict] = {}

    # Traffic volume
    for r in _query_prometheus("traffic_bytes_per_sec"):
        ip = r["metric"].get("source_ip", "unknown")
        bps = float(r["value"][1])
        scores.setdefault(ip, {"ip": ip, "traffic_bps": 0, "failed_logins": 0, "event_rate": 0})
        scores[ip]["traffic_bps"] = bps

    # Failed logins
    for r in _query_prometheus("failed_logins_per_ip_total"):
        ip = r["metric"].get("source_ip", "unknown")
        val = float(r["value"][1])
        scores.setdefault(ip, {"ip": ip, "traffic_bps": 0, "failed_logins": 0, "event_rate": 0})
        scores[ip]["failed_logins"] = val

    # Event rate
    for r in _query_prometheus("recent_event_rate_per_minute"):
        ip = r["metric"].get("source_ip", "unknown")
        val = float(r["value"][1])
        scores.setdefault(ip, {"ip": ip, "traffic_bps": 0, "failed_logins": 0, "event_rate": 0})
        scores[ip]["event_rate"] = val

    # Compute composite threat score
    for entry in scores.values():
        entry["threat_score"] = round(
            min(entry["traffic_bps"] / 1_000_000, 50) +
            min(entry["failed_logins"] * 5, 30) +
            min(entry["event_rate"], 20),
            1,
        )

    ranked = sorted(scores.values(), key=lambda x: x["threat_score"], reverse=True)[:limit]
    return [TextContent(type="text", text=json.dumps(ranked, indent=2))]


def _get_traffic_spike_alerts(hours: int) -> list[TextContent]:
    """Get current traffic spike data from Prometheus."""
    results = _query_prometheus("traffic_bytes_per_sec > 10000000")
    spikes = []
    for r in results:
        spikes.append({
            "source_ip": r["metric"].get("source_ip", "unknown"),
            "destination_ip": r["metric"].get("destination_ip", "unknown"),
            "bytes_per_sec": float(r["value"][1]),
        })

    if not spikes:
        # Also check recent events from log aggregator
        try:
            resp = requests.get(f"{LOG_AGG}/recent_events", timeout=5)
            events = resp.json()
            for e in events:
                if e.get("event_type") == "traffic_spike":
                    spikes.append(e)
        except Exception:
            pass

    if not spikes:
        return [TextContent(type="text", text="No active traffic spikes detected.")]
    return [TextContent(type="text", text=json.dumps(spikes, indent=2))]


def _get_failed_login_events(hours: int) -> list[TextContent]:
    """Get failed login counts from Prometheus."""
    results = _query_prometheus("failed_logins_per_ip_total")
    events = []
    for r in results:
        events.append({
            "source_ip": r["metric"].get("source_ip", "unknown"),
            "target_user": r["metric"].get("target_user", "unknown"),
            "count": float(r["value"][1]),
        })
    if not events:
        return [TextContent(type="text", text="No failed login events found.")]
    return [TextContent(type="text", text=json.dumps(events, indent=2))]


def _get_ip_event_history(ip: str) -> list[TextContent]:
    """Get all metrics related to a specific IP."""
    history = {"ip": ip, "traffic": [], "failed_logins": [], "event_rate": None, "threat_score": None}

    for r in _query_prometheus(f'traffic_bytes_per_sec{{source_ip="{ip}"}}'):
        history["traffic"].append({
            "destination_ip": r["metric"].get("destination_ip", "unknown"),
            "bytes_per_sec": float(r["value"][1]),
        })

    for r in _query_prometheus(f'failed_logins_per_ip_total{{source_ip="{ip}"}}'):
        history["failed_logins"].append({
            "target_user": r["metric"].get("target_user", "unknown"),
            "count": float(r["value"][1]),
        })

    for r in _query_prometheus(f'recent_event_rate_per_minute{{source_ip="{ip}"}}'):
        history["event_rate"] = float(r["value"][1])

    for r in _query_prometheus(f'payload_threat_score{{source_ip="{ip}"}}'):
        history["threat_score"] = float(r["value"][1])

    return [TextContent(type="text", text=json.dumps(history, indent=2))]
