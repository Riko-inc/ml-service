import json
import uuid
from typing import Dict, Any
from langchain.tools import BaseTool

from async_kafka_client import AsyncKafkaToolClient


class TranslateToolAsync(BaseTool):
    name: str = "translate_tool"
    description: str = (
        "Переводит текст с автоопределением языка (langdetect) на заданный 'target_lang'.\n"
        "Работает асинхронно: публикует задачу в Kafka-топик 'translation_tasks' и ждёт ответа из 'translation_results'.\n"
        "Аргументы (keyword args):\n"
        "  - text: str, исходный текст.\n"
        "  - target_lang: str, двухбуквенный код языка (например, 'ru' или 'en').\n"
        "Возвращает: dict { 'source_lang': <автоопределённый>, 'translated_text': <перевод> }, либо падает."
    )

    def __init__(self):
        super().__init__()
        self._client = AsyncKafkaToolClient(
            publisher_topic="translation_tasks",
            subscriber_topic="translation_results"
        )

    async def _arun(
        self,
        text: str,
        target_lang: str = "ru"
    ) -> Dict[str, Any]:
        if not text:
            raise ValueError("TranslateToolAsync: нужно передать непустой текст")

        task_id = str(uuid.uuid4())
        payload_dict = {
            "task_id": task_id,
            "text": text,
            "target_lang": target_lang
        }

        payload_str = json.dumps(payload_dict, ensure_ascii=False)

        try:
            result: Dict[str, Any] = await self._client.send_task_and_wait(
                payload=payload_str,
                task_id=task_id,
                timeout=60
            )
        except TimeoutError as te:
            raise RuntimeError(f"TranslateToolAsync: timed out waiting for result: {te}")

        if not result.get("success", False):
            err = result.get("error", "unknown translation error")
            raise RuntimeError(f"TranslateToolAsync error: {err}")

        return {
            "source_lang": result.get("source_lang"),
            "target_lang": result.get("target_lang"),
            "translated_text": result.get("translated_text")
        }

    async def _run(
        self,
        text: str,
        target_lang: str = "ru"
    ) -> Dict[str, Any]:
        return await self._arun(text=text, target_lang=target_lang)
