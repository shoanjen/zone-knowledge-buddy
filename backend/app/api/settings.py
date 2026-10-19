"""M9 供应商管理（规格 §12.2，B2 批次交付部分）。"""


from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import (
    NotFoundError,
    ProviderActiveError,
    ProviderConfigError,
)
from app.core.security import encrypt_secret
from app.llm.gateway import LLMGateway
from app.llm.providers import ProviderSnapshot
from app.models.llm import LLMProvider
from app.models.settings import Setting
from app.models.user import User
from app.schemas.settings import ProviderIn, ProviderOut, ProviderUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out(row: LLMProvider) -> ProviderOut:
    return ProviderOut(
        id=row.id,
        type=row.type,
        name=row.name,
        base_url=row.base_url,
        model=row.model,
        is_active=row.is_active,
        has_api_key=bool(row.api_key_enc),
    )


def _get_provider(db: Session, pid: int) -> LLMProvider:
    row = db.get(LLMProvider, pid)
    if row is None:
        raise NotFoundError(f"供应商 {pid} 不存在")
    return row


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProviderOut]:
    return [_to_out(r) for r in db.scalars(select(LLMProvider)).all()]


@router.post("/providers", response_model=ProviderOut, status_code=201)
def create_provider(
    body: ProviderIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderOut:
    if body.type == "cloud" and not (body.api_key or "").strip():
        raise ProviderConfigError("云端供应商必须提供 api_key")
    row = LLMProvider(
        type=body.type,
        name=body.name,
        base_url=body.base_url.rstrip("/"),
        model=body.model,
        api_key_enc=encrypt_secret(body.api_key.strip()) if body.api_key else None,
    )
    db.add(row)
    db.commit()
    return _to_out(row)


@router.put("/providers/{pid}", response_model=ProviderOut)
def update_provider(
    pid: int,
    body: ProviderUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderOut:
    row = _get_provider(db, pid)
    if body.name is not None:
        row.name = body.name
    if body.base_url is not None:
        row.base_url = body.base_url.rstrip("/")
    if body.model is not None:
        row.model = body.model
    if body.api_key:
        row.api_key_enc = encrypt_secret(body.api_key.strip())
    if row.type == "cloud" and not row.api_key_enc:
        raise ProviderConfigError("云端供应商必须配置 api_key")
    db.commit()
    return _to_out(row)


@router.delete("/providers/{pid}", status_code=204)
def delete_provider(
    pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    row = _get_provider(db, pid)
    if row.is_active:
        raise ProviderActiveError("不能删除当前生效中的供应商", detail={"provider_id": pid})
    db.delete(row)
    db.commit()


@router.post("/providers/{pid}/test")
async def test_provider(
    pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    row = _get_provider(db, pid)
    try:
        gw = LLMGateway(ProviderSnapshot.from_row(row))
    except Exception as e:  # noqa: BLE001 — 配置错误也按测试结果返回
        return {"ok": False, "latency_ms": 0, "models": [], "error": str(e)[:200]}
    return await gw.healthcheck()


@router.post("/providers/{pid}/activate")
def activate_provider(
    pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    row = _get_provider(db, pid)
    if row.type == "cloud" and not row.api_key_enc:
        raise ProviderConfigError("云端供应商未配置 api_key，无法启用")
    for r in db.scalars(select(LLMProvider)).all():
        r.is_active = r.id == pid
    setting = db.get(Setting, "active_provider_id")
    if setting is None:
        setting = Setting(key="active_provider_id", value_json=str(pid))
        db.add(setting)
    else:
        setting.value_json = str(pid)
    db.commit()
    return {"ok": True, "active_provider_id": pid}


def get_active_provider(db: Session) -> LLMProvider:
    setting = db.get(Setting, "active_provider_id")
    if setting is None:
        raise ProviderConfigError("尚未启用任何模型供应商：请到设置页 activate")
    row = db.get(LLMProvider, int(setting.value_json))
    if row is None:
        raise ProviderConfigError("生效供应商已不存在，请重新 activate")
    return row
