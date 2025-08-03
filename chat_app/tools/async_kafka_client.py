import os
import asyncio
from typing import Dict, Any
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


class AsyncKafkaProducerSingleton:
    """
    Одиночный (singleton) producer, чтобы все инструменты могли к нему обращаться.
    Инициализируется при первом запросе.
    """
    _producer: AIOKafkaProducer = None

    @classmethod
    async def get_producer(cls) -> AIOKafkaProducer:
        if cls._producer is None:
            cls._producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: v.encode("utf-8")
            )
            await cls._producer.start()
        return cls._producer

    @classmethod
    async def close_producer(cls):
        if cls._producer is not None:
            await cls._producer.stop()
            cls._producer = None


class AsyncKafkaToolClient:
    """
    Общий код для асинхронного инструмента, работающего через Kafka.
    - publisher_topic: куда публикуем задачи (например, 'ocr_tasks')
    - subscriber_topic: где слушаем результаты (например, 'ocr_results')
    - pending_futures: Dict[task_id -> asyncio.Future], 
      consumer читает из subscriber_topic и, найдя task_id, раздаёт результат.
    """

    def __init__(self, publisher_topic: str, subscriber_topic: str):
        self.publisher_topic = publisher_topic
        self.subscriber_topic = subscriber_topic
        # Словарь: task_id -> Future
        self.pending_futures: Dict[str, asyncio.Future] = {}
        self._consumer: AIOKafkaConsumer = None
        self._consumer_task: asyncio.Task = None
        self._loop = asyncio.get_event_loop()

    async def start_consumer(self):
        """
        Запускаем асинхронного потребителя, который слушает subscriber_topic.
        """
        if self._consumer is not None:
            return

        self._consumer = AIOKafkaConsumer(
            self.subscriber_topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda v: v.decode("utf-8")
        )
        await self._consumer.start()

        # Запускаем фоновую задачу, которая постоянно читает сообщения
        self._consumer_task = self._loop.create_task(self._consume_loop())

    async def stop_consumer(self):
        """
        Остановить consumer и фоновую задачу.
        """
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

    async def _consume_loop(self):
        """
        Фоновая корутина: постоянно слушает subscriber_topic и
        при получении сообщения извлекает task_id и “результат”,
        затем отдаёт результат в соответствующий Future.
        """
        try:
            async for msg in self._consumer:
                # msg.value — строка JSON → распарсим
                import json
                data = json.loads(msg.value)
                task_id = data.get("task_id")
                if task_id is None:
                    continue
                # Найдём future
                fut = self.pending_futures.pop(task_id, None)
                if fut and not fut.done():
                    # В будущем мы ожидаем весь JSON “как есть”
                    fut.set_result(data)
        except asyncio.CancelledError:
            # При остановке consumer — выходим
            return

    async def send_task_and_wait(
        self,
        payload: str,
        task_id: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        1. Гарантируем, что consumer запущен
        2. Создаём пустой Future и кладём его в pending_futures
        3. Публикуем payload (строка JSON) в publisher_topic
        4. Ждём, пока future разрешится при получении ответа или упадёт по таймауту
        Возвращаем распарсенный словарь JSON из результата (из subscriber_topic).
        """
        # 1. Убедимся, что consumer слушает subscriber_topic
        await self.start_consumer()

        # 2. Создаём Future и сохраняем
        future = self._loop.create_future()
        self.pending_futures[task_id] = future

        # 3. Публикуем payload
        producer = await AsyncKafkaProducerSingleton.get_producer()
        await producer.send_and_wait(self.publisher_topic, payload)

        try:
            # 4. Ждём разрешения future или таймаут
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            # Удалим future из словаря, чтобы не накапливались “забытые”
            self.pending_futures.pop(task_id, None)
            raise TimeoutError(
                f"No response in '{self.subscriber_topic}' for task_id={task_id} within {timeout}s"
            )
