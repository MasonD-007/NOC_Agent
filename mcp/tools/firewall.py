from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def block_ip(identifier: str, confirmed: bool) -> dict:
        """Block all traffic from the given IP address or hostname at the
        firewall level. Requires confirmed=True to execute."""
        if not confirmed:
            raise ValueError("Action requires confirmed=True")
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def block_subnet(subnet: str, confirmed: bool) -> dict:
        """Block all traffic originating from the given CIDR subnet.
        Requires confirmed=True to execute."""
        if not confirmed:
            raise ValueError("Action requires confirmed=True")
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def rate_limit_ip(ip: str, requests_per_minute: int, confirmed: bool) -> dict:
        """Apply a rate limit of requests_per_minute to the specified IP
        address. Requires confirmed=True to execute."""
        if not confirmed:
            raise ValueError("Action requires confirmed=True")
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def unblock_ip(ip: str, confirmed: bool) -> dict:
        """Remove an existing firewall block for the given IP address.
        Requires confirmed=True to execute."""
        if not confirmed:
            raise ValueError("Action requires confirmed=True")
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_blocked_list() -> list[dict]:
        """Return the current list of all blocked IPs and subnets managed
        by the firewall, along with the timestamp and reason for each block."""
        raise NotImplementedError("TODO: implement this tool")
