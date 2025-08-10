# chat_app/core_app/schemas/message.py
from pydantic import BaseModel
from datetime import datetime

class MessageBase(BaseModel):
    content: str
    role: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    timestamp: datetime
    user_id: int

    class Config:
        orm_mode = True