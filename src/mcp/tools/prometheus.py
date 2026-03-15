from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_top_suspicious_ips(limit: int) -> list[dict]:
        """Return the top suspicious IP addresses ranked by threat score,
        based on Prometheus metrics such as traffic volume, connection
        rate, and failed authentication attempts."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_traffic_spike_alerts(hours: int) -> list[dict]:
        """Return traffic spike alerts from the last N hours, including
        the source IP, target device, peak rate, and timestamp."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_failed_login_events(hours: int) -> list[dict]:
        """Return failed login events from the last N hours, including
        source IP, target device, username attempted, and timestamp."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_ip_event_history(ip: str) -> list[dict]:
        """Return the full event history for a given IP address, including
        all alerts, traffic patterns, and authentication events."""
        raise NotImplementedError("TODO: implement this tool")
