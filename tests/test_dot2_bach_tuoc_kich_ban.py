import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Bộ kiểm thử Đợt 2: Bạch Tuộc Công Nghệ 4 Vòi & Bộ Máy Kịch Bản 9 Chương (Huy Tưởng - Xuân Công).

Kiểm định Trụ cột 1 & 2, khớp ranh giới từ Unicode V-899, chuẩn hóa c101, giải nghĩa c145,
khóa giọng c174, rào cấm C2-200, và 4 phép đạp đổ chịu lực khôi phục SHA-256 khớp từng byte.
"""
import hashlib
import json
import pytest

from src.octopus.tech_scout import (
    OctopusTechScout,
    match_keyword_unicode_boundary,
    separate_dates,
    verify_evidence_pack,
    verify_local_evidence_sources,
)
from src.script_engine.dual_host_writer import (
    CHAPTER_DEFINITIONS,
    DualHostScriptWriter,
    annotate_first_acronym_mentions,
    create_voice_script_lock,
    normalize_vietnamese_numbers,
    verify_voice_lock_before_render,
)


def _build_sample_nine_chapters():
    """Tạo mẫu kịch bản 9 chương hợp lệ cho kiểm thử."""
    chapters = []
    base_text = (
        "Chào mừng quý khán giả đến với chương trình so sánh AI thực chiến hôm nay. "
        "Chúng ta sẽ cùng phân tích chi tiết từng bước trên máy tính cá nhân. "
        "Mô hình thử nghiệm DeepSeek-V3.2 cho tốc độ 85 token/s với chi phí tối ưu. "
    )
    for idx, defn in enumerate(CHAPTER_DEFINITIONS, start=1):
        words = base_text * 11  # ~500 words per chapter -> total within the 4,050-5,100 budget
        chapters.append(
            {
                "chapter_no": idx,
                "title": defn["title"],
                "speaker": defn["primary_host"],
                "text": words,
                "duration_sec": 110,  # 9 * 110 = 990s > 900s
            }
        )
    return chapters


# ---------------------------------------------------------------------------
# 1. KIỂM THỬ BẠCH TUỘC & KHỚP TỪ UNICODE (V-899 / C2-125 / L6)
# ---------------------------------------------------------------------------


def test_unicode_word_boundary_v899():
    """Bẫy khớp chuỗi con: 'iss' không được nhận nhầm trong 'Miss World' (V-899)."""
    assert match_keyword_unicode_boundary("Cuộc thi Miss World 2026 đang diễn ra", "iss") is False
    assert match_keyword_unicode_boundary("Trạm vũ trụ quốc tế ISS đang hoạt động", "iss") is True
    assert match_keyword_unicode_boundary("Phiên bản v2.0 của MCP vừa ra mắt", "MCP") is True
    assert match_keyword_unicode_boundary("Huy Tưởng và Xuân Công là hai người dẫn", "Huy Tưởng") is True


def test_separate_dates():
    """Phân tách rõ ràng ngày phát hành kỹ thuật gốc và ngày đăng bài."""
    res = separate_dates("2026-10-15", "2026-10-18")
    assert res["is_valid"] is True
    assert res["is_same"] is False
    assert res["release_date"] == "2026-10-15"
    assert res["article_date"] == "2026-10-18"


def test_evidence_pack_rejects_unlinked_claims_and_nested_self_rating():
    pack = {
        "topic_id": "bounded_topic",
        "sources": [{"source_id": "SRC-1", "url": "https://example.com/spec", "locator": "section-1"}],
        "claims": [{"claim_id": "C1", "text": "A synthetic claim", "source_refs": []}],
    }
    valid, errors = verify_evidence_pack(pack)
    assert valid is False
    assert "claim[0]_missing_source_refs" in errors

    pack["claims"][0]["source_refs"] = [{"source_id": "SRC-1", "locator": "section-1", "excerpt": "Excerpt", "confidence": "HIGH"}]
    valid, errors = verify_evidence_pack(pack)
    assert valid is False
    assert any("forbidden_sender_field" in error for error in errors)


def test_evidence_pack_rejects_unrelated_claim_locator():
    pack = {
        "topic_id": "bounded_topic",
        "sources": [{"source_id": "SRC-1", "url": "https://example.com/spec", "locator": "section-1"}],
        "claims": [{"claim_id": "C1", "text": "A synthetic claim", "source_refs": [
            {"source_id": "SRC-1", "locator": "invented-location#L9999", "excerpt": "Invented excerpt"}
        ]}],
    }
    valid, errors = verify_evidence_pack(pack)
    assert valid is False
    assert "claim[0]_source_ref[0]_locator_mismatch" in errors


def test_evidence_pack_rejects_claim_excerpt_mismatching_source_row():
    pack = {
        "topic_id": "bounded_topic",
        "sources": [{
            "source_id": "SRC-1",
            "url": "https://example.com/spec",
            "locator": "section-1",
            "excerpt": "Source-row excerpt",
        }],
        "claims": [{"claim_id": "C1", "text": "A synthetic claim", "source_refs": [
            {"source_id": "SRC-1", "locator": "section-1", "excerpt": "Invented claim excerpt"}
        ]}],
    }
    valid, errors = verify_evidence_pack(pack)
    assert valid is False
    assert "claim[0]_source_ref[0]_excerpt_mismatch" in errors


def _build_local_evidence_pack(tmp_path, excerpt="Source text excerpt"):
    source_file = tmp_path / "source.txt"
    content = f"Before: {excerpt} :After\n".encode("utf-8")
    source_file.write_bytes(content)
    return {
        "topic_id": "local_topic",
        "sources": [{
            "source_id": "LOCAL-1",
            "local_ref": "source.txt",
            "local_sha256": hashlib.sha256(content).hexdigest(),
            "locator": "source.txt#L1",
            "excerpt": excerpt,
        }],
        "claims": [{"claim_id": "C1", "text": "Bounded local claim", "source_refs": [
            {"source_id": "LOCAL-1", "locator": "source.txt#L1", "excerpt": excerpt}
        ]}],
    }


def test_local_evidence_verifier_matches_hash_and_excerpt(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    assert verify_local_evidence_sources(pack, tmp_path) == (True, [])


def test_backend_accepts_verified_local_snapshot(tmp_path, monkeypatch):
    from src.studio_backend_8760 import StudioBackend8760

    backend = StudioBackend8760(tmp_path)
    pack = _build_local_evidence_pack(tmp_path)
    monkeypatch.setattr(backend.router, "dispatch", lambda **kwargs: {"status": "simulated_no_provider_call"})
    result = backend.execute_end_to_end_production(
        "local evidence pilot", pack, _build_sample_nine_chapters()
    )
    assert result["evidence_validation"]["local_sources"] == "passed"
    assert result["evidence_validation"]["local_source_count"] == 1
    assert result["visual_scene"]["layers"][0]["source_citation"]["url"] is None
    assert result["media_created"] is False


def test_backend_uses_supplied_url_for_source_citation(tmp_path, monkeypatch):
    from src.studio_backend_8760 import StudioBackend8760

    backend = StudioBackend8760(tmp_path)
    pack = _build_local_evidence_pack(tmp_path)
    pack["sources"].append({
        "source_id": "REMOTE-1",
        "url": "https://example.test/reference",
        "locator": "reference#L1",
        "excerpt": "Remote reference excerpt",
    })
    pack["claims"][0]["source_refs"].append({
        "source_id": "REMOTE-1",
        "locator": "reference#L1",
        "excerpt": "Remote reference excerpt",
    })
    monkeypatch.setattr(backend.router, "dispatch", lambda **kwargs: {"status": "simulated_no_provider_call"})

    result = backend.execute_end_to_end_production(
        "local evidence pilot with URL", pack, _build_sample_nine_chapters()
    )

    assert result["visual_scene"]["layers"][0]["source_citation"]["url"] == "https://example.test/reference"


def test_backend_rejects_invalid_script_before_dispatch(tmp_path, monkeypatch):
    from src.studio_backend_8760 import StudioBackend8760

    backend = StudioBackend8760(tmp_path)
    pack = _build_local_evidence_pack(tmp_path)
    monkeypatch.setattr(
        backend.router,
        "dispatch",
        lambda **kwargs: pytest.fail("dispatch ran before script validation"),
    )

    with pytest.raises(ValueError, match="đúng 9 chương"):
        backend.execute_end_to_end_production("pilot", pack, [])
    assert backend._is_busy is False


def test_backend_rejects_local_source_changed_after_pin(tmp_path, monkeypatch):
    from src.studio_backend_8760 import StudioBackend8760

    backend = StudioBackend8760(tmp_path)
    pack = _build_local_evidence_pack(tmp_path)
    (tmp_path / "source.txt").write_text("Changed bytes", encoding="utf-8")
    monkeypatch.setattr(backend.router, "dispatch", lambda **kwargs: pytest.fail("dispatch ran before evidence check"))
    with pytest.raises(ValueError, match="local_sha256_mismatch"):
        backend.execute_end_to_end_production("pilot", pack, [])
    assert backend._is_busy is False


def test_local_evidence_verifier_rejects_changed_source_hash(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    (tmp_path / "source.txt").write_text("Changed source text", encoding="utf-8")
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_local_sha256_mismatch" in errors


def test_local_evidence_verifier_rejects_excerpt_absent_from_pinned_source(tmp_path):
    pack = _build_local_evidence_pack(tmp_path, excerpt="Source text excerpt")
    pack["sources"][0]["excerpt"] = "Invented source excerpt"
    pack["claims"][0]["source_refs"][0]["excerpt"] = "Invented source excerpt"
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_local_excerpt_not_found" in errors


def test_local_evidence_verifier_rejects_path_escape(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    pack["sources"][0]["local_ref"] = "..\\outside.txt"
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert any("invalid_local_ref" in error for error in errors)


def test_local_evidence_verifier_rejects_symlink_outside_workspace(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    outside_file = tmp_path.parent / "outside-evidence.txt"
    outside_file.write_text("Source text excerpt", encoding="utf-8")
    link_path = tmp_path / "linked-source.txt"
    try:
        link_path.symlink_to(outside_file)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    pack["sources"][0]["local_ref"] = "linked-source.txt"
    pack["sources"][0]["local_sha256"] = hashlib.sha256(outside_file.read_bytes()).hexdigest()
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_local_source_outside_workspace" in errors


def test_local_evidence_verifier_requires_at_least_one_local_source(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    source = pack["sources"][0]
    source["url"] = "https://example.com/spec"
    del source["local_ref"]
    del source["local_sha256"]
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "no_local_sources_to_verify" in errors


def test_local_evidence_verifier_rejects_oversized_snapshot(tmp_path):
    from src.octopus.tech_scout import LOCAL_EVIDENCE_MAX_BYTES

    pack = _build_local_evidence_pack(tmp_path)
    source_file = tmp_path / "source.txt"
    source_file.write_bytes(b"x" * (LOCAL_EVIDENCE_MAX_BYTES + 1))
    pack["sources"][0]["local_sha256"] = hashlib.sha256(source_file.read_bytes()).hexdigest()
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_local_source_too_large" in errors


def test_local_evidence_verifier_reports_malformed_path_without_leaking_it(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    pack["sources"][0]["local_ref"] = "invalid\x00path"
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_local_source_unavailable" in errors
    assert "invalid" not in " ".join(errors)


def test_local_evidence_verifier_requires_source_digest(tmp_path):
    pack = _build_local_evidence_pack(tmp_path)
    del pack["sources"][0]["local_sha256"]
    valid, errors = verify_local_evidence_sources(pack, tmp_path)
    assert valid is False
    assert "source[0]_invalid_local_sha256" in errors


def test_evidence_pack_rejects_claim_ref_to_unknown_source():
    pack = {
        "topic_id": "bounded_topic",
        "sources": [{"source_id": "SRC-1", "url": "https://example.com/spec", "locator": "section-1"}],
        "claims": [{"claim_id": "C1", "text": "A synthetic claim", "source_refs": [{"source_id": "SRC-2", "locator": "section-2", "excerpt": "Excerpt"}]}],
    }
    valid, errors = verify_evidence_pack(pack)
    assert valid is False
    assert "claim[0]_source_ref[0]_unknown_source" in errors

def test_evidence_pack_verification():
    """Kiểm tra hợp đồng TutorialEvidencePack: cấm tự chấm L6 và thiếu neo C2-125."""
    valid_pack = {
        "topic_id": "huong_dan_mcp_gemini",
        "title": "Hướng dẫn tích hợp MCP với Gemini API",
        "sources": [
            {
                "source_id": "SRC-1",
                "url": "https://github.com/modelcontextprotocol/specification",
                "locator": "README.md#L1-L50",
            }
        ],
        "claims": [{"claim_id": "C1", "text": "MCP là chuẩn mở", "source_refs": [{"source_id": "SRC-1", "locator": "README.md#L1-L50", "excerpt": "MCP is an open protocol"}]}],
    }
    ok, errs = verify_evidence_pack(valid_pack)
    assert ok is True
    assert errs == []

    # Bẫy thiếu neo chủ đề (C2-125)
    bad_pack_no_anchor = dict(valid_pack)
    bad_pack_no_anchor["topic_id"] = ""
    ok_no_anchor, errs_anchor = verify_evidence_pack(bad_pack_no_anchor)
    assert ok_no_anchor is False
    assert any("missing_topic_anchor" in e for e in errs_anchor)

    # Bẫy danh sách nguồn rỗng
    bad_pack_no_src = dict(valid_pack)
    bad_pack_no_src["sources"] = []
    ok_no_src, errs_src = verify_evidence_pack(bad_pack_no_src)
    assert ok_no_src is False
    assert "empty_sources_list" in errs_src

    # Bẫy trường cấm tự chấm độ tin cậy (L6 / AY-1.1)
    for forbidden in ("do_tin_cay", "confidence", "da_kiem"):
        bad_pack_forbidden = dict(valid_pack)
        bad_pack_forbidden[forbidden] = "HIGH"
        ok_forbid, errs_forbid = verify_evidence_pack(bad_pack_forbidden)
        assert ok_forbid is False
        assert any("forbidden_sender_field" in e for e in errs_forbid)


# ---------------------------------------------------------------------------
# 2. KIỂM THỬ BỘ CHUẨN HÓA KỊCH BẢN (c101 + c145 + V-812 + V-825)
# ---------------------------------------------------------------------------


def test_normalize_vietnamese_numbers():
    """Chuẩn hóa số đọc một lượt c101: 3,375 -> 3.375, 4.1% -> 4,1%, giữ DeepSeek-V3.2."""
    text = "Ngân sách 1,753 tỷ trên DeepSeek-V3.2 giảm 4.1% cho 3,375 máy chạy Python 3.12.1"
    norm, warnings = normalize_vietnamese_numbers(text)

    assert "3.375" in norm
    assert "4,1%" in norm
    assert "DeepSeek-V3.2" in norm
    assert "Python 3.12.1" in norm
    assert "1,753 tỷ" in warnings


def test_annotate_first_acronym_mentions():
    """Tự động giải nghĩa thuật ngữ viết tắt c145 ở lần xuất hiện đầu tiên."""
    text = "Giao thức MCP giúp mô hình giao tiếp bên ngoài. Nhờ MCP, hệ thống rất linh hoạt với OAuth và VRAM."
    annotated, count = annotate_first_acronym_mentions(text)

    assert count >= 3
    assert "MCP - tức giao thức kết nối mô hình với công cụ và dữ liệu" in annotated
    assert "OAuth - tức chuẩn ủy quyền truy cập mở" in annotated
    assert "VRAM - tức bộ nhớ đồ họa chuyên dụng trên card màn hình" in annotated
    assert annotated.count("- tức giao thức kết nối") == 1


# ---------------------------------------------------------------------------
# 3. KIỂM THỬ KHÓA GIỌNG SHA-256 (c174) & SÀN THỜI LƯỢNG >= 900S
# ---------------------------------------------------------------------------


def test_script_generation_and_voice_lock():
    """Tạo kịch bản 9 chương đủ thời lượng >=900s và khóa giọng c174."""
    writer = DualHostScriptWriter()
    scout = OctopusTechScout()

    evidence = scout.voi_4_cong_kiem_chung_chong_bia(
        topic_id="so_sanh_gemini_va_ollama",
        title="So sánh Gemini API và Ollama Cục Bộ",
        sources=[{"source_id": "SRC-1", "url": "https://aistudio.google.com", "locator": "pricing.md"}],
        claims=[{"claim_id": "CLM-01", "text": "Gemini hỗ trợ 1M context", "source_refs": [{"source_id": "SRC-1", "locator": "pricing.md", "excerpt": "Synthetic test excerpt"}]}],
    )

    paras = _build_sample_nine_chapters()
    script = writer.build_nine_chapters_script("So sánh Gemini và Ollama", evidence, paras)

    assert script["meets_floor"] is True
    assert script["total_duration_sec"] >= 900
    assert len(script["chapters"]) == 9
    assert script["voice_lock"]["locked"] is True

    ok_render, msg_render = verify_voice_lock_before_render(script["voice_lock"], script["chapters"], "c172_hybrid")
    assert ok_render is True
    assert msg_render == "OK"


def test_script_generation_enforces_chapter_and_total_word_budgets():
    writer = DualHostScriptWriter()
    evidence = {"topic_id": "test_anchor"}
    paragraphs = _build_sample_nine_chapters()
    script = writer.build_nine_chapters_script("Test", evidence, paragraphs)

    assert all(chapter["word_budget"] >= 450 for chapter in script["chapters"])
    assert 4050 <= script["total_words"] <= 5100
    assert script["within_word_budget"] is True

    too_short = _build_sample_nine_chapters()
    too_short[0]["text"] = "too short"
    with pytest.raises(ValueError, match="tối thiểu 450 từ"):
        writer.build_nine_chapters_script("Test", evidence, too_short)

    too_long = _build_sample_nine_chapters()
    for chapter in too_long:
        chapter["text"] *= 2
    with pytest.raises(ValueError, match="tối đa là 5100"):
        writer.build_nine_chapters_script("Test", evidence, too_long)


@pytest.mark.parametrize("duration", [0, -1, 1.5, True])
def test_script_generation_rejects_invalid_requested_duration(duration):
    paragraphs = _build_sample_nine_chapters()
    paragraphs[0]["duration_sec"] = duration

    with pytest.raises(ValueError, match="số nguyên dương"):
        DualHostScriptWriter().build_nine_chapters_script("Test", {"topic_id": "test"}, paragraphs)


def test_c2_200_whiteboard_graphic_forbidden():
    """Cấm lùi ngầm về đồ họa vẽ tay bảng giấy kẻ ô cũ (C2-200 niêm phong)."""
    paras = _build_sample_nine_chapters()
    writer = DualHostScriptWriter()
    evidence = {"topic_id": "test_anchor"}
    script = writer.build_nine_chapters_script("Test", evidence, paras)

    ok, msg = verify_voice_lock_before_render(script["voice_lock"], script["chapters"], visual_mode="ve_tay_giay_ke_o")
    assert ok is False
    assert "C2-200" in msg


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("total_duration_sec", 1),
        ("total_words", 0),
        ("meets_15min_floor", False),
        ("chapters_locked", []),
    ],
)
def test_script_voice_lock_rejects_tampered_record_fields(field, tampered_value):
    chapters = _build_sample_nine_chapters()
    lock_record = create_voice_script_lock(chapters)
    lock_record[field] = tampered_value

    valid, message = verify_voice_lock_before_render(lock_record, chapters)

    assert valid is False
    assert "c174" in message


@pytest.mark.parametrize("duration", [-1, 0, 1.5, True])
def test_script_voice_lock_rejects_nonpositive_or_noninteger_chapter_duration(duration):
    chapters = _build_sample_nine_chapters()
    chapters[0]["duration_sec"] = duration

    with pytest.raises(ValueError, match="số nguyên dương"):
        create_voice_script_lock(chapters)


def test_script_voice_lock_rejects_negative_chapter_even_when_total_exceeds_floor():
    chapters = _build_sample_nine_chapters()
    chapters[0]["duration_sec"] = -1
    chapters[1]["duration_sec"] = 300

    with pytest.raises(ValueError, match="số nguyên dương"):
        create_voice_script_lock(chapters)


def test_script_voice_lock_requires_exactly_nine_sequential_chapters():
    chapters = _build_sample_nine_chapters()
    with pytest.raises(ValueError, match="đúng 9 chương"):
        create_voice_script_lock(chapters[:-1])

    chapters[4]["chapter_no"] = 6
    with pytest.raises(ValueError, match="đúng thứ tự 1–9"):
        create_voice_script_lock(chapters)


def test_script_voice_lock_rejects_nonobject_record():
    valid, message = verify_voice_lock_before_render(None, _build_sample_nine_chapters())

    assert valid is False
    assert "c174" in message


def test_tamper_after_voice_lock_fails():
    """Phát hiện sửa 1 ký tự sau khi đã khóa giọng (V-953 / c174)."""
    paras = _build_sample_nine_chapters()
    writer = DualHostScriptWriter()
    evidence = {"topic_id": "test_anchor"}
    script = writer.build_nine_chapters_script("Test", evidence, paras)

    tampered_chapters = json.loads(json.dumps(script["chapters"], ensure_ascii=False))
    tampered_chapters[0]["dialogue_excerpt"] += " (sửa sau thu âm)"

    ok, msg = verify_voice_lock_before_render(script["voice_lock"], tampered_chapters, visual_mode="c172_hybrid")
    assert ok is False
    assert "c174" in msg


# ---------------------------------------------------------------------------
# 4. BỘ 4 PHÉP ĐẠP ĐỔ ĐỢT 2 (MUTATION SUITE) VÀ KHÔI PHỤC SHA-256 KHỚP 100%
# ---------------------------------------------------------------------------


def test_four_mutations_dap_do_dot2():
    """Chạy trọn vẹn 4 phép đạp đổ Đợt 2: chứng minh đều ĐỎ đúng tên lỗi và khôi phục SHA-256."""
    baseline_paras = _build_sample_nine_chapters()
    raw_json = json.dumps(baseline_paras, ensure_ascii=False, sort_keys=True)
    sha256_before = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    mutations_caught = 0

    # Phép 1: Bẫy khớp chuỗi con 'iss' -> 'Miss World' (V-899)
    res1 = match_keyword_unicode_boundary("Đoàn đại biểu Miss World đến thăm", "iss")
    if res1 is False:
        mutations_caught += 1

    # Phép 2: Bẫy số nhập nhằng '1,753 tỷ' (V-812)
    _, warn2 = normalize_vietnamese_numbers("Ngân sách 1,753 tỷ đồng dự kiến")
    if "1,753 tỷ" in warn2:
        mutations_caught += 1

    # Phép 3: Bẫy mất neo chủ đề trong EvidencePack (C2-125)
    bad_pack3 = {
        "topic_id": "",
        "sources": [{"url": "https://github.com", "locator": "spec.md"}],
    }
    ok3, err3 = verify_evidence_pack(bad_pack3)
    if ok3 is False and any("missing_topic_anchor" in e for e in err3):
        mutations_caught += 1

    # Phép 4: Bẫy hạ thời lượng dưới sàn cứng 900 giây
    short_chapters = json.loads(raw_json)
    for ch in short_chapters:
        ch["duration_sec"] = 30
    short_lock = create_voice_script_lock(short_chapters)
    ok4, msg4 = verify_voice_lock_before_render(short_lock, short_chapters, "c172_hybrid")
    if ok4 is False and "900s" in msg4:
        mutations_caught += 1

    sha256_after = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    assert mutations_caught == 4, f"Cả 4 phép đạp đổ phải ĐỎ đúng lỗi, hiện bắt được {mutations_caught}/4"
    assert sha256_before == sha256_after, "Mã băm SHA-256 trước và sau phải khớp từng byte"



def test_tech_scout_source_descriptor_does_not_claim_fetch():
    from src.octopus.tech_scout import OctopusTechScout

    source = OctopusTechScout().voi_1_kho_ma_va_tai_lieu_goc(
        "https://example.invalid/repo", "v1.0", "README.md"
    )
    assert source["fetched"] is False
    assert source["status"] == "metadata_only"



def _build_valid_export_pack(topic_id="safe_topic"):
    return {
        "topic_id": topic_id,
        "title": "Safe export test",
        "sources": [{"source_id": "SRC-1", "url": "https://example.com/spec", "locator": "spec.md#intro"}],
        "claims": [{"claim_id": "C1", "text": "Synthetic test claim", "source_refs": [{"source_id": "SRC-1", "locator": "spec.md#intro", "excerpt": "Synthetic supporting excerpt"}]}],
    }


def test_evidence_export_sanitizes_topic_id_and_stays_in_temp(tmp_path):
    import json

    scout = OctopusTechScout(tmp_path)
    target = scout.export_evidence_pack(_build_valid_export_pack("../../outside\\escape"))
    temp_root = (tmp_path / "du_lieu" / "tam_me").resolve()
    assert target.is_relative_to(temp_root)
    assert target.name.startswith("evidence_")
    assert json.loads(target.read_text(encoding="utf-8"))["topic_id"] == "../../outside\\escape"
    assert not (tmp_path / "outside").exists()


def test_evidence_export_rejects_paths_outside_temp(tmp_path):
    scout = OctopusTechScout(tmp_path)
    output = tmp_path / "outside.json"
    with pytest.raises(ValueError, match="du_lieu/tam_me"):
        scout.export_evidence_pack(_build_valid_export_pack(), output)
    assert not output.exists()


def test_evidence_export_does_not_overwrite_existing_file(tmp_path):
    scout = OctopusTechScout(tmp_path)
    output = tmp_path / "du_lieu" / "tam_me" / "existing.json"
    output.parent.mkdir(parents=True)
    output.write_text("preserve existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scout.export_evidence_pack(_build_valid_export_pack(), output)
    assert output.read_text(encoding="utf-8") == "preserve existing"


def test_evidence_export_rejects_nested_temp_output(tmp_path):
    scout = OctopusTechScout(tmp_path)
    output = tmp_path / "du_lieu" / "tam_me" / "nested" / "evidence.json"
    with pytest.raises(ValueError, match="tệp trực tiếp"):
        scout.export_evidence_pack(_build_valid_export_pack(), output)
    assert not output.parent.exists()


@pytest.mark.parametrize(
    "url",
    [
        "file:///E:/index.html",
        "https://127.0.0.1:8760/produce",
        "http://example.com:8760/produce",
        "http://127.0.0.1:8761/produce",
        "http://user@127.0.0.1:8760/produce",
        "not a URL",
    ],
)
def test_production_protocol_rejects_nonlocal_or_invalid_urls(url):
    from src.studio_backend_8760 import StudioBackend8760

    with pytest.raises(ValueError, match="loopback"):
        StudioBackend8760().validate_request_protocol(url)


def test_production_protocol_accepts_only_local_dashboard_origin():
    from src.studio_backend_8760 import StudioBackend8760

    backend = StudioBackend8760()
    assert backend.validate_request_protocol("http://127.0.0.1:8765/produce") is True
    assert backend.validate_request_protocol("http://localhost:8765/produce") is True



def test_evidence_export_rejects_workspace_root_on_c_drive_without_writing():
    scout = OctopusTechScout(r"C:\workspace")
    with pytest.raises(ValueError, match="ổ E"):
        scout.export_evidence_pack(_build_valid_export_pack())


def test_evidence_export_rejects_symlink_escape(tmp_path):
    import os

    scout = OctopusTechScout(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("preserve", encoding="utf-8")
    link = tmp_path / "du_lieu" / "tam_me" / "escape.json"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("Symlink creation is not available in this Windows environment")
    with pytest.raises(ValueError, match="du_lieu/tam_me"):
        scout.export_evidence_pack(_build_valid_export_pack(), link)
    assert outside.read_text(encoding="utf-8") == "preserve"



def test_evidence_export_rejects_oversized_or_nonstandard_json(tmp_path):
    scout = OctopusTechScout(tmp_path)
    oversized = _build_valid_export_pack()
    oversized["claims"] = [{"claim_id": "C1", "text": "x" * (1024 * 1024), "source_refs": [{"source_id": "SRC-1", "locator": "spec.md#intro", "excerpt": "Excerpt"}]}]
    with pytest.raises(ValueError, match="1 MiB"):
        scout.export_evidence_pack(oversized)
    nonstandard = _build_valid_export_pack()
    nonstandard["claims"] = [{"claim_id": "C1", "text": "Claim", "score": float("nan"), "source_refs": [{"source_id": "SRC-1", "locator": "spec.md#intro", "excerpt": "Excerpt"}]}]
    with pytest.raises(ValueError):
        scout.export_evidence_pack(nonstandard)
    assert list((tmp_path / "du_lieu" / "tam_me").glob("*.json")) == []
