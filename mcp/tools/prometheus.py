from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_top_suspicious_ips(n: int) -> list[dict]:
        """Query Prometheus to return the top-n IP addresses ranked by
        suspicious activity score over the most recent observation window."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_traffic_spike_alerts() -> list[dict]:
        """Return all active traffic-spike alerts currently firing in
        Prometheus, including the affected interface and magnitude."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_failed_login_events(ip: str, time_window_minutes: int) -> list[dict]:
        """Return failed login events originating from ip within the last
        time_window_minutes minutes, as recorded by Prometheus metrics."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_ip_event_history(ip: str) -> list[dict]:
        """Return the full Prometheus-recorded event history for the given
        IP address, spanning all available metric retention time."""
        raise NotImplementedError("TODO: implement this tool")
