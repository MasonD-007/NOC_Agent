import operator
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage


class NOCState(TypedDict):
    alert: dict
    messages: Annotated[list[BaseMessage], operator.add]
    investigation_log: list[str]
    phase: str
