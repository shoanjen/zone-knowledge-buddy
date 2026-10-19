"""搜索 API（规格 §7.3）。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.rag.service import search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_endpoint(
    q: str,
    top_k: int = 5,
    doc_ids: str = "",
    _: User = Depends(get_current_user),
) -> dict:
    ids = [x for x in doc_ids.split(",") if x] or None
    results = await search(q, top_k=min(max(top_k, 1), 20), doc_ids=ids)
    return {"results": results}
