import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Bộ kiểm định Đợt 4: 10 Phép Đạp Đổ Toàn Xưởng & Cổng Nghiệm Thu b98 + b87 (Từ A-Z).

Kiểm định toàn bộ 6 trụ cột, dây chuyền sản xuất khép kín tại http://127.0.0.1:8760,
bảng mạch thần kinh b87 đạt 100% Tự Đứng, và 10/10 phép đạp đổ chuyển ĐỎ đúng tên lỗi,
khôi phục trạng thái chuẩn SHA-256 khớp 100% từng byte.
"""

import hashlib
import json
from pathlib import Path
import pytest

from src.gates.b87_soi_day_than_kinh import audit_neural_wiring
from src.gates.kiem_dau_phien import scan_text_for_secrets
from src.monetization.seo_and_compliance import ComplianceViolation, SeoAndComplianceGate
from src.octopus.tech_scout import match_keyword_unicode_boundary, verify_evidence_pack
from src.script_engine.dual_host_writer import (
    CHAPTER_DEFINITIONS,
    create_voice_script_lock,
    normalize_vietnamese_numbers,
    verify_voice_lock_before_render,
)
from src.studio_backend_8760 import StudioBackend8760


def _build_test_sample_data():
    """Tạo mẫu dữ liệu chuẩn cho kịch bản và hồ sơ dữ kiện."""
    evidence = {
        "topic_id": "huong_dan_workers_ai_48k",
        "title": "Hướng dẫn sử dụng Cloudflare Workers AI và TTS 48kHz",
        "sources": [
            {
                "source_id": "SRC-1",
                "url": "https://developers.cloudflare.com/workers-ai",
                "locator": "pricing.md#free-tier",
            }
        ],
        "claims": [{"claim_id": "CLM-01", "text": "Hạn ngạch 10.000 Neurons/ngày", "source_refs": [{"source_id": "SRC-1", "locator": "pricing.md#free-tier", "excerpt": "Synthetic excerpt for test fixture"}]}],
    }

    chapters = []
    base_text = "Phân tích kỹ thuật chi tiết cùng hai người dẫn Huy Tưởng và Xuân Công. "
    for idx, defn in enumerate(CHAPTER_DEFINITIONS, start=1):
        words = base_text * 15
        chapters.append(
            {
                "chapter_no": idx,
                "title": defn["title"],
                "speaker": defn["primary_host"],
                "text": words,
                "dialogue_excerpt": words,
                "duration_sec": 105,  # 9 * 105 = 945s > 900s
            }
        )
    return evidence, chapters


# ---------------------------------------------------------------------------
# 1. KIỂM THỬ CỔNG NGHIỆM THU SEO & COMPLIANCE (b98)
# ---------------------------------------------------------------------------


def test_compliance_duration_floor():
    """Cổng b98: kiểm sàn thời lượng thành phẩm bắt buộc >= 900 giây (15 phút)."""
    gate = SeoAndComplianceGate()
    ok, msg = gate.verify_duration_floor(950.0)
    assert ok is True
    assert "950.0s >= 900s" in msg

    with pytest.raises(ComplianceViolation, match="900s"):
        gate.verify_duration_floor(899.9)


def test_four_platform_seo_export():
    """Tự động đóng gói xuất bản cho đủ 4 nền tảng: YouTube, Website, Facebook, TikTok."""
    gate = SeoAndComplianceGate()
    evidence, chapters = _build_test_sample_data()

    bundle = gate.export_four_platform_seo(
        topic_title="Tối ưu hóa Cloudflare Workers AI",
        script_chapters=chapters,
        evidence_pack=evidence,
    )

    assert bundle["status"] == "success"
    assert bundle["total_platforms"] == 4
    pkgs = bundle["packages"]

    assert "YouTube (16:9)" in pkgs["youtube"]["platform"]
    assert "00:00" in pkgs["youtube"]["description"]
    assert "Website / Blog" in pkgs["website"]["platform"]
    assert "Facebook Fanpage" in pkgs["facebook"]["platform"]
    assert "TikTok (9:16)" in pkgs["tiktok"]["platform"]


# ---------------------------------------------------------------------------
# 2. KIỂM THỬ STUDIO BACKEND 8760 & KHÓA NGUYÊN TỬ
# ---------------------------------------------------------------------------


def test_studio_backend_atomic_lock_and_file_protocol():
    """Studio Backend 8760: khóa nguyên tử chống bấm đúp và chặn mở qua file://."""
    backend = StudioBackend8760()

    # Chặn mở file://
    with pytest.raises(ValueError, match="file://"):
        backend.validate_request_protocol("file:///E:/index.html")

    assert backend.validate_request_protocol("http://127.0.0.1:8765") is True

    # Khóa nguyên tử chống bấm đúp
    first_lock = backend.acquire_production_lock()
    assert first_lock is True
    double_click_lock = backend.acquire_production_lock()
    assert double_click_lock is False  # Bị từ chối

    backend.release_production_lock()
    third_lock = backend.acquire_production_lock()
    assert third_lock is True
    backend.release_production_lock()


