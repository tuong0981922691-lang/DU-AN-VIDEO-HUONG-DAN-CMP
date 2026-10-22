import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Bộ kiểm thử Đợt 3: Điều Phối GPU Miễn Phí, Giọng 48kHz (-14 LUFS, c174) & Đồ Họa 3 Lớp c172 + HandRig 0.3.

Kiểm định Trụ cột 3 & 4, điều phối 4 tầng c170, chuẩn âm thanh phát sóng, khóa giọng c174,
HandRig 0.3, niêm phong C2-200 và 2 phép đạp đổ chịu lực khôi phục SHA-256 byte-exact.
"""

import hashlib
import json
import pytest

from src.compute_voice.router_and_tts import (
    InferenceRouter,
    VoiceEngine48k,
    create_c174_voice_lock,
    verify_c174_lock,
)
from src.visual_engine.hybrid_c172_renderer import (
    HandRig03,
    HybridC172Renderer,
    KhongDatChuan,
    validate_scene_render_contract,
)


def _build_sample_audio_manifest():
    """Tạo danh sách 9 đoạn âm thanh mẫu đạt tổng thời lượng > 900 giây."""
    segments = []
    base_text = "Thực hiện kiểm thử hệ thống phân phối mô hình AI trên nền tảng máy tính cá nhân. "
    for i in range(1, 10):
        speaker = "Huy Tưởng" if i % 2 == 1 else "Xuân Công"
        text = f"Đoạn {i}: {base_text * 8}"
        segments.append(
            {
                "index": i,
                "speaker": speaker,
                "duration_sec": 105.0,  # 9 * 105 = 945s > 900s
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return segments


# ---------------------------------------------------------------------------
# 1. KIỂM THỬ ĐIỀU PHỐI SUY LUẬN 4 TẦNG $0 (c170)
# ---------------------------------------------------------------------------


def test_inference_router_dispatch():
    """Verify routing preview makes no provider call and claims no verified free quota."""
    router = InferenceRouter()
    assert all(not tier["available"] and tier["status"] == "unverified" for tier in router.tiers_status.values())

    # Tầng 1: Cloudflare Workers AI
    r1 = router.dispatch("Viết tóm tắt kỹ thuật", preferred_tier=1)
    assert r1["tier"] == 1
    assert r1["provider"] is None
    assert "Cloudflare" in r1["candidate_provider"]
    assert r1["connected"] is False
    assert r1["status"] == "simulated_no_provider_call"
    assert r1["cost_usd"] is None

    # Candidate tier 2: Groq; free eligibility is unverified
    r2 = router.dispatch("So sánh token/s", preferred_tier=2)
    assert r2["tier"] == 2
    assert "Groq" in r2["candidate_provider"]

    # Candidate tier 3: Gemini; no credentials are read or used
    r3 = router.dispatch("Phân tích mã nguồn", preferred_tier=3)
    assert r3["tier"] == 3
    assert "Gemini" in r3["candidate_provider"]

    # Tầng 4: Ollama metadata is interpreted from a synthetic response
    mock_ollama_resp = {
        "models": [{"name": "qwen2.5-coder:7b", "size_vram": 5368709120}]  # 5 GB
    }
    vram_info = router.check_ollama_vram(mock_ollama_resp)
    assert vram_info["running"] is True
    assert vram_info["processor"] == "GPU"
    assert vram_info["vram_mb"] == 5120.0
    unprobed_vram = router.check_ollama_vram()
    assert unprobed_vram["processor"] == "unverified"
    assert unprobed_vram["status"] == "unverified"
    empty_model_vram = router.check_ollama_vram({"models": []})
    assert empty_model_vram["running"] is True
    assert empty_model_vram["processor"] == "unverified"
    assert empty_model_vram["status"] == "unverified"


# ---------------------------------------------------------------------------
# 2. KIỂM THỬ ÂM THANH 48KHZ MONO, -14 LUFS & DE-ESSER
# ---------------------------------------------------------------------------


def test_voice_engine_broadcast_specs():
    """Kiểm tra thông số âm thanh chuẩn phát sóng: 48kHz mono, -14 LUFS, De-esser, fade 12ms."""
    engine = VoiceEngine48k()
    segment = engine.synthesize_speech_segment(
        speaker="Huy Tưởng",
        text="Xin chào quý vị, hôm nay chúng ta cấu hình Cloudflare Workers AI.",
        target_duration_sec=6.5,
    )

    assert segment["sample_rate"] == 48000
    assert segment["channels"] == 1  # Mono
    assert segment["target_lufs"] == -14.0
    assert segment["true_peak_dbtp"] == -0.5
    assert segment["status"] == "metadata_only"
    assert segment["audio_created"] is False
    assert segment["deesser_applied"] is False
    assert segment["deesser_planned"] is True
    assert segment["deesser_attenuation"] == 0.66  # Giảm 66% năng lượng âm s/x
    assert segment["edge_fade_samples"] == 576  # 48000 * 0.012s = 576 samples


# ---------------------------------------------------------------------------
# 3. KIỂM THỬ KHÓA GIỌNG SHA-256 (c174) & SÀN >= 900S
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -float("inf"), -1.0])
def test_c174_rejects_nonfinite_or_negative_duration(duration):
    segments = _build_sample_audio_manifest()
    segments[0]["duration_sec"] = duration
    with pytest.raises(ValueError, match="hữu hạn và không âm"):
        create_c174_voice_lock(segments)


def test_c174_rejects_overflowing_total_duration():
    segments = _build_sample_audio_manifest()
    for segment in segments:
        segment["duration_sec"] = 1e308

    with pytest.raises(ValueError, match="hữu hạn"):
        create_c174_voice_lock(segments)

def test_c174_rejects_stale_text_hash():
    segments = _build_sample_audio_manifest()
    lock_record = create_c174_voice_lock(segments)
    tampered = json.loads(json.dumps(segments, ensure_ascii=False))
    tampered[0]["text"] += " changed while retaining stale hash"

    ok, message = verify_c174_lock(lock_record, tampered)
    assert ok is False
    assert "c174" in message


def test_c174_rejects_invalid_lock_code():
    segments = _build_sample_audio_manifest()
    lock_record = create_c174_voice_lock(segments)
    lock_record["lock_code"] = "other"

    ok, message = verify_c174_lock(lock_record, segments)
    assert ok is False
    assert "c174" in message

@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("manifest", []),
        ("total_segments", 999),
        ("total_duration_sec", 0.0),
        ("meets_900s_floor", False),
    ],
)
def test_c174_rejects_inconsistent_recorded_fields(field, tampered_value):
    segments = _build_sample_audio_manifest()
    lock_record = create_c174_voice_lock(segments)
    lock_record[field] = tampered_value

    ok, message = verify_c174_lock(lock_record, segments)
    assert ok is False
    assert "recomputed" in message


def test_voice_lock_c174_contract():
    """Khóa giọng c174: bảo vệ bất biến văn bản và mốc thời gian."""
    segments = _build_sample_audio_manifest()
    lock_record = create_c174_voice_lock(segments)

    assert lock_record["lock_code"] == "c174_khoa_giong"
    assert lock_record["meets_900s_floor"] is True
    assert lock_record["total_duration_sec"] >= 900.0

    # Đối chiếu hợp lệ
    ok, msg = verify_c174_lock(lock_record, segments)
    assert ok is True
    assert msg == "OK"


# ---------------------------------------------------------------------------
# 4. KIỂM THỬ ĐỒ HỌA 3 LỚP c172 & HANDRIG 0.3 (NIÊM PHONG C2-200)
# ---------------------------------------------------------------------------


def test_hybrid_c172_renderer_three_layers():
    """Describe three scene layers at 1920x1080 and 1080x1920; no media is rendered."""
    renderer = HybridC172Renderer()

    # Dạng ngang 16:9
    scene_16_9 = renderer.render_scene(
        visual_mode="c172_hybrid",
        voice_lock_ok=True,
        resolution="1920x1080",
        channel_name="AI_TUTORIALS",
        public_source_url="https://github.com/modelcontextprotocol",
        terminal_snippet="curl -X POST https://api.cloudflare.com/...",
        sentence_duration_sec=8.0,
    )
    assert scene_16_9["status"] == "metadata_only"
    assert scene_16_9["media_created"] is False
    assert scene_16_9["scene_assets_verified"] is False
    assert scene_16_9["layers"][1]["screenshot_captured"] is False
    assert scene_16_9["layers"][1]["zoom_magnifier_applied"] is False
    assert len(scene_16_9["layers"]) == 3

    # Lớp 1 kiểm tem kênh và nhãn nội bộ
    l1 = scene_16_9["layers"][0]
    assert l1["channel_stamp"]["x"] == 8
    assert l1["channel_stamp"]["y"] == 8
    assert l1["internal_labels_count"] == 0

    # Lớp 3 kiểm HandRig 0.3
    l3 = scene_16_9["layers"][2]
    motion = l3["motion"]
    assert motion["draw_phase_sec"] == 2.0  # 8.0 * 25% = 2.0s
    assert motion["hold_phase_sec"] == 6.0  # 8.0 * 75% = 6.0s
    assert motion["pen_tip_error_px"] == 0
    assert motion["arm_edge_margin_px"] >= 86


def test_render_contract_rejects_missing_or_asserted_assets():
    with pytest.raises(KhongDatChuan, match="paths must be provided"):
        validate_scene_render_contract("c172_hybrid", voice_lock_ok=True)
    with pytest.raises(KhongDatChuan, match="paths must be provided"):
        validate_scene_render_contract("c172_hybrid", voice_lock_ok=True, scene_assets=True)


def test_render_contract_requires_existing_nonempty_asset_files(tmp_path):
    canvas = tmp_path / "canvas.png"
    screenshot = tmp_path / "source.png"
    canvas.write_bytes(b"canvas")
    scene_assets = {"technical_canvas": canvas, "source_screenshot": screenshot}

    with pytest.raises(KhongDatChuan, match="source_screenshot"):
        validate_scene_render_contract("c172_hybrid", voice_lock_ok=True, scene_assets=scene_assets)

    screenshot.write_bytes(b"source screenshot")
    assert validate_scene_render_contract(
        "c172_hybrid", voice_lock_ok=True, scene_assets=scene_assets
    ) is True

    screenshot.write_bytes(b"")
    with pytest.raises(KhongDatChuan, match="empty"):
        validate_scene_render_contract("c172_hybrid", voice_lock_ok=True, scene_assets=scene_assets)


def test_metadata_scene_does_not_claim_assets_are_verified():
    scene = HybridC172Renderer().render_scene("c172_hybrid", voice_lock_ok=True)
    assert scene["status"] == "metadata_only"
    assert scene["media_created"] is False
    assert scene["asset_validation"] == "not_performed_metadata_only"
    assert scene["scene_assets_verified"] is False

@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), True])
def test_handrig_rejects_invalid_sentence_duration(duration):
    with pytest.raises(ValueError, match="số hữu hạn dương"):
        HandRig03().compute_motion_timeline(duration)


def test_handrig_constraints_fail_closed():
    """HandRig 0.3: từ chối nếu lấn mép dưới 86px hoặc sai số ngòi khác 0px."""
    with pytest.raises(ValueError, match="86px"):
        HandRig03(edge_distance_px=80, pen_tip_error_px=0)

    with pytest.raises(ValueError, match="0px"):
        HandRig03(edge_distance_px=90, pen_tip_error_px=2)


# ---------------------------------------------------------------------------
# 5. NEGATIVE CONTRACT CHECKS; NOT SOURCE MUTATION TESTS


def test_two_negative_contract_checks_dot3():
    """Reject changed locked text and the prohibited legacy visual mode."""
    baseline_segments = _build_sample_audio_manifest()
    baseline_snapshot = json.loads(json.dumps(baseline_segments, ensure_ascii=False))
    raw_json = json.dumps(baseline_segments, ensure_ascii=False, sort_keys=True)
    rejected_checks = 0

    lock_record = create_c174_voice_lock(baseline_segments)
    changed_segments = json.loads(raw_json)
    changed_segments[0]["text"] += " changed after voice lock"
    ok, message = verify_c174_lock(lock_record, changed_segments)
    if not ok and "c174" in message:
        rejected_checks += 1

    try:
        validate_scene_render_contract(visual_mode="ve_tay_giay_ke_o", voice_lock_ok=True)
        legacy_mode_rejected = False
    except KhongDatChuan as error:
        legacy_mode_rejected = "C2-200" in str(error)
    if legacy_mode_rejected:
        rejected_checks += 1

    assert rejected_checks == 2
    assert baseline_segments == baseline_snapshot
