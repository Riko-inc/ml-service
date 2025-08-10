import os
import requests
import logging
from typing import List, Dict, Optional
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
SPACE_SERVICE_HOST = os.getenv("SPACE_SERVICE_HOST", "http://82.202.138.236:31064/space")

def get_user_spaces(token: str) -> Optional[List[Dict]]:
    """
    Получает список пространств пользователя из space-service
    """
    url = f"{SPACE_SERVICE_HOST}/api/v1/spaces"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "*/*"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"Space service error: {response.status_code} - {response.text}")
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Space service request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Space service unavailable"
        )



def get_user_space_by_prefix(token: HTTPAuthorizationCredentials, workspace_prefix: str) -> Optional[Dict]:
    """
    Получает информацию о пространстве по его префиксу
    """

    token = token.credentials

    logger.error(f"Getting user spaces by prefix {workspace_prefix}")
    url = f"{SPACE_SERVICE_HOST}/api/v1/spaces/{workspace_prefix}/prefix"

    logger.error(f"url: {url}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "*/*"
    }

    logger.error(f"header token: {token}")
    logger.error(f"header token type: {type(token)}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"Space service error: {response.status_code} - {response.text}")
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Space service request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Space service unavailable"
        )