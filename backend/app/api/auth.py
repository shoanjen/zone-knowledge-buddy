"""M1 认证（规格 §4）。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import AuthError
from app.core.security import TOKEN_TTL, create_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginIn, MeOut, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthError("用户名或密码错误")
    return TokenOut(
        token=create_token(user.id, user.username),
        expires_in=int(TOKEN_TTL.total_seconds()),
        username=user.username,
    )


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(username=user.username)
