"""M8 报告 API（规格 §11.3）。"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import NotFoundError, ValidationError
from app.models.documents import Document
from app.models.reports import Report
from app.models.tasks import AgentTask
from app.models.user import User
from app.schemas.reports import ReportGenerateIn
from app.tasks.runner import submit

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate", status_code=202)
def generate_report(
    body: ReportGenerateIn,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    docs = db.scalars(select(Document).where(Document.id.in_(body.doc_ids))).all()
    found = {d.id for d in docs}
    not_ready = [d.id for d in docs if d.status != "ready"]
    missing = [i for i in body.doc_ids if i not in found]
    if missing or not_ready:
        raise ValidationError("文档不可用", detail={"missing": missing, "not_ready": not_ready})
    from app.api.settings import get_active_provider

    provider = get_active_provider(db)
    task = AgentTask(
        type="report.generate",
        status="pending",
        provider_id=provider.id,
        input_json=json.dumps(
            {"doc_ids": body.doc_ids, "intent": body.intent, "title": body.title},
            ensure_ascii=False,
        ),
    )
    db.add(task)
    db.commit()
    from app.agent.orchestrator import run_agent_task

    submit(run_agent_task, task.id)
    return {"task_id": task.id}


def _report_out(r: Report) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "intent": r.intent,
        "has_html": bool(r.html_path and Path(r.html_path).exists()),
        "source_doc_ids": json.loads(r.source_doc_ids_json or "[]"),
        "task_id": r.task_id,
        "created_at": r.created_at,
    }


@router.get("")
def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Report).order_by(Report.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_report_out(r) for r in rows]}


@router.get("/{report_id}")
def get_report(
    report_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    r = db.get(Report, report_id)
    if r is None:
        raise NotFoundError(f"报告 {report_id} 不存在")
    out = _report_out(r)
    if r.html_path and Path(r.html_path).exists():
        import re

        html = Path(r.html_path).read_text(encoding="utf-8")
        out["sections"] = re.findall(r"<h2>\s*([^<]+)</h2>", html)
        out["size_bytes"] = len(html.encode())
    return out


@router.get("/{report_id}/html")
def get_report_html(
    report_id: str,
    download: int = 0,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    r = db.get(Report, report_id)
    if r is None:
        raise NotFoundError(f"报告 {report_id} 不存在")
    if not r.html_path or not Path(r.html_path).exists():
        raise NotFoundError("报告 HTML 不存在（可能生成失败）")
    headers = (
        {"Content-Disposition": f'attachment; filename="{report_id}.html"'} if download else None
    )
    return FileResponse(r.html_path, media_type="text/html", headers=headers)