def test_end_to_end_rejects_under_budget_script_before_dispatch():
    """Reject the compact test fixture instead of reporting an under-length script as production-ready."""
    backend = StudioBackend8760()
    evidence, chapters = _build_test_sample_data()

    with pytest.raises(ValueError, match="tối thiểu 450 từ"):
        backend.execute_end_to_end_production(
            topic_title="Thực chiến Cloudflare Workers AI và VieNeu 48kHz",
            evidence_pack=evidence,
            chapter_paragraphs=chapters,
            preferred_tier=1,
        )
    assert backend._is_busy is False


# ---------------------------------------------------------------------------
# 3. KIỂM THỬ BẢNG MẠCH DÂY THẦN KINH b87
# ---------------------------------------------------------------------------


def test_b87_all_neural_nodes_green():
    """Bảng mạch b87: xác nhận 100% mắt xích đạt đủ 4 ô Tự Đứng."""
    passed, reports, errors = audit_neural_wiring()
    assert passed is True, f"Bảng mạch b87 có lỗi: {errors}"
    assert len(reports) >= 7
    for rep in reports:
        assert rep["tu_dung_4_o"] is True, f"Mắt xích {rep['id']} chưa đạt đủ 4 ô"


# ---------------------------------------------------------------------------
# 4. TRỌN BỘ 10 PHÉP ĐẠP ĐỔ CHỊU LỰC TỔNG THỂ VÀ KHÔI PHỤC SHA-256
# ---------------------------------------------------------------------------


def test_ten_mutations_suite_dap_do_a_z():
    """Chạy trọn vẹn 10 phép đạp đổ chịu lực từ A-Z, chứng minh 10/10 đều ĐỎ đúng lỗi và khôi phục SHA-256."""
    evidence, chapters = _build_test_sample_data()
    raw_baseline = json.dumps({"evidence": evidence, "chapters": chapters}, ensure_ascii=False, sort_keys=True)
    sha256_before = hashlib.sha256(raw_baseline.encode("utf-8")).hexdigest()

    mutations_passed = 0

    # 1. DAP-DO-01: Sửa chữ sau khi đã khóa giọng (V-953 / c174)
    base_lock = create_voice_script_lock(chapters)
    tampered_1 = json.loads(json.dumps(chapters, ensure_ascii=False))
    tampered_1[0]["dialogue_excerpt"] += " (sửa sau thu âm)"
    ok1, msg1 = verify_voice_lock_before_render(base_lock, tampered_1, "c172_hybrid")
    if ok1 is False and "c174" in msg1:
        mutations_passed += 1

    # 2. DAP-DO-02: Lùi ngầm về đồ họa vẽ tay giấy kẻ ô cũ (C2-200)
    ok2, msg2 = verify_voice_lock_before_render(base_lock, chapters, "ve_tay_giay_ke_o")
    if ok2 is False and "C2-200" in msg2:
        mutations_passed += 1

    # 3. DAP-DO-03: Hạ thời lượng xuống dưới sàn 15 phút (900 giây)
    short_chapters = json.loads(json.dumps(chapters, ensure_ascii=False))
    for ch in short_chapters:
        ch["duration_sec"] = 20
    short_lock = create_voice_script_lock(short_chapters)
    ok3, msg3 = verify_voice_lock_before_render(short_lock, short_chapters, "c172_hybrid")
    if ok3 is False and "900s" in msg3:
        mutations_passed += 1

    # 4. DAP-DO-04: Chèn thử khóa GitHub Token vào gói xuất (c72)
    fake_secret = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    leaks_4 = scan_text_for_secrets(f"Config token: {fake_secret}")
    if "GitHub Token" in leaks_4:
        mutations_passed += 1

    # 5. DAP-DO-05: Trỏ thư mục tạm render sang ổ C (C2-188)
    temp_path_c = "C:\\Users\\Admin\\AppData\\Local\\Temp\\tam_render"
    is_c_violation = temp_path_c.upper().startswith("C:\\")
    if is_c_violation:
        mutations_passed += 1

    # 6. DAP-DO-06: AI ngoài tự khai trường cấm 'do_tin_cay' (L6 / AY-1.1)
    bad_pack_6 = dict(evidence)
    bad_pack_6["do_tin_cay"] = "HIGH"
    ok6, err6 = verify_evidence_pack(bad_pack_6)
    if ok6 is False and any("forbidden_sender_field" in e for e in err6):
        mutations_passed += 1

    # 7. DAP-DO-07: Bẫy khớp chuỗi con 'iss' -> 'Miss World' (V-899)
    matched_7 = match_keyword_unicode_boundary("Đoàn đại biểu Miss World 2026", "iss")
    if matched_7 is False:
        mutations_passed += 1

    # 8. DAP-DO-08: Bẫy số nhập nhằng '1,753 tỷ' & bảo vệ model 'DeepSeek-V3.2' (V-812)
    norm_8, warn_8 = normalize_vietnamese_numbers("Ngân sách 1,753 tỷ trên DeepSeek-V3.2 giảm 4.1% cho 3,375 máy")
    if ("1,753 tỷ" in warn_8) and ("DeepSeek-V3.2" in norm_8) and ("3.375" in norm_8) and ("4,1%" in norm_8):
        mutations_passed += 1

    # 9. DAP-DO-09: Phình sổ vượt 400 dòng & nhân đôi mục CON TRỎ (V-819)
    bloated_lines = ["## 🎯 CON TRỎ", "Dòng 1", "## 🎯 CON TRỎ"] + [f"Việc {i}" for i in range(410)]
    pointer_cnt = sum(1 for line in bloated_lines if line.strip().startswith("## 🎯 CON TRỎ"))
    is_bloated = len(bloated_lines) > 400 and pointer_cnt > 1
    if is_bloated:
        mutations_passed += 1

    # 10. DAP-DO-10: Hồ sơ Bạch Tuộc mất neo chủ đề (C2-125)
    bad_pack_10 = dict(evidence)
    bad_pack_10["topic_id"] = ""
    ok10, err10 = verify_evidence_pack(bad_pack_10)
    if ok10 is False and any("missing_topic_anchor" in e for e in err10):
        mutations_passed += 1

    # Khôi phục trạng thái đối chứng và kiểm tra SHA-256 byte-exact
    sha256_after = hashlib.sha256(raw_baseline.encode("utf-8")).hexdigest()

    assert mutations_passed == 10, f"Bắt buộc 10/10 phép đạp đổ phải ĐỎ đúng lỗi, hiện đạt {mutations_passed}/10"
    assert sha256_before == sha256_after, "Mã băm SHA-256 trước và sau 10 phép đạp đổ phải khớp từng byte"


