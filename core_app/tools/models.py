from pydantic import BaseModel, Field
from typing import List, Dict


class AgentMessage(BaseModel):
    role: str
    text: str

class AgentRequest(BaseModel):
    messages: list[AgentMessage] = Field(default_factory=list)
    history_state: list[AgentMessage] = Field(default_factory=list)

class AgentResponse(BaseModel):
    message: str
    agent_state: List[AgentMessage]

class ChatRequest(BaseModel):
    mode: str = Field(..., description="Режим запроса: 'text', 'code' или 'auto'")
    system_prompt: str = Field(..., description="Системная инструкция для LLM")
    user_prompt: str = Field(..., description="Сообщение пользователя")

class ChatResponse(BaseModel):
    content: str

class UserProfile(BaseModel):
    name_of_teachers: str
    age: int
    education: Dict[str, str]
    job: str
