"""B3+B4 集成验收：上传→解析→分块→检索全链（embed/存储 mock，规格 §15.1）。

后台线程池与真实 SessionLocal 被 monkeypatch 到测试内存库，保证确定性。
"""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def wired(client, db_engine, monkeypatch, tmp_path):
    """把后台管线接到测试内存库 + 假 embedding + tmp Chroma。"""
    from sqlalchemy.orm import sessionmaker

    import app.api.documents as docs_api
    import app.parsing.dispatcher as dispatcher
    import app.rag.pipeline as pipeline
    import app.rag.service as service
    import app.rag.store as store

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(dispatcher, "SessionLocal", TestSession)
    monkeypatch.setattr(pipeline, "SessionLocal", TestSession)
    monkeypatch.setattr(service, "SessionLocal", TestSession)
    monkeypatch.setattr(
        docs_api, "submit", lambda fn, *a, **k: fn(*a, **k)
    )  # BackgroundTasks 内同步执行

    async def fake_embed(texts):
        def vec(t: str) -> list[float]:
            # 简单确定性向量：字符计数桶 + 首字符权重
            v = [0.0] * 8
            for ch in t:
                v[ord(ch) % 8] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            return [x / norm for x in v]

        return [vec(t) for t in texts]

    import app.llm.gateway as gw_mod

    # pipeline/service 内部为延迟 import，patch 源头即可
    monkeypatch.setattr(gw_mod, "embed_texts", fake_embed)

    # tmp Chroma（隔离持久目录）
    import chromadb

    client_chroma = chromadb.EphemeralClient()
    col = client_chroma.get_or_create_collection("kb_chunks", metadata={"hnsw:space": "cosine"})
    monkeypatch.setattr(store, "_client", client_chroma)
    monkeypatch.setattr(store, "_col", lambda: col)
    return client


def _md_file(tmp_path: Path) -> Path:
    p = tmp_path / "kb.md"
    p.write_text(
        "# 知识库架构\n\n系统采用分层设计，解析层负责多格式归一。\n\n"
        "## 检索方案\n\n检索使用向量召回与引用溯源结合的方式，保证结论可核验。\n\n"
        "| 组件 | 用途 |\n| --- | --- |\n| Chroma | 向量存储 |\n| SQLite | 元数据 |\n",
        encoding="utf-8",
    )
    return p


def test_upload_parse_chunk_search(wired, auth_headers, tmp_path):
    p = _md_file(tmp_path)
    with p.open("rb") as f:
        resp = wired.post(
            "/api/documents/upload",
            files={"files": ("kb.md", f, "text/markdown")},
            headers=auth_headers,
        )
    assert resp.status_code == 202, resp.text
    doc_id = resp.json()["items"][0]["doc_id"]

    # 解析 + 分块完成
    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "ready", detail.get("error")
    assert detail["block_count"] >= 4
    assert detail["chunk_count"] >= 2
    types = {b["type"] for b in detail["blocks"]}
    assert {"heading", "paragraph", "table"} <= types

    # 检索：表格块独立、doc_ids 过滤
    resp = wired.get("/api/search", params={"q": "向量存储"}, headers=auth_headers)
    assert resp.status_code == 200
    hits = resp.json()["results"]
    assert hits and hits[0]["doc_id"] == doc_id
    assert hits[0]["title"] == "知识库架构"

    resp = wired.get(
        "/api/search",
        params={"q": "向量存储", "doc_ids": "d_NONEXIST"},
        headers=auth_headers,
    )
    assert resp.json()["results"] == []


