import os
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from netmiko import ConnectHandler
import uvicorn

load_dotenv()

server = Server("noc-security-agent")

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


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ssh_execute",
            description=(
                "Execute a shell command on a network device via SSH. "
                "device_hostname: Docker DNS name (e.g. 'edge-sw-02'). "
                "command: shell command to run (e.g. 'iptables -A INPUT -s 172.20.0.5 -j DROP'). "
                "confirmed: safety flag — must be true to execute."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_hostname": {"type": "string", "description": "Docker DNS name of the device"},
                    "command": {"type": "string", "description": "Shell command to run on the device"},
                    "confirmed": {"type": ["boolean", "string"], "description": "Safety flag — must be true to execute"},
                },
                "required": ["device_hostname", "command", "confirmed"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "ssh_execute":
        device_hostname = arguments["device_hostname"]
        command = arguments["command"]
        confirmed = arguments.get("confirmed", False)
        if isinstance(confirmed, str):
            confirmed = confirmed.lower() == "true"

        if not confirmed:
            return [TextContent(type="text", text=f"Action requires confirmed=true. Got confirmed=false for: {command}")]

        device = DEVICE_INVENTORY.get(device_hostname)
        if device is None:
            return [TextContent(type="text", text=f"Unknown device '{device_hostname}'. Available: {', '.join(DEVICE_INVENTORY.keys())}")]

        try:
            conn = ConnectHandler(**device)
            output = conn.send_command(command)
            conn.disconnect()
            return [TextContent(type="text", text=f"SUCCESS on {device_hostname}:\n$ {command}\n{output}")]
        except Exception as e:
            return [TextContent(type="text", text=f"FAILED on {device_hostname}: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
