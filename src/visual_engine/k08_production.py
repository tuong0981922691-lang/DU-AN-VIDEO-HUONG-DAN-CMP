"""Offline K08 speech, source-canvas, HandRig and MP4 production helpers."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import hashlib
import re
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.compute_voice.router_and_tts import create_c174_voice_lock, verify_c174_lock, VoiceEngine48k
from src.visual_engine.hybrid_c172_renderer import HybridC172Renderer

CHAPTER_NAMES = (
    "CH01_Khoi_Dong_Dat_Bai_Toan_Thuc_Te",
    "CH02_Buc_Tranh_Kien_Truc_Boi_Canh_Ky_Thuat",
    "CH03_Khao_Sat_Cong_Cu_Nguon_Tai_Lieu_Goc",
    "CH04_Mo_Xe_Thong_So_Bang_Do_Thuc_Nghiem_AI",
    "CH05_Cai_Dat_Cau_Hinh_Tung_Buoc_May_Ca_Nhan",
    "CH06_Thuc_Thi_Lenh_Bat_Benh_Thuc_Chien",
    "CH07_Toi_Uu_Hieu_Nang_Chien_Luoc_Chi_Phi_0",
    "CH08_Doi_Chieu_An_Toan_Chong_Ro_Ri_Du_Lieu",
    "CH09_Tong_Ket_He_Thong_Lo_Trinh_Tu_Dong_Hoa",
)

BG = "#08111f"
PANEL = "#101d2e"
PANEL_ALT = "#0b1726"
INK = "#e8f0fb"
MUTED = "#9db0c8"
CYAN = "#4bd5e8"
AMBER = "#ffb86b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    paths = {
        "regular": Path(r"C:\Windows\Fonts\segoeui.ttf"),
        "bold": Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        "mono": Path(r"C:\Windows\Fonts\consola.ttf"),
    }
    return ImageFont.truetype(str(paths[name]), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _find_source(root: Path, reference: str) -> tuple[Path | None, int, int]:
    match = re.search(r"([A-Za-z0-9_.-]+\.py):(\d+)(?:[\u2013-](\d+))?", reference)
    if not match:
        return None, 0, 0
    candidates = list((root / "src").rglob(match.group(1))) + list((root / "tests").rglob(match.group(1)))
    if len(candidates) != 1:
        return None, int(match.group(2)), int(match.group(3) or match.group(2))
    start = int(match.group(2))
    end = int(match.group(3) or start + 9)
    return candidates[0], start, min(end, start + 11)


def _source_excerpt(root: Path, reference: str) -> tuple[str, str]:
    path, start, end = _find_source(root, reference)
    if path is None:
        return "Source locator", reference[:160]
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, min(start, len(lines)))
    end = max(start, min(end, len(lines)))
    excerpt = "\n".join(f"{line_no:04d}  {lines[line_no - 1]}" for line_no in range(start, end + 1))
    unsafe = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}")
    if unsafe.search(excerpt) or re.search(r"(?i)[CDE]:\\Users\\|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", excerpt):
        raise ValueError(f"Unsafe content found in code exhibit {path.name}:{start}-{end}")
    return f"{path.relative_to(root)}:{start}-{end}", excerpt


def render_canvas_assets(
    *, root: Path, chapter_index: int, title: str, narration: str,
    canvas_spec: str, code_reference: str, handrig_target: str,
    assets_dir: Path,
) -> dict[str, Any]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    canvas_path = assets_dir / f"CH{chapter_index:02d}_c172_canvas.png"
    screenshot_path = assets_dir / f"CH{chapter_index:02d}_source_code.png"
    pointer_path = assets_dir / f"CH{chapter_index:02d}_handrig_pen.png"
    image = Image.new("RGB", (1920, 1080), BG)
    draw = ImageDraw.Draw(image)
    title_font, body_font, small_font, mono_font = _font("bold", 44), _font("regular", 27), _font("regular", 20), _font("mono", 19)
    draw.rounded_rectangle((42, 34, 1878, 122), radius=18, fill=PANEL, outline="#243953", width=2)
    draw.text((72, 53), f"CMP  /  CH{chapter_index:02d} OF 09", font=small_font, fill=CYAN)
    draw.text((420, 47), title, font=title_font, fill=INK)
    draw.rounded_rectangle((52, 150, 1868, 257), radius=15, fill=PANEL_ALT, outline="#1c314c", width=2)
    intro = " ".join(narration.split())[:330]
    y = 168
    for line in _wrap(draw, intro, body_font, 1750)[:2]:
        draw.text((78, y), line, font=body_font, fill=MUTED)
        y += 39

    draw.rounded_rectangle((52, 284, 960, 878), radius=20, fill=PANEL, outline="#28415d", width=2)
    draw.text((84, 310), "CANVAS  /  LU\u1ed2NG K\u1ef8 THU\u1eacT", font=small_font, fill=CYAN)
    spec_body = re.sub(r"^F\d+:?\s*", "", canvas_spec.strip())
    nodes = [part.strip(" ;.") for part in re.split(r"\s*(?:\u2192|->)\s*", spec_body) if part.strip()]
    if len(nodes) < 2:
        nodes = textwrap.wrap(spec_body, 42)[:4] or ["Canvas b\u1eb1ng ch\u1ee9ng c172"]
    node_y = 390
    node_height = 76
    gap = 35
    max_nodes = min(5, len(nodes))
    nodes = nodes[:max_nodes]
    for idx, node in enumerate(nodes):
        rect = (92, node_y + idx * (node_height + gap), 916, node_y + idx * (node_height + gap) + node_height)
        draw.rounded_rectangle(rect, radius=12, fill="#132b42", outline=CYAN if idx == 0 else "#335271", width=2)
        for offset, line in enumerate(_wrap(draw, node, body_font, 780)[:2]):
            draw.text((116, rect[1] + 12 + offset * 30), line, font=body_font, fill=INK)
        if idx < len(nodes) - 1:
            cx = 504
            ay = rect[3] + 7
            draw.line((cx, ay, cx, ay + gap - 10), fill=AMBER, width=4)
            draw.polygon([(cx - 9, ay + gap - 17), (cx + 9, ay + gap - 17), (cx, ay + gap - 3)], fill=AMBER)

    draw.rounded_rectangle((992, 284, 1868, 878), radius=20, fill=PANEL_ALT, outline="#28415d", width=2)
    draw.text((1024, 310), "CODE EVIDENCE  /  SOURCE LOCATOR", font=small_font, fill=CYAN)
    source_name, excerpt = _source_excerpt(root, code_reference)
    draw.text((1024, 352), source_name[:77], font=small_font, fill=AMBER)
    code_y = 396
    for row in excerpt.splitlines()[:13]:
        for offset, line in enumerate(_wrap(draw, row, mono_font, 790)[:2]):
            draw.text((1024, code_y + offset * 25), line, font=mono_font, fill=INK)
        code_y += 31
    draw.rounded_rectangle((1024, 792, 1828, 850), radius=10, fill="#18283b")
    for i, line in enumerate(_wrap(draw, "HandRig V-900 -> " + handrig_target, small_font, 760)[:2]):
        draw.text((1042, 801 + i * 22), line, font=small_font, fill=AMBER)

    draw.rounded_rectangle((52, 906, 1868, 1030), radius=16, fill="#0d1a29", outline="#1c314c", width=2)
    draw.text((80, 932), "CH\u1ed0T KI\u1ec2M \u0110\u1ecaNH TO\u00c0N V\u1eb8N K\u1ecaCH B\u1ea2N c174", font=body_font, fill=CYAN)
    draw.text((80, 981), "T\u01b0 li\u1ec7u ngu\u1ed3n c\u1ee5c b\u1ed9 - h\u00ecnh minh h\u1ecda t\u1ea1o t\u1eeb source - kh\u00f4ng hi\u1ec3n th\u1ecb credential", font=small_font, fill=MUTED)
    image.save(canvas_path, format="PNG", optimize=True)

    code_image = image.crop((992, 284, 1868, 878))
    code_image.save(screenshot_path, format="PNG", optimize=True)

    pointer = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pointer)
    pd.polygon([(18, 78), (68, 18), (82, 30), (32, 90)], fill="#ffcf63", outline="#132238")
    pd.polygon([(18, 78), (32, 90), (11, 94)], fill="#f15b52", outline="#132238")
    pd.line((26, 78, 68, 29), fill="#fff4d0", width=3)
    pointer.save(pointer_path, format="PNG", optimize=True)
    return {"canvas": canvas_path, "source_screenshot": screenshot_path, "pointer": pointer_path,
            "source_locator": source_name, "handrig_target": handrig_target,
            "target_xy": {"x": 1430, "y": 725},
            "sha256": {"canvas": sha256_file(canvas_path), "source_screenshot": sha256_file(screenshot_path)}}


def synthesize_chapter_audio(*, engine: VoiceEngine48k, speaker: str, narration: str, output: Path, ffmpeg: Path) -> dict[str, Any]:
    record = engine.synthesize_wav(speaker, narration, output, ffmpeg_path=ffmpeg)
    import wave
    with wave.open(str(output), "rb") as stream:
        duration = stream.getnframes() / stream.getframerate()
        record["duration_sec"] = duration
        record["frames"] = stream.getnframes()
    record["sha256"] = sha256_file(output)
    return record


def create_and_verify_c174(segments: list[dict[str, Any]]) -> dict[str, Any]:
    lock = create_c174_voice_lock(segments)
    verified, message = verify_c174_lock(lock, segments)
    if not verified or message != "OK":
        raise RuntimeError(f"Final c174 verification failed: {message}")
    return lock


def render_chapter(*, renderer: HybridC172Renderer, assets: dict[str, Any], audio: Path,
                   output: Path, ffmpeg: Path) -> dict[str, Any]:
    return renderer.render_chapter_video(
        voice_lock_ok=True,
        scene_assets={"technical_canvas": assets["canvas"], "source_screenshot": assets["source_screenshot"]},
        canvas_path=assets["canvas"], pointer_path=assets["pointer"], audio_path=audio,
        output_path=output, ffmpeg_path=ffmpeg,
        target_x=assets["target_xy"]["x"], target_y=assets["target_xy"]["y"],
        pointer_travel_sec=3.0,
    )
