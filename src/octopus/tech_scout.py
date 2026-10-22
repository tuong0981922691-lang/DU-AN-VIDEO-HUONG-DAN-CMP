import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Octopus evidence-pack prototype; methods validate supplied metadata and do not fetch or capture sources.

Thu thập tài liệu kỹ thuật gốc, lọc ranh giới từ Unicode V-899, tách ngày phát hành
với ngày đăng bài, từ chối trường tự chấm độ tin cậy L6, xuất TutorialEvidencePack.json.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


LOCAL_EVIDENCE_MAX_BYTES = 8 * 1024 * 1024


def match_keyword_unicode_boundary(text: str, keyword: str) -> bool:
    """Khớp từ khóa với ranh giới từ Unicode chống nhận nhầm chuỗi con (V-899: 'iss' -> 'Miss World')."""
    if not text or not keyword:
        return False
    escaped = re.escape(keyword.strip())
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE | re.UNICODE)
    return bool(pattern.search(text))


def separate_dates(release_date: str, article_date: str) -> dict[str, Any]:
    """Phân định rõ ràng ngày phát hành kỹ thuật gốc (release_date) và ngày báo chí đăng bài (article_date)."""
    rel = str(release_date or "").strip()
    art = str(article_date or "").strip()
    return {
        "release_date": rel,
        "article_date": art,
        "is_valid": bool(rel),
        "is_same": bool(rel and art and rel == art),
    }


