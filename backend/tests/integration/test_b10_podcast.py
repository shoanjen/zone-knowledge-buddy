"""B10 验收：播客生成（LLM 脚本 → TTS → MP3）与播客 API。"""

from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker


class FakePodcastGateway:
    """脚本化假网关：chat_json 依次返回预设结果。"""

    def __init__(self, script: list[dict]):
        self.script = list(script)
        self.calls: list[str] = []

    async def chat_json(self, messages, schema, *, task_type, params=None):
        self.calls.append(task_type)
        assert self.script, "脚本耗尽：网关收到的调用比预期多"
        return self.script.pop(0)

    async def chat(self, messages, *, task_type, params=None, stream=False):
        self.calls.append(task_type)
        return ""


GOOD_SCRIPT = {
    "title": "聊聊成本与风险",
    "turns": [
        {"speaker": "A", "text": "大家好，欢迎收听本期节目。"},
        {"speaker": "B", "text": "今天我们聊聊这份材料。"},
        {"speaker": "A", "text": "先说结论：成本在下降。"},
        {"speaker": "B", "text": "那风险呢？"},
        {"speaker": "A", "text": "风险有所上升，需要关注。"},
        {"speaker": "B", "text": "好的，感谢收听，我们下期见。"},
    ],
}


@pytest.fixture()
def podcast_env(client, db_engine, auth_headers, monkeypatch, tmp_path):
    """ready 文档 + 生效供应商 + runner 接测试库；TTS 与音频目录打桩。"""

    from app.models.documents import Block, Document
    from app.models.llm import LLMProvider
    from app.models.settings import Setting

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    s = TestSession()
    doc = Document(id="d_POD01", source_type="md", origin="a.md", title="成本风险分析",
                   status="ready", block_count=2, chunk_count=1)
    s.add(doc)
    s.add(Block(doc_id="d_POD01", seq=1, block_id="b1", type="paragraph", text="成本下降的论述。"))
    s.add(Block(doc_id="d_POD01", seq=2, block_id="b2", type="paragraph", text="风险上升的论述。"))
    provider = LLMProvider(type="cloud", name="cloud-glm", base_url="https://x/v1",
                           model="glm-4.6", api_key_enc="enc")
    s.add(provider)
    s.flush()
    s.add(Setting(key="active_provider_id", value_json=str(provider.id)))
    s.commit()
    s.close()

    import app.api.podcasts as podcasts_api
    import app.podcast.runner as runner

    monkeypatch.setattr(runner, "SessionLocal", TestSession)
    monkeypatch.setattr(podcasts_api, "submit", lambda fn, *a, **k: fn(*a, **k))
    monkeypatch.setattr(runner, "get_settings", lambda: SimpleNamespace(podcasts_dir=tmp_path))

    async def fake_synth_dialogue(turns, voice_a, voice_b, should_stop=None):
        payload = b"\xff\xf3" + b"0" * (sum(len(t["text"]) for t in turns) * 120)
        return payload, False

    monkeypatch.setattr(runner, "synth_dialogue", fake_synth_dialogue)
    return {"doc_id": "d_POD01", "tmp_path": tmp_path}


def _patch_gateway(monkeypatch, gw: FakePodcastGateway):
    import app.podcast.runner as runner

    monkeypatch.setattr(runner, "build_gateway", lambda db, pid: gw)


