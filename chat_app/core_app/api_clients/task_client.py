import os
import requests
import logging
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
TASK_SERVICE_HOST = os.getenv("TASK_SERVICE_HOST", "http://82.202.138.236:31064/task")

def get_tasks_in_space(token: HTTPAuthorizationCredentials, space_id: int, page: int = 0, size: int = 50) -> str | None:
    """
    Получает список задач в указанном пространстве
    """

    token = token.credentials

    url = f"{TASK_SERVICE_HOST}/api/v1/task"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    params = {
            "spaceId": space_id,
            "page": page,
            "size": size
        }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Task service error: {response.status_code} - {response.text}")
            return None
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Task service request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task service unavailable"
        )