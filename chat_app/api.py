from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import os
import uvicorn
from dotenv import load_dotenv

from core_app.models.text_llm import CustomChatModel
from core_app.api_clients.api_clients import GigaChatClient, GIGACHAT_API_URL
from core_app.tools.models import AgentRequest, AgentResponse, ChatRequest, ChatResponse
from core_app.tools.setup_logger import setup_logger
from core_app.tools.llm_tools import SummarizationTool, ThinkTool

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Маршрутизирует запрос чата к соответствующей модели.
    """
    system = request.system_prompt
    user = request.user_prompt

    # Вызов модели
    try:
        result_obj = text_llm.invoke([system, user], token=giga_client.get_access_token())
        result = result_obj.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(content=result)


@app.post("/chat/agent", response_model=AgentResponse)
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
