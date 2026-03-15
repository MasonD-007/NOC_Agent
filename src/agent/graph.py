import json
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from state import NOCState
from config import NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL

llm = ChatOpenAI(
    api_key=NEBIUS_API_KEY,
    base_url=NEBIUS_BASE_URL,
    model=NEBIUS_MODEL,
)

SYSTEM_PROMPT = (
    "You are a senior Network Operations Center (NOC) engineer AI assistant. "
    "You analyze network alerts from Prometheus/AlertManager, investigate root causes, "
    "and recommend remediation actions. Be concise and specific."
)


def triage(state: NOCState) -> NOCState:
    alert_json = json.dumps(state["alert"], indent=2)
    msg = HumanMessage(content=(
        f"Triage this alert. Classify its severity (critical/warning/info) and type "
        f"(traffic, latency, availability, security). Briefly explain why.\n\n"
        f"Alert:\n```json\n{alert_json}\n```"
    ))
    messages = [SystemMessage(content=SYSTEM_PROMPT), msg]
    response = llm.invoke(messages)
    return {
        "messages": messages + [response],
        "investigation_log": [f"[triage] {response.content}"],
        "phase": "triage",
    }


def investigate(state: NOCState) -> NOCState:
    msg = HumanMessage(content=(
        "Based on the triage above, investigate further. "
        "What are the likely root causes? What data points support your analysis? "
        "List possible failure scenarios."
    ))
    messages = state["messages"] + [msg]
    response = llm.invoke(messages)
    return {
        "messages": messages + [response],
        "investigation_log": state["investigation_log"] + [f"[investigate] {response.content}"],
        "phase": "investigate",
    }


def recommend(state: NOCState) -> NOCState:
    msg = HumanMessage(content=(
        "Based on your investigation, recommend specific remediation actions. "
        "Prioritize them by impact. Include both immediate mitigations and longer-term fixes."
    ))
    messages = state["messages"] + [msg]
    response = llm.invoke(messages)
    return {
        "messages": messages + [response],
        "investigation_log": state["investigation_log"] + [f"[recommend] {response.content}"],
        "phase": "recommend",
    }


def report(state: NOCState) -> NOCState:
    msg = HumanMessage(content=(
        "Write a final NOC incident summary report. Include: "
        "1) Alert overview, 2) Severity & classification, 3) Root cause analysis, "
        "4) Recommended actions, 5) Escalation notes if needed. Keep it structured and actionable."
    ))
    messages = state["messages"] + [msg]
    response = llm.invoke(messages)
    return {
        "messages": messages + [response],
        "investigation_log": state["investigation_log"] + [f"[report] {response.content}"],
        "phase": "report",
    }


def build_graph() -> StateGraph:
    graph = StateGraph(NOCState)
    graph.add_node("triage", triage)
    graph.add_node("investigate", investigate)
    graph.add_node("recommend", recommend)
    graph.add_node("report", report)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "investigate")
    graph.add_edge("investigate", "recommend")
    graph.add_edge("recommend", "report")
    graph.add_edge("report", END)
    return graph.compile()


noc_graph = build_graph()
