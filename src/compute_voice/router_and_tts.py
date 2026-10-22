import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Prototype provider routing metadata and voice-script locks; no inference or audio is generated.

Provider availability and pricing are unverified. Voice methods return descriptors, not audio files.
"""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


class InferenceRouter:
    """Prototype tier selector; provider availability and pricing are unverified."""

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        if workspace_root is not None:
            self.root = Path(workspace_root)
        else:
            self.root = Path(__file__).resolve().parents[2]
        self.tiers_status = {
            1: {"name": "Cloudflare Workers AI", "free_quota": "unverified", "available": False, "status": "unverified"},
            2: {"name": "Groq", "free_quota": "unverified", "available": False, "status": "unverified"},
            3: {"name": "Gemini", "free_quota": "unverified", "available": False, "status": "unverified"},
            4: {"name": "Ollama Local GPU/CPU", "free_quota": "unverified", "available": False, "status": "unverified"},
        }

    def check_ollama_vram(self, api_response: dict[str, Any] | None = None) -> dict[str, Any]:
        """Interpret a supplied Ollama /api/ps response; this method makes no network request."""
        if api_response is None:
            return {"running": False, "size_vram_bytes": 0, "processor": "unverified", "vram_mb": 0.0, "status": "unverified"}
        models = api_response.get("models", [])
        if not models:
            return {
                "running": True,
                "size_vram_bytes": 0,
                "processor": "unverified",
                "vram_mb": 0.0,
                "status": "unverified",
            }
        top = models[0]
        if not isinstance(top, dict) or "size_vram" not in top:
            return {
                "running": True,
                "size_vram_bytes": 0,
                "processor": "unverified",
                "vram_mb": 0.0,
                "status": "unverified",
            }
        vram_bytes = int(top["size_vram"])
        if vram_bytes < 0:
            raise ValueError("Ollama size_vram must not be negative")
        return {
            "running": True,
            "model": top.get("name", "unknown"),
            "size_vram_bytes": vram_bytes,
            "vram_mb": round(vram_bytes / (1024 * 1024), 2),
            "processor": "GPU" if vram_bytes > 0 else "CPU",
        }

    def dispatch(self, prompt: str, preferred_tier: int = 1) -> dict[str, Any]:
        """Return a deterministic routing preview without contacting any provider."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt suy luận không được để trống")

        tier_chosen = preferred_tier if preferred_tier in self.tiers_status else 1
        tier_info = self.tiers_status[tier_chosen]

        return {
            "tier": tier_chosen,
            "provider": None,
            "candidate_provider": tier_info["name"],
            "connected": False,
            "cost_usd": None,
            "quota_type": "unverified",
            "prompt_hash": hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16],
            "status": "simulated_no_provider_call",
        }


