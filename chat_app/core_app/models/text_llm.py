from typing import Optional, List
import requests
from langchain.schema import AIMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from chat_app.core_app.tools.setup_logger import setup_logger
from chat_app.core_app.api_clients.api_clients import GigaChatClient, GIGACHAT_API_URL

import logging
from time import sleep
from dotenv import load_dotenv
import asyncio
import aiohttp

load_dotenv()

logger = setup_logger(__name__.upper())
semaphore = asyncio.Semaphore(4)
client = GigaChatClient()


class CustomChatModel(BaseChatModel):
    tools: Optional[List[Runnable]] = None
    api_url: str

    @property
    def _identifying_params(self):
        return {"api_url": f"{self.api_url}"}

    @property
    def _llm_type(self):
        return "Universal LLM"

    async def send_post_request_with_retry(self, url, headers, data, model_name, timeout, retries=1, url_name=None):
        async with semaphore:
            logger.info(f"____[LLM] Request to {model_name} (temp={data['temperature']}) {url_name}")
            async with aiohttp.ClientSession() as session:
                for attempt in range(retries):
                    try:
                        logger.debug(f"[LLM] Attempt {attempt + 1}/{retries} to {model_name}")
                        async with session.post(url, headers=headers, json=data, timeout=timeout, verify=False) as response:
                            response.raise_for_status()
                            return await response.json()
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"[LLM] Request to {model_name} timed out ({attempt + 1}/{retries}). Retrying...")
                    except aiohttp.ClientError as e:
                        logger.error(f"[LLM] Client error: {e}")
                        break
                    await asyncio.sleep(3)
        return None

    def _generate(
            self,
            messages,
            stop=None,
            run_manager=None,
            **kwargs
    ) -> ChatResult:
        prompt = messages[-2]
        prompt_user = messages[-1]

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {client.get_access_token()}"
        }

        data = {
            "system_prompt": prompt.content,
            "user_prompts": [prompt_user.content]
        }
        model_name = "GigaChat-2"
        timeout_llm = 200
        temperature = 0.3


        data = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": prompt.content},
                {
                    "role": "user",
                    "content": prompt_user.content
                }
            ],
            "temperature": temperature,
        }

        def send_post_request_with_retry(url, headers, data, timeout, retries=5):
            for attempt in range(retries):
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=timeout, verify=False)
                    response.raise_for_status()
                    return response
                except requests.exceptions.Timeout:
                    logger.error("[LLM] Request timed out. Retrying...")
                except requests.exceptions.RequestException as e:
                    logger.error(f"[LLM] An error occurred: {e}")
                    break
                sleep(3)
            return None

        logger.info(f"[LLM] Request to {model_name} ({temperature})")
        logger.info(f"[LLM] Header: {headers}")
        logger.info(f"[LLM] Data: {data}")
        logger.info(f"[LLM] Model: {model_name}")

        response = send_post_request_with_retry(self.api_url, headers, data, timeout_llm)

        try:
            result = response.json()
            response_message = result['choices'][0]['message']['content']

            message = AIMessage(
                content=response_message,
                additional_kwargs={},
                response_metadata={"time_in_seconds": 3},
            )
        except Exception as e:
            logger.error(e)
            message = AIMessage(
                content="Ошибка при запросе к API",
                additional_kwargs={},
                response_metadata={"error_code": 500},
            )

        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    async def _agenerate(
            self,
            messages,
            stop=None,
            run_manager=None,
            **kwargs
    ) -> ChatResult:
        prompt = messages[-2]
        prompt_user = messages[-1]
        logger.info('ASYNC')
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {client.get_access_token()}"
        }

        model_name = "GigaChat-2"
        timeout_llm = 200
        temperature = 0.3

        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": prompt.content},
                {"role": "user", "content": prompt_user.content}
            ],
            "temperature": temperature,
        }

        result = await self.send_post_request_with_retry(
            self.api_url, headers, data, model_name, timeout_llm, url_name=kwargs['url_name']
        )

        try:
            response_message = result['choices'][0]['message']['content'] if result else "Ошибка при запросе к API"
        except Exception as e:
            logger.error(f"[LLM] Error parsing API response: {e}")
            response_message = "Ошибка при разборе ответа API"

        message = AIMessage(
            content=response_message,
            additional_kwargs={},
            response_metadata={"time_in_seconds": 3},
        )

        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
        
        
if __name__ == "__main__":
    # Настройка логирования для отображения информации в консоли
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Тестирование GigaChatClient
        print("Testing GigaChatClient...")
        client = GigaChatClient()
        token = client.get_access_token()
        print(f"Successfully obtained access token: {token[:15]}...")
        
        # Тестирование GigaChatModelAdvanced
        print("\nTesting GigaChatModelAdvanced...")
        model = CustomChatModel(api_url=GIGACHAT_API_URL)
    
        
        print("Sending test message...")
        user_prompt = "test"
        sys_prompt = "test_system"
        result = model.invoke([sys_prompt, user_prompt], token=token)
        print(f"Response from GigaChat: {result}")
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        raise
