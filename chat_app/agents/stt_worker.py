import os
import json
import asyncio
import logging
import aiohttp
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import base64

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("STTWorker")

# Конфигурация SaluteSpeech API
SALUTE_API_URL = "https://api.salutespeech.com/v1/asr" 
SALUTE_API_KEY = os.getenv("SALUTE_API_KEY")

class STTWorker:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.input_topic = "speech2text_tasks"
        self.output_topic = "speech2text_results"
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
        logger.info("STT Worker started")

    async def stop(self):
        """Остановка Kafka-клиентов"""
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("STT Worker stopped")

    async def process_message(self, msg):
        """Обработка сообщения из Kafka"""
        task_id = msg.value.get("task_id")
        audio_format = msg.value.get("audio_format", "wav")
        
        try:
            # Получаем аудиофайл
            if "audio_path" in msg.value:
                audio_path = msg.value["audio_path"]
                logger.info(f"Processing local audio: {audio_path}")
                with open(audio_path, "rb") as f:
                    audio_data = f.read()
            elif "audio_bytes" in msg.value:
                audio_data = base64.b64decode(msg.value["audio_bytes"])
                logger.info("Processing base64 audio")
            else:
                raise ValueError("No audio provided")

            # Отправляем на SaluteSpeech API
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Api-Key {SALUTE_API_KEY}",
                    "Content-Type": "audio/{audio_format}"
                }
                async with session.post(SALUTE_API_URL, headers=headers, data=audio_data) as resp:
                    if resp.status != 200:
                        raise Exception(f"API error: {await resp.text()}")
                    result = await resp.json()
                    text = result.get("result", "")

            # Отправляем результат
            await self.send_result(task_id, text, success=True)

        except Exception as e:
            logger.error(f"STT error: {str(e)}")
            await self.send_result(task_id, error=str(e), success=False)

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
                logger.info(f"Received STT task: {msg.value.get('task_id')}")
                await self.process_message(msg)
        finally:
            await self.stop()

if __name__ == "__main__":
    worker = STTWorker()
    asyncio.run(worker.run())
    