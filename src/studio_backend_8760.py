import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""CMP Local Dashboard - G5 review and metadata prototype (not a media renderer).

Cung cấp dashboard cục bộ và bản xem trước metadata tại http://127.0.0.1:8765:
- Khóa nguyên tử (Atomic Lock) chống bấm đúp chạy đè tiến trình gây phình ổ đĩa.
- Chặn tuyệt đối mở tệp dạng file:// (chỉ chấp nhận giao thức HTTP localhost an toàn).
- Nối kết toàn bộ 6 trụ cột: Bạch Tuộc -> Kịch Bản -> GPU/Voice 48k -> Đồ Họa c172 -> SEO b98.
"""

import argparse
import hashlib
import http.server
import ipaddress
import json
import re
import threading
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.compute_voice.router_and_tts import (
    InferenceRouter,
    VoiceEngine48k,
    create_c174_voice_lock,
    verify_c174_lock,
)
from src.gates.b87_soi_day_than_kinh import audit_neural_wiring
from src.gates.kiem_dau_phien import scan_text_for_secrets
from src.monetization.seo_and_compliance import ComplianceViolation, SeoAndComplianceGate
from src.octopus.tech_scout import (
    OctopusTechScout,
    verify_evidence_pack,
    verify_local_evidence_sources,
)
from src.script_engine.dual_host_writer import (
    DualHostScriptWriter,
    verify_voice_lock_before_render,
)
from src.visual_engine.hybrid_c172_renderer import HybridC172Renderer, KhongDatChuan

MASTER_COMMAND_MAX_BYTES = 45 * 1024 - 1
MASTER_COMMAND_SOURCES = (
    "BAT_DAU.md",
    ".gitignore",
    "src/gates/kiem_dau_phien.py",
    "src/gates/quet_vo_rong.py",
    "src/gates/chay_10_phep_dap_do.py",
    "tests/test_dap_do_10_phep.py",
)
DEFAULT_PORT = 8765
MEDIA_ASSET_PATHS = {
    "/media/video": Path("D:\\khoa\\04_DO_HOA_VA_AM_THANH\\G5_whiteboard_hand_rig_c2_45s.mp4"),
    "/media/audio": Path(__file__).resolve().parents[1]
    / "du_lieu" / "tam_me" / "g4_g5_mau_3_phut" / "G4_audio_dien_cam_van_nguoi_3_phut.wav",
}
MEDIA_CHUNK_SIZE = 64 * 1024


def parse_single_byte_range(header: str, file_size: int) -> tuple[int, int] | None:
    """Parse one HTTP byte range; reject malformed and multi-range requests."""
    if not header:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if match is None or file_size <= 0:
        raise ValueError("Invalid or unsatisfiable byte range")
    first, last = match.groups()
    if not first and not last:
        raise ValueError("Invalid or unsatisfiable byte range")
    if not first:
        suffix_length = int(last)
        if suffix_length <= 0:
            raise ValueError("Invalid or unsatisfiable byte range")
        return max(0, file_size - suffix_length), file_size - 1
    start = int(first)
    end = min(int(last), file_size - 1) if last else file_size - 1
    if start >= file_size or end < start:
        raise ValueError("Invalid or unsatisfiable byte range")
    return start, end


class MasterCommandBuildError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def is_trusted_local_request(client_address: str, host_header: str, server_port: int) -> bool:
    """Require a loopback peer and an exact local Host authority."""
    try:
        if not ipaddress.ip_address(client_address).is_loopback:
            return False
        accepted_hosts = {
            f"127.0.0.1:{server_port}",
            f"localhost:{server_port}",
            f"[::1]:{server_port}",
        }
        return host_header in accepted_hosts
    except (ValueError, TypeError):
        return False


def build_master_all_in_one_command_prompt(workspace_root: Path | str | None = None) -> str:
    """Build a bounded, local-only prompt from explicitly allowlisted safe files."""
    root = Path(workspace_root) if workspace_root else Path(__file__).resolve().parents[1]
    root = root.resolve()
    sections = []
    total_source_bytes = 0
    for relative_name in MASTER_COMMAND_SOURCES:
        source_path = root / relative_name
        try:
            resolved_path = source_path.resolve(strict=True)
            resolved_path.relative_to(root)
        except (OSError, ValueError) as error:
            raise MasterCommandBuildError(f"Không thể đọc tệp nguồn được cho phép: {relative_name}") from error
        if not resolved_path.is_file():
            raise MasterCommandBuildError(f"Nguồn không phải tệp thông thường: {relative_name}")
        if resolved_path.stat().st_size > MASTER_COMMAND_MAX_BYTES:
            raise MasterCommandBuildError(f"Nguồn vượt giới hạn trước khi đọc: {relative_name}", 413)
        try:
            source_bytes = resolved_path.read_bytes()
            content = source_bytes.decode("utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as error:
            raise MasterCommandBuildError(f"Nguồn không đọc được UTF-8: {relative_name}") from error
        total_source_bytes += len(source_bytes)
        if total_source_bytes > MASTER_COMMAND_MAX_BYTES:
            raise MasterCommandBuildError(
                f"Tổng nguồn vượt giới hạn: {total_source_bytes} byte.", 413
            )
        labels = scan_text_for_secrets(content)
        if labels:
            raise MasterCommandBuildError(
                f"Từ chối tạo lệnh: mẫu bí mật {', '.join(labels)} trong {relative_name}", 422
            )
        digest = hashlib.sha256(source_bytes).hexdigest()
        fence_length = max((len(run) for run in re.findall(r"`+", content)), default=2) + 1
        fence = "`" * max(3, fence_length)
        embedded_content = content if content.endswith(("\n", "\r")) else content + "\n"
        sections.append(
            f"### `{relative_name}` — SHA-256 `{digest}`\n\n{fence}text\n{embedded_content}{fence}\n"
        )

    prompt = "\n\n".join(
        (
            "# SIÊU LỆNH CHỈ HUY C2 — DU-AN-VIDEO-HUONG-DAN-CMP",
            "## I. Bối cảnh và đối chiếu thực tế\n"
            "Đích duy nhất là workspace Windows `E:\\DU-AN-VIDEO-HUONG-DAN-CMP`, quy trình máy cá nhân; "
            "backend hiện tại dùng 127.0.0.1:8765, không có `apex_core` hay cổng 3000. "
            "Không nhầm hoặc truy cập dự án `E:\\TIN_TUC_VIDEO`. Không tuyên bố AI, TTS hay video thật đã chạy: "
            "các module hiện là nguyên mẫu logic/metadata.",
            "## II. Quy trình thi công\n"
            "Đọc hồ sơ bàn giao nội bộ có sẵn trong workspace; xác nhận root, trạng thái và dung lượng trước khi ghi. "
            "Chỉ làm mốc được C2 giao; không tự mở mốc sau, không ghi đè thay đổi có sẵn, không xóa hàng loạt, "
            "không cài/tải/render/gọi dịch vụ khi chưa duyệt.",
            "## III. Nguồn mã được nhúng\n"
            "Các bản chụp UTF-8 trong phần dưới chỉ lấy từ allowlist; mỗi tệp kèm SHA-256. Đây không phải bản sao đầy đủ dự án. "
            "Không bao gồm credential, sổ/yêu cầu nội bộ hay tệp ngoài allowlist. Không đưa prompt này lên repo public.",
            "## IV. Chất lượng và ranh giới\n"
            "TEMP/TMP phải nằm trong thư mục tạm của workspace; khóa và hồ sơ nội bộ không được publish. "
            "Chỉ dùng dịch vụ miễn phí đã xác minh; không dùng credential cũ. Test xanh chỉ chứng minh logic được test, "
            "không chứng minh GPU, provider, TTS, renderer hay xuất video hoạt động thật.",
            "## V. Cổng kiểm tra\n"
            "Chạy từ root với TEMP/TMP trên ổ E: `python src/gates/kiem_dau_phien.py`, "
            "`python src/gates/quet_vo_rong.py`, `python src/gates/chay_10_phep_dap_do.py`, "
            "`python -m pytest tests/ -q`, `python -m compileall -q src tests`. Dừng khi bất kỳ cổng nào đỏ. "
            "Gate đạp đổ phải báo đúng 10 tên và SHA-256 src/tests trước/sau trùng khớp.",
            "## VI. Biên bản bàn giao\n"
            "Báo bằng tiếng Việt: phạm vi; file thay đổi; bằng chứng lệnh/test; dung lượng và số tệp trước/sau; "
            "việc còn thiếu/chặn; bảo mật/chi phí; bước kế tiếp. Nêu rõ chưa làm gì. Không tuyên bố hoàn tất vượt bằng chứng.",
            "## Mã nguồn allowlist\n" + "\n\n".join(sections),
        )
    )
    size = len(prompt.encode("utf-8"))
    if size > MASTER_COMMAND_MAX_BYTES:
        raise MasterCommandBuildError(
            f"Lệnh vượt giới hạn: {size} byte; mức tối đa là {MASTER_COMMAND_MAX_BYTES} byte.", 413
        )
    return prompt


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CMP | G5 Media Review</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --accent: #38bdf8;
            --green: #22c55e;
            --text: #f8fafc;
            --sub: #94a3b8;
            --border: #334155;
        }
        body {
            margin: 0;
            padding: 24px;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        h1 {
            margin: 0;
            font-size: 22px;
            color: var(--accent);
        }
        .badge {
            background: rgba(34, 197, 94, 0.2);
            color: var(--green);
            border: 1px solid var(--green);
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
        }
        .badge.prototype {
            background: rgba(234, 179, 8, 0.15);
            color: #facc15;
            border-color: #eab308;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }
        .card h2 {
            font-size: 16px;
            margin-top: 0;
            color: var(--accent);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }
        ul {
            padding-left: 20px;
            margin: 8px 0;
        }
        li {
            margin-bottom: 6px;
            color: var(--sub);
        }
        li strong {
            color: var(--text);
        }
        .media-review {
            margin: 0 0 24px;
            padding: 24px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
        }
        .media-review h2 { margin: 0 0 6px; font-size: 20px; }
        .media-review > p, .media-item p { color: var(--sub); }
        .media-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
            gap: 24px;
            margin-top: 20px;
        }
        .media-item { min-width: 0; margin: 0; }
        .media-item h3 { margin: 0 0 4px; font-size: 16px; }
        .media-item p { margin: 0 0 12px; font-size: 14px; }
        .media-item video, .media-item audio { display: block; width: 100%; }
        .media-item video { max-height: 60vh; background: #05080d; border-radius: 8px; }
        .media-item audio { margin-top: 20px; }
        button:focus-visible, a:focus-visible, video:focus-visible, audio:focus-visible {
            outline: 3px solid #facc15;
            outline-offset: 3px;
        }
        @media (max-width: 720px) {
            body { padding: 16px; }
            header { align-items: flex-start; gap: 12px; flex-direction: column; }
            .media-grid { grid-template-columns: 1fr; }
            .media-review { padding: 18px; }
            .btn-group { flex-wrap: wrap; }
        }
        .btn-group {
            display: flex;
            gap: 12px;
            margin-top: 16px;
        }
        button {
            background: var(--accent);
            color: #000;
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        button:hover {
            opacity: 0.9;
        }
        pre {
            background: #090d16;
            padding: 12px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 13px;
            color: #a5f3fc;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>XUONG VIDEO HUONG DAN AI | G5 MEDIA REVIEW</h1>
                <small style="color: var(--sub);">Dashboard local: <code>127.0.0.1:8765</code> - loopback only</small>
            </div>
            <div class="badge prototype">G5 SAMPLE - C2 APPROVED, REVIEW PENDING</div>
        </header>

        <section class="media-review" aria-labelledby="media-title">
            <h2 id="media-title">X&#432;&#7903;ng xem duy&#7879;t m&#7851;u G5</h2>
            <p>M&#7851;u local &#273;&#227; &#273;&#432;&#7907;c C2 ph&#234; duy&#7879;t. Ph&#225;t t&#7841;i ch&#7895;, kh&#244;ng t&#7843;i l&#234;n d&#7883;ch v&#7909; ngo&#224;i.</p>
            <div class="media-grid">
                <figure class="media-item">
                    <figcaption>
                        <h3>Video Whiteboard c&#225;nh tay th&#7853;t</h3>
                        <p>V-900 | 1280 x 720 | 12 FPS | MP4</p>
                    </figcaption>
                    <video controls preload="metadata" playsinline aria-label="Video m&#7851;u Whiteboard G5">
                        <source src="/media/video" type="video/mp4">
                        Tr&#236;nh duy&#7879;t kh&#244;ng h&#7895; tr&#7907; ph&#225;t video MP4.
                    </video>
                </figure>
                <figure class="media-item">
                    <figcaption>
                        <h3>B&#7843;n thu VieNeu MAI1 / MAI2</h3>
                        <p>233.40 gi&#226;y | WAV | 48 kHz | mono</p>
                    </figcaption>
                    <audio controls preload="metadata" aria-label="B&#7843;n thu VieNeu MAI1 MAI2">
                        <source src="/media/audio" type="audio/wav">
                        Tr&#236;nh duy&#7879;t kh&#244;ng h&#7895; tr&#7907; ph&#225;t WAV.
                    </audio>
                </figure>
            </div>
        </section>

        <div class="grid">
            <div class="card">
                <h2>📊 Trạng Thái Hệ Thống & Ổ Đĩa</h2>
                <ul>
                    <li><strong>Vị trí xưởng:</strong> <code>E:\\DU-AN-VIDEO-HUONG-DAN-CMP</code></li>
                    <li><strong>Dung lượng ổ E:</strong> Đo lại tại mỗi lần tiền kiểm</li>
                    <li><strong>Thư mục tạm:</strong> <code>du_lieu\\tam_me</code> (Không ghi ổ C)</li>
                    <li><strong>Sổ việc SO_VIEC.md:</strong> Gate kiểm trần &le; 400 dòng</li>
                    <li><strong>Bảo mật khóa:</strong> <code>du_lieu\\khoa\\</code> (Chặn Git 100%)</li>
                </ul>
            </div>

            <div class="card">
                <h2>⚡ Trạng Thái Tích Hợp AI/GPU — Chưa Xác Minh</h2>
                <ul>
                    <li><strong>Tầng 1:</strong> Workers AI chưa xác minh tài khoản/quota; chưa gọi API</li>
                    <li><strong>Tầng 2:</strong> Groq chưa xác minh gói miễn phí; không bật</li>
                    <li><strong>Tầng 3:</strong> Gemini chưa cấu hình/xác minh khóa; không dùng khóa trong hồ sơ</li>
                    <li><strong>Tầng 4:</strong> Ollama/GPU cục bộ chưa được xác minh trên máy</li>
                </ul>
            </div>

            <div class="card">
                <h2>🎙️ Giọng Đọc 48kHz & Đồ Họa 3 Lớp</h2>
                <ul>
                    <li><strong>Gi&#7885;ng m&#7851;u &#273;&#227; duy&#7879;t:</strong> VieNeu MAI1 (Huy T&#432;&#7903;ng) &amp; MAI2 (Xu&#226;n C&#244;ng)</li>
                    <li><strong>Sàn thời lượng:</strong> &ge; 900 giây (15 phút) · 4.050 - 5.100 từ</li>
                    <li><strong>Audio m&#7851;u:</strong> WAV 48kHz mono, 233.40 gi&#226;y; nghe t&#7841;i player ph&#237;a tr&#234;n</li>
                    <li><strong>Khóa giọng:</strong> c174_khoa_giong (SHA-256 bất biến)</li>
                    <li><strong>Video m&#7851;u:</strong> Whiteboard V-900; xem t&#7841;i player ph&#237;a tr&#234;n</li>
                    <li><strong>Niêm phong:</strong> C2-200 (Cấm vẽ tay bảng kẻ ô)</li>
                </ul>
            </div>

            <div class="card">
                <h2>🌐 Xuất Bản SEO 4 Nền Tảng (b98)</h2>
                <ul>
                    <li><strong>YouTube (16:9):</strong> Chapters 00:00 + Nguồn tài liệu</li>
                    <li><strong>Website / b&#225;n h&#224;ng:</strong> Ngo&#224;i ph&#7841;m vi x&#432;&#7903;ng desktop hi&#7879;n t&#7841;i</li>
                    <li><strong>Facebook Fanpage:</strong> Bài tóm tắt tương tác</li>
                    <li><strong>TikTok (9:16):</strong> Video ngắn 60s điểm nhấn</li>
                </ul>
            </div>
        </div>

        <div class="card">
            <h2>📋 Siêu Lệnh Chỉ Huy C2 — All-In-One</h2>
            <p style="color: var(--sub); margin: 0 0 12px 0;">Tạo lệnh tại chỗ từ danh sách mã nguồn an toàn; không đọc khóa/sổ nội bộ, không ghi tệp vào đĩa. Giới hạn dưới 45 KiB.</p>
            <div class="btn-group">
                <button onclick="copyMasterCommand()">Copy Siêu Lệnh</button>
                <button onclick="downloadMasterCommand()">Tải Siêu Lệnh (.MD)</button>
            </div>
            <pre id="master-command-status">Lệnh chỉ được tạo khi bạn bấm nút.</pre>
        </div>

        <div class="card">
            <h2>🔬 Bảng Mạch Dây Thần Kinh b87 & 10 Phép Đạp Đổ</h2>
            <p style="color: var(--sub); margin: 0 0 12px 0;">b87 kiểm tra cấu trúc liên kết; kết quả test logic không chứng minh inference, TTS hay render thực.</p>
            <div class="btn-group">
                <button onclick="checkHealth()">Kiểm Tra Trạng Thái API (b87)</button>
            </div>
            <pre id="output">Use the button above to check the local API.</pre>
        </div>
    </div>

    <script>
        function checkHealth() {
            document.getElementById('output').innerText = 'Đang truy vấn backend...';
            fetch('/api/health')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('output').innerText = JSON.stringify(data, null, 2);
                })
                .catch(err => {
                    document.getElementById('output').innerText = 'Lỗi truy vấn: ' + err;
                });
        }
        async function fetchMasterCommand() {
            const response = await fetch('/api/master-command');
            const body = await response.text();
            if (!response.ok) throw new Error(body || ('HTTP ' + response.status));
            return body;
        }

        async function copyMasterCommand() {
            const status = document.getElementById('master-command-status');
            try {
                const command = await fetchMasterCommand();
                await navigator.clipboard.writeText(command);
                status.innerText = 'Đã sao chép lệnh (' + new TextEncoder().encode(command).length + ' byte).';
            } catch (error) {
                status.innerText = 'Không thể tạo/sao chép: ' + error;
            }
        }

        async function downloadMasterCommand() {
            const status = document.getElementById('master-command-status');
            let objectUrl;
            try {
                const command = await fetchMasterCommand();
                objectUrl = URL.createObjectURL(new Blob([command], { type: 'text/markdown;charset=utf-8' }));
                const link = document.createElement('a');
                link.href = objectUrl;
                link.download = 'SIEU_LENH_CHI_HUY_C2_ALL_IN_ONE.md';
                link.click();
                status.innerText = 'Đã tạo gói tải (' + new TextEncoder().encode(command).length + ' byte).';
            } catch (error) {
                status.innerText = 'Không thể tạo/tải: ' + error;
            } finally {
                if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
            }
        }
    </script>
</body>
</html>
"""


