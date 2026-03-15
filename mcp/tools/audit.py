from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_action_log() -> list[dict]:
        """Return the audit log of all actions taken by the security agent,
        including timestamps, action type, target, and operator identity."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def explain_threat(ip: str) -> dict:
        """Generate a human-readable explanation of why the given IP address
        has been flagged as a threat, citing relevant evidence from logs,
        Prometheus metrics, and prior audit entries."""
        raise NotImplementedError("TODO: implement this tool")
