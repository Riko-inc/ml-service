import os
import json
import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

# Для определения языка
from langdetect import detect, DetectorFactory, LangDetectException

# Вместо MarianMT — LLM Cotype-Nano
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TranslateWorker")

# Карта для сопоставления кодов и «читаемых» названий языков
LANG_MAP = {
    "en": "en",
    "ru": "ru",
    "de": "de",
    "fr": "fr",
    "es": "es"
}
LANG_NAME = {
    "en": "English",
    "ru": "Russian",
    "de": "German",
    "fr": "French",
    "es": "Spanish"
}

class TranslateWorker:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.input_topic = "translation_tasks"
        self.output_topic = "translation_results"
        self.consumer = None
        self.producer = None

        # Модель и токенизатор
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    async def start(self):
        """Запуск Kafka-клиентов и загрузка модели Cotype-Nano"""
        # Настраиваем потребителя и продюсера Kafka
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

        # Фиксируем seed для langdetect, чтобы детектирование было воспроизводимым
        DetectorFactory.seed = 0

        # Загружаем LLM Cotype-Nano для перевода
        model_name = "MTSAIR/Cotype-Nano"
        logger.info(f"Loading model {model_name} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(self.device)
        # Делаем модель в режиме eval
        self.model.eval()

        logger.info("Translate Worker started (Cotype-Nano loaded)")

    async def stop(self):
        """Остановка Kafka-клиентов"""
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("Translate Worker stopped")

    def detect_language(self, text: str) -> str:
        """
        Определяет язык текста с помощью langdetect.
        Возвращает двухбуквенный код (ISO 639-1) или пустую строку, если не удалось определить.
        """
        try:
            lang = detect(text)
            return LANG_MAP.get(lang, lang)
        except LangDetectException:
            return ""

    async def translate_text(self, text: str, target_lang: str):
        """
        Переводит текст через Cotype-Nano, формируя соответствующий prompt.
        Если модель «не справляется» (нет информации о языках), возвращаем оригинал.
        """
        src_lang = self.detect_language(text)
        if not src_lang:
            # Не удалось определить язык — просто возвращаем текст «как есть»
            logger.warning("Language detection failed, returning original text")
            return text, src_lang

        # Если исходный язык уже совпадает с целевым, не переводим
        if src_lang == target_lang:
            return text, src_lang

        # Убедимся, что у нас есть «читаемое» имя языка
        src_name = LANG_NAME.get(src_lang, src_lang)
        tgt_name = LANG_NAME.get(target_lang, target_lang)

        # Формируем prompt для перевода
        prompt = (
            f"Translate from {src_name} to {tgt_name}:\n"
            f"{text}\n"
            f"Translation:"
        )

        # Токенизируем и генерируем
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024  # усечём слишком длинные входы
        ).to(self.device)

        # Генерация. Можно подстроить параметры temperature/top_p/num_beams при необходимости
        generated_ids = self.model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,       # жадная стратегия
            num_beams=4,           # лучевой поиск
            eos_token_id=self.tokenizer.eos_token_id
        )

        output_text = self.tokenizer.decode(
            generated_ids[0],
            skip_special_tokens=True
        )

        # В output_text вместе с prompt попадёт и сам «Translate from...», поэтому обрежем всё до слова "Translation:"
        # Предполагаем, что модель после prompt выдаёт «..., Translation: <сам перевод>»
        split_token = "Translation:"
        if split_token in output_text:
            translated_text = output_text.split(split_token, 1)[1].strip()
        else:
            # Если чего-то пошло не так — вернём полный текст генерации (хотя в норме это не должно случаться).
            translated_text = output_text

        return translated_text, src_lang

    async def process_message(self, msg):
        """Обработка одного сообщения (задачи) из Kafka"""
        task_id = msg.value.get("task_id")
        target_lang = msg.value.get("target_lang", "ru")
        text = msg.value.get("text", "")

        try:
            translated_text, source_lang = await self.translate_text(text, target_lang)
            await self.send_result(
                task_id=task_id,
                source_lang=source_lang,
                target_lang=target_lang,
                translated_text=translated_text,
                success=True
            )
        except Exception as e:
            logger.error(f"Translate error: {str(e)}")
            await self.send_result(task_id=task_id, error=str(e), success=False)

    async def send_result(
        self,
        task_id: str,
        source_lang: str = None,
        target_lang: str = None,
        translated_text: str = None,
        error: str = None,
        success: bool = False
    ):
        """Отправляет результат (успех либо ошибку) обратно в Kafka"""
        result = {
            "task_id": task_id,
            "success": success
        }
        if success:
            result.update({
                "source_lang": source_lang,
                "target_lang": target_lang,
                "translated_text": translated_text
            })
        else:
            result["error"] = error

        await self.producer.send(
            self.output_topic,
            value=json.dumps(result, ensure_ascii=False)
        )

    async def run(self):
        """Основной цикл: читаем задачи из Kafka, переводим, отправляем результат"""
        try:
            await self.start()
            async for msg in self.consumer:
                logger.info(f"Received translation task: {msg.value.get('task_id')}")
                await self.process_message(msg)
        finally:
            await self.stop()

if __name__ == "__main__":
    worker = TranslateWorker()
    asyncio.run(worker.run())
