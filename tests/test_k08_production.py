import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pytest

from src.visual_engine.hybrid_c172_renderer import HybridC172Renderer, KhongDatChuan
from src.visual_engine.k08_production import CHAPTER_NAMES, create_and_verify_c174
from src.visual_engine.render_k08 import _parse_script, _parse_storyboard


def test_k08_names_cover_exactly_nine_chapters():
    assert len(CHAPTER_NAMES) == 9
    assert CHAPTER_NAMES[0] == "CH01_Khoi_Dong_Dat_Bai_Toan_Thuc_Te"
    assert CHAPTER_NAMES[-1] == "CH09_Tong_Ket_He_Thong_Lo_Trinh_Tu_Dong_Hoa"


def test_current_script_and_storyboard_are_nine_chapter_inputs():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    chapters = _parse_script(root / "du_lieu/tam_me/K01_K03_c174_evidence_script_draft.md")
    storyboard = _parse_storyboard(root / "du_lieu/tam_me/K06_storyboard_duration_proposal.md")
    assert len(chapters) == len(storyboard) == 9
    assert sum(len(chapter["text"].split()) for chapter in chapters) == 4564
    assert all(all(storyboard[index][key] for key in ("narration", "canvas", "code", "handrig")) for index in range(9))


def test_c174_uses_measured_audio_durations_for_all_nine_segments():
    segments = [
        {"speaker": "Microsoft An", "text": f"chapter {index}", "duration_sec": 105.0}
        for index in range(9)
    ]
    lock = create_and_verify_c174(segments)
    assert lock["lock_code"] == "c174_khoa_giong"
    assert lock["total_segments"] == 9
    assert lock["total_duration_sec"] == 945.0
    assert lock["meets_900s_floor"] is True


def test_real_renderer_rejects_missing_verified_assets(tmp_path):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"not a wav")
    with pytest.raises(KhongDatChuan, match="technical_canvas"):
        HybridC172Renderer().render_chapter_video(
            voice_lock_ok=True,
            scene_assets={"technical_canvas": tmp_path / "missing.png", "source_screenshot": tmp_path / "source.png"},
            canvas_path=tmp_path / "missing.png", pointer_path=tmp_path / "pointer.png",
            audio_path=audio, output_path=tmp_path / "chapter.mp4",
            ffmpeg_path=tmp_path / "ffmpeg.exe", target_x=500, target_y=500,
        )


def test_real_renderer_rejects_out_of_canvas_handrig_target(tmp_path):
    renderer = HybridC172Renderer()
    canvas = tmp_path / "canvas.png"
    source = tmp_path / "source.png"
    pointer = tmp_path / "pointer.png"
    ffmpeg = tmp_path / "ffmpeg.exe"
    audio = tmp_path / "voice.wav"
    for path in (canvas, source, pointer, ffmpeg, audio):
        path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="inside the 1920x1080 canvas"):
        renderer.render_chapter_video(
            voice_lock_ok=True,
            scene_assets={"technical_canvas": canvas, "source_screenshot": source},
            canvas_path=canvas, pointer_path=pointer, audio_path=audio,
            output_path=tmp_path / "chapter.mp4", ffmpeg_path=ffmpeg,
            target_x=1920, target_y=100,
        )
