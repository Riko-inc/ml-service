import asyncio
import json
import logging
from typing import Dict, Any, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from prefect import flow, task, get_run_logger

from core_app.models.text_llm import CustomChatModel
from core_app.api_clients.api_clients import GIGACHAT_API_URL
from tools.ocr_tool_async import OCRToolAsync
from tools.speech2text_tool_async import Speech2TextToolAsync
from tools.translate_tool_async import TranslateToolAsync
from tools.async_kafka_client import AsyncKafkaProducerSingleton

# ===========================
#  Настройка логирования
# ===========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PrefectAgent")

# ===========================
#    Конфигурация Kafka
# ===========================
INPUT_TOPIC = "input_tasks"
OUTPUT_TOPIC = "processed_results"
KAFKA_BOOTSTRAP_SERVERS = "localhost:29092"

# ===========================
#     Инициализация LLM и инструментов
# ===========================
llm = CustomChatModel(api_url=GIGACHAT_API_URL)
ocr_tool = OCRToolAsync()
speech_tool = Speech2TextToolAsync()
trans_tool = TranslateToolAsync()

# ===========================
#   Описание доступных инструментов
# ===========================
def agent_tools_description() -> str:
    return "\n".join([
        f"{t.name}: {t.description}"
        for t in (ocr_tool, speech_tool, trans_tool)
    ])


# ===========================
#         Prefect-tasks
# ===========================

@task(name="PlannerTask")
async def planner_task(user_input: str, chat_history: str) -> str:
    """
    Асинхронный таск, который формирует запрос LLM и возвращает 'план' (строку с указанием,
    какой инструмент нужно вызвать).
    """
    logger = get_run_logger()
    prompt = f"""Ты — ассистент, у тебя есть доступ к следующим инструментам:
{agent_tools_description()}

Если нужно несколько шагов, сначала вызывай нужный tool, дождись результата, потом следующий.
{chat_history}
User: {user_input}
Assistant:"""
    response = await llm.ainvoke([{"role": "system", "content": prompt}])
    plan = response.content
    logger.info(f"LLM вернул план:\n{plan}")
    return plan


@task(name="OCRToolTask")
async def ocr_tool_task(file_obj: str) -> Dict[str, Any]:
    """
    Асинхронный таск для OCRToolAsync. В кач-ве входа — путь (или base64) к PDF/изображению.
    Возвращает словарь {"output": str} или {"error": str}.
    """
    logger = get_run_logger()
    try:
        logger.info(f"Запускаем OCRToolAsync на объекте {file_obj}")
        result_text = await ocr_tool.arun(file_path=file_obj, file_type="pdf")
        return {"output": result_text}
    except Exception as e:
        logger.error(f"OCRToolAsync упал: {e}")
        return {"error": str(e)}


@task(name="Speech2TextTask")
async def speech2text_tool_task(audio_obj: str) -> Dict[str, Any]:
    """
    Асинхронный таск для Speech2TextToolAsync. 
    Вход: путь (или base64) к WAV-аудио. 
    Выход: {"output": str} или {"error": str}.
    """
    logger = get_run_logger()
    try:
        logger.info(f"Запускаем Speech2TextToolAsync на объекте {audio_obj}")
        result_text = await speech_tool.arun(audio_path=audio_obj, audio_format="wav")
        return {"output": result_text}
    except Exception as e:
        logger.error(f"Speech2TextToolAsync упал: {e}")
        return {"error": str(e)}


@task(name="TranslateTask")
async def translate_tool_task(text_to_translate: str) -> Dict[str, Any]:
    """
    Асинхронный таск для TranslateToolAsync. 
    Вход: строка с текстом. 
    Выход: {"translated_text": str} или {"error": str}.
    """
    logger = get_run_logger()
    try:
        logger.info(f"Запускаем TranslateToolAsync с текстом {text_to_translate}")
        result = await trans_tool.arun(text=text_to_translate, target_lang="ru")
        return {"translated_text": result.get("translated_text", "")}
    except Exception as e:
        logger.error(f"TranslateToolAsync упал: {e}")
        return {"error": str(e)}


