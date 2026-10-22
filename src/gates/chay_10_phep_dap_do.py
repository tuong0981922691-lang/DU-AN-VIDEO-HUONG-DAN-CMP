import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.gates.kiem_dau_phien import check_ledger_invariants, check_temp_paths, scan_text_for_secrets
from src.octopus.tech_scout import match_keyword_unicode_boundary, verify_evidence_pack
from src.script_engine.dual_host_writer import (
    CHAPTER_DEFINITIONS,
    create_voice_script_lock,
    normalize_vietnamese_numbers,
    verify_voice_lock_before_render,
)


def _sample_data() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence = {
        "topic_id": "mutation-suite-synthetic",
        "title": "Synthetic mutation test data",
        "sources": [{"url": "https://example.invalid/spec", "locator": "section-1"}],
        "claims": [],
    }
    chapters = []
    for definition in CHAPTER_DEFINITIONS:
        text = "Synthetic chapter text for a local, offline mutation check."
        chapters.append(
            {
                "chapter_no": definition["chapter_no"],
                "title": definition["title"],
                "speaker": definition["primary_host"],
                "text": text,
                "dialogue_excerpt": text,
                "duration_sec": 105,
            }
        )
    return evidence, chapters


def _source_snapshot(root: Path) -> str:
    digest = hashlib.sha256()
    for folder in (root / "src", root / "tests"):
        for path in sorted(folder.rglob("*.py")):
            relative = path.relative_to(root).as_posix().encode("utf-8")
            content = path.read_bytes()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return digest.hexdigest()


def run_mutation_suite(root: Path | str | None = None) -> dict[str, Any]:
    """Run ten offline negative checks and verify source files stay byte-identical."""
    project_root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
    source_sha_before = _source_snapshot(project_root)
    evidence, chapters = _sample_data()
    checks: list[tuple[str, bool]] = []

    voice_lock = create_voice_script_lock(chapters)
    tampered = json.loads(json.dumps(chapters))
    tampered[0]["dialogue_excerpt"] += " modified after voice lock"
    ok, message = verify_voice_lock_before_render(voice_lock, tampered)
    checks.append(("DAP-DO-01 c174_voice_lock", not ok and "c174" in message))

    ok, message = verify_voice_lock_before_render(voice_lock, chapters, "ve_tay_giay_ke_o")
    checks.append(("DAP-DO-02 C2-200_legacy_visual", not ok and "C2-200" in message))

    short_chapters = json.loads(json.dumps(chapters))
    for chapter in short_chapters:
        chapter["duration_sec"] = 20
    short_lock = create_voice_script_lock(short_chapters)
    ok, message = verify_voice_lock_before_render(short_lock, short_chapters)
    checks.append(("DAP-DO-03 duration_floor_900s", not ok and "900s" in message))

    synthetic_token = "ghp_" + "A" * 30
    checks.append(("DAP-DO-04 synthetic_secret", "GitHub Token" in scan_text_for_secrets(synthetic_token)))

    expected_temp = project_root / "du_lieu" / "tam_me"
    temp_issues = check_temp_paths(
        project_root,
        {"TEMP": "C:\\Temp", "TMP": str(expected_temp)},
    )
    checks.append(("DAP-DO-05 temp_on_C_drive", "TEMP_khong_o_du_lieu_tam_me" in temp_issues))

    bad_evidence = dict(evidence)
    bad_evidence["confidence"] = "HIGH"
    valid, errors = verify_evidence_pack(bad_evidence)
    checks.append(
        ("DAP-DO-06 forbidden_confidence", not valid and any("forbidden_sender_field" in e for e in errors))
    )

    checks.append(
        ("DAP-DO-07 unicode_substring_boundary", not match_keyword_unicode_boundary("Miss World 2026", "iss"))
    )

    normalized, warnings = normalize_vietnamese_numbers(
        "Budget 1,753 tỷ; DeepSeek-V3.2; 3,375 units; 4.1%."
    )
    checks.append(
        (
            "DAP-DO-08 ambiguous_numbers",
            "1,753 tỷ" in warnings
            and "DeepSeek-V3.2" in normalized
            and "3.375" in normalized
            and "4,1%" in normalized,
        )
    )

    ledger_lines = ["## 🎯 CON TRỎ", "pointer body", "## 🎯 CON TRỎ"] + [f"line {i}" for i in range(401)]
    ledger_issues = check_ledger_invariants("\n".join(ledger_lines))
    checks.append(
        (
            "DAP-DO-09 ledger_limit_and_pointer",
            any(issue.startswith("SO_VIEC_vuot_400_dong:") for issue in ledger_issues)
            and "CON_TRO_phai_xuat_hien_dung_mot_lan" in ledger_issues,
        )
    )

    missing_anchor = dict(evidence)
    missing_anchor["topic_id"] = ""
    valid, errors = verify_evidence_pack(missing_anchor)
    checks.append(
        ("DAP-DO-10 required_topic_anchor", not valid and any("missing_topic_anchor" in e for e in errors))
    )

    source_sha_after = _source_snapshot(project_root)
    return {
        "checks": checks,
        "passed": sum(passed for _, passed in checks),
        "total": len(checks),
        "source_sha_before": source_sha_before,
        "source_sha_after": source_sha_after,
        "source_unchanged": source_sha_before == source_sha_after,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_mutation_suite()
    for name, passed in result["checks"]:
        print(f"{'XANH' if passed else 'DO'}: {name} — {'bị chặn đúng' if passed else 'không bị chặn'}")
    print(f"KẾT QUẢ: {result['passed']}/{result['total']} phép đạp đổ bị chặn đúng.")
    print("SHA-256 trước: {}".format(result["source_sha_before"]))
    print("SHA-256 sau:   {}".format(result["source_sha_after"]))
    print("Kết luận mã nguồn: " + ("KHỚP — không tệp mã nguồn nào bị thay đổi." if result["source_unchanged"] else "LỆCH."))
    return 0 if result["passed"] == result["total"] and result["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())