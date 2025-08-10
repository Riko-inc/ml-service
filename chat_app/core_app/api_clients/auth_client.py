# chat_app/core_app/api_clients/auth_client.py
from dotenv import load_dotenv
import os
import requests
from typing import Optional, Dict
import logging
from fastapi import HTTPException, status

load_dotenv()

logger = logging.getLogger(__name__)


def validate_token(token: str) -> Optional[Dict]:
    """
    Проверяет JWT токен через user-service и возвращает данные пользователя.
    Использует два эндпоинта:
    1. /api/v1/auth/check-token - для проверки валидности токена
    2. /api/v1/auth/details - для получения деталей пользователя
    """
    # Конфигурация из переменных окружения
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://82.202.138.236:31064/auth")

    # 1. Проверка валидности токена
    check_token_url = f"{AUTH_SERVICE_URL}/api/v1/auth/check-token"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "*/*"
    }

    logger.error("trying auth with token: %s \non server %s", token, AUTH_SERVICE_URL)

    try:
        # Проверяем валидность токена
        check_response = requests.get(
            check_token_url,
            headers=headers,
            timeout=5
        )

        if check_response.status_code != 200:
            logger.error(f"Token validation failed: {check_response.status_code}")
            return None

        is_valid = check_response.json()
        if not is_valid:
            logger.warning("Token is invalid")
            return None

        # 2. Получаем детали пользователя
        user_details_url = f"{AUTH_SERVICE_URL}/api/v1/auth/details"
        details_response = requests.get(
            user_details_url,
            headers=headers,
            timeout=5
        )

        if details_response.status_code != 200:
            logger.error(f"Failed to get user details: {details_response.status_code}")
            return None

        user_details = details_response.json()

        # Форматируем данные пользователя для нашего приложения
        return {
            "id": user_details.get("userId"),
            "user_id": user_details.get("userId"),  # дублируем для совместимости
            "email": user_details.get("username"),
            "role": user_details.get("authorities", ["USER"])[0] if user_details.get("authorities") else "USER",
            "is_active": user_details.get("enabled", True)
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Auth service request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )