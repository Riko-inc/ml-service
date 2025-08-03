from typing import TypedDict, List, Dict, Any, Optional

class GraphState(TypedDict):
    input: str
    chat_history: List[Dict[str, str]]
    intermediate_steps: List[Dict[str, Any]]
    tool_response: Optional[Dict[str, Any]]
    answer: Optional[str]
    