@task(name="FinalAnswerTask")
def final_answer_task(
    plan: str,
    tool_response: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Сборщик финального ответа. 
    Берёт план, ответ инструмента и формирует итоговую структуру.
    """
    logger = get_run_logger()
    output = {
        "plan": plan,
        "tool_response": tool_response,
        "answer": None
    }
    if tool_response is None:
        output["answer"] = "Ошибка: не было запущено ни одного инструмента."
    elif tool_response.get("error"):
        output["answer"] = f"Ошибка при выполнении инструмента: {tool_response['error']}"
    else:
        # Например, просто оборачиваем ответ инструмента в Assistant: ...
        tool_out = tool_response.get("output", "")
        output["answer"] = f"Assistant: {tool_out}"
    logger.info(f"Формируем итоговый ответ: {output}")
    return output


# ===========================
#        Prefect-flow
# ===========================

@flow(name="TaskOrchestrationFlow")
async def orchestration_flow(
    user_input: str,
    chat_history: str,
    task_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Основной поток: 
    1) получаем план от LLM 
    2) в зависимости от содержимого плана запускаем нужный инструмент
    3) объединяем всё в финальный результат
    """
    logger = get_run_logger()
    # 1) Получаем план
    plan = await planner_task(user_input, chat_history)

    # 2) Определяем, какой инструмент вызывать
    plan_lower = plan.lower()
    tool_response: Optional[Dict[str, Any]] = None

    if "ocr_tool" in plan_lower:
        # предполагаем, что task_metadata["object"] хранит путь/строку для OCR
        obj = task_metadata.get("object")
        tool_response = await ocr_tool_task(obj)

    elif "speech2text_tool" in plan_lower:
        obj = task_metadata.get("object")
        tool_response = await speech2text_tool_task(obj)

    elif "translate_tool" in plan_lower:
        obj = task_metadata.get("object")
        # тут передаём текст для перевода
        tool_response = await translate_tool_task(obj)

    else:
        # Ни один инструмент не подошёл → оставляем tool_response = None
        logger.info("План не содержит ни одного известного инструмента, сразу финальный ответ.")

    # 3) Финальная агрегация
    final = final_answer_task(user_input, plan, tool_response)
    return final


# ===========================
#       Утилита для Kafka-отправки
# ===========================

async def send_to_output_topic(result: Dict[str, Any], operation_type: str):
    """
    Отправляет обогащённый результат в OUTPUT_TOPIC через AsyncKafkaProducerSingleton.
    """
    producer = await AsyncKafkaProducerSingleton.get_producer()
    enriched = {
        "operation": operation_type,
        "result": result,
        "status": "success" if not result.get("tool_response", {}).get("error") else "error"
    }
    await producer.send(OUTPUT_TOPIC, json.dumps(enriched, ensure_ascii=False))
    get_run_logger().info(f"Отправлен результат в {OUTPUT_TOPIC}: {enriched}")


# ===========================
#      Основная точка входа
# ===========================

async def main():
    logger.info("Prefect-Agent запущен. Ожидание сообщений из Kafka...")

    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8"))
    )
    await consumer.start()

    try:
        async for msg in consumer:
            logger.info(f"Получено сообщение из {INPUT_TOPIC}: {msg.value}")
            try:
                # Ожидаем формат:
                # {
                #   "task": "<строка с тем, что попросил пользователь>",
                #   "object": "<путь/строка для инструмента (PDF, WAV, текст)>"
                # }
                payload = msg.value
                user_task = payload.get("task")
                obj = payload.get("object")

                if not user_task or obj is None:
                    logger.error("Невалидный формат: нет 'task' или 'object'")
                    continue

                # Запускаем поток Prefect, чтобы получить итоговый ответ
                result: Dict[str, Any] = await orchestration_flow(
                    user_input=user_task,
                    chat_history="",
                    task_metadata={"object": obj}
                )

                # Определяем тип операции по плану
                plan_lower = result.get("plan", "").lower()
                operation = "unknown"
                if "ocr_tool" in plan_lower:
                    operation = "ocr"
                elif "speech2text_tool" in plan_lower:
                    operation = "speech_recognition"
                elif "translate_tool" in plan_lower:
                    operation = "translation"
                else:
                    operation = "chat_only"

                # Отправляем результат в Kafka
                await send_to_output_topic(result, operation)

            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
                await send_to_output_topic({"error": str(e)}, "unknown")

    finally:
        await consumer.stop()
        await AsyncKafkaProducerSingleton.close_producer()
        logger.info("Prefect-Agent остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
