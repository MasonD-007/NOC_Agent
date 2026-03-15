from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_network_topology() -> dict:
        """Return the full network topology graph including all devices,
        links, and their current status."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_switch_connections(switch_name: str) -> list[dict]:
        """List all active connections on the specified network switch,
        including connected device, port, VLAN, and link speed."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_device_info(device_name: str) -> dict:
        """Return detailed information about a specific network device
        including hostname, IP addresses, model, firmware version, and
        uptime."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_router_stats(router_name: str) -> dict:
        """Return current performance statistics for the specified router
        including CPU usage, memory usage, interface throughput, and
        routing table size."""
        raise NotImplementedError("TODO: implement this tool")
