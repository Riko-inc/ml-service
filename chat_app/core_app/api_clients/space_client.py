import os
import requests
import logging
from typing import List, Dict, Optional
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)
SPACE_SERVICE_HOST = os.getenv("SPACE_SERVICE_HOST", "http://82.202.138.236:31064/space")

def get_user_spaces(token: str) -> Optional[List[Dict]]:
    """
    Получает список пространств пользователя из space-service
    """
    url = f"{SPACE_SERVICE_HOST}/api/v1/spaces"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
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



def get_user_space_by_prefix(token: str, prefix: str) -> Optional[Dict]:
    """
    Получает информацию о пространстве по его префиксу
    """
    url = f"{SPACE_SERVICE_HOST}/api/v1/spaces/{prefix}/prefix]"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
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