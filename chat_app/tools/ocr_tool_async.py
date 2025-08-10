import json
import uuid
from typing import Optional, Dict, Any
from langchain.tools import BaseTool

from async_kafka_client import AsyncKafkaToolClient


class OCRToolAsync(BaseTool):
    name: str = "ocr_tool"
    description: str = (
        "Преобразует PDF или изображение в текст (русский+английский) с помощью Tesseract.\n"
        "Работает асинхронно: публикует задачу в Kafka-топик 'ocr_tasks' и ждёт ответа из 'ocr_results'.\n"
        "Аргументы (keyword args):\n"
        "  - file_path: str, путь до PDF или картинки (если файл лежит локально).\n"
        "  - file_bytes_base64: str, Base64-строка с содержимым файла (pdf/image).\n"
        "  - file_type: str, 'pdf' или 'image'.\n"
        "Возвращает: распознанный текст (string), либо падает с ошибкой."
    )

    def __init__(self):
        super().__init__()
        # Клиент, который будет работать с ocr_tasks -> ocr_results
        self._client = AsyncKafkaToolClient(
            publisher_topic="ocr_tasks",
            subscriber_topic="ocr_results"
        )

    async def _arun(
        self,
        file_path: Optional[str] = None,
        file_bytes_base64: Optional[str] = None,
        file_type: str = "pdf"
    ) -> str:
        if not (file_path or file_bytes_base64):
            raise ValueError("OCRToolAsync: нужно передать либо file_path, либо file_bytes_base64")

        task_id = str(uuid.uuid4())

        payload_dict = {
            "task_id": task_id,
            "file_type": file_type
        }
        if file_path:
            payload_dict["file_path"] = file_path
        else:
            payload_dict["file_bytes"] = file_bytes_base64

        # 4. Сериализуем в JSON-строку (UTF-8)
        payload_str = json.dumps(payload_dict, ensure_ascii=False)

        # 5. Посылаем задачу и ждём результата (result — dict)
        try:
            result: Dict[str, Any] = await self._client.send_task_and_wait(
                payload=payload_str,
                task_id=task_id,
                timeout=90  # секунд
            )
        except TimeoutError as te:
            raise RuntimeError(f"OCRToolAsync: timed out waiting for result: {te}")

        # 6. Проверяем результат
        if not result.get("success", False):
            err = result.get("error", "unknown OCR error")
            raise RuntimeError(f"OCRToolAsync error: {err}")

        text = result.get("text", "")
        return text

    async def _run(
        self,
        file_path: Optional[str] = None,
        file_bytes_base64: Optional[str] = None,
        file_type: str = "pdf"
    ) -> str:
        # Для совместимости, просто вызывает async-версию
        return await self._arun(file_path=file_path, file_bytes_base64=file_bytes_base64, file_type=file_type)
