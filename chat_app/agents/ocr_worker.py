import os
import json
import asyncio
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import base64
import tempfile

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCRWorker")

# Путь к Tesseract (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRWorker:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.input_topic = "ocr_tasks"
        self.output_topic = "ocr_results"
        self.consumer = None
        self.producer = None

    async def start(self):
        """Запуск Kafka-клиентов"""
        self.consumer = AIOKafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8"))
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8")
        )
        await self.consumer.start()
        await self.producer.start()
        logger.info("OCR Worker started")

    async def stop(self):
        """Остановка Kafka-клиентов"""
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("OCR Worker stopped")

    async def process_message(self, msg):
        """Обработка сообщения из Kafka"""
        task_id = msg.value.get("task_id")
        file_type = msg.value.get("file_type", "pdf")
        
        try:
            # Получаем файл
            if "file_path" in msg.value:
                file_path = msg.value["file_path"]
                logger.info(f"Processing local file: {file_path}")
            elif "file_bytes" in msg.value:
                file_data = base64.b64decode(msg.value["file_bytes"])
                file_path = await self.save_temp_file(file_data, file_type)
                logger.info(f"Processing base64 file: {file_path}")
            else:
                raise ValueError("No file provided")

            # Распознаем текст
            if file_type == "pdf":
                
                images = convert_from_path(file_path)
                text = "\n".join([pytesseract.image_to_string(img, lang='rus+eng') for img in images])
            else:
                img = Image.open(file_path)
                text = pytesseract.image_to_string(img, lang='rus+eng')

            # Отправляем результат
            await self.send_result(task_id, text, success=True)

            # Удаляем временный файл
            if "file_bytes" in msg.value:
                os.unlink(file_path)

        except Exception as e:
            logger.error(f"OCR error: {str(e)}")
            await self.send_result(task_id, error=str(e), success=False)

    async def save_temp_file(self, data, file_type):
        """Сохраняет временный файл"""
        suffix = f".{file_type}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmpfile:
            tmpfile.write(data)
            return tmpfile.name

    async def send_result(self, task_id, text=None, error=None, success=False):
        """Отправляет результат в Kafka"""
        result = {
            "task_id": task_id,
            "success": success
        }
        if success:
            result["text"] = text
        else:
            result["error"] = error
        await self.producer.send(self.output_topic, value=json.dumps(result, ensure_ascii=False))

    async def run(self):
        """Основной цикл работы"""
        try:
            await self.start()
            async for msg in self.consumer:
                logger.info(f"Received task: {msg.value.get('task_id')}")
                await self.process_message(msg)
        finally:
            await self.stop()

if __name__ == "__main__":
    worker = OCRWorker()
    asyncio.run(worker.run())
