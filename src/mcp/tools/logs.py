from mcp.server import Server
from models import LogEvent

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_recent_logs(limit: int, severity: str) -> list[LogEvent]:
        """Fetch the most recent log events from the log aggregator, capped
        at limit entries and filtered to the specified severity level
        (e.g. 'info', 'warning', 'error', 'critical')."""
        raise NotImplementedError("TODO: implement this tool")
