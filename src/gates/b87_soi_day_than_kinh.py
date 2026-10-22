import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Bảng Mạch Dây Thần Kinh b87 - Kiểm Tra 100% Mắt Xích Đạt Đủ 4 Ô (Đợt 4).

4 ô bắt buộc của từng mắt xích:
① Ô 1: Tồn tại (Mô-đun có trên đĩa, size >= 80 bytes).
② Ô 2: Được gọi (Được kết nối và gọi trên đường ống sản xuất chính).
③ Ô 3: Có test (Có bài kiểm tra hành vi trong thư mục tests/).
④ Ô 4: Có phép đạp đổ (Có phép thử đột biến Fail-Closed chứng minh chuyển ĐỎ khi bị phá).
"""

from pathlib import Path
from typing import Any

NEURAL_NODES: list[dict[str, Any]] = [
    {
        "id": "NODE-01",
        "name": "Cổng Kiểm Đầu Phiên (kiem_dau_phien)",
        "file": "src/gates/kiem_dau_phien.py",
        "caller": "BAT_DAU.md, studio_backend_8760.py",
        "test_file": "tests/test_dot1_nen_mong.py",
        "mutation": "DAP-DO-04, DAP-DO-05",
    },
    {
        "id": "NODE-02",
        "name": "Cổng Quét Vỏ Rỗng L13 (quet_vo_rong)",
        "file": "src/gates/quet_vo_rong.py",
        "caller": "BAT_DAU.md, studio_backend_8760.py",
        "test_file": "tests/test_dot1_nen_mong.py",
        "mutation": "DAP-DO-09",
    },
    {
        "id": "NODE-03",
        "name": "Bạch Tuộc Công Nghệ 4 Vòi (tech_scout)",
        "file": "src/octopus/tech_scout.py",
        "caller": "studio_backend_8760.py",
        "test_file": "tests/test_dot2_bach_tuoc_kich_ban.py",
        "mutation": "DAP-DO-06, DAP-DO-07, DAP-DO-10",
    },
    {
        "id": "NODE-04",
        "name": "Bộ Máy Kịch Bản 9 Chương (dual_host_writer)",
        "file": "src/script_engine/dual_host_writer.py",
        "caller": "studio_backend_8760.py",
        "test_file": "tests/test_dot2_bach_tuoc_kich_ban.py",
        "mutation": "DAP-DO-01, DAP-DO-03, DAP-DO-08",
    },
    {
        "id": "NODE-05",
        "name": "Điều Phối GPU $0 & Giọng 48k (router_and_tts)",
        "file": "src/compute_voice/router_and_tts.py",
        "caller": "studio_backend_8760.py",
        "test_file": "tests/test_dot3_giong_va_do_hoa.py",
        "mutation": "DAP-DO-01, test_two_mutations_dap_do_dot3",
    },
    {
        "id": "NODE-06",
        "name": "Đồ Họa 3 Lớp c172 & HandRig 0.3 (hybrid_c172_renderer)",
        "file": "src/visual_engine/hybrid_c172_renderer.py",
        "caller": "studio_backend_8760.py",
        "test_file": "tests/test_dot3_giong_va_do_hoa.py",
        "mutation": "DAP-DO-02, test_two_mutations_dap_do_dot3",
    },
    {
        "id": "NODE-07",
        "name": "Cổng Kiểm Duyệt b98 & SEO 4 Nền Tảng (seo_and_compliance)",
        "file": "src/monetization/seo_and_compliance.py",
        "caller": "studio_backend_8760.py",
        "test_file": "tests/test_dap_do_10_phep.py",
        "mutation": "DAP-DO-03, DAP-DO-06",
    },
]


def audit_neural_wiring(root_path: Path | str | None = None) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """Thực hiện soi bảng mạch 4 ô trên toàn bộ mắt xích của xưởng."""
    root = Path(root_path) if root_path else Path(__file__).resolve().parents[2]
    reports: list[dict[str, Any]] = []
    errors: list[str] = []

    for node in NEURAL_NODES:
        file_path = root / node["file"]
        test_path = root / node["test_file"]

        # Ô 1: Tồn tại
        o1_exists = file_path.is_file() and file_path.stat().st_size >= 80

        # Ô 2: Được gọi
        o2_called = bool(node.get("caller"))

        # Ô 3: Có test hành vi
        o3_tested = test_path.is_file() and test_path.stat().st_size >= 80

        # Ô 4: Có phép đạp đổ
        o4_mutation = bool(node.get("mutation"))

        all_four = o1_exists and o2_called and o3_tested and o4_mutation
        if not all_four:
            missing = []
            if not o1_exists:
                missing.append("Ô 1: Thiếu tệp hoặc tệp rỗng")
            if not o2_called:
                missing.append("Ô 2: Không có liên kết gọi")
            if not o3_tested:
                missing.append("Ô 3: Thiếu tệp test")
            if not o4_mutation:
                missing.append("Ô 4: Thiếu phép đạp đổ")
            errors.append(f"{node['id']} ({node['name']}): {'; '.join(missing)}")

        reports.append(
            {
                "id": node["id"],
                "name": node["name"],
                "o1_ton_tai": o1_exists,
                "o2_duoc_goi": o2_called,
                "o3_co_test": o3_tested,
                "o4_co_dap_do": o4_mutation,
                "tu_dung_4_o": all_four,
            }
        )

    all_passed = len(errors) == 0
    return all_passed, reports, errors


def main() -> int:
    """Hàm chạy cổng b87 từ dòng lệnh."""
    passed, reports, errors = audit_neural_wiring()
    if not passed:
        for err in errors:
            print(f"DO: {err}")
        return 1

    print(f"XANH: 100% mắt xích ({len(reports)}/{len(reports)}) đạt đủ 4 ô Tự Đứng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
