from typing import List, Tuple, Any
from gradio_client import Client
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from chat_app.core_app.tools.setup_logger import setup_logger
import json


logger = setup_logger(__name__.upper())


class QwenChatModel(BaseChatModel):
    client: Client = Client("Qwen/Qwen2.5-Coder-demo")
    history: List[Tuple[str, str]] = []
    system_prompt: str = "You are a helpful assistant."
    model_size: str = "32B"

    @property
    def _llm_type(self):
        return "Qwen2.5-Coder"
    
    def _process_messages(self, messages: List[Any]) -> Tuple[str, str]:
        query = ""
        system = self.system_prompt
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system = msg.content
                logger.info(f"System prompt updated: {system}")
            elif isinstance(msg, HumanMessage):
                query = msg.content
                logger.info(f"User query: {query}")
            elif isinstance(msg, AIMessage):
                self.history.append((query, msg.content))
                logger.debug(f"History updated: {self.history[-1]}")
                query = ""
        
        return query, system

    def _generate(self, messages: List[Any], **kwargs) -> ChatResult:
        try:
            query, system = self._process_messages(messages)
            
            if not query:
                logger.error("No user query found")
                raise ValueError("No user query in messages")
            
            logger.debug("Request parameters:\n%s", json.dumps({
                "query": query,
                "history": self.history,
                "system": system,
                "model_size": self.model_size,
                "temperature": 0.1
            }, indent=2, ensure_ascii=False))
            
            try:
                response = self.client.predict(
                    query=query,
                    history=self.history,
                    system=system,
                    radio=self.model_size,
                    api_name="/model_chat"
                )
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise
                
            logger.debug("Raw API response: %s", str(response))
            
            if not response or len(response) < 3:
                logger.error("Invalid API response structure")
                raise ValueError("Invalid API response")
                
            # Извлекаем ответ из истории диалога
            bot_response = response[1][-1][1]

            
            logger.info(f"Bot response: {bot_response[:100]}...")
            
            ai_message = AIMessage(content=bot_response)
            self.history.append((query, bot_response))
            
            return ChatResult(generations=[ChatGeneration(message=ai_message)])
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}", exc_info=True)
            raise

    def clear_history(self):
        """Очищает историю диалога"""
        self.history = []
        try:
            self.client.predict(api_name="/clear_session")
            logger.info("History cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear history: {str(e)}")
            raise

if __name__ == "__main__":
    def run_tests():
        logger.info("Starting Qwen API tests")
        
        model = QwenChatModel()
        
        # Тест 1: Простой запрос
        try:
            logger.info("Test 1: Basic query")
            result = model.invoke([
                SystemMessage(content="You are a Python expert"), 
                HumanMessage(content="Write 'Hello World' in Python")
            ])
            print("\nTest 1 Result:", result.content[:200])
        except Exception as e:
            logger.error(f"Test 1 failed: {e}")
        
        # Тест 2: Проверка истории
        try:
            logger.info("Test 2: History check")
            result = model.invoke([
                HumanMessage(content="Explain your solution")
            ])
            print("\nTest 2 Result:", result.content[:200])
        except Exception as e:
            logger.error(f"Test 2 failed: {e}")
        
        # Тест 3: Очистка истории
        try:
            logger.info("Test 3: Clear history")
            model.clear_history()
            print("\nHistory cleared successfully")
        except Exception as e:
            logger.error(f"Test 3 failed: {e}")
        
        logger.info("Testing completed")

    run_tests()
