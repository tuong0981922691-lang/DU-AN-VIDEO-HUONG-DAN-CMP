import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Dual Host Script Writer - Bộ máy Kịch bản 9 Chương Huy Tưởng & Xuân Công (Đợt 2).

Sinh kịch bản 9 chương cố định đạt ngân sách 4.050 - 5.100 từ, thời lượng >= 900 giây (15 phút),
chuẩn hóa số đọc một lượt c101, tự động giải nghĩa thuật ngữ viết tắt c145, khóa giọng c174.
Cấm in nhãn MAI1/MAI2 lên mặt chữ khán giả.
"""
import hashlib
import json
import re
from typing import Any

ACRONYM_GLOSSARY: dict[str, str] = {
    "MCP": "giao thức kết nối mô hình với công cụ và dữ liệu",
    "ABI": "giao diện nhị phân ứng dụng",
    "PAT": "khóa truy cập cá nhân phân quyền tinh",
    "OAuth": "chuẩn ủy quyền truy cập mở",
    "VRAM": "bộ nhớ đồ họa chuyên dụng trên card màn hình",
    "LUFS": "đơn vị đo độ to âm thanh chuẩn phát sóng",
}

_COMBINED_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_.,-])(?:(?P<th_head>\d{1,3}),(?P<th_tail>\d{3})(?!\d)|(?P<dec_head>\d+)\.(?P<dec_tail>\d+)(?![.\d]))"
)

CHAPTER_DEFINITIONS: list[dict[str, Any]] = [
    {
        "chapter_no": 1,
        "title": "Khởi động & Đặt bài toán thực tế",
        "primary_host": "Huy Tưởng",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 2,
        "title": "Bức tranh kiến trúc & Bối cảnh kỹ thuật",
        "primary_host": "Xuân Công",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 3,
        "title": "Khảo sát công cụ & Nguồn tài liệu gốc",
        "primary_host": "Huy Tưởng",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 4,
        "title": "Mổ xẻ thông số & Bảng đo thực nghiệm AI",
        "primary_host": "Xuân Công",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 5,
        "title": "Cài đặt & Cấu hình từng bước trên máy cá nhân",
        "primary_host": "Huy Tưởng",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 6,
        "title": "Thực thi lệnh & Bắt bệnh thực chiến",
        "primary_host": "Xuân Công",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 7,
        "title": "Tối ưu hóa hiệu năng & Chiến lược chi phí $0",
        "primary_host": "Huy Tưởng",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 8,
        "title": "Đối chiếu an toàn & Chống rò rỉ dữ liệu riêng tư",
        "primary_host": "Xuân Công",
        "min_words": 450,
        "min_sec": 100,
    },
    {
        "chapter_no": 9,
        "title": "Tổng kết hệ thống & Lộ trình tự động hóa tương lai",
        "primary_host": "Huy Tưởng và Xuân Công",
        "min_words": 450,
        "min_sec": 100,
    },
]


def normalize_vietnamese_numbers(text: str) -> tuple[str, list[str]]:
    """Chuẩn hóa dấu phân cách hàng nghìn (3,375 -> 3.375) và số thập phân (4.1% -> 4,1%) một lượt (c101).

    Bảo toàn tên phiên bản gắn liền với chữ La-tinh (ví dụ 'DeepSeek-V3.2', 'Python 3.12.1', 'GLM-5.3-Flash')
    và cảnh báo cụm số nhập nhằng độ lớn '1,753 tỷ' (V-812 & V-825).
    """
    if not text:
        return "", []

    ambiguous_warnings: list[str] = []
    for match in re.finditer(r"\b(\d,\d{3})\s+(tỷ|triệu|nghìn)\b", text, flags=re.IGNORECASE):
        ambiguous_warnings.append(match.group(0))

    def _replace_match(m: re.Match[str]) -> str:
        start, end = m.span()
        left_window = text[max(0, start - 12) : start]
        right_window = text[end : min(len(text), end + 12)]

        if m.group("th_head") is not None:
            if re.search(r"[A-Za-z]-\d*$", left_window):
                return m.group(0)
            if re.match(r"^\s+(tỷ|triệu|nghìn)\b", right_window, flags=re.IGNORECASE):
                return m.group(0)
            return f"{m.group('th_head')}.{m.group('th_tail')}"

        if re.search(r"[A-Za-z][A-Za-z0-9_-]*$", left_window) or re.match(r"^-[A-Za-z]", right_window):
            return m.group(0)
        if re.search(r"\b(?:v|phiên bản|Python|Ubuntu)\s*$", left_window, flags=re.IGNORECASE):
            return m.group(0)
        return f"{m.group('dec_head')},{m.group('dec_tail')}"

    normalized = _COMBINED_NUMBER_RE.sub(_replace_match, text)
    return normalized, ambiguous_warnings


def annotate_first_acronym_mentions(text: str) -> tuple[str, int]:
    """Tự động chèn '- tức ...' giải nghĩa thuật ngữ viết tắt kỹ thuật ở lần xuất hiện đầu tiên (c145)."""
    if not text:
        return "", 0

    inserted = 0
    out = text
    for acronym, meaning in ACRONYM_GLOSSARY.items():
        if f"{acronym} - tức " in out or f"{acronym} — tức " in out:
            continue
        pattern = re.compile(rf"(?<!\w)({re.escape(acronym)})(?!\w)")
        match = pattern.search(out)
        if not match:
            continue
        end_pos = match.end()
        tail = out[end_pos : end_pos + 15]
        if re.match(r"^\.\w", tail):
            continue
        replacement = f"{acronym} - tức {meaning}"
        out = out[: match.start()] + replacement + out[end_pos:]
        inserted += 1

    return out, inserted


def create_voice_script_lock(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a canonical lock from validated chapter text and positive integer durations."""
    if not isinstance(chapters, list) or len(chapters) != 9:
        raise ValueError("Khóa c174 của kịch bản yêu cầu đúng 9 chương")

    canonical_rows = []
    total_sec = 0
    total_words = 0
    for idx, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            raise ValueError(f"Chương {idx} phải là object")
        excerpt = str(chapter.get("dialogue_excerpt") or chapter.get("text") or "").strip()
        if not excerpt:
            raise ValueError(f"Chương {idx} thiếu văn bản đọc")
        duration = chapter.get("duration_sec")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            raise ValueError(f"Thời lượng chương {idx} phải là số nguyên dương")
        chapter_no = chapter.get("chapter_no")
        if isinstance(chapter_no, bool) or not isinstance(chapter_no, int) or chapter_no != idx:
            raise ValueError(f"Số thứ tự chương {idx} phải đúng thứ tự 1–9")
        speaker = str(chapter.get("speaker") or "").strip()
        if not speaker:
            raise ValueError(f"Chương {idx} thiếu người đọc")

        words = len(excerpt.split())
        total_sec += duration
        total_words += words
        canonical_rows.append(
            {
                "chapter_no": chapter_no,
                "speaker": speaker,
                "duration_sec": duration,
                "text_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            }
        )

    master_digest = hashlib.sha256(
        json.dumps(canonical_rows, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "locked": True,
        "master_sha256": master_digest,
        "total_duration_sec": total_sec,
        "total_words": total_words,
        "meets_15min_floor": total_sec >= 900,
        "chapters_locked": canonical_rows,
    }


def verify_voice_lock_before_render(
    lock_record: dict[str, Any], current_chapters: list[dict[str, Any]], visual_mode: str = "c172_hybrid"
) -> tuple[bool, str]:
    """Fail closed unless the complete lock record matches validated current chapters."""
    if visual_mode != "c172_hybrid":
        return False, "KhongDatChuan: Cấm lùi về đồ họa vẽ tay cũ (C2-200 niêm phong)"
    if not isinstance(lock_record, dict):
        return False, "Thiếu hoặc sai hồ sơ khóa giọng c174"

    try:
        recomputed = create_voice_script_lock(current_chapters)
        recorded_json = json.dumps(lock_record, ensure_ascii=False, sort_keys=True, allow_nan=False)
        recomputed_json = json.dumps(recomputed, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as error:
        return False, f"Dữ liệu khóa giọng c174 không hợp lệ: {error}"
    if recorded_json != recomputed_json:
        return False, "Lệch khóa giọng c174: Hồ sơ không khớp dữ liệu chương đã tính lại (V-953)"

    if not recomputed["meets_15min_floor"]:
        return False, f"Thời lượng {recomputed['total_duration_sec']}s dưới sàn cứng 900s (15 phút)"

    return True, "OK"


class DualHostScriptWriter:
    """Bộ máy tạo kịch bản 9 chương Huy Tưởng & Xuân Công chuẩn phát sóng >15 phút."""

    def __init__(self) -> None:
        self.chapters_blueprint = CHAPTER_DEFINITIONS

    def validate_script_text(self, text: str) -> tuple[bool, list[str]]:
        """Kiểm tra không chứa nhãn máy nội bộ MAI1/MAI2."""
        issues = []
        if re.search(r"\bMAI[12]\b", text):
            issues.append("Chứa nhãn máy nội bộ MAI1/MAI2 trên mặt chữ khán giả")
        return len(issues) == 0, issues

    def build_nine_chapters_script(
        self,
        topic_title: str,
        evidence_pack: dict[str, Any],
        chapter_paragraphs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a nine-chapter script and enforce its chapter/total word budgets."""
        if not isinstance(topic_title, str) or not topic_title.strip():
            raise ValueError("Chủ đề kịch bản không được để trống")
        if not isinstance(chapter_paragraphs, list) or len(chapter_paragraphs) != 9:
            actual_count = len(chapter_paragraphs) if isinstance(chapter_paragraphs, list) else "invalid"
            raise ValueError(f"Kịch bản bắt buộc đúng 9 chương cố định, hiện có {actual_count}")

        processed_chapters: list[dict[str, Any]] = []
        total_words = 0
        total_duration = 0

        for idx, (defn, para) in enumerate(zip(self.chapters_blueprint, chapter_paragraphs), start=1):
            if not isinstance(para, dict):
                raise ValueError(f"Chương {idx} phải là object")
            raw_text = para.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                raise ValueError(f"Chương {idx} thiếu văn bản")
            raw_text = raw_text.strip()
            ok_valid, issues = self.validate_script_text(raw_text)
            if not ok_valid:
                raise ValueError(f"Chương {idx} vi phạm: {'; '.join(issues)}")

            norm_text, _ = normalize_vietnamese_numbers(raw_text)
            final_text, _ = annotate_first_acronym_mentions(norm_text)

            word_cnt = len(final_text.split())
            if word_cnt < defn["min_words"]:
                raise ValueError(
                    f"Chương {idx} có {word_cnt} từ; yêu cầu tối thiểu {defn['min_words']} từ"
                )
            requested_duration = para.get("duration_sec")
            if requested_duration is None:
                duration_sec = max(defn["min_sec"], int(word_cnt / 4.2))
            elif isinstance(requested_duration, int) and not isinstance(requested_duration, bool) and requested_duration > 0:
                duration_sec = requested_duration
            else:
                raise ValueError(f"Thời lượng chương {idx} phải là số nguyên dương")

            total_words += word_cnt
            total_duration += duration_sec

            processed_chapters.append(
                {
                    "chapter_no": idx,
                    "title": defn["title"],
                    "speaker": defn["primary_host"],
                    "word_budget": word_cnt,
                    "duration_sec": duration_sec,
                    "dialogue_excerpt": final_text,
                }
            )

        if total_words > 5100:
            raise ValueError(f"Kịch bản có {total_words} từ; ngân sách tối đa là 5100 từ")

        lock_record = create_voice_script_lock(processed_chapters)
        return {
            "topic_title": topic_title,
            "topic_id": evidence_pack.get("topic_id", "unnamed_topic"),
            "total_words": total_words,
            "total_duration_sec": total_duration,
            "meets_floor": total_duration >= 900,
            "within_word_budget": 4050 <= total_words <= 5100,
            "chapters": processed_chapters,
            "voice_lock": lock_record,
        }
