import json
import uuid
from typing import Optional, Dict, Any
from langchain.tools import BaseTool

from tools.async_kafka_client import AsyncKafkaToolClient


class Speech2TextToolAsync(BaseTool):
    name: str = "speech2text_tool"
    description: str = (
        "Преобразует аудио (WAV/MP3/OGG) в текст с помощью SaluteSpeech API.\n"
        "Работает асинхронно: публикует задачу в Kafka-топик 'speech2text_tasks' и ждёт ответа из 'speech2text_results'.\n"
        "Аргументы (keyword args):\n"
        "  - audio_path: str, путь до аудиофайла (если файл лежит локально).\n"
        "  - audio_bytes_base64: str, Base64-строка с содержимым аудио.\n"
        "  - audio_format: str, например 'wav' или 'mp3'.\n"
        "Возвращает: транскрибированный текст (string), либо падает с ошибкой."
    )

    def __init__(self):
        super().__init__()
        self._client = AsyncKafkaToolClient(
            publisher_topic="speech2text_tasks",
            subscriber_topic="speech2text_results"
        )

    async def _arun(
        self,
        audio_path: Optional[str] = None,
        audio_bytes_base64: Optional[str] = None,
        audio_format: str = "wav"
    ) -> str:
        if not (audio_path or audio_bytes_base64):
            raise ValueError("Speech2TextToolAsync: нужно передать либо audio_path, либо audio_bytes_base64")

        task_id = str(uuid.uuid4())
        payload_dict = {
            "task_id": task_id,
            "audio_format": audio_format
        }
        if audio_path:
            payload_dict["audio_path"] = audio_path
        else:
            payload_dict["audio_bytes"] = audio_bytes_base64

        payload_str = json.dumps(payload_dict, ensure_ascii=False)

        try:
            result: Dict[str, Any] = await self._client.send_task_and_wait(
                payload=payload_str,
                task_id=task_id,
                timeout=120  # секунд (больший запас на сеть)
            )
        except TimeoutError as te:
            raise RuntimeError(f"Speech2TextToolAsync: timed out waiting for result: {te}")

        if not result.get("success", False):
            err = result.get("error", "unknown Speech2Text error")
            raise RuntimeError(f"Speech2TextToolAsync error: {err}")

        text = result.get("text", "")
        return text

    async def _run(
        self,
        audio_path: Optional[str] = None,
        audio_bytes_base64: Optional[str] = None,
        audio_format: str = "wav"
    ) -> str:
        return await self._arun(audio_path=audio_path, audio_bytes_base64=audio_bytes_base64, audio_format=audio_format)
