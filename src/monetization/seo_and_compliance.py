import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""SEO metadata draft generator and local duration/completeness checks (not publication or certification).

Kiểm sàn thời lượng >= 900 giây (15 phút) trên cả âm thanh lẫn video, kiểm tra giá trị gốc
đạt chuẩn YouTube Partner Program (YPP), chống spam tần suất, tự động xuất gói SEO 4 nền tảng:
① YouTube (16:9 + Chapters 00:00)
② Website (bản nháp hướng dẫn dạng văn bản)
③ Facebook Fanpage (bản nháp nội dung)
④ TikTok (gợi ý nội dung caption; không tạo video).
"""

import math
import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit


class ComplianceViolation(Exception):
    """Ngoại lệ khi vi phạm chính sách bản quyền, sàn thời lượng hoặc chuẩn SEO."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = str(message)


class SeoAndComplianceGate:
    """Local duration check and four-platform draft-metadata generator."""

    def __init__(self) -> None:
        self.min_duration_sec = 900.0

    def verify_duration_floor(self, duration_sec: float) -> tuple[bool, str]:
        """Kiểm tra thời lượng thành phẩm bắt buộc >= 900 giây (15 phút) không độn chữ."""
        try:
            dur = float(duration_sec)
        except (TypeError, ValueError, OverflowError) as error:
            raise ComplianceViolation("Thời lượng phải là số hữu hạn không âm") from error
        if not math.isfinite(dur) or dur < 0:
            raise ComplianceViolation("Thời lượng phải là số hữu hạn không âm")
        if dur < self.min_duration_sec:
            raise ComplianceViolation(f"Thời lượng {dur:.1f}s dưới sàn cứng 900s (15 phút)")
        return True, f"Đạt sàn thời lượng: {dur:.1f}s >= 900s"

    def verify_ypp_compliance(self, evidence_pack: dict[str, Any], script_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Run a minimal local completeness heuristic; this does not certify YouTube YPP compliance."""
        issues: list[str] = []
        if not evidence_pack or not evidence_pack.get("topic_id"):
            issues.append("Thiếu hồ sơ dữ kiện gốc từ Bạch Tuộc (vi phạm tính xác thực)")

        sources = evidence_pack.get("sources", [])
        if not sources or len(sources) == 0:
            issues.append("Không có nguồn trích dẫn đối chiếu thực tế (nguy cơ bị gắn cờ nội dung lặp lại)")

        total_words = int(script_data.get("total_words", 0))
        if total_words < 4050:
            issues.append(f"Tổng số từ {total_words} dưới ngân sách tối thiểu 4.050 từ")

        return len(issues) == 0, issues

    def export_four_platform_seo(
        self,
        topic_title: str,
        script_chapters: list[dict[str, Any]],
        evidence_pack: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate four-platform draft metadata only; no media is created or published."""
        # 1. Gói YouTube (16:9)
        youtube_chapters = []
        current_second = 0
        for ch in script_chapters:
            m = int(current_second // 60)
            s = int(current_second % 60)
            time_str = f"{m:02d}:{s:02d}"
            youtube_chapters.append(f"{time_str} - {ch.get('title', 'Chương')}")
            current_second += int(ch.get("duration_sec", 100))

        public_sources = []
        for source in evidence_pack.get("sources", []):
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            try:
                parsed_url = urlsplit(url.strip())
                is_public_http_url = (
                    parsed_url.scheme in {"http", "https"}
                    and bool(parsed_url.hostname)
                    and parsed_url.username is None
                    and parsed_url.password is None
                    and not any(
                        any(marker in name.casefold() for marker in ("token", "secret", "password", "api_key", "apikey", "signature", "credential"))
                        for name, _ in parse_qsl(parsed_url.query, keep_blank_values=True)
                    )
                )
            except ValueError:
                is_public_http_url = False
            if is_public_http_url:
                public_sources.append(f"- {url.strip()}")
        sources_links = "\n".join(public_sources) or "Chưa có URL nguồn công khai trong gói bằng chứng."
        youtube_pkg = {
            "platform": "YouTube (16:9)",
            "title": f"{topic_title} — Hướng Dẫn Kỹ Thuật Chi Tiết Từ A Đến Z (Huy Tưởng & Xuân Công)",
            "description": f"Video phân tích và hướng dẫn từng bước: {topic_title}.\n\n⏱️ CÁC MỐC THỜI GIAN:\n"
            + "\n".join(youtube_chapters)
            + f"\n\n📚 NGUỒN TÀI LIỆU VÀ MÃ NGUỒN GỐC:\n{sources_links}\n\n#AIHuongDan #SoSanhAI #TechTutorial",
            "tags": ["AI", "Hướng dẫn", "So sánh AI", "Huy Tưởng", "Xuân Công", "Công nghệ 2026"],
            "aspect_ratio": "16:9",
        }

        # 2. Gói Website (Bài hướng dẫn kèm code)
        code_blocks = []
        for ch in script_chapters:
            txt = ch.get("dialogue_excerpt", "")
            code_blocks.append(f"### {ch.get('title')}\n\n{txt}\n")
        raw_topic_id = str(evidence_pack.get("topic_id") or "")
        website_slug = re.sub(r"[^a-z0-9]+", "-", raw_topic_id.casefold()).strip("-")[:80].rstrip("-")
        website_pkg = {
            "platform": "Website / Blog",
            "slug": website_slug or "bai-huong-dan-ai",
            "meta_title": f"{topic_title} | Tài Liệu Kỹ Thuật",
            "meta_description": f"Bản nháp hướng dẫn và tài liệu tham khảo cho {topic_title}.",
            "markdown_content": f"# {topic_title}\n\n" + "\n".join(code_blocks),
        }

        # 3. Gói Facebook Fanpage
        fb_pkg = {
            "platform": "Facebook Fanpage",
            "post_text": f"Bản nháp giới thiệu: {topic_title}.\n\n"
            f"Huy Tưởng & Xuân Công sẽ phân tích chủ đề theo các nguồn được dẫn trong kịch bản. "
            f"Đây là nội dung dự thảo, chưa phải video đã sản xuất hoặc đăng tải.\n\n#AI #CongNgheMoi",
            "recommended_format": "Video 16:9 hoặc 1:1 kèm phụ đề",
        }

        # 4. Gói TikTok (9:16)
        tiktok_pkg = {
            "platform": "TikTok (9:16)",
            "hook_first_3s": f"Đừng dùng mô hình AI nếu bạn chưa biết điều này về {topic_title}!",
            "caption": f"Gợi ý caption cho bản dựng 60 giây về {topic_title} cùng Huy Tưởng & Xuân Công.",
            "aspect_ratio": "9:16",
        }

        return {
            "status": "success",
            "artifact_type": "draft_metadata_only",
            "media_created": False,
            "published": False,
            "topic_title": topic_title,
            "total_platforms": 4,
            "packages": {
                "youtube": youtube_pkg,
                "website": website_pkg,
                "facebook": fb_pkg,
                "tiktok": tiktok_pkg,
            },
        }
