from langchain.tools import BaseTool
from langchain.schema import AIMessage
from langchain_core.outputs import ChatResult

from chat_app.core_app.models.text_llm import CustomChatModel
from chat_app.core_app.api_clients.api_clients import GigaChatClient, GIGACHAT_API_URL

llm = CustomChatModel(api_url=GIGACHAT_API_URL)
client = GigaChatClient()


class SummarizationTool(BaseTool):
    name = "summarize"
    description = "Сжимает историю чата до ключевых фактов, если она слишком велика."

    def _run(self, text: str) -> str:
        # Запрос к вашей модели для суммаризации
        token = client.get_access_token()
        prompt = (
            "Резюмируй следующие сообщения чата, оставив только ключевые факты:\n" + text
        )
        # Формируем сообщения
        msgs = [
            AIMessage(content=prompt)
        ]
        result: ChatResult = llm.invoke(msgs, token=token)
        return result.generations[0].message.content

class ThinkTool(BaseTool):
    name = "think"
    description = "Внутренние размышления для поиска лучшего ответа."

    def _run(self, prompt_text: str) -> str:
        token = client.get_access_token()
        prompt = (
            "Подумай над этой задачей и запиши рассуждения:\n" + prompt_text
        )
        msgs = [
            AIMessage(content=prompt)
        ]
        result: ChatResult = llm.invoke(msgs, token=token)
        return result.generations[0].message.content