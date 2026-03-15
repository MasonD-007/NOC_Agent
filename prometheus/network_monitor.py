"""
Network Monitor / Bridge Script
================================
Runs inside demo-network as a container.
Watches Docker stats for traffic on edge-sw-02, translates UDP flood
into security events and POSTs them to the log aggregator.

Data flow:
  rogue-device --UDP--> edge-sw-02
                              |
                    docker stats (bytes received)
                              |
                    network_monitor.py  (this script)
                              |
                    POST /ingest
                              |
                    log-aggregator:8000
                              |
                    Prometheus scrapes /metrics every 5s
"""

import docker
import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_AGGREGATOR_URL = "http://log-aggregator:8000/ingest"
WATCHED_CONTAINER   = "edge-sw-02"      # target of the DDoS
ATTACKER_CONTAINER  = "rogue-device"    # source of the attack
POLL_INTERVAL       = 2                 # seconds between samples
DDOS_THRESHOLD_BPS  = 5_000_000        # 5 MB/s - anything above = spike


def get_container_ip(client: docker.DockerClient, name: str) -> str:
    """Resolve a container name to its IP on demo-network."""
    try:
        container = client.containers.get(name)
        networks = container.attrs["NetworkSettings"]["Networks"]
        for net in networks.values():
            if net["IPAddress"]:
                return net["IPAddress"]
    except Exception:
        pass
    return name  # fallback to container name


def get_network_bytes(client: docker.DockerClient, container_name: str) -> int:
    """Return cumulative bytes received by the container."""
    try:
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)
        networks = stats.get("networks", {})
        total = sum(iface["rx_bytes"] for iface in networks.values())
        return total
    except Exception as e:
        log.warning(f"Could not get stats for {container_name}: {e}")
        return 0


def post_event(event: dict):
    try:
        r = requests.post(LOG_AGGREGATOR_URL, json=event, timeout=3)
        log.info(f"Posted event → {r.status_code} {r.json()}")
    except Exception as e:
        log.error(f"Failed to POST event: {e}")


def main():
    log.info("Network monitor starting...")
    client = docker.from_env()

    prev_bytes = get_network_bytes(client, WATCHED_CONTAINER)
    prev_time  = time.time()

    while True:
        time.sleep(POLL_INTERVAL)

        now_bytes = get_network_bytes(client, WATCHED_CONTAINER)
        now_time  = time.time()

        delta_bytes = now_bytes - prev_bytes
        delta_time  = now_time  - prev_time
        bytes_per_sec = delta_bytes / delta_time if delta_time > 0 else 0

        log.info(f"edge-sw-02 rx rate: {bytes_per_sec:,.0f} bytes/sec")

        if bytes_per_sec > DDOS_THRESHOLD_BPS:
            attacker_ip = get_container_ip(client, ATTACKER_CONTAINER)
            victim_ip   = get_container_ip(client, WATCHED_CONTAINER)

            post_event({
                "source_ip":      attacker_ip,
                "destination_ip": victim_ip,
                "event_type":     "traffic_spike",
                "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "severity":       "critical",
                "details": {
                    "bytes_per_sec": int(bytes_per_sec),
                    "protocol":      "UDP",
                    "note":          "iperf3 flood detected on edge-sw-02"
                }
            })

        prev_bytes = now_bytes
        prev_time  = now_time


if __name__ == "__main__":
    main()
