import os
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server

import tools.network as network_tools
import tools.prometheus as prometheus_tools
import tools.logs as logs_tools
import tools.firewall as firewall_tools
import tools.audit as audit_tools

load_dotenv()

PROMETHEUS_URL: str = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
LOG_AGGREGATOR_URL: str = os.environ.get("LOG_AGGREGATOR_URL", "http://localhost:8000")
DOCKER_NETWORK_NAME: str = os.environ.get("DOCKER_NETWORK_NAME", "security-sim-network")

server = Server("noc-security-agent")

network_tools.register(server)
prometheus_tools.register(server)
logs_tools.register(server)
firewall_tools.register(server)
audit_tools.register(server)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