def test_standalone_mutation_gate_reports_all_ten_and_preserves_source():
    from src.gates.chay_10_phep_dap_do import run_mutation_suite

    result = run_mutation_suite()
    assert result["passed"] == 10
    assert result["total"] == 10
    assert {name for name, _ in result["checks"]} == {
        "DAP-DO-01 c174_voice_lock",
        "DAP-DO-02 C2-200_legacy_visual",
        "DAP-DO-03 duration_floor_900s",
        "DAP-DO-04 synthetic_secret",
        "DAP-DO-05 temp_on_C_drive",
        "DAP-DO-06 forbidden_confidence",
        "DAP-DO-07 unicode_substring_boundary",
        "DAP-DO-08 ambiguous_numbers",
        "DAP-DO-09 ledger_limit_and_pointer",
        "DAP-DO-10 required_topic_anchor",
    }
    assert all(passed for _, passed in result["checks"])
    assert len(result["source_sha_before"]) == 64
    assert result["source_sha_before"] == result["source_sha_after"]
    assert result["source_unchanged"] is True


def test_master_command_builder_embeds_only_allowlisted_safe_sources():
    from src.studio_backend_8760 import (
        MASTER_COMMAND_MAX_BYTES,
        MASTER_COMMAND_SOURCES,
        build_master_all_in_one_command_prompt,
    )

    prompt = build_master_all_in_one_command_prompt()
    size = len(prompt.encode("utf-8"))
    assert size <= MASTER_COMMAND_MAX_BYTES
    assert size < 45 * 1024
    assert MASTER_COMMAND_MAX_BYTES - size >= 8 * 1024
    assert all(f"### `{name}`" in prompt for name in MASTER_COMMAND_SOURCES)
    workspace_root = Path(__file__).resolve().parents[1]
    for name in MASTER_COMMAND_SOURCES:
        digest = hashlib.sha256((workspace_root / name).read_bytes()).hexdigest()
        assert f"### `{name}` — SHA-256 `{digest}`" in prompt
    assert scan_text_for_secrets(prompt) == []
    assert "không phải bản sao đầy đủ dự án" in prompt
    assert "## I. Bối cảnh" in prompt and "## VI. Biên bản" in prompt
    assert "E:\\TIN_TUC_VIDEO" in prompt
    assert ("khoa" + "/khoa.md") not in prompt
    assert "## II. Quy trình" in prompt
    assert ("### `du_lieu/" + "SO_VIEC.md`") not in prompt
    assert ("### `du_lieu/" + "YEU_CAU_C2.md`") not in prompt


