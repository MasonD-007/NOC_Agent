# NOC Agent

An AI-powered Network Operations Center that detects, investigates, and remediates network security threats autonomously. Prometheus fires alerts → an LLM agent analyses the threat and executes iptables rules via SSH — all visible in a real-time chat UI.

## Demo

[![NOC Agent Demo](https://img.youtube.com/vi/cwtIRS0HMYg/maxresdefault.jpg)](https://www.youtube.com/watch?v=cwtIRS0HMYg)

## How It Works

```
rogue-device  ──UDP flood──►  edge-sw-02
                                  │
                        network_monitor.py (Docker stats)
                                  │
                         log-aggregator:8000 (/ingest)
                                  │
                        Prometheus scrapes /metrics
                                  │
                         alert.rules → Alertmanager
                                  │
                         ai-agent:5050/alert (webhook)
                                  │
                         LangGraph ReAct loop
                          ┌───────┴────────┐
                     explain_threat    ssh_execute
                     (Prometheus)   (iptables DROP)
                                  │
                         frontend:3000 (chat UI)
```

## Architecture

The stack is split into five layers:

| Layer | Services | Purpose |
|---|---|---|
| **Network devices** | `core-router`, `edge-sw-01`, `edge-sw-02` | Simulated Linux routers/switches (SSH on ports 2222–2224) |
| **Attack simulation** | `rogue-device` | Blasts 1 Gbps UDP at `edge-sw-02` via iperf3 |
| **NOC brain** | `mcp-server` · `ai-agent` · `frontend` | MCP tool server, LangGraph agent, React chat UI |
| **Monitoring** | `network-monitor` · `log-aggregator` · `prometheus` · `alertmanager` | Event ingestion, metrics, alerting |
| **Bootstrap** | `metrics-simulator` | Seeds an initial Prometheus metric on startup |

### Agent (`src/agent/`)

FastAPI service (port **5050**) with two endpoints:

- `POST /alert` — receives Alertmanager webhook payloads and runs the autonomous remediation graph
- `POST /chat` — streams agent responses over SSE for the interactive chat UI

The agent is a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` with a classic **ReAct loop**: `agent → tools → agent`. It uses DeepSeek-V3 via the Nebius API.

### MCP Tool Server (`src/mcp/`)

Starlette service (port **8080**) that exposes tools to the agent over the MCP SSE transport.

| Tool | Description |
|---|---|
| `ssh_execute(device_hostname, command, confirmed)` | Runs a shell command on a network device via SSH. `confirmed=True` is a required safety flag. |
| `explain_threat(ip)` | Aggregates Prometheus metrics and log-aggregator data for an IP into a structured threat summary (risk level, event breakdown, traffic rate, threat score). |

### Monitoring stack

- **`log_aggregator.py`** — Flask service that ingests security events (`POST /ingest`) and exposes Prometheus metrics per source IP: failed logins, suspicious requests, traffic rate, payload threat score, event rate.
- **`network_monitor.py`** — Polls Docker container stats for `edge-sw-02` to detect traffic spikes, then posts events to the log aggregator.
- **`prometheus`** — Scrapes log aggregator metrics every 5 s and evaluates five alerting rules.
- **`alertmanager`** — Routes all alerts to the `ai-agent /alert` webhook.

### Alerting rules (`config/alert.rules`)

| Alert | Condition | Severity |
|---|---|---|
| `BruteForceLoginAttempt` | >10 failed logins in 5 min from same IP | high |
| `TrafficSpike` | traffic > 10 MB/s for 30 s | critical |
| `SuspiciousEndpointScanning` | >5 hits to suspicious endpoint in 2 min | medium |
| `HighThreatPayload` | payload threat score > 60 | critical |
| `EventRateSpike` | >50 events/min from same IP for 1 min | medium |

### Frontend (`src/frontend/`)

React + Vite app served by Nginx on port **3000**.

- Real-time SSE streaming renders the agent's investigation and response as they arrive
- **Investigation panel** — each tool call/result rendered as a structured card (tool name, args, status badge, output)
- **Response panel** — agent's Markdown response
- **Explain Threat button** — appears after SSH remediation; clicking it sends `explain_threat(ip)` and displays a full threat breakdown

## Getting started

### Prerequisites

- Docker + Docker Compose
- A [Nebius](https://nebius.com) API key (DeepSeek-V3 access)

### Setup

```bash
cp .env.example .env
# Add your NEBIUS_API_KEY to .env
```

### Run

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Chat UI | http://localhost:3000 |
| NOC Agent API | http://localhost:5050 |
| Prometheus | http://localhost:9090 |
| Log Aggregator | http://localhost:8000 |
| Alertmanager | http://localhost:9093 |

The `rogue-device` starts blasting traffic immediately. Within ~30 seconds Prometheus fires a `TrafficSpike` alert, Alertmanager forwards it to the agent, and the agent begins investigating autonomously. You can also type alerts directly in the chat UI.

### Example prompts

```
BruteForceLoginAttempt on edge-sw-02 — 500 failed SSH attempts from 10.0.0.5
TrafficSpike alert: edge-sw-02 showing 50,000 pps, baseline is 200 pps
Prometheus fired HighThreatPayload — threat score 0.92 on core-router
```

## Project structure

```
NOC_Agent/
├── config/
│   ├── alert.rules          # Prometheus alerting rules
│   ├── alertmanager.yml     # Webhook routing to ai-agent
│   ├── prometheus.yml       # Scrape config
│   └── init-iperf.sh        # Starts iperf3 server on edge-sw-02
├── prometheus/
│   ├── log_aggregator.py    # Event ingestion + Prometheus metrics
│   └── network_monitor.py   # Docker stats → traffic spike detection
└── src/
    ├── agent/
    │   ├── app.py           # FastAPI: /alert, /chat, /health
    │   ├── graph.py         # LangGraph StateGraph (ReAct loop)
    │   ├── state.py         # NOCState TypedDict
    │   └── config.py        # LLM config (Nebius / DeepSeek)
    ├── mcp/
    │   └── server.py        # MCP tool server: ssh_execute, explain_threat
    └── frontend/
        └── src/
            ├── App.jsx      # SSE streaming, conversation state
            └── components/
                ├── MessageBubble.jsx   # Phase blocks, tool call cards
                ├── ChatWindow.jsx
                ├── Sidebar.jsx
                ├── Header.jsx
                └── InputBar.jsx
```
