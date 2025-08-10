from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from chat_app.core_app.api_clients.auth_client import validate_token

oauth2_scheme = HTTPBearer()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
    """
    Получает текущего пользователя на основе JWT токена.
    Возвращает словарь с данными пользователя.
    """
    token_str = token.credentials

    user_data = validate_token(token_str)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_data