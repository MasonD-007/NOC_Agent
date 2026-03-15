"""
Firewall tools — implemented via iptables over SSH (netmiko).

All write operations require confirmed=True.
Default device is core-router (the network border device).
"""

from mcp.server import Server
from tools.ssh import _connect

_server: Server | None = None

DEFAULT_DEVICE = "core-router"


def _ssh_run(device_hostname: str, cmd: str) -> str:
    conn   = _connect(device_hostname)
    output = conn.send_command(cmd)
    conn.disconnect()
    return output


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def block_ip(ip: str, confirmed: bool, device_hostname: str = DEFAULT_DEVICE) -> dict:
        """Block all inbound and forwarded traffic from an IP using iptables.
        Uses -C to check before inserting so duplicate rules are avoided.
        confirmed must be True to execute."""
        if not confirmed:
            raise ValueError("confirmed must be True")
        cmd = (
            f"iptables -C INPUT -s {ip} -j DROP 2>/dev/null || iptables -I INPUT 1 -s {ip} -j DROP; "
            f"iptables -C FORWARD -s {ip} -j DROP 2>/dev/null || iptables -I FORWARD 1 -s {ip} -j DROP"
        )
        output = _ssh_run(device_hostname, cmd)
        return {"ip": ip, "device": device_hostname, "status": "blocked", "output": output}

    @server.tool()
    def unblock_ip(ip: str, confirmed: bool, device_hostname: str = DEFAULT_DEVICE) -> dict:
        """Remove an existing iptables DROP rule for the given IP.
        Silences 'rule not found' errors so it's idempotent.
        confirmed must be True to execute."""
        if not confirmed:
            raise ValueError("confirmed must be True")
        cmd = (
            f"iptables -D INPUT -s {ip} -j DROP 2>/dev/null; "
            f"iptables -D FORWARD -s {ip} -j DROP 2>/dev/null; echo done"
        )
        output = _ssh_run(device_hostname, cmd)
        return {"ip": ip, "device": device_hostname, "status": "unblocked", "output": output}

    @server.tool()
    def block_subnet(subnet: str, confirmed: bool, device_hostname: str = DEFAULT_DEVICE) -> dict:
        """Block all traffic from a CIDR subnet (e.g. '192.168.1.0/24').
        confirmed must be True to execute."""
        if not confirmed:
            raise ValueError("confirmed must be True")
        cmd = (
            f"iptables -C INPUT -s {subnet} -j DROP 2>/dev/null || iptables -I INPUT 1 -s {subnet} -j DROP; "
            f"iptables -C FORWARD -s {subnet} -j DROP 2>/dev/null || iptables -I FORWARD 1 -s {subnet} -j DROP"
        )
        output = _ssh_run(device_hostname, cmd)
        return {"subnet": subnet, "device": device_hostname, "status": "blocked", "output": output}

    @server.tool()
    def rate_limit_ip(
        ip: str,
        requests_per_minute: int,
        confirmed: bool,
        device_hostname: str = DEFAULT_DEVICE,
    ) -> dict:
        """Rate-limit traffic from an IP using iptables hashlimit.
        Traffic above requests_per_minute is DROPped (burst=5).
        confirmed must be True to execute."""
        if not confirmed:
            raise ValueError("confirmed must be True")
        name = f"rl_{ip.replace('.', '_')}"
        cmd = (
            f"iptables -I INPUT 1 -s {ip} "
            f"-m hashlimit --hashlimit-name {name} "
            f"--hashlimit-above {requests_per_minute}/min --hashlimit-burst 5 "
            f"--hashlimit-mode srcip -j DROP"
        )
        output = _ssh_run(device_hostname, cmd)
        return {
            "ip": ip,
            "requests_per_minute": requests_per_minute,
            "device": device_hostname,
            "status": "rate_limited",
            "output": output,
        }

    @server.tool()
    def get_blocked_list(device_hostname: str = DEFAULT_DEVICE) -> dict:
        """Return current iptables rules for INPUT and FORWARD chains
        on the specified device (default: core-router)."""
        return {
            "device":  device_hostname,
            "INPUT":   _ssh_run(device_hostname, "iptables -L INPUT -n --line-numbers 2>&1"),
            "FORWARD": _ssh_run(device_hostname, "iptables -L FORWARD -n --line-numbers 2>&1"),
        }
