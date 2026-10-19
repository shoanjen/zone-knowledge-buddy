"""JWT 与 Fernet（规格 §4.2、§14）。

- JWT：HS256，密钥由 KB_SECRET_KEY 派生（与 Fernet 密钥隔离）
- api_key：Fernet 加密落库，仅在网关内存解密
"""

import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import AuthError

_fernet: Fernet | None = None

TOKEN_TTL = timedelta(days=7)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = get_settings().kb_secret_key.encode()
        try:
            _fernet = Fernet(key)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"KB_SECRET_KEY 不是合法的 Fernet 密钥：{e}") from e
    return _fernet


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def encrypt_secret(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise AuthError("密钥解密失败：KB_SECRET_KEY 已变更") from e


def _jwt_secret() -> str:
    return hashlib.sha256(b"jwt:" + get_settings().kb_secret_key.encode()).hexdigest()


def create_token(user_id: int, username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + TOKEN_TTL).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("登录已过期，请重新登录") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("无效的登录凭证") from e
