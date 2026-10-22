import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import math
from pathlib import Path
import pytest

from src.visual_engine.pipeline_k08_render import (
    get_ffmpeg_binary,
    measure_ebur128,
    generate_c174_master_seal,
    render_chapter_segment,
    concat_mp4_segments,
)

ROOT = Path(__file__).resolve().parents[1]


def test_get_ffmpeg_binary_returns_usable_path():
    binary = get_ffmpeg_binary()
    assert isinstance(binary, str)
    assert len(binary) > 0


def test_measure_ebur128_on_real_sample_g5():
    g5_path = ROOT / "du_lieu" / "tam_me" / "g4_g5_mau_3_phut" / "G5_mau_video_c172_3_phut_MAI1_MAI2_1080p.mp4"
    if not g5_path.is_file():
        pytest.skip("G5 MP4 sample not present on disk")

    ffmpeg_exe = get_ffmpeg_binary()
    metrics = measure_ebur128(ffmpeg_exe, g5_path)

    assert isinstance(metrics["integrated_loudness_lufs"], float)
    assert -16.0 <= metrics["integrated_loudness_lufs"] <= -13.0
    assert isinstance(metrics["true_peak_dbtp"], float)
    assert metrics["true_peak_dbtp"] <= 0.0
    assert metrics["compliant_itu_r_bs1770"] is True


def test_generate_c174_master_seal_deterministic_and_fails_under_900s():
    sample_chapters = [
        {"text": "Chương 1 lời thoại khởi động kiến trúc.", "duration_sec": 120.0, "speaker": "Huy Tưởng"},
        {"text": "Chương 2 phản biện kiểm thử chịu lực.", "duration_sec": 130.0, "speaker": "Xuân Công"},
        {"text": "Chương 3 tổng kết hệ thống và quy trình.", "duration_sec": 140.0, "speaker": "Huy Tưởng"},
    ]
    seal = generate_c174_master_seal(sample_chapters)
    assert seal["lock_code"] == "c174_khoa_giong"
    assert len(seal["master_sha256"]) == 64
    assert seal["total_chapters"] == 3
    assert math.isclose(seal["total_duration_sec"], 390.0)
    assert seal["meets_900s_floor"] is False  # 390s < 900s


def test_generate_c174_master_seal_meets_floor_with_full_chapters():
    full_chapters = [
        {"text": f"Chương {i} nội dung chi tiết bài giảng AI.", "duration_sec": 120.0, "speaker": "Huy Tưởng"}
        for i in range(1, 10)
    ]  # 9 chapters * 120s = 1080s >= 900s
    seal = generate_c174_master_seal(full_chapters)
    assert seal["total_chapters"] == 9
    assert seal["total_duration_sec"] == 1080.0
    assert seal["meets_900s_floor"] is True


def test_render_and_concat_reject_invalid_paths(tmp_path):
    ffmpeg_exe = get_ffmpeg_binary()
    with pytest.raises(FileNotFoundError):
        render_chapter_segment(ffmpeg_exe, tmp_path / "missing.png", tmp_path / "missing.wav", tmp_path / "out.mp4", 10.0)

    with pytest.raises(ValueError, match="rỗng"):
        concat_mp4_segments(ffmpeg_exe, [], tmp_path / "master.mp4")
