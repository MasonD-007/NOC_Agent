import os
from mcp.types import Tool
from prometheus_api_client import PrometheusConnect

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


def _prom() -> PrometheusConnect:
    return PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)


def get_top_suspicious_ips(n: int = 5) -> list[dict]:
    try:
        prom = _prom()
        top = prom.custom_query(f"topk({n}, payload_threat_score)")
        results = []
        for entry in top:
            ip = entry["metric"].get("source_ip", "unknown")
            threat_score = float(entry["value"][1])

            logins = prom.custom_query(
                f'failed_logins_per_ip_total{{source_ip="{ip}"}}'
            )
            failed_logins = sum(float(r["value"][1]) for r in logins)

            reqs = prom.custom_query(
                f'suspicious_requests_total{{source_ip="{ip}"}}'
            )
            suspicious_requests = sum(float(r["value"][1]) for r in reqs)

            results.append({
                "ip": ip,
                "threat_score": threat_score,
                "failed_logins": failed_logins,
                "suspicious_requests": suspicious_requests,
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


def get_traffic_spike_alerts() -> list[dict]:
    try:
        prom = _prom()
        flows = prom.custom_query("traffic_bytes_per_sec")
        results = []
        for entry in flows:
            bps = float(entry["value"][1])
            results.append({
                "source_ip": entry["metric"].get("source_ip", "unknown"),
                "destination_ip": entry["metric"].get("destination_ip", "unknown"),
                "bytes_per_sec": bps,
                "is_spike": bps > 10_000_000,
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


def get_failed_login_events(ip: str, hours: int = 1) -> list[dict]:
    try:
        prom = _prom()
        data = prom.custom_query(
            f'increase(failed_logins_per_ip_total{{source_ip="{ip}"}}[{hours}h])'
        )
        results = []
        for entry in data:
            count = float(entry["value"][1])
            if count > 0:
                results.append({
                    "source_ip": ip,
                    "target_user": entry["metric"].get("target_user", "unknown"),
                    "count": count,
                })
        return results
    except Exception as e:
        return [{"error": str(e)}]


def get_ip_event_history(ip: str) -> dict:
    try:
        prom = _prom()

        ts = prom.custom_query(f'payload_threat_score{{source_ip="{ip}"}}')
        threat_score = float(ts[0]["value"][1]) if ts else None

        fl = prom.custom_query(f'failed_logins_per_ip_total{{source_ip="{ip}"}}')
        failed_logins = sum(float(r["value"][1]) for r in fl)

        sr = prom.custom_query(f'suspicious_requests_total{{source_ip="{ip}"}}')
        suspicious_requests = sum(float(r["value"][1]) for r in sr)

        tf = prom.custom_query(f'traffic_bytes_per_sec{{source_ip="{ip}"}}')
        traffic_flows = [
            {
                "destination_ip": r["metric"].get("destination_ip", "unknown"),
                "bytes_per_sec": float(r["value"][1]),
            }
            for r in tf
        ]

        er = prom.custom_query(f'recent_event_rate_per_minute{{source_ip="{ip}"}}')
        event_rate = float(er[0]["value"][1]) if er else None

        return {
            "ip": ip,
            "threat_score": threat_score,
            "failed_logins": failed_logins,
            "suspicious_requests": suspicious_requests,
            "traffic_flows": traffic_flows,
            "event_rate": event_rate,
        }
    except Exception as e:
        return {"error": str(e)}


def get_tools() -> tuple[list[Tool], dict[str, callable]]:
    tools = [
        Tool(
            name="get_top_suspicious_ips",
            description=(
                "Return the top N suspicious IP addresses ranked by payload threat score, "
                "enriched with failed login and suspicious request counts from Prometheus."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of top IPs to return", "default": 5},
                },
            },
        ),
        Tool(
            name="get_traffic_spike_alerts",
            description=(
                "Return all current traffic flows from Prometheus, flagging any above "
                "10 MB/s as a spike. Useful for DDoS or exfiltration detection."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_failed_login_events",
            description=(
                "Return failed login event counts for a specific IP over the last N hours, "
                "broken down by target user."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Source IP address to query"},
                    "hours": {"type": "integer", "description": "Lookback window in hours", "default": 1},
                },
                "required": ["ip"],
            },
        ),
        Tool(
            name="get_ip_event_history",
            description=(
                "Return a consolidated event history for a given IP address including "
                "threat score, failed logins, suspicious requests, traffic flows, and event rate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Source IP address to query"},
                },
                "required": ["ip"],
            },
        ),
    ]
    handlers = {
        "get_top_suspicious_ips": get_top_suspicious_ips,
        "get_traffic_spike_alerts": get_traffic_spike_alerts,
        "get_failed_login_events": get_failed_login_events,
        "get_ip_event_history": get_ip_event_history,
    }
    return tools, handlers
