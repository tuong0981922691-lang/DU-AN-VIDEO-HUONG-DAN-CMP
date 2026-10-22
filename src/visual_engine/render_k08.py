"""Render all nine K08 chapters locally with WinRT Microsoft An and FFmpeg."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from src.compute_voice.router_and_tts import VoiceEngine48k
from src.visual_engine.hybrid_c172_renderer import HybridC172Renderer
from src.visual_engine.k08_production import (
    CHAPTER_NAMES, create_and_verify_c174, render_canvas_assets,
    render_chapter, sha256_file, synthesize_chapter_audio,
)

SCRIPT_REL = Path("du_lieu/tam_me/K01_K03_c174_evidence_script_draft.md")
STORYBOARD_REL = Path("du_lieu/tam_me/K06_storyboard_duration_proposal.md")


def _parse_script(path: Path) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    headers = list(re.finditer(r"^### Ch\u01b0\u01a1ng (\d+):\s*(.*)$", source, re.MULTILINE))
    chapters: list[dict[str, Any]] = []
    for idx, header in enumerate(headers):
        end = headers[idx + 1].start() if idx + 1 < len(headers) else source.find("\n## ", header.end())
        if end < 0:
            end = len(source)
        section = source[header.end():end]
        speaker = re.search(r"- \*\*Ng\u01b0\u1eddi d\u1eabn ch\u00ednh:\*\* (.+)", section)
        narration = re.search(r"\*\*L\u1eddi d\u1eabn \([^)]*\):\*\*\s*\"(.*)\"", section, re.DOTALL)
        duration = re.search(r"- \*\*Th\u1eddi l\u01b0\u1ee3ng d\u1ef1 ki\u1ebfn:\*\* `([0-9]+)", section)
        if not (speaker and narration and duration):
            raise ValueError(f"Chapter {idx + 1} is missing speaker, narration, or duration metadata")
        chapter_number = int(header.group(1))
        if chapter_number != idx + 1 or chapter_number > len(CHAPTER_NAMES):
            raise ValueError("Script chapter sequence does not match K08 file naming")
        chapters.append({
            "chapter_no": chapter_number,
            "title": header.group(2).strip(),
            "speaker": speaker.group(1).strip(),
            "text": narration.group(1).strip(),
            "contract_duration_sec": int(duration.group(1)),
        })
    if len(chapters) != 9:
        raise ValueError(f"K08 requires exactly nine chapters, found {len(chapters)}")
    return chapters


def _parse_storyboard(path: Path) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if re.match(r"^\| S0[1-9] ?", line)]
    if len(lines) != 9:
        raise ValueError(f"K06 requires 9 storyboard rows, found {len(lines)}")
    result = []
    for expected, line in enumerate(lines, 1):
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 5 or not all(columns[idx] for idx in range(1, 5)):
            raise ValueError(f"Storyboard chapter {expected} is missing a required target")
        result.append({"cue": columns[0], "narration": columns[1], "canvas": columns[2], "code": columns[3], "handrig": columns[4]})
    return result


def _loudness(ffmpeg: str, audio: Path) -> dict[str, float]:
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(audio), "-af", "loudnorm=I=-14:TP=-0.5:LRA=7:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Loudness verification failed: {proc.stderr[-2000:]}")
    reports = []
    for match in re.finditer(r"\{[^{}]*\}", proc.stderr, re.DOTALL):
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if "input_i" in parsed:
            reports.append(parsed)
    if not reports:
        raise RuntimeError("FFmpeg did not return loudness measurement JSON")
    report = reports[-1]
    return {"integrated_lufs": float(report["input_i"]), "true_peak_dbtp": float(report["input_tp"])}


def _silence_gaps(ffmpeg: str, audio: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(audio), "-af", "silencedetect=noise=-50dB:d=0.25", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Silence-gap verification failed: {proc.stderr[-2000:]}")
    durations = [float(value) for value in re.findall(r"silence_duration:\s*([0-9.]+)", proc.stderr)]
    return {"threshold_dbfs": -50, "detection_floor_sec": 0.25, "long_silence_count": len(durations),
            "max_detected_silence_sec": max(durations, default=0.0)}


def _decode_duration(ffmpeg: str, media: Path, selector: str) -> float:
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(media), "-map", f"0:{selector}", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Full stream decode failed for {selector}: {proc.stderr[-2000:]}")
    stamps = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not stamps:
        raise RuntimeError(f"FFmpeg returned no decoded duration for {selector}")
    hours, minutes, seconds = map(float, stamps[-1])
    duration = hours * 3600 + minutes * 60 + seconds
    if selector.startswith("v"):
        frames = re.findall(r"frame=\s*(\d+)", proc.stderr)
        if frames:
            duration = max(duration, int(frames[-1]) / 24)
    return duration


def _probe_mux(ffmpeg: str, video: Path, audio_duration: float) -> dict[str, Any]:
    video_duration = _decode_duration(ffmpeg, video, "v:0")
    muxed_audio = _decode_duration(ffmpeg, video, "a:0")
    delta = abs(video_duration - muxed_audio)
    if delta > 1 / 24 + 0.001:
        raise RuntimeError(f"Video/audio tracks are not aligned: {video_duration:.3f}s vs {muxed_audio:.3f}s")
    if abs(muxed_audio - audio_duration) > 0.12:
        raise RuntimeError(f"Muxed audio differs from source PCM: {muxed_audio:.3f}s vs {audio_duration:.3f}s")
    return {"video_duration_sec": round(video_duration, 6), "audio_duration_sec": round(muxed_audio, 6),
            "source_pcm_duration_sec": round(audio_duration, 6), "video_audio_delta_sec": round(delta, 6)}


def _concat(ffmpeg: str, videos: list[Path], output: Path, work: Path) -> None:
    listing = work / "concat.ffconcat"
    escaped = [path.as_posix().replace("'", "'\\''") for path in videos]
    listing.write_text("ffconcat version 1.0\n" + "".join(f"file '{item}'\n" for item in escaped), encoding="utf-8")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )
    if proc.returncode != 0 or not output.is_file() or not output.stat().st_size:
        raise RuntimeError(f"Final K08 concat failed: {proc.stderr[-3000:]}")


def render_k08(root: Path, output_dir: Path | None = None, ffmpeg: str | None = None, limit: int = 9) -> dict[str, Any]:
    root = root.resolve()
    script_path = root / SCRIPT_REL
    storyboard_path = root / STORYBOARD_REL
    chapters = _parse_script(script_path)
    storyboard = _parse_storyboard(storyboard_path)
    if limit < 1 or limit > 9:
        raise ValueError("limit must be between 1 and 9")
    if limit != 9 and output_dir is None:
        raise ValueError("A bounded smoke run must use an explicit output directory")
    ffmpeg_exe = ffmpeg or imageio_ffmpeg.get_ffmpeg_exe()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = output_dir.resolve() if output_dir else root / "du_lieu" / "tam_me" / f"K08_render_{stamp}"
    if work.exists() and any(work.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty render directory: {work}")
    audio_dir, video_dir, asset_dir = work / "audio", work / "video", work / "assets"
    for path in (audio_dir, video_dir, asset_dir):
        path.mkdir(parents=True, exist_ok=True)

    engine = VoiceEngine48k(cache_dir=audio_dir)
    renderer = HybridC172Renderer()
    audio_records: list[dict[str, Any]] = []
    segment_records: list[dict[str, Any]] = []
    active = chapters[:limit]
    for chapter, visual in zip(active, storyboard[:limit], strict=True):
        stem = CHAPTER_NAMES[chapter["chapter_no"] - 1]
        audio_path = audio_dir / f"{stem}.wav"
        audio_record = synthesize_chapter_audio(engine=engine, speaker=chapter["speaker"], narration=chapter["text"], output=audio_path, ffmpeg=Path(ffmpeg_exe))
        if audio_record["duration_sec"] <= 0:
            raise RuntimeError(f"Empty audio duration: {stem}")
        loudness = _loudness(ffmpeg_exe, audio_path)
        if abs(loudness["integrated_lufs"] - (-14.0)) > 0.25 or loudness["true_peak_dbtp"] > -0.4:
            raise RuntimeError(f"Audio normalization outside tolerance for {stem}: {loudness}")
        silence = _silence_gaps(ffmpeg_exe, audio_path)
        if silence["max_detected_silence_sec"] > 0.28:
            raise RuntimeError(f"Long silence exceeds 280ms in {stem}: {silence}")
        assets = render_canvas_assets(
            root=root, chapter_index=chapter["chapter_no"], title=chapter["title"], narration=chapter["text"],
            canvas_spec=visual["canvas"], code_reference=visual["code"], handrig_target=visual["handrig"], assets_dir=asset_dir,
        )
        video_path = video_dir / f"{stem}.mp4"
        render = render_chapter(renderer=renderer, assets=assets, audio=audio_path, output=video_path, ffmpeg=Path(ffmpeg_exe))
        mux = _probe_mux(ffmpeg_exe, video_path, audio_record["duration_sec"])
        audio_record.update({"loudness": loudness, "silence": silence})
        audio_records.append(audio_record)
        segment_records.append({
            "chapter_no": chapter["chapter_no"], "title": chapter["title"], "file_stem": stem,
            "script_speaker": chapter["speaker"], "voice": "Microsoft An (vi-VN)",
            "word_count": len(chapter["text"].split()), "audio": audio_record,
            "canvas": assets["sha256"]["canvas"], "source_screenshot": assets["sha256"]["source_screenshot"],
            "code_locator": assets["source_locator"], "handrig": render["handrig_target"],
            "video": {"path": str(video_path), "bytes": video_path.stat().st_size, "sha256": sha256_file(video_path), **mux},
        })
        print(f"PASS {stem}: {audio_record['duration_sec']:.3f}s, {loudness['integrated_lufs']:.2f} LUFS, max silence {silence['max_detected_silence_sec']:.3f}s, mux delta {mux['video_audio_delta_sec']:.3f}s", flush=True)

    result: dict[str, Any] = {
        "status": "SMOKE_RENDER_ONLY" if limit < 9 else "K08_RENDERED_PENDING_HUMAN_QA",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "script_sha256": sha256_file(script_path), "storyboard_sha256": sha256_file(storyboard_path),
        "voice_engine": "Windows Runtime SpeechSynthesizer / Microsoft An (vi-VN), offline",
        "audio_processing": "FFmpeg deesser + silenceremove max 180ms residual target 50ms + two-pass loudnorm I=-14 LUFS TP=-0.5 dBTP",
        "chapters": segment_records, "output_directory": str(work),
        "total_audio_duration_sec": round(sum(record["duration_sec"] for record in audio_records), 6),
    }
    if limit == 9:
        lock_segments = [
            {"speaker": record["script_speaker"], "text": chapter["text"], "duration_sec": record["audio"]["duration_sec"]}
            for chapter, record in zip(chapters, segment_records, strict=True)
        ]
        lock = create_and_verify_c174(lock_segments)
        if len(lock["manifest"]) != 9 or not lock["meets_900s_floor"]:
            raise RuntimeError("Final c174 gate requires exactly 9 measured segments and at least 900s audio")
        result["c174"] = lock
        result["c174_verified"] = True
        final = work / "K08_9_Chuong_1080p.mp4"
        _concat(ffmpeg_exe, [video_dir / f"{name}.mp4" for name in CHAPTER_NAMES], final, work)
        muxed_audio = _decode_duration(ffmpeg_exe, final, "a:0")
        muxed_video = _decode_duration(ffmpeg_exe, final, "v:0")
        delta = abs(muxed_audio - muxed_video)
        if muxed_audio < 900 or muxed_video < 900 or delta > 1 / 24 + 0.001:
            raise RuntimeError(f"Final K08 gate failed: audio={muxed_audio:.3f}s video={muxed_video:.3f}s delta={delta:.3f}s")
        result["final_video"] = {"path": str(final), "bytes": final.stat().st_size, "sha256": sha256_file(final),
                                 "audio_duration_sec": round(muxed_audio, 6), "video_duration_sec": round(muxed_video, 6),
                                 "duration_sec": round(min(muxed_audio, muxed_video), 6), "av_delta_sec": round(delta, 6)}
    manifest_path = work / "K08_manifest.json"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["manifest_file"] = str(manifest_path)
    result["manifest_sha256"] = sha256_file(manifest_path)
    print(json.dumps({"status": result["status"], "output_directory": str(work), "manifest_sha256": result["manifest_sha256"],
                      "total_audio_duration_sec": result["total_audio_duration_sec"],
                      "final_video": result.get("final_video")}, ensure_ascii=False, indent=2), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--limit", type=int, default=9, help="Bounded smoke run only; 9 is the complete K08")
    args = parser.parse_args()
    render_k08(args.workspace, args.output_dir, args.ffmpeg, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