class VoiceEngine48k:
    """Prototype voice settings and lock metadata; no audio processing is performed."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).resolve().parents[2] / "du_lieu" / "tam_me" / "tts_cache_48k"

    def apply_deesser_filter(self, high_freq_energy: float) -> tuple[float, float]:
        """Bộ lọc De-esser động 5,5 - 20 kHz: triệt tiêu 66% năng lượng chói gắt của âm x/s."""
        attenuation_ratio = 0.66
        attenuated_energy = high_freq_energy * (1.0 - attenuation_ratio)
        return attenuated_energy, attenuation_ratio

    def calculate_edge_fade(self, sample_rate: int = 48000, fade_ms: float = 12.0) -> int:
        """Tính số mẫu âm thanh áp dụng fade biên 12ms chống tiếng bụp tại điểm nối."""
        return int(sample_rate * (fade_ms / 1000.0))

    def synthesize_speech_segment(
        self,
        speaker: str,
        text: str,
        target_duration_sec: float,
    ) -> dict[str, Any]:
        """Describe a planned voice segment and attach a text hash; no TTS call or audio file is produced."""
        cleaned_text = str(text or "").strip()
        if not cleaned_text:
            raise ValueError("Văn bản phát âm không được để trống")

        text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
        fade_samples = self.calculate_edge_fade(sample_rate=48000, fade_ms=12.0)
        _, deesser_ratio = self.apply_deesser_filter(high_freq_energy=1.0)

        segment = {
            "speaker": speaker,
            "sample_rate": 48000,
            "channels": 1,  # Mono
            "target_lufs": -14.0,
            "true_peak_dbtp": -1.0,
            "status": "metadata_only",
            "audio_created": False,
            "deesser_applied": False,
            "deesser_planned": True,
            "deesser_attenuation": deesser_ratio,
            "edge_fade_samples": fade_samples,
            "duration_sec": float(target_duration_sec),
            "text": cleaned_text,
            "text_sha256": text_hash,
            "cache_key": f"tts_48k_{text_hash[:16]}",
        }
        return segment


def create_c174_voice_lock(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Hash the actual segment text and validate finite, nonnegative durations."""
    if not isinstance(segments, list) or not segments:
        raise ValueError("Danh sách đoạn âm thanh rỗng, không thể tạo khóa c174")

    manifest = []
    durations = []
    for idx, seg in enumerate(segments, start=1):
        if not isinstance(seg, dict):
            raise ValueError(f"Đoạn âm thanh {idx} phải là object")
        text = str(seg.get("text") or "").strip()
        if not text:
            raise ValueError(f"Đoạn âm thanh {idx} thiếu văn bản")
        try:
            duration = float(seg.get("duration_sec", 0.0))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Thời lượng đoạn {idx} không hợp lệ") from error
        if not math.isfinite(duration) or duration < 0:
            raise ValueError(f"Thời lượng đoạn {idx} phải hữu hạn và không âm")
        durations.append(duration)
        manifest.append(
            {
                "index": idx,
                "speaker": str(seg.get("speaker") or "Unknown"),
                "duration_sec": duration,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )

    try:
        total_duration = math.fsum(durations)
    except OverflowError as error:
        raise ValueError("Tổng thời lượng vượt phạm vi hữu hạn") from error
    if not math.isfinite(total_duration):
        raise ValueError("Tổng thời lượng phải hữu hạn")
    canonical_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    master_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    return {
        "lock_code": "c174_khoa_giong",
        "master_sha256": master_sha256,
        "total_segments": len(manifest),
        "total_duration_sec": total_duration,
        "meets_900s_floor": total_duration >= 900.0,
        "manifest": manifest,
    }


def verify_c174_lock(lock_record: dict[str, Any], current_segments: list[dict[str, Any]]) -> tuple[bool, str]:
    """Verify c174 against current text and finite audio-duration metadata."""
    if not isinstance(lock_record, dict) or lock_record.get("lock_code") != "c174_khoa_giong":
        return False, "Thiếu hoặc sai hồ sơ khóa giọng c174"
    recorded_digest = lock_record.get("master_sha256")
    if not isinstance(recorded_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_digest):
        return False, "Thiếu hoặc sai mã băm khóa giọng c174"

    try:
        recomputed = create_c174_voice_lock(current_segments)
    except (TypeError, ValueError) as error:
        return False, f"Dữ liệu khóa giọng c174 không hợp lệ: {error}"
    if recomputed["master_sha256"] != recorded_digest:
        return False, "Lệch khóa giọng c174: Kịch bản bị sửa sau khi đã thu giọng (V-953)"

    try:
        recorded_json = json.dumps(lock_record, ensure_ascii=False, sort_keys=True, allow_nan=False)
        recomputed_json = json.dumps(recomputed, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False, "Voice lock record is not valid JSON"
    if recorded_json != recomputed_json:
        return False, "Voice lock record does not match the recomputed manifest and duration"

    if not recomputed["meets_900s_floor"]:
        return False, f"Thời lượng âm thanh {recomputed['total_duration_sec']}s dưới sàn cứng 900s"

    return True, "OK"