from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.constants import JWT_ALGORITHM

limiter = Limiter(key_func=get_remote_address, default_limits=[])


def rate_limit_key(request) -> str:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return f"user:{int(payload['sub'])}"
        except (JWTError, KeyError, TypeError, ValueError):
            pass
    return get_remote_address(request)
