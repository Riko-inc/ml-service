# chat_app/core_app/database/models.py
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    external_id = Column(Integer, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="user")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="messages")