def test_podcast_generate_full_flow(client, auth_headers, podcast_env, monkeypatch):
    gw = FakePodcastGateway([dict(GOOD_SCRIPT)])
    _patch_gateway(monkeypatch, gw)

    resp = client.post(
        "/api/podcasts/generate",
        json={"doc_ids": [podcast_env["doc_id"]], "intent": "把文档聊成一期播客"},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "done", detail
    assert detail["type"] == "podcast.generate"
    # 步骤留痕：脚本 + TTS + 产出
    phases = [s["content"].get("phase") for s in detail["steps"]
              if s["step_type"] == "thought"]
    assert "script" in phases and "tts" in phases

    items = client.get("/api/podcasts", headers=auth_headers).json()["items"]
    assert len(items) == 1
    row = items[0]
    assert row["title"] == "聊聊成本与风险"
    assert row["has_audio"] is True
    assert row["duration_s"] > 0
    assert row["style"] == "轻松闲聊"

    # 详情含脚本轮次
    d = client.get(f"/api/podcasts/{row['id']}", headers=auth_headers).json()
    assert len(d["turns"]) == 6
    assert d["turns"][0]["speaker"] == "A"

    # 音频可取回，mp3 落盘
    audio = client.get(f"/api/podcasts/{row['id']}/audio", headers=auth_headers)
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/mpeg")
    assert audio.content.startswith(b"\xff\xf3")
    assert (podcast_env["tmp_path"] / f"{row['id']}.mp3").exists()

    # 下载响应头
    dl = client.get(f"/api/podcasts/{row['id']}/audio?download=1", headers=auth_headers)
    assert "attachment" in dl.headers.get("content-disposition", "")

    # 删除：行 + 文件一并清理
    resp = client.delete(f"/api/podcasts/{row['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert not (podcast_env["tmp_path"] / f"{row['id']}.mp3").exists()
    assert client.get("/api/podcasts", headers=auth_headers).json()["total"] == 0


def test_podcast_generate_custom_voices_and_style(client, auth_headers, podcast_env, monkeypatch):
    gw = FakePodcastGateway([dict(GOOD_SCRIPT)])
    _patch_gateway(monkeypatch, gw)
    resp = client.post(
        "/api/podcasts/generate",
        json={
            "doc_ids": [podcast_env["doc_id"]],
            "intent": "深度聊聊这份材料",
            "style": "深度讲解",
            "voice_a": "zh-CN-YunjianNeural",
            "voice_b": "zh-CN-XiaoyiNeural",
            "title": "定制标题",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()["status"] == "done"
    row = client.get("/api/podcasts", headers=auth_headers).json()["items"][0]
    assert row["voice_a"] == "zh-CN-YunjianNeural"
    assert row["voice_b"] == "zh-CN-XiaoyiNeural"
    assert row["style"] == "深度讲解"


def test_podcast_generate_validation(client, auth_headers, podcast_env):
    doc = podcast_env["doc_id"]
    base = {"doc_ids": [doc], "intent": "聊聊这份材料"}

    # 同音色 / 未知音色 / 未知风格 / 文档不存在（ValidationError 统一 422）
    same_voice = client.post("/api/podcasts/generate", json={**base, "voice_a": "zh-CN-YunxiNeural",
                              "voice_b": "zh-CN-YunxiNeural"}, headers=auth_headers)
    assert same_voice.status_code == 422
    assert "不同音色" in same_voice.json()["message"]
    bad_voice = client.post("/api/podcasts/generate", json={**base, "voice_a": "alice"},
                            headers=auth_headers)
    assert bad_voice.status_code == 422
    bad_style = client.post("/api/podcasts/generate", json={**base, "style": "说唱"},
                            headers=auth_headers)
    assert bad_style.status_code == 422
    missing_doc = client.post("/api/podcasts/generate", json={**base, "doc_ids": ["d_NOPE"]},
                              headers=auth_headers)
    assert missing_doc.status_code == 422


def test_podcast_task_fails_on_empty_script(client, auth_headers, podcast_env, monkeypatch):
    # 模型输出全部为空文本 → 清洗后轮数不足 → 任务 failed，不产生播客行
    gw = FakePodcastGateway([{"title": "空脚本", "turns": [
        {"speaker": "A", "text": "  "}, {"speaker": "B", "text": ""},
        {"speaker": "A", "text": "…"}, {"speaker": "B", "text": "  "},
        {"speaker": "A", "text": " "}, {"speaker": "B", "text": ""},
    ]}])
    _patch_gateway(monkeypatch, gw)
    resp = client.post(
        "/api/podcasts/generate",
        json={"doc_ids": [podcast_env["doc_id"]], "intent": "聊聊这份材料"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    task_id = resp.json()["task_id"]
    detail = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
    assert detail["status"] == "failed"
    assert "轮数不足" in detail["error"]
    assert client.get("/api/podcasts", headers=auth_headers).json()["total"] == 0


def test_podcast_voices_endpoint(client, auth_headers):
    data = client.get("/api/podcasts/voices", headers=auth_headers).json()
    assert any(v["id"] == "zh-CN-XiaoxiaoNeural" for v in data["voices"])
    assert "轻松闲聊" in data["styles"]


def test_podcast_audio_404(client, auth_headers, podcast_env):
    assert client.get("/api/podcasts/p_NOPE/audio", headers=auth_headers).status_code == 404
    assert client.get("/api/podcasts/p_NOPE", headers=auth_headers).status_code == 404
