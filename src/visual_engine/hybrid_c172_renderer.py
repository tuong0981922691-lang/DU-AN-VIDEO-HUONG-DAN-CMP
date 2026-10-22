import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Prototype metadata for a c172 scene and HandRig contract; no images or videos are rendered.

Describes a planned 3-layer scene (1920x1080 16:9 or 1080x1920 9:16):
- Lớp 1: Cảnh kỹ thuật c172 (sơ đồ kiến trúc, bảng so sánh AI, tem kênh x=8px, y=8px, nguồn công khai).
- Lớp 2: Metadata giao diện / Terminal dự kiến; chưa chụp màn hình hay phóng đại thật.
- Lớp 3: Bàn tay HandRig 0.3 (tiếp xúc mép >= 86px, sai số ngòi 0px, vẽ 25% đầu câu rồi giữ tĩnh).

Niêm phong vĩnh viễn lối bảng trắng vẽ tay giấy kẻ ô cũ (C2-200).
Ném lỗi KhongDatChuan ngay lập tức nếu vi phạm hoặc lệch khóa giọng c174 (Fail-Closed).
"""

from collections.abc import Mapping
import math
import subprocess
import wave
from pathlib import Path
from typing import Any


class KhongDatChuan(Exception):
    """Ngoại lệ chuẩn ném ra khi vi phạm hợp đồng C2-200 hoặc lệch khóa giọng c174."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = str(message)


def _validate_scene_mode_and_voice(visual_mode: str, voice_lock_ok: bool) -> None:
    if visual_mode != "c172_hybrid":
        raise KhongDatChuan("KhongDatChuan: Cấm lùi về đồ họa vẽ tay cũ (C2-200 niêm phong)")
    if not voice_lock_ok:
        raise KhongDatChuan("KhongDatChuan: Lệch khóa giọng c174 hoặc kịch bản bị sửa đổi sau thu âm")


def validate_scene_render_contract(
    visual_mode: str,
    voice_lock_ok: bool,
    scene_assets: Mapping[str, str | Path] | None = None,
) -> bool:
    """Require non-empty files for the technical canvas and source screenshot."""
    _validate_scene_mode_and_voice(visual_mode, voice_lock_ok)
    required_assets = ("technical_canvas", "source_screenshot")
    if not isinstance(scene_assets, Mapping):
        raise KhongDatChuan("Scene asset paths must be provided")

    for asset_name in required_assets:
        asset_path = scene_assets.get(asset_name)
        if not isinstance(asset_path, (str, Path)) or not str(asset_path).strip():
            raise KhongDatChuan(f"Missing scene asset path: {asset_name}")
        path = Path(asset_path)
        try:
            is_valid_file = path.is_file() and path.stat().st_size > 0
        except OSError as error:
            raise KhongDatChuan(f"Cannot read scene asset {asset_name}: {error}") from error
        if not is_valid_file:
            raise KhongDatChuan(f"Scene asset is missing or empty: {asset_name}")
    return True


class HandRig03:
    """Bộ mô phỏng và kiểm soát bàn tay HandRig 0.3 vẽ chú thích đồng bộ."""

    def __init__(self, edge_distance_px: int = 86, pen_tip_error_px: int = 0) -> None:
        if edge_distance_px < 86:
            raise ValueError(f"Khoảng cách thoát mép khung {edge_distance_px}px vi phạm chuẩn >= 86px")
        if pen_tip_error_px != 0:
            raise ValueError(f"Sai số ngòi bút {pen_tip_error_px}px vi phạm chuẩn tuyệt đối 0px")
        self.edge_distance_px = edge_distance_px
        self.pen_tip_error_px = pen_tip_error_px

    def compute_motion_timeline(self, sentence_duration_sec: float) -> dict[str, Any]:
        """Tính toán mốc vẽ 25% đầu câu và 75% còn lại giữ tĩnh tuyệt đối."""
        if (
            isinstance(sentence_duration_sec, bool)
            or not isinstance(sentence_duration_sec, (int, float))
            or not math.isfinite(sentence_duration_sec)
            or sentence_duration_sec <= 0
        ):
            raise ValueError("Thời lượng câu HandRig phải là số hữu hạn dương")
        draw_duration = round(sentence_duration_sec * 0.25, 3)
        hold_duration = round(sentence_duration_sec * 0.75, 3)
        return {
            "draw_phase_sec": draw_duration,
            "hold_phase_sec": hold_duration,
            "total_sec": sentence_duration_sec,
            "draw_ratio": 0.25,
            "pen_tip_error_px": self.pen_tip_error_px,
            "arm_edge_margin_px": self.edge_distance_px,
        }


