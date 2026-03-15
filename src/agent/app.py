import json
import logging
import asyncio
import uuid
import time

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

# ---- SSE broadcast for alert events ----
alert_subscribers: set[asyncio.Queue] = set()

# ---- Alert deduplication ----
# Track seen alert fingerprints with timestamp to ignore Alertmanager retries
_seen_alerts: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 300  # ignore same fingerprint for 5 minutes


async def broadcast(event: dict):
    data = json.dumps(event)
    for queue in list(alert_subscribers):
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            pass


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


@app.get("/events")
async def events():
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    alert_subscribers.add(queue)
    logger.info("SSE client connected (%d total)", len(alert_subscribers))

    async def stream():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            alert_subscribers.discard(queue)
            logger.info("SSE client disconnected (%d remaining)", len(alert_subscribers))

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


async def _process_alert(alert: dict, alert_id: str):
    """Background task: run the agent graph and broadcast events to SSE subscribers."""
    try:
        initial_state = {
            "alert": alert,
            "messages": [],
            "investigation_log": [],
            "phase": "received",
        }

        async for event in noc_graph.astream(initial_state, stream_mode="updates", config={"recursion_limit": 25}):
            for node_name, node_output in event.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        await broadcast({
                            "type": "tool_call",
                            "alert_id": alert_id,
                            "calls": msg.tool_calls,
                        })
                        if msg.content:
                            await broadcast({
                                "type": "agent",
                                "alert_id": alert_id,
                                "content": msg.content,
                            })
                    elif msg.type == "tool":
                        await broadcast({
                            "type": "tool_result",
                            "alert_id": alert_id,
                            "name": msg.name,
                            "output": msg.content,
                        })
                    elif msg.content:
                        await broadcast({
                            "type": "agent",
                            "alert_id": alert_id,
                            "content": msg.content,
                        })

        await broadcast({"type": "done", "alert_id": alert_id})
    except Exception as e:
        logger.exception("Alert processing failed [%s]: %s", alert_id, e)
        await broadcast({"type": "done", "alert_id": alert_id})


@app.post("/alert")
async def webhook(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    if not alerts:
        return JSONResponse(status_code=400, content={"error": "no alerts in payload"})

    # Clean up old entries from dedup cache
    now = time.time()
    expired = [fp for fp, ts in _seen_alerts.items() if now - ts > DEDUP_WINDOW_SECONDS]
    for fp in expired:
        del _seen_alerts[fp]

    accepted = []
    for alert in alerts:
        # Deduplicate: skip if we've seen this fingerprint recently
        fingerprint = alert.get("fingerprint", "")
        if fingerprint and fingerprint in _seen_alerts:
            logger.info("Skipping duplicate alert (fingerprint=%s)", fingerprint)
            continue
        if fingerprint:
            _seen_alerts[fingerprint] = now

        alert_id = str(uuid.uuid4())
        alert_name = alert.get("labels", {}).get("alertname", "Unknown")
        logger.info("Accepted alert [%s]: %s", alert_id, alert_name)

        await broadcast({
            "type": "alert_start",
            "alert_id": alert_id,
            "alert_name": alert_name,
            "alert": alert,
        })

        # Process in background so we return 200 to Alertmanager immediately
        asyncio.create_task(_process_alert(alert, alert_id))
        accepted.append(alert_id)

    # Return immediately — Alertmanager won't timeout and retry
    return {"accepted": len(accepted), "alert_ids": accepted}


@app.post("/chat")
async def chat(request: Request):
    from graph import SYSTEM_PROMPT

    payload = await request.json()
    user_message = payload.get("message", "")
    if not user_message:
        return JSONResponse(status_code=400, content={"error": "no message provided"})

    logger.info("Chat message: %s", user_message)

    initial_state = {
        "alert": {},
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ],
        "investigation_log": [],
        "phase": "chat",
    }

    async def event_stream():
        async for event in noc_graph.astream(initial_state, stream_mode="updates", config={"recursion_limit": 25}):
            for node_name, node_output in event.items():
                messages = node_output.get("messages", [])
                for msg in messages:
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
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
