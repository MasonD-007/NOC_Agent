from mcp.server import Server
from netmiko import ConnectHandler

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

_server: Server | None = None


def _connect(device_hostname: str) -> ConnectHandler:
    device = DEVICE_INVENTORY.get(device_hostname)
    if device is None:
        raise ValueError(
            f"Unknown device '{device_hostname}'. "
            f"Available devices: {', '.join(DEVICE_INVENTORY.keys())}"
        )
    return ConnectHandler(**device)


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def ssh_execute(device_hostname: str, command: str, confirmed: bool) -> dict:
        """Execute a shell command on a network device via SSH.
        device_hostname: Docker DNS name (e.g. 'edge-sw-02').
        command: shell command to run (e.g. 'iptables -A INPUT -s 172.20.0.5 -j DROP').
        confirmed: safety flag — must be True to execute."""
        if not confirmed:
            return {
                "device": device_hostname,
                "command": command,
                "error": "Action requires confirmed=True",
                "status": "failed",
            }
        try:
            conn = _connect(device_hostname)
            output = conn.send_command(command)
            conn.disconnect()
            return {
                "device": device_hostname,
                "command": command,
                "output": output,
                "status": "success",
            }
        except Exception as e:
            return {
                "device": device_hostname,
                "command": command,
                "error": str(e),
                "status": "failed",
            }

