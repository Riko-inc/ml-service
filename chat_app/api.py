from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware

import os
import uvicorn
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from chat_app.core_app.database.session import get_db

from chat_app.core_app.dependencies.auth import get_current_user
from chat_app.core_app.services.chat import get_user_messages, save_message
from chat_app.core_app.models.text_llm import CustomChatModel
from chat_app.core_app.api_clients.api_clients import GigaChatClient, GIGACHAT_API_URL
from chat_app.core_app.tools.models import AgentRequest, AgentResponse, ChatRequest, ChatResponse
from chat_app.core_app.tools.setup_logger import setup_logger

load_dotenv()

logger = setup_logger(__name__.upper())

app = FastAPI(
    title="Универсальный чат API",
    version="1.0.0",
    description="Маршрутизирует запросы к текстовым или кодовым LLM в зависимости от режима или содержимого."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация моделей
giga_client = GigaChatClient()
text_llm = CustomChatModel(api_url=GIGACHAT_API_URL)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
        request: ChatRequest,
        user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Обрабатывает запрос к чат-модели и сохраняет историю
    """
    system = "Ты полезный ассистент, готовый ответить на вопросы пользователя"
    user_id = user["id"]

    # Сохраняем запрос пользователя
    save_message(db, user_id, request.content, "user")

    try:
        result_obj = text_llm.invoke([system, request.content], token=giga_client.get_access_token())
        result = result_obj.content

        # Сохраняем ответ ассистента
        save_message(db, user_id, result, "assistant")

    except Exception as e:
        logger.error(f"Model invocation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing your request"
        )

    return ChatResponse(content=result, role="assistant")


@app.get("/api/v1/history", response_model=list[ChatResponse])
async def history(
        user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Возвращает историю сообщений для текущего пользователя
    """
    user_id = user["id"]
    messages = get_user_messages(db, user_id)

    response = [ChatResponse(content=message.content.__str__(), role=message.role.__str__()) for message in messages]

    return response


@app.post("/api/v1/agent", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    """
    Обработка запроса через агентский интерфейс chat_agent.
    """
    from chat_agent import chat_agent  # Импорт здесь, чтобы избежать циклических зависимостей

    try:
        state = {
            "messages": [msg.model_dump() for msg in request.messages],
            "history_state": [msg.model_dump() for msg in request.history_state]
        }
        result = chat_agent(state)
        return AgentResponse(
            message=result["messages"]["message"],
            agent_state=result.get("history_state", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    


@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
