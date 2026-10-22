"""Local Windows Runtime speech synthesis and offline PCM processing."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

def synthesize_wav(
    speaker: str,
    text: str,
    output_path: Path | str,
    *,
    ffmpeg_path: Path | str,
    powershell_path: str = "powershell.exe",
) -> dict[str, Any]:
    """Synthesize Vietnamese speech with local WinRT, then filter and normalize a PCM WAV."""
    cleaned_text = str(text or "").strip()
    if not cleaned_text:
        raise ValueError("Speech text must not be empty")
    target = Path(output_path).resolve()
    if target.suffix.lower() != ".wav":
        raise ValueError("Speech output path must use WAV format")
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = str(Path(ffmpeg_path).resolve())
    helper = Path(__file__).with_name("winrt_synthesize.ps1")
    if not helper.is_file():
        raise FileNotFoundError(f"WinRT speech helper is missing: {helper}")
    if not shutil.which(powershell_path) and not Path(powershell_path).is_file():
        raise FileNotFoundError(f"PowerShell executable not found: {powershell_path}")
    if not Path(ffmpeg).is_file():
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")

    raw_path = None
    filtered_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="winrt-", suffix=".wav", dir=target.parent, delete=False) as raw:
            raw_path = Path(raw.name)
        with tempfile.NamedTemporaryFile(prefix="filtered-", suffix=".wav", dir=target.parent, delete=False) as filtered:
            filtered_path = Path(filtered.name)
        request = json.dumps({"text": cleaned_text, "output_path": str(raw_path)}, ensure_ascii=False)
        environment = os.environ.copy()
        environment["CMP_WINRT_REQUEST"] = request
        command = [powershell_path, "-NoProfile", "-NonInteractive", "-Command", helper.read_text(encoding="utf-8")]
        synthesis_error = "WinRT synthesis failed without diagnostic output"
        for attempt in range(2):
            synthesis = subprocess.run(
                command, env=environment, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300,
            )
            if synthesis.returncode == 0 and raw_path.is_file() and raw_path.stat().st_size:
                break
            synthesis_error = f"WinRT synthesis attempt {attempt + 1}/2 failed (exit {synthesis.returncode}): {synthesis.stderr[-8000:]}"
            raw_path.unlink(missing_ok=True)
        else:
            raise RuntimeError(synthesis_error)

        filter_chain = (
            "highpass=f=85,deesser=i=0.5:f=0.5,"
            "silenceremove=stop_periods=-1:stop_duration=0.10:"
            "stop_threshold=-50dB:stop_silence=0.05,aresample=48000"
        )
        filtering = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_path),
             "-af", filter_chain, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(filtered_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if filtering.returncode != 0:
            raise RuntimeError(f"FFmpeg filtering failed: {filtering.stderr[-2000:]}")

        measure_filter = "loudnorm=I=-14:TP=-0.5:LRA=7:print_format=json"
        measured = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(filtered_path), "-af", measure_filter, "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if measured.returncode != 0:
            raise RuntimeError(f"FFmpeg loudness measurement failed: {measured.stderr[-2000:]}")
        report = None
        for match in re.finditer(r"\{[^{}]*\}", measured.stderr, re.DOTALL):
            try:
                candidate = json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
            if "input_i" in candidate:
                report = candidate
        if report is None or any(report.get(key) in (None, "-inf", "inf", "nan") for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")):
            raise RuntimeError("FFmpeg returned no finite loudness measurement")
        loudnorm = (
            "loudnorm=I=-14:TP=-0.5:LRA=7:"
            f"measured_I={report['input_i']}:measured_TP={report['input_tp']}:"
            f"measured_LRA={report['input_lra']}:measured_thresh={report['input_thresh']}:"
            f"offset={report['target_offset']}:linear=true:print_format=json"
        )
        normalized = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(filtered_path),
             "-af", loudnorm, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if normalized.returncode != 0 or not target.is_file() or not target.stat().st_size:
            raise RuntimeError(f"FFmpeg loudness normalization failed: {normalized.stderr[-2000:]}")
        return {
            "speaker": speaker, "voice": "Microsoft An", "locale": "vi-VN",
            "sample_rate_hz": 48000, "channels": 1, "format": "pcm_s16le",
            "target_lufs": -14.0, "true_peak_dbtp": -0.5,
            "text": cleaned_text, "text_sha256": hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest(),
            "audio_created": True, "audio_path": str(target), "bytes": target.stat().st_size,
        }
    finally:
        for temporary in (raw_path, filtered_path):
            if temporary is not None:
                temporary.unlink(missing_ok=True)

