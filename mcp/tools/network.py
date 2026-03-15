from mcp.server import Server

_server: Server | None = None


def register(server: Server) -> None:
    global _server
    _server = server

    @server.tool()
    def get_network_topology() -> dict:
        """Return the full network topology as a graph of nodes and edges,
        including all switches, routers, and connected devices."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_switch_connections(switch_id: str) -> dict:
        """Return all devices and ports connected to the given switch,
        identified by its switch_id (e.g. a MAC address or management IP)."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_device_info(identifier: str) -> dict:
        """Return detailed information about a network device identified by
        IP address, MAC address, or hostname."""
        raise NotImplementedError("TODO: implement this tool")

    @server.tool()
    def get_router_stats() -> dict:
        """Return current statistics for all routers in the network,
        including throughput, packet loss, and interface states."""
        raise NotImplementedError("TODO: implement this tool")
