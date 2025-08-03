from langchain.agents import initialize_agent, AgentType, Tool
from core_app.tools.setup_logger import setup_logger
from core_app.models.text_llm import CustomChatModel
from core_app.tools.llm_tools import SummarizationTool, ThinkTool
from core_app.api_clients.api_clients import GigaChatClient, GIGACHAT_API_URL

# Setup
logger = setup_logger(__name__.upper())
client = GigaChatClient()
llm = CustomChatModel(api_url=GIGACHAT_API_URL)

# Wrap our custom tools as LangChain Tools
tools = [
    Tool(
        name="summarize",
        func=SummarizationTool()._run,
        description="Сжимает историю чата до ключевых фактов"
    ),
    Tool(
        name="think",
        func=ThinkTool()._run,
        description="Внутренние размышления для поиска лучшего ответа"
    )
]

# Initialize a conversational agent with our LLM and tools
agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=False
)


def chat_agent(state: dict) -> dict:
    """
    Обрабатывает запрос через LangChain AgentExecutor, автоматически
    вызывая инструменты при необходимости.
    """
    logger.info(f"Начало chat_agent. State: {state}")

    # Build the conversation input
    history = state.get("history_state", [])
    chat_history = '\n'.join(f"{m['role']}: {m['text']}" for m in history)
    current_user = state.get("messages", [])[-1]["text"] if state.get("messages") else ""

    # Optionally summarize if history is long
    if len(chat_history) > 1000:
        logger.debug("History too long, summarizing...")
        chat_history = SummarizationTool()._run(chat_history)

    prompt = f"Conversation so far:\n{chat_history}\nUser: {current_user}"
    logger.debug(f"Prompt for agent: {prompt}")

    try:
        # Ensure valid token
        token = state.get("token") or client.get_access_token()
        agent_executor.llm_token = token  # assume llm reads this attribute

        # Run the agent
        logger.info("Запуск AgentExecutor...")
        result_text = agent_executor.run(input=prompt)
        logger.debug(f"Agent result: {result_text}")

        # Build return structure
        return {
            "messages": {
                "type": "message",
                "message": result_text,
                "agent_state": history
            },
            "history_state": history + [{"role": "assistant", "text": result_text}]
        }

    except Exception as e:
        logger.error(f"Ошибка в chat_agent: {e}", exc_info=True)
        return {
            "messages": {
                "type": "message",
                "message": "Произошла ошибка при обработке запроса",
                "agent_state": history
            },
            "history_state": history
        }
    

if __name__ == "__main__":
    # Пример простого теста
    state = {"messages": [{"role":"user","text":"Привет!"}], "history_state": []}
    print(chat_agent(state))