class StudioBackend8760:
    """Local dashboard backend for prototype workflow metadata on port 8765."""

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.root = Path(workspace_root) if workspace_root else Path(__file__).resolve().parents[1]
        self.host = "127.0.0.1"
        self.port = DEFAULT_PORT
        self._lock = threading.Lock()
        self._is_busy = False

        # Khởi tạo các động cơ
        self.scout = OctopusTechScout(self.root)
        self.script_writer = DualHostScriptWriter()
        self.router = InferenceRouter(self.root)
        self.voice_engine = VoiceEngine48k()
        self.renderer = HybridC172Renderer()
        self.compliance_gate = SeoAndComplianceGate()

    def validate_request_protocol(self, protocol_or_url: str) -> bool:
        """Accept only HTTP URLs for this local dashboard instance."""
        try:
            parsed = urlsplit(str(protocol_or_url or "").strip())
            valid_local_url = (
                parsed.scheme.lower() == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
                and parsed.port == self.port
                and parsed.username is None
                and parsed.password is None
                and not parsed.fragment
            )
        except ValueError:
            valid_local_url = False
        if not valid_local_url:
            raise ValueError(
                "Vi phạm bảo mật: file:// bị cấm; chỉ chấp nhận URL HTTP loopback cục bộ"
            )
        return True

    def acquire_production_lock(self) -> bool:
        """Khóa nguyên tử: ngăn chặn bấm đúp nút render gây phình ổ đĩa hoặc xung đột tài nguyên."""
        with self._lock:
            if self._is_busy:
                return False
            self._is_busy = True
            return True

    def release_production_lock(self) -> None:
        """Giải phóng khóa sản xuất."""
        with self._lock:
            self._is_busy = False

    def get_system_health(self) -> dict[str, Any]:
        """Lấy trạng thái tổng quan xưởng và kiểm tra bảng mạch b87."""
        b87_passed, b87_nodes, _ = audit_neural_wiring(self.root)
        return {
            "server": f"http://{self.host}:{self.port}",
            "is_busy": self._is_busy,
            "b87_all_green": b87_passed,
            "total_neural_nodes": len(b87_nodes),
            "tiers_status": self.router.tiers_status,
        }

    def execute_end_to_end_production(
        self,
        topic_title: str,
        evidence_pack: dict[str, Any],
        chapter_paragraphs: list[dict[str, Any]],
        preferred_tier: int = 1,
        url_context: str = "http://127.0.0.1:8765/produce",
    ) -> dict[str, Any]:
        """Return prototype workflow metadata; this method does not create audio or video."""
        self.validate_request_protocol(url_context)

        acquired = self.acquire_production_lock()
        if not acquired:
            raise RuntimeError("Khóa nguyên tử: Hệ thống đang bận render tiến trình khác, cấm bấm đúp!")

        try:
            # 1. Kiểm tra Bạch Tuộc
            ok_pack, pack_errs = verify_evidence_pack(evidence_pack)
            if not ok_pack:
                raise ValueError(f"Bạch Tuộc từ chối: {'; '.join(pack_errs)}")

            local_sources = [
                source
                for source in evidence_pack["sources"]
                if isinstance(source, dict) and str(source.get("local_ref") or "").strip()
            ]
            local_verification = "not_applicable"
            if local_sources:
                ok_local, local_errors = verify_local_evidence_sources(evidence_pack, self.root)
                if not ok_local:
                    raise ValueError(f"Xác minh nguồn local thất bại: {'; '.join(local_errors)}")
                local_verification = "passed"

            # 2. Validate the script and all local metadata before any provider dispatch.
            script = self.script_writer.build_nine_chapters_script(topic_title, evidence_pack, chapter_paragraphs)
            ok_script_lock, script_lock_message = verify_voice_lock_before_render(
                script["voice_lock"], script["chapters"]
            )
            if not ok_script_lock:
                raise KhongDatChuan(f"KhongDatChuan: {script_lock_message}")
            self.compliance_gate.verify_duration_floor(script["total_duration_sec"])

            # 3. Giọng 48kHz & Khóa giọng c174
            segments = []
            for ch in script["chapters"]:
                seg = self.voice_engine.synthesize_speech_segment(
                    speaker=ch["speaker"],
                    text=ch["dialogue_excerpt"],
                    target_duration_sec=ch["duration_sec"],
                )
                segments.append(seg)
            voice_lock = create_c174_voice_lock(segments)

            # 5. Đối chiếu khóa trước khi Render đồ họa c172 (Fail-Closed)
            ok_lock, msg_lock = verify_c174_lock(voice_lock, segments)
            if not ok_lock:
                raise KhongDatChuan(f"KhongDatChuan: {msg_lock}")

            public_source_url = next(
                (
                    str(source.get("url") or "").strip()
                    for source in evidence_pack["sources"]
                    if str(source.get("url") or "").strip()
                ),
                None,
            )
            scene_render = self.renderer.render_scene(
                visual_mode="c172_hybrid",
                voice_lock_ok=ok_lock,
                resolution="1920x1080",
                channel_name="AI_HUONG_DAN_CMP",
                public_source_url=public_source_url,
                sentence_duration_sec=segments[0]["duration_sec"],
            )

            # 6. Prepare draft metadata; dispatch only after local validation succeeds.
            seo_bundle = self.compliance_gate.export_four_platform_seo(
                topic_title=topic_title,
                script_chapters=script["chapters"],
                evidence_pack=evidence_pack,
            )
            dispatch_info = self.router.dispatch(prompt=topic_title, preferred_tier=preferred_tier)

            return {
                "status": "prototype_simulation",
                "media_created": False,
                "evidence_validation": {
                    "metadata": "passed",
                    "local_sources": local_verification,
                    "local_source_count": len(local_sources),
                },
                "topic_title": topic_title,
                "total_duration_sec": script["total_duration_sec"],
                "meets_floor": script["meets_floor"],
                "dispatch": dispatch_info,
                "voice_lock": voice_lock,
                "visual_scene": scene_render,
                "seo_bundle": seo_bundle,
            }
        finally:
            self.release_production_lock()


