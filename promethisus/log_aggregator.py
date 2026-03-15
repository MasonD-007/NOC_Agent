"""
Log Aggregator Service
======================
Receives raw security event logs from the simulated network,
groups them by IP, and exposes Prometheus metrics for the MCP server to query.

Security Event Format (POST to /ingest):
{
    "source_ip": "172.20.0.5",
    "destination_ip": "172.20.0.3",
    "event_type": "failed_login" | "endpoint_request" | "suspicious_payload" | "traffic_spike",
    "timestamp": "2026-03-15T10:30:00Z",
    "details": {
        "endpoint": "/admin",          # for endpoint_request
        "username": "root",            # for failed_login
        "payload_snippet": "...",      # for suspicious_payload
        "bytes_per_sec": 50000000      # for traffic_spike
    },
    "severity": "low" | "medium" | "high" | "critical"
}
"""

from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from collections import defaultdict
import time
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Prometheus Metrics ───────────────────────────────────────────────────────

# Total security events seen, labeled by type and severity
security_events_total = Counter(
    "security_events_total",
    "Total number of security events received",
    ["event_type", "severity", "source_ip"]
)

# Failed login attempts per source IP (rolling - decays over time via Gauge)
failed_logins_per_ip = Counter(
    "failed_logins_per_ip_total",
    "Cumulative failed login attempts grouped by source IP",
    ["source_ip", "target_user"]
)

# Suspicious endpoint requests per IP
suspicious_requests_per_ip = Counter(
    "suspicious_requests_total",
    "Requests to suspicious endpoints",
    ["source_ip", "endpoint"]
)

# Current traffic rate per source IP (bytes/sec) - Gauge because it goes up AND down
traffic_bytes_per_sec = Gauge(
    "traffic_bytes_per_sec",
    "Current observed traffic rate from source IP",
    ["source_ip", "destination_ip"]
)

# Payload threat score (0-100) per IP - set by heuristic scorer
payload_threat_score = Gauge(
    "payload_threat_score",
    "Heuristic threat score for suspicious payloads (0-100)",
    ["source_ip"]
)

# How many events per IP in the last 60 seconds (for spike detection)
recent_event_rate = Gauge(
    "recent_event_rate_per_minute",
    "Events per minute from this source IP (rolling 60s window)",
    ["source_ip"]
)

# ─── In-Memory State ──────────────────────────────────────────────────────────

# Tracks raw events with timestamps for rolling window calculations
event_log: list[dict] = []
event_lock = threading.Lock()

SUSPICIOUS_ENDPOINTS = {"/admin", "/root", "/.env", "/etc/passwd", "/shell", "/cmd", "/exec"}
HIGH_SEVERITY_PAYLOADS = ["DROP TABLE", "SELECT *", "<script>", "eval(", "base64_decode"]


def score_payload(payload: str) -> int:
    """Heuristic scorer: returns 0-100 threat score for a payload string."""
    score = 0
    payload_lower = payload.lower()
    if any(sig.lower() in payload_lower for sig in HIGH_SEVERITY_PAYLOADS):
        score += 60
    if len(payload) > 500:
        score += 20
    if payload.count("%") > 5:  # URL encoding abuse
        score += 20
    return min(score, 100)


def update_rolling_rates():
    """Background thread: recalculates rolling 60s event rates per IP."""
    while True:
        time.sleep(15)
        cutoff = time.time() - 60
        with event_lock:
            recent = [e for e in event_log if e["ts"] > cutoff]
            counts: dict[str, int] = defaultdict(int)
            for e in recent:
                counts[e["source_ip"]] += 1
        for ip, count in counts.items():
            recent_event_rate.labels(source_ip=ip).set(count)


# Start background thread for rolling rate calculations
threading.Thread(target=update_rolling_rates, daemon=True).start()


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route("/ingest", methods=["POST"])
def ingest_event():
    """
    Receives a security event from the simulated network.
    Updates Prometheus counters/gauges accordingly.
    """
    data = request.get_json(force=True)

    source_ip = data.get("source_ip", "unknown")
    dest_ip = data.get("destination_ip", "unknown")
    event_type = data.get("event_type", "unknown")
    severity = data.get("severity", "low")
    details = data.get("details", {})

    # Record the raw event for rolling window
    with event_lock:
        event_log.append({"source_ip": source_ip, "ts": time.time()})
        # Trim log older than 5 minutes
        cutoff = time.time() - 300
        event_log[:] = [e for e in event_log if e["ts"] > cutoff]

    # Always increment the general event counter
    security_events_total.labels(
        event_type=event_type,
        severity=severity,
        source_ip=source_ip
    ).inc()

    # Event-specific metric updates
    if event_type == "failed_login":
        username = details.get("username", "unknown")
        failed_logins_per_ip.labels(source_ip=source_ip, target_user=username).inc()
        log.info(f"Failed login from {source_ip} targeting user '{username}'")

    elif event_type == "endpoint_request":
        endpoint = details.get("endpoint", "/")
        if endpoint in SUSPICIOUS_ENDPOINTS:
            suspicious_requests_per_ip.labels(source_ip=source_ip, endpoint=endpoint).inc()
            log.warning(f"Suspicious endpoint hit: {source_ip} → {endpoint}")

    elif event_type == "traffic_spike":
        bps = details.get("bytes_per_sec", 0)
        traffic_bytes_per_sec.labels(source_ip=source_ip, destination_ip=dest_ip).set(bps)
        log.warning(f"Traffic spike: {source_ip} → {dest_ip} at {bps:,} bytes/sec")

    elif event_type == "suspicious_payload":
        payload = details.get("payload_snippet", "")
        score = score_payload(payload)
        payload_threat_score.labels(source_ip=source_ip).set(score)
        log.warning(f"Suspicious payload from {source_ip}, threat score: {score}")

    return jsonify({"status": "ok", "source_ip": source_ip, "event_type": event_type}), 200


@app.route("/metrics")
def metrics():
    """Prometheus scrapes this endpoint every 10 seconds."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/recent_events")
def recent_events():
    """Debug endpoint: returns last 50 events with timestamps."""
    with event_lock:
        return jsonify(event_log[-50:]), 200


if __name__ == "__main__":
    log.info("Log Aggregator starting on port 8000...")
    app.run(host="0.0.0.0", port=8000)
