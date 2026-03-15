import json
import os
import time

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from netmiko import ConnectHandler
import uvicorn

load_dotenv()

server = Server("noc-security-agent")

PROM_URL    = os.getenv("PROMETHEUS_URL",    "http://prometheus:9090")
LOG_AGG_URL = os.getenv("LOG_AGGREGATOR_URL", "http://log-aggregator:8000")

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

# ─── SSH Helper ───────────────────────────────────────────────────────────────

def _ssh_run(device_hostname: str, command: str) -> str:
    device = DEVICE_INVENTORY.get(device_hostname)
    if device is None:
        raise ValueError(
            f"Unknown device '{device_hostname}'. "
            f"Available: {', '.join(DEVICE_INVENTORY.keys())}"
        )
    conn = ConnectHandler(**device)
    output = conn.send_command(command)
    conn.disconnect()
    return output

# ─── Prometheus Helper ────────────────────────────────────────────────────────

def _prom_query(q: str) -> list:
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=8)
    r.raise_for_status()
    return r.json().get("data", {}).get("result", [])

def _prom_query_range(q: str, hours: int) -> list:
    end   = int(time.time())
    start = end - hours * 3600
    step  = max(60, hours * 36)  # ~100 data points across the window
    r = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": q, "start": start, "end": end, "step": f"{step}s"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("result", [])

def _prom_alerts() -> list:
    r = requests.get(f"{PROM_URL}/api/v1/alerts", timeout=8)
    r.raise_for_status()
    return r.json().get("data", {}).get("alerts", [])

# ─── Tool Definitions ─────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── SSH ──────────────────────────────────────────────────────────────
        Tool(
            name="ssh_execute",
            description=(
                "Execute an arbitrary shell command on a network device via SSH. "
                "device_hostname: Docker DNS name (core-router, edge-sw-01, edge-sw-02). "
                "command: shell command to run. confirmed: safety flag — must be true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_hostname": {"type": "string"},
                    "command":         {"type": "string"},
                    "confirmed":       {"type": ["boolean", "string"]},
                },
                "required": ["device_hostname", "command", "confirmed"],
            },
        ),

        # ── Firewall ─────────────────────────────────────────────────────────
        Tool(
            name="block_ip",
            description=(
                "Block all inbound and forwarded traffic from an IP address using iptables. "
                "Runs on device_hostname (default: core-router). confirmed must be true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip":              {"type": "string", "description": "IP address to block"},
                    "device_hostname": {"type": "string", "default": "core-router"},
                    "confirmed":       {"type": ["boolean", "string"]},
                },
                "required": ["ip", "confirmed"],
            },
        ),
        Tool(
            name="unblock_ip",
            description=(
                "Remove an existing iptables DROP rule for the given IP address. "
                "Runs on device_hostname (default: core-router). confirmed must be true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip":              {"type": "string"},
                    "device_hostname": {"type": "string", "default": "core-router"},
                    "confirmed":       {"type": ["boolean", "string"]},
                },
                "required": ["ip", "confirmed"],
            },
        ),
        Tool(
            name="block_subnet",
            description=(
                "Block all traffic from a CIDR subnet using iptables (e.g. '192.168.1.0/24'). "
                "Runs on device_hostname (default: core-router). confirmed must be true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subnet":          {"type": "string"},
                    "device_hostname": {"type": "string", "default": "core-router"},
                    "confirmed":       {"type": ["boolean", "string"]},
                },
                "required": ["subnet", "confirmed"],
            },
        ),
        Tool(
            name="rate_limit_ip",
            description=(
                "Rate-limit traffic from an IP to requests_per_minute using iptables hashlimit. "
                "Traffic above the limit is DROPped. confirmed must be true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip":                  {"type": "string"},
                    "requests_per_minute": {"type": "integer"},
                    "device_hostname":     {"type": "string", "default": "core-router"},
                    "confirmed":           {"type": ["boolean", "string"]},
                },
                "required": ["ip", "requests_per_minute", "confirmed"],
            },
        ),
        Tool(
            name="get_blocked_list",
            description=(
                "Return all current iptables DROP rules on a device "
                "(default: core-router), showing blocked IPs and subnets."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_hostname": {"type": "string", "default": "core-router"},
                },
                "required": [],
            },
        ),

        # ── Prometheus ────────────────────────────────────────────────────────
        Tool(
            name="get_top_suspicious_ips",
            description=(
                "Return the top N most suspicious IPs ranked by a composite threat score "
                "derived from failed logins, traffic volume, payload threat score, and event rate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_traffic_spike_alerts",
            description=(
                "Return traffic spike events from the last N hours where bytes/sec exceeded "
                "the DDoS threshold (10 MB/s), including source IP, destination, and peak rate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 1},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_failed_login_events",
            description=(
                "Return failed SSH login events aggregated by source IP and target user "
                "over the last N hours, sorted by attempt count descending."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 1},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_ip_event_history",
            description=(
                "Return all available Prometheus metrics and recent log-aggregator events "
                "for a specific IP address — full threat profile for one IP."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                },
                "required": ["ip"],
            },
        ),

        # ── Audit / Explain ───────────────────────────────────────────────────
        Tool(
            name="explain_threat",
            description=(
                "Aggregate all available evidence for an IP address into a single structured "
                "threat report: Prometheus metrics, active alerts, recent events from the log "
                "aggregator, and current firewall block status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                },
                "required": ["ip"],
            },
        ),
    ]