class HybridC172Renderer:
    """Build a scene metadata description; this prototype does not render image/video files."""

    def __init__(self) -> None:
        self.hand_rig = HandRig03(edge_distance_px=86, pen_tip_error_px=0)

    def render_chapter_video(
        self,
        *,
        voice_lock_ok: bool,
        scene_assets: Mapping[str, str | Path],
        canvas_path: Path | str,
        pointer_path: Path | str,
        audio_path: Path | str,
        output_path: Path | str,
        ffmpeg_path: Path | str,
        target_x: int,
        target_y: int,
        pointer_travel_sec: float = 3.0,
    ) -> dict[str, Any]:
        """Render a still technical canvas, purposeful moving pen target, and matching WAV to MP4."""
        _validate_scene_mode_and_voice("c172_hybrid", voice_lock_ok)
        validate_scene_render_contract("c172_hybrid", voice_lock_ok, scene_assets)
        canvas = Path(canvas_path).resolve()
        pointer = Path(pointer_path).resolve()
        audio = Path(audio_path).resolve()
        output = Path(output_path).resolve()
        ffmpeg = Path(ffmpeg_path).resolve()
        for label, path in (("canvas", canvas), ("pointer", pointer), ("audio", audio)):
            if not path.is_file() or path.stat().st_size == 0:
                raise KhongDatChuan(f"Render input {label} is missing or empty")
        if output.suffix.lower() != ".mp4":
            raise ValueError("Chapter video output must use .mp4")
        if not ffmpeg.is_file():
            raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")
        if not (0 <= target_x < 1920 and 0 <= target_y < 1080):
            raise ValueError("HandRig target must be inside the 1920x1080 canvas")
        if not math.isfinite(pointer_travel_sec) or pointer_travel_sec <= 0:
            raise ValueError("HandRig travel duration must be finite and positive")
        with wave.open(str(audio), "rb") as wav:
            if wav.getframerate() != 48000 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise KhongDatChuan("K08 voice input must be 48kHz mono PCM16 WAV")
            audio_duration = wav.getnframes() / wav.getframerate()
        output.parent.mkdir(parents=True, exist_ok=True)
        start_x, start_y = 72, 890
        pen_tip_x, pen_tip_y = 10, 76
        end_x, end_y = target_x - pen_tip_x, target_y - pen_tip_y
        x_expr = f"if(lt(t,{pointer_travel_sec}),{start_x}+({end_x-start_x})*t/{pointer_travel_sec},{end_x})"
        y_expr = f"if(lt(t,{pointer_travel_sec}),{start_y}+({end_y-start_y})*t/{pointer_travel_sec},{end_y})"
        frame_count = math.ceil(audio_duration * 24)
        graph = (
            "[0:v]scale=1920:1080,setsar=1,format=yuv420p[bg];"
            f"[1:v]format=rgba,trim=duration={pointer_travel_sec},setpts=PTS-STARTPTS[pen];"
            f"[bg][pen]overlay=x='{x_expr}':y='{y_expr}':eof_action=pass:repeatlast=0[v]"
        )
        command = [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", "24", "-i", str(canvas),
            "-loop", "1", "-framerate", "24", "-i", str(pointer),
            "-i", str(audio), "-filter_complex", graph, "-map", "[v]", "-map", "2:a:0",
            "-frames:v", str(frame_count), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(output),
        ]
        rendered = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        if rendered.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            output.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg chapter render failed: {rendered.stderr[-3000:]}")
        return {
            "media_created": True, "visual_mode": "c172_hybrid",
            "video_path": str(output), "video_bytes": output.stat().st_size,
            "audio_duration_sec": audio_duration, "fps": 24, "resolution": "1920x1080",
            "handrig_target": {"x": target_x, "y": target_y, "travel_sec": pointer_travel_sec},
            "scene_assets_verified": True,
        }

    def render_scene(
        self,
        visual_mode: str,
        voice_lock_ok: bool,
        resolution: str = "1920x1080",
        channel_name: str = "AI_HUONG_DAN",
        public_source_url: str | None = "https://github.com/modelcontextprotocol",
        terminal_snippet: str = "pip install -r requirements.txt",
        annotation_keyword: str = "Cấu hình chuẩn",
        sentence_duration_sec: float = 6.0,
    ) -> dict[str, Any]:
        """Return a metadata description of the planned three-layer scene."""
        _validate_scene_mode_and_voice(visual_mode, voice_lock_ok)

        if resolution not in ("1920x1080", "1080x1920"):
            raise ValueError(f"Độ phân giải {resolution} không được hỗ trợ (chỉ nhận 1920x1080 và 1080x1920)")

        # Lớp 1: Cảnh kỹ thuật c172
        layer_1 = {
            "layer_name": "L1_Technical_Canvas_c172",
            "resolution": resolution,
            "channel_stamp": {"x": 8, "y": 8, "name": channel_name},
            "source_citation": {"corner": "bottom_right", "url": public_source_url},
            "internal_labels_count": 0,  # 0 nhãn máy nội bộ
        }

        # Lớp 2: Ảnh chụp màn hình thật / Terminal
        layer_2 = {
            "layer_name": "L2_Planned_Screen_Terminal",
            "terminal_code": terminal_snippet,
            "screenshot_captured": False,
            "zoom_magnifier_applied": False,
            "highlight_region": {"x": 120, "y": 240, "w": 800, "h": 400},
        }

        # Lớp 3: Bàn tay HandRig 0.3
        hand_timeline = self.hand_rig.compute_motion_timeline(sentence_duration_sec)
        layer_3 = {
            "layer_name": "L3_HandRig_0.3",
            "keyword": annotation_keyword,
            "motion": hand_timeline,
            "arm_escapes_edge": True,
        }

        return {
            "status": "metadata_only",
            "media_created": False,
            "asset_validation": "not_performed_metadata_only",
            "scene_assets_verified": False,
            "visual_mode": visual_mode,
            "resolution": resolution,
            "layers": [layer_1, layer_2, layer_3],
            "c2_200_sealed": True,
        }
