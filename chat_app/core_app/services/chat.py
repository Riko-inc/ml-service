# chat_app/core_app/services/chat.py
from typing import List, Type

from sqlalchemy.orm import Session
from chat_app.core_app.database import models, Message, User
from chat_app.core_app.database.session import get_database_url


def save_message(db: Session, user_id: int, content: str, role: str):
    user = db.query(models.User).filter(models.User.external_id == user_id).first()
    if not user:
        user = models.User(external_id=user_id)
        db.add(user)
        db.commit()

    message = models.Message(
        content=content,
        role=role,
        user_id=user.id
    )
    db.add(message)
    db.commit()
    return message


def get_user_messages(db: Session, user_id: int) -> list[Type[Message]]:
    return db.query(Message).join(models.User).filter(User.external_id == user_id).all()