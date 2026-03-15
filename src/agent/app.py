import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from graph import noc_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("noc-agent")

app = FastAPI(title="NOC Agent")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    if not alerts:
        return JSONResponse(status_code=400, content={"error": "no alerts in payload"})

    results = []
    for alert in alerts:
        logger.info("Processing alert: %s", json.dumps(alert, indent=2))
        initial_state = {
            "alert": alert,
            "messages": [],
            "investigation_log": [],
            "phase": "received",
        }
        final_state = noc_graph.invoke(initial_state)
        results.append({
            "alert": alert,
            "phase": final_state["phase"],
            "investigation_log": final_state["investigation_log"],
        })

    return {"processed": len(results), "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