def test_upload_rejects_bad_format(wired, auth_headers):
    resp = wired.post(
        "/api/documents/upload",
        files={"files": ("a.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "UPLOAD_FORMAT"


def test_upload_rejects_fake_pdf(wired, auth_headers):
    resp = wired.post(
        "/api/documents/upload",
        files={"files": ("a.pdf", b"not a pdf", "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 415


def test_batch_upload_keeps_valid_files_and_reports_errors(wired, auth_headers, tmp_path):
    """回归：批量中单个非法文件不得让已入库文档永久停在 pending。"""
    ok = _md_file(tmp_path)
    with ok.open("rb") as f1:
        resp = wired.post(
            "/api/documents/upload",
            files=[
                ("files", ("ok.md", f1, "text/markdown")),
                ("files", ("bad.txt", b"hello", "text/plain")),
            ],
            headers=auth_headers,
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["errors"] and body["errors"][0]["code"] == "UPLOAD_FORMAT"

    doc_id = body["items"][0]["doc_id"]
    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "ready", detail
    docs = wired.get("/api/documents?page_size=100", headers=auth_headers).json()["items"]
    assert not [d for d in docs if d["status"] == "pending"]


def test_page_size_is_validated(wired, auth_headers):
    resp = wired.get("/api/documents?page_size=-1", headers=auth_headers)
    assert resp.status_code == 422, resp.text


def test_url_import_and_fail_path(wired, auth_headers, monkeypatch):
    import app.parsing.web as web_mod
    from app.core.errors import ParseError

    monkeypatch.setattr(web_mod, "_fetch_html", lambda url: "<html>x</html>")

    def boom(url):
        raise ParseError("网页正文抽取失败（web_empty）：正文过短或需要登录")

    monkeypatch.setattr(web_mod, "_html_to_parsed", lambda h, u: None)
    monkeypatch.setattr(web_mod, "_render_html", boom)
    resp = wired.post("/api/documents/url", json={"url": "https://x.com/a"}, headers=auth_headers)
    assert resp.status_code == 202
    doc_id = resp.json()["doc_id"]
    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "failed"
    assert "web_empty" in detail["error"]

    # retry：恢复解析函数后重试成功
    def ok_parsed(html, url):
        from app.parsing.ir import IRBlock, IRMeta, ParsedDoc

        return ParsedDoc(
            meta=IRMeta(title="T"),
            blocks=[IRBlock(type="paragraph", text="正文内容足够长。" * 20)],
        )

    monkeypatch.setattr(web_mod, "_html_to_parsed", ok_parsed)
    resp = wired.post(f"/api/documents/{doc_id}/retry", headers=auth_headers)
    assert resp.status_code == 202
    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "ready"
    assert detail["chunk_count"] >= 1


def test_retry_after_embed_failure_recovers(wired, auth_headers, tmp_path, monkeypatch):
    """回归：首跑解析成功、embedding 失败置 failed 后，重试不得因块重复卡死在 parsing。

    线上事故：重试重插 b1..bN 撞 UNIQUE(doc_id, block_id)，兜底 commit 再抛
    PendingRollbackError 逃逸，文档永远停在 parsing（不可重试/不可删）。
    """
    import app.llm.gateway as gw_mod
    from app.core.errors import GatewayError

    def broken_embed(texts):
        raise GatewayError("embedding 端点不可达：All connection attempts failed")

    monkeypatch.setattr(gw_mod, "embed_texts", broken_embed)

    p = _md_file(tmp_path)
    with p.open("rb") as f:
        resp = wired.post(
            "/api/documents/upload",
            files={"files": ("kb.md", f, "text/markdown")},
            headers=auth_headers,
        )
    assert resp.status_code == 202, resp.text
    doc_id = resp.json()["items"][0]["doc_id"]

    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "failed", detail
    assert "embedding" in detail["error"]
    first_block_count = detail["block_count"]
    assert first_block_count >= 4

    async def ok_embed(texts):
        return [[0.1] * 8 for _ in texts]

    monkeypatch.setattr(gw_mod, "embed_texts", ok_embed)
    resp = wired.post(f"/api/documents/{doc_id}/retry", headers=auth_headers)
    assert resp.status_code == 202, resp.text
    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
    assert detail["status"] == "ready", detail
    assert detail["block_count"] == first_block_count  # 块清旧重插，不重复累加
    assert detail["chunk_count"] >= 1


def test_startup_sweep_marks_orphans_failed(db_engine, monkeypatch):
    """启动自愈：残留 pending/parsing 的文档与进行中任务（进程中断遗留）统一置 failed；paused 保留。"""
    from sqlalchemy.orm import sessionmaker

    import app.core.db as core_db
    import app.main as main_mod
    from app.models import AgentTask, Document

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(core_db, "SessionLocal", TestSession)

    with TestSession() as s:
        s.add(Document(id="d_stuck", source_type="md", origin="x.md", status="parsing"))
        s.add(Document(id="d_queued", source_type="md", origin="y.md", status="pending"))
        s.add(Document(id="d_ok", source_type="md", origin="z.md", status="ready"))
        s.add(AgentTask(id="t_run", type="note.generate", status="running"))
        s.add(AgentTask(id="t_plan", type="note.generate", status="planning"))
        s.add(AgentTask(id="t_paused", type="note.generate", status="paused"))
        s.add(AgentTask(id="t_done", type="note.generate", status="done"))
        s.commit()

    main_mod._recover_orphans()

    with TestSession() as s:
        assert s.get(Document, "d_stuck").status == "failed"
        assert s.get(Document, "d_queued").status == "failed"
        assert s.get(Document, "d_ok").status == "ready"  # ready/failed 不受影响
        assert s.get(AgentTask, "t_run").status == "failed"
        assert s.get(AgentTask, "t_plan").status == "failed"
        # paused 草稿已生成，确认/拒绝不依赖 LLM，重启后保留
        assert s.get(AgentTask, "t_paused").status == "paused"
        assert s.get(AgentTask, "t_done").status == "done"


def test_delete_cascade_and_broken_citation(wired, auth_headers, tmp_path, db_session):
    from app.models.notes import Note, NoteCitation

    p = _md_file(tmp_path)
    with p.open("rb") as f:
        resp = wired.post(
            "/api/documents/upload",
            files={"files": ("kb.md", f, "text/markdown")},
            headers=auth_headers,
        )
    doc_id = resp.json()["items"][0]["doc_id"]

    note = Note(title="t", content_md="x", source_doc_ids_json=json.dumps([doc_id]))
    db_session.add(note)
    db_session.flush()
    db_session.add(NoteCitation(note_id=note.id, doc_id=doc_id, block_id="b1"))
    db_session.commit()
    note_id = note.id

    resp = wired.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 204

    detail = wired.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert detail.status_code == 404

    # 笔记保留、引用仍存（历史产出，规格 §6.1）
    db_session.expire_all()
    assert db_session.get(Note, note_id) is not None
    assert db_session.query(NoteCitation).filter_by(note_id=note_id).count() == 1

    # 检索无残留
    resp = wired.get("/api/search", params={"q": "向量存储"}, headers=auth_headers)
    assert all(h["doc_id"] != doc_id for h in resp.json()["results"])
