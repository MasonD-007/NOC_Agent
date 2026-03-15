import json
import logging
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import SystemMessage, HumanMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("noc-agent")

mcp_client: MultiServerMCPClient | None = None
noc_graph = None
session_store: dict[str, list] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp_client, noc_graph
    from graph import build_graph

    mcp_client = MultiServerMCPClient({
        "noc-tools": {
            "url": "http://mcp-server:8080/sse",
            "transport": "sse",
        }
    })
    tools = await mcp_client.get_tools()
    logger.info("Loaded %d MCP tools: %s", len(tools), [t.name for t in tools])
    noc_graph = build_graph(tools)
    yield


app = FastAPI(title="NOC Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


async def process_alert(alert: dict):
    logger.info("Processing alert: %s", json.dumps(alert, indent=2))
    initial_state = {
        "alert": alert,
        "messages": [],
        "investigation_log": [],
        "phase": "received",
    }
    final_state = await noc_graph.ainvoke(initial_state)
    session_store["default"] = final_state["messages"]
    logger.info("Alert processed, saved %d messages to session store", len(final_state["messages"]))


@app.post("/alert")
async def webhook(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    if not alerts:
        return JSONResponse(status_code=400, content={"error": "no alerts in payload"})

    for alert in alerts:
        asyncio.create_task(process_alert(alert))

    return JSONResponse(status_code=202, content={"accepted": len(alerts)})


@app.post("/chat")
async def chat(request: Request):
    from graph import SYSTEM_PROMPT

    payload = await request.json()
    user_message = payload.get("message", "")
    if not user_message:
        return JSONResponse(status_code=400, content={"error": "no message provided"})

    session_id = payload.get("session_id", "default")
    history = session_store.get(session_id, [])

    logger.info("Chat message: %s (session=%s, history=%d msgs)", user_message, session_id, len(history))

    initial_state = {
        "alert": {},
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(content=user_message),
        ],
        "investigation_log": [],
        "phase": "chat",
    }

    async def event_stream():
        collected = []
        async for event in noc_graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    collected.append(msg)
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        yield f"data: {json.dumps({'type': 'tool_call', 'calls': msg.tool_calls})}\n\n"
                        if msg.content:
                            yield f"data: {json.dumps({'type': 'agent', 'content': msg.content})}\n\n"
                    elif msg.type == "tool":
                        content = msg.content
                        if isinstance(content, list):
                            parsed_parts = []
                            for block in content:
                                text = block.get("text", "") if isinstance(block, dict) else str(block)
                                try:
                                    parsed_parts.append(json.loads(text))
                                except (json.JSONDecodeError, TypeError):
                                    parsed_parts.append(text)
                            content = parsed_parts[0] if len(parsed_parts) == 1 else parsed_parts
                        elif isinstance(content, str):
                            try:
                                content = json.loads(content)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': msg.name, 'output': content})}\n\n"
                    elif msg.content:
                        yield f"data: {json.dumps({'type': 'agent', 'content': msg.content})}\n\n"
        session_store[session_id] = history + collected
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
