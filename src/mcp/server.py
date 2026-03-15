import os
import json

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn

from tools import prometheus, ssh

load_dotenv()

server = Server("noc-security-agent")

# Collect tool definitions and handlers from each module
TOOLS: dict[str, Tool] = {}
HANDLERS: dict[str, callable] = {}

for module in [prometheus, ssh]:
    tools, handlers = module.get_tools()
    for tool in tools:
        TOOLS[tool.name] = tool
        HANDLERS[tool.name] = handlers[tool.name]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return list(TOOLS.values())


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    result = handler(**arguments)
    if isinstance(result, (dict, list)):
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    return [TextContent(type="text", text=str(result))]


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
