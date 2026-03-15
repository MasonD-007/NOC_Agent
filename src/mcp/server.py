import os
import json as _json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from netmiko import ConnectHandler
import uvicorn

from tools.prometheus import (
    _get_top_suspicious_ips,
    _get_traffic_spike_alerts,
    _get_failed_login_events,
    _get_ip_event_history,
)
from tools.logs import _get_recent_logs

load_dotenv()

server = Server("noc-security-agent")

DEVICE_INVENTORY = {
    "core-router": {
        "device_type": "linux",
        "host": "core-router",
        "port": 2222,
        "username": "admin",
        "password": "hackathon",
    },
    "edge-sw-01": {
        "device_type": "linux",
        "host": "edge-sw-01",
        "port": 2222,
        "username": "admin",
        "password": "hackathon",
    },
    "edge-sw-02": {
        "device_type": "linux",
        "host": "edge-sw-02",
        "port": 2222,
        "username": "admin",
        "password": "hackathon",
    },
}

PROMETHEUS_URL = "http://prometheus:9090"
LOG_AGGREGATOR_URL = "http://log-aggregator:8000"


def _prom_query(query: str) -> list:
    url = f"{PROMETHEUS_URL}/api/v1/query?" + urllib.parse.urlencode({"query": query})
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = _json.loads(resp.read())
            return data.get("data", {}).get("result", [])
    except Exception:
        return []