def verify_evidence_pack(pack: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate supplied claim/source lineage metadata; does not verify source truth."""
    if not isinstance(pack, dict):
        return False, ["pack_not_dict"]

    errors: list[str] = []
    topic_anchor = str(pack.get("topic_id") or pack.get("chu_de") or "").strip()
    if not topic_anchor:
        errors.append("missing_topic_anchor (C2-125)")

    source_rows = pack.get("sources")
    sources_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(source_rows, list) or not source_rows:
        errors.append("empty_sources_list")
    else:
        for idx, source in enumerate(source_rows):
            if not isinstance(source, dict):
                errors.append(f"source[{idx}]_not_object")
                continue
            source_id = str(source.get("source_id") or "").strip()
            if not source_id:
                errors.append(f"source[{idx}]_missing_source_id")
            elif source_id in sources_by_id:
                errors.append(f"source[{idx}]_duplicate_source_id")
            else:
                sources_by_id[source_id] = source

            locator = str(source.get("locator") or "").strip()
            if not locator:
                errors.append(f"source[{idx}]_missing_locator")
            url = str(source.get("url") or "").strip()
            local_ref = str(source.get("local_ref") or "").strip()
            if url:
                try:
                    parsed = urlsplit(url)
                    valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
                except ValueError:
                    valid_url = False
                if not valid_url:
                    errors.append(f"source[{idx}]_invalid_url")
            elif local_ref:
                normalized = local_ref.replace("\\", "/")
                if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
                    errors.append(f"source[{idx}]_invalid_local_ref")
            else:
                errors.append(f"source[{idx}]_missing_reference")

    claims = pack.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("empty_claims_list")
    else:
        claim_ids: set[str] = set()
        for idx, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errors.append(f"claim[{idx}]_not_object")
                continue
            claim_id = str(claim.get("claim_id") or "").strip()
            if not claim_id:
                errors.append(f"claim[{idx}]_missing_claim_id")
            elif claim_id in claim_ids:
                errors.append(f"claim[{idx}]_duplicate_claim_id")
            claim_ids.add(claim_id)
            if not str(claim.get("text") or "").strip():
                errors.append(f"claim[{idx}]_missing_text")

            source_refs = claim.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs:
                errors.append(f"claim[{idx}]_missing_source_refs")
                continue
            for ref_idx, source_ref in enumerate(source_refs):
                if not isinstance(source_ref, dict):
                    errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_not_object")
                    continue
                source_id = str(source_ref.get("source_id") or "").strip()
                locator = str(source_ref.get("locator") or "").strip()
                if source_id not in sources_by_id:
                    errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_unknown_source")
                elif source_id in sources_by_id:
                    source = sources_by_id[source_id]
                    if locator and locator != str(source.get("locator") or "").strip():
                        errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_locator_mismatch")
                    source_excerpt = str(source.get("excerpt") or "").strip()
                    claim_excerpt = str(source_ref.get("excerpt") or "").strip()
                    if source_excerpt and claim_excerpt != source_excerpt:
                        errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_excerpt_mismatch")
                if not locator:
                    errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_missing_locator")
                if not str(source_ref.get("excerpt") or "").strip():
                    errors.append(f"claim[{idx}]_source_ref[{ref_idx}]_missing_excerpt")

    forbidden_fields = {"da_kiem", "claim_dung", "claim_sai", "ty_le_sai", "do_tin_cay", "confidence"}

    def find_forbidden_fields(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key)
                nested_path = f"{path}.{key_text}" if path else key_text
                if key_text.casefold() in forbidden_fields:
                    errors.append(f"forbidden_sender_field:{nested_path}")
                find_forbidden_fields(nested, nested_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                find_forbidden_fields(nested, f"{path}[{index}]")

    find_forbidden_fields(pack)
    return len(errors) == 0, errors


def verify_local_evidence_sources(
    pack: dict[str, Any], workspace_root: Path | str
) -> tuple[bool, list[str]]:
    """Verify local source snapshots against files contained in the workspace."""
    is_valid, metadata_errors = verify_evidence_pack(pack)
    if not is_valid:
        return False, [f"metadata:{error}" for error in metadata_errors]

    try:
        root = Path(workspace_root).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        return False, ["workspace_root_unavailable"]
    if not root.is_dir():
        return False, ["workspace_root_not_directory"]

    errors: list[str] = []
    local_source_count = 0
    for idx, source in enumerate(pack["sources"]):
        local_ref = str(source.get("local_ref") or "").strip()
        if not local_ref:
            continue
        local_source_count += 1

        normalized = local_ref.replace("\\", "/")
        expected_digest = str(source.get("local_sha256") or "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            errors.append(f"source[{idx}]_invalid_local_sha256")
            continue

        try:
            source_path = (root / Path(normalized)).resolve(strict=True)
        except ValueError:
            errors.append(f"source[{idx}]_invalid_local_path")
            continue
        except (OSError, RuntimeError):
            errors.append(f"source[{idx}]_local_source_unavailable")
            continue
        try:
            source_path.relative_to(root)
        except ValueError:
            errors.append(f"source[{idx}]_local_source_outside_workspace")
            continue

        try:
            if not source_path.is_file():
                errors.append(f"source[{idx}]_local_source_not_file")
                continue
            if source_path.stat().st_size > LOCAL_EVIDENCE_MAX_BYTES:
                errors.append(f"source[{idx}]_local_source_too_large")
                continue
            with source_path.open("rb") as source_file:
                content = source_file.read(LOCAL_EVIDENCE_MAX_BYTES + 1)
        except OSError:
            errors.append(f"source[{idx}]_local_source_unavailable")
            continue
        if len(content) > LOCAL_EVIDENCE_MAX_BYTES:
            errors.append(f"source[{idx}]_local_source_too_large")
            continue

        actual_digest = hashlib.sha256(content).hexdigest()
        if actual_digest != expected_digest:
            errors.append(f"source[{idx}]_local_sha256_mismatch")
            continue
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            errors.append(f"source[{idx}]_local_source_not_utf8")
            continue

        excerpt = str(source.get("excerpt") or "").strip()
        if not excerpt:
            errors.append(f"source[{idx}]_missing_local_excerpt")
        elif excerpt not in decoded:
            errors.append(f"source[{idx}]_local_excerpt_not_found")

    if local_source_count == 0:
        errors.append("no_local_sources_to_verify")
    return len(errors) == 0, errors


class OctopusTechScout:
    """Four-source evidence metadata prototype; no network collection is implemented."""

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        if workspace_root is not None:
            self.root = Path(workspace_root)
        else:
            self.root = Path(__file__).resolve().parents[2]

    def voi_1_kho_ma_va_tai_lieu_goc(self, repo_url: str, release_tag: str, locator: str) -> dict[str, Any]:
        """Describe a GitHub/spec source supplied by the caller; no remote fetch is performed."""
        url_clean = str(repo_url or "").strip()
        return {
            "source_type": "github_or_spec",
            "url": url_clean,
            "release_tag": str(release_tag).strip(),
            "locator": str(locator).strip(),
            "fetched": False,
            "status": "metadata_only",
        }

    def voi_2_radar_ai_da_quoc_gia(self, model_name: str, benchmark_name: str, score: float, locator: str) -> dict[str, Any]:
        """Describe caller-supplied benchmark metadata; no benchmark is run."""
        return {
            "source_type": "ai_benchmark",
            "model_name": str(model_name).strip(),
            "benchmark_name": str(benchmark_name).strip(),
            "score": float(score),
            "locator": str(locator).strip(),
            "status": "metadata_only",
        }

    def voi_3_truc_quan_man_hinh(self, screen_id: str, terminal_cmd: str, file_locator: str) -> dict[str, Any]:
        """Describe requested visual evidence; no screenshot or configuration file is captured."""
        return {
            "source_type": "visual_evidence",
            "screen_id": str(screen_id).strip(),
            "terminal_cmd": str(terminal_cmd).strip(),
            "file_locator": str(file_locator).strip(),
            "resolution": "1920x1080",
            "status": "metadata_only",
        }

    def voi_4_cong_kiem_chung_chong_bia(
        self,
        topic_id: str,
        title: str,
        sources: list[dict[str, Any]],
        claims: list[dict[str, Any]],
        release_date: str = "",
        article_date: str = "",
    ) -> dict[str, Any]:
        """Vòi 4: Đóng gói và kiểm định hồ sơ TutorialEvidencePack chống bịa đặt và từ chối trường tự chấm."""
        dates_info = separate_dates(release_date, article_date)
        pack: dict[str, Any] = {
            "schema_version": "TutorialEvidencePack/1.0",
            "topic_id": str(topic_id).strip(),
            "title": str(title).strip(),
            "dates": dates_info,
            "sources": sources,
            "claims": claims,
        }
        is_valid, errors = verify_evidence_pack(pack)
        if not is_valid:
            raise ValueError(f"TutorialEvidencePack không hợp lệ: {'; '.join(errors)}")
        return pack

    def export_evidence_pack(self, pack: dict[str, Any], output_path: Path | str | None = None) -> Path:
        """Xuất hồ sơ TutorialEvidencePack ra định dạng JSON chuẩn UTF-8."""
        is_valid, errors = verify_evidence_pack(pack)
        if not is_valid:
            raise ValueError(f"Từ chối xuất hồ sơ lỗi: {'; '.join(errors)}")

        temp_root = (self.root / "du_lieu" / "tam_me").resolve()
        if temp_root.drive.upper() != "E:":
            raise ValueError("Thư mục xuất phải nằm trên ổ E trong workspace dự án")
        temp_root.mkdir(parents=True, exist_ok=True)
        if output_path is None:
            safe_topic_id = re.sub(r"[^A-Za-z0-9_-]", "_", pack["topic_id"]).strip("_") or "topic"
            target = temp_root / f"evidence_{safe_topic_id}.json"
        else:
            target = Path(output_path)

        resolved_target = target.resolve()
        if resolved_target.parent != temp_root:
            raise ValueError("Đường dẫn xuất phải là tệp trực tiếp trong du_lieu/tam_me")

        payload = json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False)
        if len(payload.encode("utf-8")) > 1024 * 1024:
            raise ValueError("TutorialEvidencePack vượt giới hạn xuất 1 MiB")
        with resolved_target.open("x", encoding="utf-8", newline="") as output_file:
            output_file.write(payload)
        return resolved_target
