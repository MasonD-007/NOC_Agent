import json
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from state import NOCState
from config import NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL

logger = logging.getLogger("noc-agent")

SYSTEM_PROMPT = (
    "You are a senior Network Operations Center (NOC) engineer AI assistant. "
    "You analyze network alerts and take remediation actions using the tools available to you.\n\n"
    "Network topology:\n"
    "  - core-router: the backbone router\n"
    "  - edge-sw-01: edge switch 1\n"
    "  - edge-sw-02: edge switch 2\n\n"
    "All devices are reachable via their Docker DNS hostname. "
    "SSH credentials: admin / hackathon on port 2222.\n\n"
    "When you identify a threat (e.g. a traffic spike from a source IP), use the ssh_execute tool "
    "to remediate it. For example, to block an attacker IP on a device:\n"
    "  ssh_execute(device_hostname='edge-sw-02', command='iptables -A INPUT -s <attacker_ip> -j DROP', confirmed=True)\n\n"
    "Always set confirmed=True when you are ready to execute. Be concise and act decisively."
)


def build_graph(tools: list) -> StateGraph:
    llm = ChatOpenAI(
        api_key=NEBIUS_API_KEY,
        base_url=NEBIUS_BASE_URL,
        model=NEBIUS_MODEL,
        timeout=120,
    )
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: NOCState) -> dict:
        # On first invocation, inject the system prompt and alert as a human message
        if not state["messages"]:
            alert_json = json.dumps(state["alert"], indent=2)
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Analyze this alert and take remediation action using your tools.\n\n"
                    f"Alert:\n```json\n{alert_json}\n```"
                )),
            ]
        else:
            messages = state["messages"]

        logger.info("Calling LLM with %d messages...", len(messages))
        response = await llm_with_tools.ainvoke(messages)
        logger.info("LLM response: tool_calls=%s, content=%s",
                     getattr(response, 'tool_calls', []),
                     response.content[:200] if response.content else "(empty)")
        return {"messages": [response], "phase": "acting"}

    async def tool_node_with_logging(state: NOCState) -> dict:
        last_msg = state["messages"][-1]
        logger.info("Executing tool calls: %s", getattr(last_msg, 'tool_calls', []))
        tool_executor = ToolNode(tools)
        result = await tool_executor.ainvoke(state)
        for msg in result.get("messages", []):
            logger.info("Tool result: %s", msg.content[:300] if hasattr(msg, 'content') else str(msg)[:300])
        return result

    graph = StateGraph(NOCState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node_with_logging)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()
