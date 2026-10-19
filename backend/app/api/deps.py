"""通用依赖：DB 会话、当前用户（规格 §2.1 deps.py）。"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AuthError
from app.core.security import decode_token
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("未登录")
    payload = decode_token(auth.removeprefix("Bearer ").strip())
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise AuthError("用户不存在")
    request.state.user_id = user.id
    return user
