
from dataclasses import dataclass
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated
from typing import Optional

@dataclass(kw_only=True)
class ChatState:
    messages: Annotated[list[AnyMessage], add_messages]
    evaluation: Optional[str] = None
    next_node: Optional[str] = None
    