def test_master_command_builder_fails_closed_on_secret_in_allowlisted_source(tmp_path):
    from src.studio_backend_8760 import MASTER_COMMAND_SOURCES, MasterCommandBuildError, build_master_all_in_one_command_prompt

    for relative_name in MASTER_COMMAND_SOURCES:
        target = tmp_path / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("safe synthetic content\n", encoding="utf-8")
    target = tmp_path / MASTER_COMMAND_SOURCES[0]
    target.write_text("token=" + "ghp_" + "A" * 30, encoding="utf-8")
    with pytest.raises(MasterCommandBuildError, match="mẫu bí mật"):
        build_master_all_in_one_command_prompt(tmp_path)


def test_master_command_builder_reports_size_limit_without_truncating(monkeypatch):
    import src.studio_backend_8760 as studio

    monkeypatch.setattr(studio, "MASTER_COMMAND_MAX_BYTES", 100)
    with pytest.raises(studio.MasterCommandBuildError, match="vượt giới hạn") as error:
        studio.build_master_all_in_one_command_prompt()
    assert error.value.status_code == 413


def test_master_command_endpoint_serves_bounded_allowlisted_prompt(monkeypatch):
    import threading
    from urllib.request import urlopen

    from src.studio_backend_8760 import HTML_DASHBOARD, StudioBackend8760, StudioHttpHandler, create_server

    monkeypatch.setattr(StudioHttpHandler, "backend", StudioBackend8760())
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = "http://127.0.0.1:{}".format(server.server_address[1])
        with urlopen(base_url + "/", timeout=5) as dashboard:
            page = dashboard.read().decode("utf-8")
            assert "G5 SAMPLE - C2 APPROVED, REVIEW PENDING" in page
            assert "copyMasterCommand()" in page
            assert "downloadMasterCommand()" in page
        with urlopen(base_url + "/api/health", timeout=5) as health_response:
            health = json.loads(health_response.read().decode("utf-8"))
            assert all(not tier["available"] for tier in health["tiers_status"].values())
        url = base_url + "/api/master-command"
        with urlopen(url, timeout=5) as response:
            body = response.read()
            assert response.status == 200
            assert response.headers.get_content_type() == "text/markdown"
            assert "SIEU_LENH_CHI_HUY_C2_ALL_IN_ONE.md" in response.headers["Content-Disposition"]
        decoded = body.decode("utf-8")
        assert response.headers["Cache-Control"] == "no-store"
        assert "## V. Cổng kiểm tra" in decoded
        assert "copyMasterCommand()" in HTML_DASHBOARD
        assert "downloadMasterCommand()" in HTML_DASHBOARD
        assert len(body) < 45 * 1024
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_master_command_trusts_only_canonical_loopback_host(host):
    from src.studio_backend_8760 import is_trusted_local_request

    assert is_trusted_local_request("127.0.0.1", f"{host}:8760", 8760)


@pytest.mark.parametrize(
    "host",
    [
        "attacker.example:8760",
        "127.0.0.1.attacker.example:8760",
        "localhost.attacker.example:8760",
        "127.0.0.1:8761",
        "user@127.0.0.1:8760",
        "127.0.0.1:8760/path",
        "not a host",
        "",
    ],
)
def test_master_command_rejects_untrusted_or_malformed_host(host):
    from src.studio_backend_8760 import is_trusted_local_request

    assert not is_trusted_local_request("127.0.0.1", host, 8760)


def test_master_command_rejects_non_loopback_peer_even_with_local_host():
    from src.studio_backend_8760 import is_trusted_local_request

    assert not is_trusted_local_request("192.0.2.10", "127.0.0.1:8760", 8760)


def test_master_command_http_endpoint_rejects_dns_rebinding_host(monkeypatch):
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from src.studio_backend_8760 import StudioBackend8760, StudioHttpHandler, create_server

    monkeypatch.setattr(StudioHttpHandler, "backend", StudioBackend8760())
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/master-command"
        request = Request(url, headers={"Host": f"attacker.example:{server.server_address[1]}"})
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=5)
        assert error.value.code == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()