class StudioHttpHandler(http.server.BaseHTTPRequestHandler):
    """Trình xử lý yêu cầu HTTP phục vụ giao diện và API tại cổng 8760."""

    backend = StudioBackend8760()

    def serve_media(self) -> None:
        """Stream one fixed approved asset; never accept a caller-supplied path."""
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or not is_trusted_local_request(
            self.client_address[0], hosts[0], self.server.server_port
        ):
            self.send_error(403, "Media preview is restricted to this loopback dashboard")
            return
        asset_path = MEDIA_ASSET_PATHS.get(self.path)
        if asset_path is None:
            self.send_error(404)
            return
        try:
            resolved_path = asset_path.resolve(strict=True)
            if not resolved_path.is_file():
                raise FileNotFoundError
            file_size = resolved_path.stat().st_size
        except (OSError, RuntimeError):
            self.send_error(404, "Approved preview media is unavailable")
            return
        try:
            byte_range = parse_single_byte_range(self.headers.get("Range", ""), file_size)
        except (ValueError, OverflowError):
            self.send_response(416)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if byte_range is None:
            start, end, status = 0, file_size - 1, 200
        else:
            start, end = byte_range
            status = 206
        content_length = max(0, end - start + 1)
        content_type = "video/mp4" if self.path == "/media/video" else "audio/wav"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Disposition", "inline")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        remaining = content_length
        with resolved_path.open("rb") as media_file:
            media_file.seek(start)
            while remaining:
                chunk = media_file.read(min(MEDIA_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    def do_GET(self) -> None:
        """Xử lý yêu cầu GET trả về Dashboard HTML hoặc JSON API."""
        if self.path in MEDIA_ASSET_PATHS:
            self.serve_media()
        elif self.path in ("/", "/index.html"):
            content = HTML_DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/master-command":
            host_headers = self.headers.get_all("Host", [])
            if len(host_headers) != 1 or not is_trusted_local_request(
                self.client_address[0], host_headers[0], self.server.server_port
            ):
                self.send_error(403, "Master command requires a canonical loopback Host")
                return
            try:
                content = build_master_all_in_one_command_prompt(self.backend.root).encode("utf-8")
            except MasterCommandBuildError as error:
                body = str(error).encode("utf-8")
                self.send_response(error.status_code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Disposition", 'attachment; filename="SIEU_LENH_CHI_HUY_C2_ALL_IN_ONE.md"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/health":
            host_headers = self.headers.get_all("Host", [])
            if len(host_headers) != 1 or not is_trusted_local_request(
                self.client_address[0], host_headers[0], self.server.server_port
            ):
                self.send_error(403, "API requires a canonical loopback Host")
                return
            health = self.backend.get_system_health()
            content = json.dumps(health, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Ghi đè log để không làm ô nhiễm console chuẩn."""
        return


def create_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> http.server.ThreadingHTTPServer:
    """Create the dashboard server on an IPv4 loopback address only."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError("Dashboard must bind to an IPv4 loopback address") from error
    if address.version != 4 or not address.is_loopback:
        raise ValueError("Dashboard must bind to an IPv4 loopback address")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer from 0 through 65535")
    return http.server.ThreadingHTTPServer((str(address), port), StudioHttpHandler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CMP local video-workshop dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="loopback port (default: 8765)")
    args = parser.parse_args(argv)
    server = create_server("127.0.0.1", args.port)
    print(f"Studio CMP dang chay tai http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
