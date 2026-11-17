"""B10 单元：脚本清洗 / 素材包截断 / 时长估算。"""


from app.podcast.runner import PER_DOC_CHARS, TOTAL_CHARS, build_content_pack, clean_turns
from app.podcast.tts import MP3_BYTES_PER_SECOND, estimate_duration_s


def test_estimate_duration():
    assert estimate_duration_s(MP3_BYTES_PER_SECOND) == 1.0
    assert estimate_duration_s(MP3_BYTES_PER_SECOND * 90) == 90.0


def test_clean_turns_normalizes_and_drops():
    raw = [
        {"speaker": "a", "text": "小写说话人规范化"},   # → A
        {"speaker": "C", "text": "未知说话人归 A"},      # → A
        {"speaker": "B", "text": "   "},                # 空文本 → 丢弃
        {"speaker": "B", "text": None},                 # None → 丢弃
        {"text": "缺说话人默认 A"},                      # → A
    ]
    turns = clean_turns(raw)
    assert [t["speaker"] for t in turns] == ["A", "A", "A"]
    assert all(len(t["text"]) >= 2 for t in turns)


def test_clean_turns_caps_at_30():
    raw = [{"speaker": "A" if i % 2 else "B", "text": f"第{i}轮"} for i in range(50)]
    assert len(clean_turns(raw)) == 30


def test_build_content_pack_truncates(db_session):
    from app.models.documents import Block, Document

    long_text = "字" * 500
    doc = Document(id="d_PACK", source_type="md", origin="a.md", title="长文",
                   status="ready", block_count=2, chunk_count=1)
    db_session.add(doc)
    db_session.add(Block(doc_id="d_PACK", seq=1, block_id="b1", type="paragraph", text=long_text))
    db_session.add(Block(doc_id="d_PACK", seq=2, block_id="b2", type="paragraph", text=long_text))
    db_session.commit()

    pack = build_content_pack(db_session, ["d_PACK"])
    assert "# 长文" in pack
    assert len(pack) <= TOTAL_CHARS + len("# 长文") + 2
    assert pack.count("字") <= PER_DOC_CHARS + 1  # 单篇截断生效（含标题行少量字符）
