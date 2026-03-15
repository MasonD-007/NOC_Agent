import json
import requests
from mcp.server import Server
from mcp.types import TextContent

LOG_AGG = "http://log-aggregator:8000"
PROMETHEUS = "http://prometheus:9090"

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.call_tool()
    async def _handle(name: str, arguments: dict) -> list[TextContent]:
        if name == "get_recent_logs":
            return _get_recent_logs(
                arguments.get("limit", 20),
                arguments.get("severity", "all"),
            )
        return None  # not our tool, pass through


def _get_recent_logs(limit: int, severity: str) -> list[TextContent]:
    """Fetch recent events from the log aggregator and optionally filter by severity."""
    try:
        resp = requests.get(f"{LOG_AGG}/recent_events", timeout=5)
        events = resp.json()
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to fetch logs: {e}")]

    # Also pull security_events_total from Prometheus for richer data
    try:
        prom_resp = requests.get(
            f"{PROMETHEUS}/api/v1/query",
            params={"query": "security_events_total"},
            timeout=5,
        )
        prom_data = prom_resp.json()
        if prom_data.get("status") == "success":
            for r in prom_data["data"]["result"]:
                events.append({
                    "source_ip": r["metric"].get("source_ip", "unknown"),
                    "event_type": r["metric"].get("event_type", "unknown"),
                    "severity": r["metric"].get("severity", "unknown"),
                    "count": float(r["value"][1]),
                })
    except Exception:
        pass

    # Filter by severity if specified
    if severity and severity != "all":
        events = [e for e in events if e.get("severity", "").lower() == severity.lower()]

    events = events[-limit:]

    if not events:
        return [TextContent(type="text", text=f"No log events found (severity={severity}).")]
    return [TextContent(type="text", text=json.dumps(events, indent=2))]
