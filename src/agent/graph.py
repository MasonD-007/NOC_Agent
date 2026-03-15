import json
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from state import NOCState
from config import NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL

logger = logging.getLogger("noc-agent")

SYSTEM_PROMPT = """\
You are a NOC security bot that blocks network attacks. You have one tool: ssh_execute.

The tool parameters are:
- device_hostname (string): one of "core-router", "edge-sw-01", "edge-sw-02"
- command (string): the shell command to run
- confirmed (boolean): always set to true

These are the ONLY three devices. Do not invent other device names.
Always use "sudo" before iptables commands.\
"""

# Maps docker hostnames to their IPs (discovered at alert time via SSH)
# We do the IP lookup ourselves so the LLM doesn't have to
async def _find_device_by_ip(target_ip: str, tools: list) -> str | None:
    """SSH into each device and check if it has the target IP. Returns hostname or None."""
    from langchain_mcp_adapters.tools import load_mcp_tools
    for hostname in ["core-router", "edge-sw-01", "edge-sw-02"]:
        try:
            # Find the ssh_execute tool
            ssh_tool = next((t for t in tools if t.name == "ssh_execute"), None)
            if not ssh_tool:
                return None
            result = await ssh_tool.ainvoke({
                "device_hostname": hostname,
                "command": "ip addr show eth0",
                "confirmed": True,
            })
            # result is a dict or string containing the IP
            result_str = str(result)
            if target_ip in result_str:
                logger.info("Found %s on device %s", target_ip, hostname)
                return hostname
        except Exception as e:
            logger.warning("Failed to check %s: %s", hostname, e)
    return None


def build_graph(tools: list) -> StateGraph:
    llm = ChatOpenAI(
        api_key=NEBIUS_API_KEY,
        base_url=NEBIUS_BASE_URL,
        model=NEBIUS_MODEL,
        timeout=120,
    )
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: NOCState) -> dict:
        if not state["messages"]:
            alert = state["alert"]
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            source_ip = labels.get("source_ip", "UNKNOWN")
            dest_ip = labels.get("destination_ip", "UNKNOWN")
            alert_name = labels.get("alertname", "Unknown")
            description = annotations.get("description", "")

            # Do the IP-to-device lookup ourselves before involving the LLM
            target_device = await _find_device_by_ip(dest_ip, tools)
            if not target_device:
                target_device = "edge-sw-02"  # fallback for demo
                logger.warning("Could not find device for %s, defaulting to %s", dest_ip, target_device)

            human_msg = (
                f"A DDoS attack has been detected.\n"
                f"Attacker IP: {source_ip}\n"
                f"Victim device: {target_device} (IP: {dest_ip})\n"
                f"Description: {description}\n\n"
                f"Please do the following:\n"
                f'1. Block the attacker by running: ssh_execute(device_hostname="{target_device}", command="sudo iptables -A INPUT -s {source_ip} -j DROP", confirmed=true)\n'
                f'2. Verify the rule by running: ssh_execute(device_hostname="{target_device}", command="sudo iptables -L INPUT -n", confirmed=true)\n'
                f"3. Write a short summary of what happened and what you did."
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=human_msg),
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
        tool_executor = ToolNode(tools, handle_tool_errors=True)
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
