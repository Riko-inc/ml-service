from pydantic import BaseModel
from typing import Optional
from time import time
import os
import requests
from uuid import uuid4
from chat_app.core_app.tools.setup_logger import setup_logger


logger = setup_logger(__name__.upper())

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
TOKEN_REFRESH_MARGIN = 30

class TokenCache(BaseModel):
    access_token: str
    expires_at: float

class GigaChatClient:
    def __init__(self):
        self.key = os.getenv("GIGACHAT_KEY")
        if not self.key:
            raise ValueError("GIGACHAT_KEY environment variable is not set")
        
        self._token_cache: Optional[TokenCache] = None

    def get_access_token(self) -> str:
        return self._request_new_token()

    def _get_cached_token(self) -> Optional[str]:
        if not self._token_cache:
            return None

        return None

    def _request_new_token(self) -> str:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid4()),
            'Authorization': f'Basic {self.key}'
        }
        try:
            resp = requests.post(
                GIGACHAT_AUTH_URL,
                headers=headers,
                data={'scope': 'GIGACHAT_API_PERS'},
                timeout=10,
                verify=False
            )
            resp.raise_for_status()
            jd = resp.json()
            
            self._token_cache = TokenCache(
                access_token=jd['access_token'],
                expires_at=float(jd['expires_at'])
            )
            
            logger.info("Successfully obtained new access token")
            return self._token_cache.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token request failed: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid token response: {e}")
            raise ValueError("Invalid token response from server")