def _log_recent_for_ip(ip: str) -> list:
    try:
        with urllib.request.urlopen(f"{LOG_AGGREGATOR_URL}/recent_events", timeout=5) as resp:
            events = _json.loads(resp.read())
            return [e for e in events if e.get("source_ip") == ip]
    except Exception:
        return []


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ssh_execute",
            description=(
                "Execute a shell command on a network device via SSH. "
                "device_hostname: Docker DNS name (e.g. 'edge-sw-02'). "
                "command: shell command to run (e.g. 'iptables -A INPUT -s 172.20.0.5 -j DROP'). "
                "confirmed: safety flag — must be true to execute."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_hostname": {"type": "string", "description": "Docker DNS name of the device"},
                    "command": {"type": "string", "description": "Shell command to run on the device"},
                    "confirmed": {"type": ["boolean", "string"], "description": "Safety flag — must be true to execute"},
                },
                "required": ["device_hostname", "command", "confirmed"],
            },
        ),
        Tool(
            name="explain_threat",
            description=(
                "Aggregate Prometheus metrics and log-aggregator data for a given source IP "
                "into a single structured threat summary. Use this to explain why an IP was "
                "flagged and quantify its activity across all event types."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "The source IP address to explain"},
                },
                "required": ["ip"],
            },
        ),
        Tool(
            name="get_traffic_spike_alerts",
            description="Return active traffic spike alerts from Prometheus, including source IP, destination IP, and bytes per second.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {"type": ["integer", "string"], "description": "Look back N hours (default 1)", "default": 1},
                },
            },
        ),
        Tool(
            name="get_top_suspicious_ips",
            description="Return the top suspicious IP addresses ranked by threat score based on traffic volume, failed logins, and event rate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": ["integer", "string"], "description": "Max results to return (default 5)", "default": 5},
                },
            },
        ),
        Tool(
            name="get_failed_login_events",
            description="Return failed login attempts from Prometheus metrics, including source IP, target user, and count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {"type": ["integer", "string"], "description": "Look back N hours (default 1)", "default": 1},
                },
            },
        ),
        Tool(
            name="get_ip_event_history",
            description="Return the full event history for a specific IP address including traffic, failed logins, event rate, and threat score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address to look up"},
                },
                "required": ["ip"],
            },
        ),
        Tool(
            name="get_recent_logs",
            description="Fetch recent security log events from the log aggregator, optionally filtered by severity (info, warning, error, critical).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": ["integer", "string"], "description": "Max events to return (default 20)", "default": 20},
                    "severity": {"type": "string", "description": "Filter by severity level (info/warning/error/critical/all)", "default": "all"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "ssh_execute":
        device_hostname = arguments["device_hostname"]
        command = arguments["command"]
        confirmed = arguments.get("confirmed", False)
        if isinstance(confirmed, str):
            confirmed = confirmed.lower() == "true"

        if not confirmed:
            return [TextContent(type="text", text=f"Action requires confirmed=true. Got confirmed=false for: {command}")]

        device = DEVICE_INVENTORY.get(device_hostname)
        if device is None:
            return [TextContent(type="text", text=f"Unknown device '{device_hostname}'. Available: {', '.join(DEVICE_INVENTORY.keys())}")]

        try:
            conn = ConnectHandler(**device)
            output = conn.send_command(command)
            conn.disconnect()
            return [TextContent(type="text", text=f"SUCCESS on {device_hostname}:\n$ {command}\n{output}")]
        except Exception as e:
            return [TextContent(type="text", text=f"FAILED on {device_hostname}: {e}")]

    if name == "explain_threat":
        ip = arguments.get("ip", "")
        if not ip:
            return [TextContent(type="text", text=_json.dumps({"error": "ip argument required"}))]

        security_events  = _prom_query(f'security_events_total{{source_ip="{ip}"}}')
        failed_logins    = _prom_query(f'failed_logins_per_ip_total{{source_ip="{ip}"}}')
        suspicious_reqs  = _prom_query(f'suspicious_requests_total{{source_ip="{ip}"}}')
        traffic          = _prom_query(f'traffic_bytes_per_sec{{source_ip="{ip}"}}')
        threat_score_res = _prom_query(f'payload_threat_score{{source_ip="{ip}"}}')
        event_rate_res   = _prom_query(f'recent_event_rate_per_minute{{source_ip="{ip}"}}')

        total_events = int(sum(float(r["value"][1]) for r in security_events))

        event_breakdown: dict = {}
        for r in security_events:
            evt = r["metric"].get("event_type", "unknown")
            sev = r["metric"].get("severity", "unknown")
            event_breakdown.setdefault(evt, {})[sev] = int(float(r["value"][1]))

        failed_login_breakdown: dict = {}
        for r in failed_logins:
            user = r["metric"].get("target_user", "unknown")
            failed_login_breakdown[user] = int(float(r["value"][1]))

        suspicious_req_breakdown: dict = {}
        for r in suspicious_reqs:
            ep = r["metric"].get("endpoint", "unknown")
            suspicious_req_breakdown[ep] = int(float(r["value"][1]))

        current_bps   = int(float(traffic[0]["value"][1]))          if traffic          else 0
        payload_score = int(float(threat_score_res[0]["value"][1])) if threat_score_res else 0
        event_rate    = int(float(event_rate_res[0]["value"][1]))    if event_rate_res   else 0

        recent_activity = _log_recent_for_ip(ip)

        if total_events > 100 or payload_score > 70 or current_bps > 50_000_000:
            risk_level = "critical"
        elif total_events > 20 or payload_score > 40:
            risk_level = "high"
        elif total_events > 5:
            risk_level = "medium"
        else:
            risk_level = "low"

        summary = {
            "ip": ip,
            "risk_level": risk_level,
            "threat_summary": {
                "total_events": total_events,
                "event_breakdown": event_breakdown,
                "failed_logins_by_user": failed_login_breakdown,
                "suspicious_requests_by_endpoint": suspicious_req_breakdown,
                "current_traffic_bps": current_bps,
                "payload_threat_score": payload_score,
                "recent_event_rate_per_minute": event_rate,
            },
            "recent_activity_count": len(recent_activity),
        }
        return [TextContent(type="text", text=_json.dumps(summary))]

    if name == "get_traffic_spike_alerts":
        return _get_traffic_spike_alerts(int(arguments.get("hours", 1)))

    if name == "get_top_suspicious_ips":
        return _get_top_suspicious_ips(int(arguments.get("limit", 5)))

    if name == "get_failed_login_events":
        return _get_failed_login_events(int(arguments.get("hours", 1)))

    if name == "get_ip_event_history":
        return _get_ip_event_history(arguments.get("ip", ""))

    if name == "get_recent_logs":
        return _get_recent_logs(int(arguments.get("limit", 20)), arguments.get("severity", "all"))

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
