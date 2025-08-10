from frozenlist import FrozenList
from pydantic import BaseModel, Field
from typing import List, Dict


class AgentMessage(BaseModel):
    role: str
    text: str

class AgentRequest(BaseModel):
    messages: list[AgentMessage] = Field(default_factory=FrozenList)
    history_state: list[AgentMessage] = Field(default_factory=FrozenList)

class AgentResponse(BaseModel):
    message: str
    agent_state: List[AgentMessage]

# class ChatRequest(BaseModel):
#     mode: str = Field(..., description="Режим запроса: 'text', 'code' или 'auto'")
#     system_prompt: str = Field(..., description="Системная инструкция для LLM")
#     user_prompt: str = Field(..., description="Сообщение пользователя")

class ChatResponse(BaseModel):
    content: str = Field(..., description="Текст ответа")
    role: str

class ChatRequest(BaseModel):
    content: str = Field(..., description="Текст запроса пользователя")
    space_prefix: str = Field(..., description="Префикс пространства пользователя")

class UserProfile(BaseModel):
    name_of_teachers: str
    age: int
    education: Dict[str, str]
    job: str
