"""B7 验收：报告生成与自包含 HTML（规格 §11）。"""

import json

import pytest
from sqlalchemy.orm import sessionmaker

from tests.integration.test_b5_agent_notes import FakeGateway  # 复用脚本化假网关


@pytest.fixture()
def report_env(client, db_engine, auth_headers, monkeypatch, tmp_path):
    from app.models.documents import Block, Document
    from app.models.llm import LLMProvider
    from app.models.settings import Setting

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    s = TestSession()
    doc = Document(id="d_RPT01", source_type="excel", origin="data.xlsx", title="数据表",
                   status="ready", block_count=2, chunk_count=1)
    s.add(doc)
    s.add(Block(doc_id="d_RPT01", seq=1, block_id="b1", type="paragraph", text="年度数据说明。"))
    s.add(Block(doc_id="d_RPT01", seq=2, block_id="b2", type="table", caption="销量",
                data_json=json.dumps([["季度", "销量"], ["Q1", "100"], ["Q2", "180"]])))
    provider = LLMProvider(type="cloud", name="cloud-glm", base_url="https://x/v1",
                           model="glm-4.6", api_key_enc="enc")
    s.add(provider)
    s.flush()
    s.add(Setting(key="active_provider_id", value_json=str(provider.id)))
    s.commit()
    s.close()

    import app.agent.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "SessionLocal", TestSession)
    import app.api.reports as reports_api

    monkeypatch.setattr(reports_api, "submit", lambda fn, *a, **k: fn(*a, **k))

    # 报告 HTML 落到 tmp 目录（builder 内部 get_settings 返回轻量替身）
    from types import SimpleNamespace

    import app.report.builder as builder

    monkeypatch.setattr(builder, "get_settings", lambda: SimpleNamespace(reports_dir=tmp_path))

    import app.rag.service as rag_service

    monkeypatch.setattr(
        rag_service, "search_sync",
        lambda q, **kw: [{"chunk_id": "c1", "doc_id": "d_RPT01", "block_ids": ["b1"],
                          "text": "年度数据说明。", "score": 0.9}],
    )
    return {"doc_id": "d_RPT01"}


SCRIPT = [
    {"steps": [{"no": 1, "description": "看数据", "tool_hint": "kb.read"}]},
    {"type": "tool", "thought": "读表格", "tool": "kb.read",
     "args": {"doc_id": "d_RPT01", "block_ids": ["b2"]}},
    {"type": "tool", "thought": "出图", "tool": "chart.spec",
     "args": {"doc_id": "d_RPT01", "block_id": "b2", "chart_type": "bar",
              "title": "季度销量", "x_field": "季度", "y_field": "销量"}},
    {"type": "final", "thought": "完成",
     "content": "# 年度销售报告\n\n## 概述\n\n本年度销量持续增长 [d_RPT01:b1]。\n\n## 分析\n\nQ2 环比显著提升 [d_RPT01:b2]。"},
    {"results": [{"claim_id": 0, "supported": True}, {"claim_id": 1, "supported": True}]},
]


def test_report_generate_selfcontained_html(client, auth_headers, report_env, monkeypatch, tmp_path):
    gw = FakeGateway(list(SCRIPT))
    import app.agent.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "build_gateway", lambda db, pid: gw)

    resp = client.post(
        "/api/reports/generate",
        json={"doc_ids": [report_env["doc_id"]], "intent": "生成销售分析报告"},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "done", detail

    reports = client.get("/api/reports", headers=auth_headers).json()
    assert reports["total"] == 1
    rid = reports["items"][0]["id"]
    assert reports["items"][0]["has_html"] is True

    # 元数据：章节与大小
    meta = client.get(f"/api/reports/{rid}", headers=auth_headers).json()
    assert any("概述" in s for s in meta["sections"]) and any("分析" in s for s in meta["sections"]) and len(meta["sections"]) == 2

    # HTML 内容断言：自包含、目录、引用折叠、图表初始化
    resp = client.get(f"/api/reports/{rid}/html", headers=auth_headers)
    assert resp.status_code == 200
    html = resp.text
    assert "<script>" in html and "echarts" in html.lower()
    assert "季度销量" in html                      # 图表标题
    assert 'data-cite="d_RPT01:b1"' in html      # 引用折叠标记
    assert "IntersectionObserver" in html          # 目录滚动联动
    assert "http://" not in html.replace("http://www.w3.org", "")  # 无外链（自包含）

    # 下载响应头
    resp = client.get(f"/api/reports/{rid}/html?download=1", headers=auth_headers)
    assert "attachment" in resp.headers.get("content-disposition", "")

    # 文件确实落盘在 tmp reports 目录
    assert (tmp_path / f"{rid}.html").exists()
