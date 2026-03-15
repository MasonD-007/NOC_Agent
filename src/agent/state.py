from typing import TypedDict
from langchain_core.messages import BaseMessage


class NOCState(TypedDict):
    alert: dict
    messages: list[BaseMessage]
    investigation_log: list[str]
    phase: str