# ─── Tool Handlers ────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    def ok(data) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    def err(msg: str) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps({"error": msg}))]

    def _confirmed(arguments: dict) -> bool:
        v = arguments.get("confirmed", False)
        return v is True or str(v).lower() == "true"

    # ── ssh_execute ───────────────────────────────────────────────────────────
    if name == "ssh_execute":
        device_hostname = arguments["device_hostname"]
        command         = arguments["command"]
        if not _confirmed(arguments):
            return err(f"confirmed must be true to run: {command}")
        device = DEVICE_INVENTORY.get(device_hostname)
        if not device:
            return err(f"Unknown device '{device_hostname}'. Available: {list(DEVICE_INVENTORY)}")
        try:
            conn   = ConnectHandler(**device)
            output = conn.send_command(command)
            conn.disconnect()
            return ok({"device": device_hostname, "command": command, "output": output, "status": "success"})
        except Exception as e:
            return err(f"SSH failed on {device_hostname}: {e}")

    # ── block_ip ──────────────────────────────────────────────────────────────
    if name == "block_ip":
        ip     = arguments["ip"]
        device = arguments.get("device_hostname", "core-router")
        if not _confirmed(arguments):
            return err(f"confirmed must be true to block {ip}")
        try:
            # Insert at top of chain so it takes priority; suppress duplicate-rule errors
            cmd    = f"iptables -C INPUT -s {ip} -j DROP 2>/dev/null || iptables -I INPUT 1 -s {ip} -j DROP; " \
                     f"iptables -C FORWARD -s {ip} -j DROP 2>/dev/null || iptables -I FORWARD 1 -s {ip} -j DROP"
            output = _ssh_run(device, cmd)
            return ok({"ip": ip, "device": device, "status": "blocked", "output": output})
        except Exception as e:
            return err(f"block_ip failed: {e}")

    # ── unblock_ip ────────────────────────────────────────────────────────────
    if name == "unblock_ip":
        ip     = arguments["ip"]
        device = arguments.get("device_hostname", "core-router")
        if not _confirmed(arguments):
            return err(f"confirmed must be true to unblock {ip}")
        try:
            cmd    = f"iptables -D INPUT -s {ip} -j DROP 2>/dev/null; " \
                     f"iptables -D FORWARD -s {ip} -j DROP 2>/dev/null; echo done"
            output = _ssh_run(device, cmd)
            return ok({"ip": ip, "device": device, "status": "unblocked", "output": output})
        except Exception as e:
            return err(f"unblock_ip failed: {e}")

    # ── block_subnet ──────────────────────────────────────────────────────────
    if name == "block_subnet":
        subnet = arguments["subnet"]
        device = arguments.get("device_hostname", "core-router")
        if not _confirmed(arguments):
            return err(f"confirmed must be true to block subnet {subnet}")
        try:
            cmd    = f"iptables -C INPUT -s {subnet} -j DROP 2>/dev/null || iptables -I INPUT 1 -s {subnet} -j DROP; " \
                     f"iptables -C FORWARD -s {subnet} -j DROP 2>/dev/null || iptables -I FORWARD 1 -s {subnet} -j DROP"
            output = _ssh_run(device, cmd)
            return ok({"subnet": subnet, "device": device, "status": "blocked", "output": output})
        except Exception as e:
            return err(f"block_subnet failed: {e}")

    # ── rate_limit_ip ─────────────────────────────────────────────────────────
    if name == "rate_limit_ip":
        ip  = arguments["ip"]
        rpm = int(arguments["requests_per_minute"])
        device = arguments.get("device_hostname", "core-router")
        if not _confirmed(arguments):
            return err(f"confirmed must be true to rate-limit {ip}")
        try:
            # Allow up to rpm/min, burst 5; drop everything above
            cmd = (
                f"iptables -I INPUT 1 -s {ip} -m hashlimit "
                f"--hashlimit-name rl_{ip.replace('.','_')} "
                f"--hashlimit-above {rpm}/min --hashlimit-burst 5 "
                f"--hashlimit-mode srcip -j DROP"
            )
            output = _ssh_run(device, cmd)
            return ok({"ip": ip, "requests_per_minute": rpm, "device": device, "status": "rate_limited", "output": output})
        except Exception as e:
            return err(f"rate_limit_ip failed: {e}")

    # ── get_blocked_list ──────────────────────────────────────────────────────
    if name == "get_blocked_list":
        device = arguments.get("device_hostname", "core-router")
        try:
            input_rules   = _ssh_run(device, "iptables -L INPUT -n --line-numbers 2>&1")
            forward_rules = _ssh_run(device, "iptables -L FORWARD -n --line-numbers 2>&1")
            return ok({"device": device, "INPUT": input_rules, "FORWARD": forward_rules})
        except Exception as e:
            return err(f"get_blocked_list failed: {e}")

    # ── get_top_suspicious_ips ────────────────────────────────────────────────
    if name == "get_top_suspicious_ips":
        limit = int(arguments.get("limit", 10))
        try:
            scores: dict[str, dict] = {}

            def _acc(metric_name, label_key=None):
                for item in _prom_query(metric_name):
                    ip = item["metric"].get("source_ip", "unknown")
                    if ip == "unknown":
                        continue
                    scores.setdefault(ip, {})
                    key = label_key or metric_name
                    scores[ip][key] = float(item["value"][1])

            _acc("failed_logins_per_ip_total",    "failed_logins")
            _acc("traffic_bytes_per_sec",          "traffic_bps")
            _acc("payload_threat_score",           "payload_threat_score")
            _acc("recent_event_rate_per_minute",   "event_rate_per_min")
            _acc("suspicious_requests_total",      "suspicious_requests")

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
            return ok(result[:limit])
        except Exception as e:
            return err(f"get_top_suspicious_ips failed: {e}")

    # ── get_traffic_spike_alerts ──────────────────────────────────────────────
    if name == "get_traffic_spike_alerts":
        hours = int(arguments.get("hours", 1))
        try:
            # Current firing alerts from Prometheus
            firing = [
                {
                    "alertname":   a["labels"].get("alertname"),
                    "source_ip":   a["labels"].get("source_ip"),
                    "destination": a["labels"].get("destination_ip"),
                    "severity":    a["labels"].get("severity"),
                    "state":       a["state"],
                    "description": a.get("annotations", {}).get("description"),
                }
                for a in _prom_alerts()
                if a["labels"].get("alertname") == "TrafficSpike"
            ]

            # Historical spikes from range query
            historical = []
            for series in _prom_query_range(f"traffic_bytes_per_sec > 10000000", hours):
                ip   = series["metric"].get("source_ip", "unknown")
                dest = series["metric"].get("destination_ip", "unknown")
                peak = max(float(v[1]) for v in series["values"])
                historical.append({
                    "source_ip":      ip,
                    "destination_ip": dest,
                    "peak_bytes_per_sec": int(peak),
                    "data_points":    len(series["values"]),
                })

            return ok({"window_hours": hours, "firing_alerts": firing, "historical_spikes": historical})
        except Exception as e:
            return err(f"get_traffic_spike_alerts failed: {e}")

    # ── get_failed_login_events ───────────────────────────────────────────────
    if name == "get_failed_login_events":
        hours = int(arguments.get("hours", 1))
        try:
            results = _prom_query(f"increase(failed_logins_per_ip_total[{hours}h])")
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
            return ok({"window_hours": hours, "events": events, "total_source_ips": len(events)})
        except Exception as e:
            return err(f"get_failed_login_events failed: {e}")

    # ── get_ip_event_history ──────────────────────────────────────────────────
    if name == "get_ip_event_history":
        ip = arguments["ip"]
        try:
            metrics_to_query = [
                ("failed_logins_per_ip_total",   "failed_logins_total"),
                ("traffic_bytes_per_sec",         "traffic_bytes_per_sec"),
                ("payload_threat_score",          "payload_threat_score"),
                ("suspicious_requests_total",     "suspicious_requests_total"),
                ("recent_event_rate_per_minute",  "event_rate_per_min"),
                ("security_events_total",         "security_events_total"),
            ]
            metric_snapshot: dict = {}
            for prom_name, friendly_name in metrics_to_query:
                for item in _prom_query(f'{prom_name}{{source_ip="{ip}"}}'):
                    val    = float(item["value"][1])
                    labels = {k: v for k, v in item["metric"].items() if k not in ("__name__", "source_ip")}
                    key    = f"{friendly_name}({','.join(f'{k}={v}' for k, v in labels.items())})" if labels else friendly_name
                    metric_snapshot[key] = val

            # Recent raw events from log aggregator
            recent_events: list = []
            try:
                r = requests.get(f"{LOG_AGG_URL}/recent_events", timeout=5)
                all_events = r.json()
                recent_events = [e for e in all_events if e.get("source_ip") == ip][-20:]
            except Exception:
                pass

            return ok({"ip": ip, "prometheus_metrics": metric_snapshot, "recent_events": recent_events})
        except Exception as e:
            return err(f"get_ip_event_history failed: {e}")

    # ── explain_threat ────────────────────────────────────────────────────────
    if name == "explain_threat":
        ip = arguments["ip"]
        try:
            report: dict = {
                "ip":         ip,
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            # ── 1. Prometheus metrics snapshot ────────────────────────────────
            metrics: dict = {}
            def _snap(prom_name, key):
                rows = _prom_query(f'{prom_name}{{source_ip="{ip}"}}')
                if rows:
                    metrics[key] = float(rows[0]["value"][1])

            _snap("failed_logins_per_ip_total",  "failed_logins_total")
            _snap("traffic_bytes_per_sec",        "traffic_bytes_per_sec")
            _snap("payload_threat_score",         "payload_threat_score")
            _snap("recent_event_rate_per_minute", "event_rate_per_min")
            _snap("suspicious_requests_total",    "suspicious_requests_total")
            report["metrics"] = metrics

            # ── 2. Active Prometheus alerts involving this IP ──────────────────
            report["active_alerts"] = [
                {
                    "name":        a["labels"].get("alertname"),
                    "severity":    a["labels"].get("severity"),
                    "state":       a["state"],
                    "description": a.get("annotations", {}).get("description"),
                }
                for a in _prom_alerts()
                if a["labels"].get("source_ip") == ip
            ]

            # ── 3. Recent log-aggregator events ───────────────────────────────
            report["recent_events"] = []
            try:
                r = requests.get(f"{LOG_AGG_URL}/recent_events", timeout=5)
                all_events = r.json()
                report["recent_events"] = [
                    e for e in all_events if e.get("source_ip") == ip
                ][-20:]
            except Exception:
                pass

            # ── 4. Firewall block status (check core-router iptables) ─────────
            report["firewall_status"] = "unknown"
            try:
                rules  = _ssh_run("core-router", f"iptables -L INPUT -n 2>&1 | grep -w '{ip}' || echo NOT_FOUND")
                report["firewall_status"] = "blocked" if "DROP" in rules else "not_blocked"
                report["firewall_rules"]  = rules.strip()
            except Exception:
                pass

            # ── 5. Composite threat level ─────────────────────────────────────
            failed_logins = metrics.get("failed_logins_total", 0)
            traffic_bps   = metrics.get("traffic_bytes_per_sec", 0)
            threat_score  = metrics.get("payload_threat_score", 0)
            event_rate    = metrics.get("event_rate_per_min", 0)
            num_alerts    = len(report["active_alerts"])

            composite = (
                min(failed_logins * 2,         100) +
                min(traffic_bps   / 1_000_000, 100) +
                threat_score                        +
                min(event_rate    * 2,         100)
            ) / 4

            if composite >= 60 or num_alerts >= 2:
                level = "critical"
            elif composite >= 30 or num_alerts >= 1:
                level = "high"
            elif composite >= 10:
                level = "medium"
            else:
                level = "low"

            report["threat_level"]      = level
            report["composite_score"]   = round(composite, 1)
            report["is_blocked"]        = report["firewall_status"] == "blocked"

            return ok(report)
        except Exception as e:
            return err(f"explain_threat failed: {e}")

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ─── SSE Transport ────────────────────────────────────────────────────────────

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
