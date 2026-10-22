import sys
import pytest
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

from src.gates.kiem_dau_phien import check_disk_thresholds, check_ledger_invariants, check_project_drive, check_temp_paths, run_checks, scan_project_for_secrets, scan_text_for_secrets
from src.gates.quet_vo_rong import find_empty_shells

ROOT = Path(__file__).resolve().parents[1]


def test_four_authority_anchors_and_pointer_are_present():
    ledger_path = ROOT / "du_lieu" / "SO_VIEC.md"
    requirements_path = ROOT / "du_lieu" / "YEU_CAU_C2.md"
    if not ledger_path.is_file() or not requirements_path.is_file():
        pytest.skip("private handoff records are not included in the public source mirror")
    ledger = ledger_path.read_text(encoding="utf-8").splitlines()
    requirements = requirements_path.read_text(encoding="utf-8")
    assert ledger[0] == "## 🎯 CON TRỎ"
    assert sum(line.strip().startswith("## 🎯 CON TRỎ") for line in ledger) == 1
    assert len(ledger) <= 400
    required_terms = {
        "C2-M01": ("900 giây", "15 phút"),
        "C2-M02": ("Huy Tưởng", "Xuân Công", "nguồn"),
        "C2-M03": ("c172", "C2-200", "HandRig"),
        "C2-M04": ("C2-188", "Windows", "ổ C", "du_lieu/khoa/", "du_lieu/tam_me/"),
    }
    for anchor, terms in required_terms.items():
        assert anchor in requirements
        assert all(term in requirements for term in terms)


def test_disk_thresholds_fail_closed():
    assert check_disk_thresholds(10.0, 15.0)
    assert check_disk_thresholds(9.99, 20.0)
    assert check_disk_thresholds(20.0, 14.99)
    assert check_disk_thresholds(20.0, 20.0) == []


def test_temp_paths_must_be_project_local(tmp_path):
    expected_path = tmp_path / "du_lieu" / "tam_me"
    expected_path.mkdir(parents=True)
    expected = str(expected_path)
    assert check_temp_paths(tmp_path, {"TEMP": expected, "TMP": expected}) == []
    issues = check_temp_paths(tmp_path, {"TEMP": "C:\\Temp", "TMP": expected})
    assert "TEMP_khong_o_du_lieu_tam_me" in issues


def test_temp_paths_require_existing_temp_directory(tmp_path):
    temp_dir = tmp_path / "du_lieu" / "tam_me"
    issues = check_temp_paths(tmp_path, {"TEMP": str(temp_dir), "TMP": str(temp_dir)})
    assert "thu_muc_du_lieu_tam_me_khong_ton_tai" in issues
    temp_dir.mkdir(parents=True)
    assert check_temp_paths(tmp_path, {"TEMP": str(temp_dir), "TMP": str(temp_dir)}) == []


def test_secret_patterns_detect_synthetic_credentials():
    pem_marker = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
    samples = (
        ("GitHub Token", "ghp_" + ("A" * 20)),
        ("GitHub Fine-Grained PAT", "github_pat_" + ("B" * 20)),
        ("Telegram Bot Token", "1234567890:" + ("C" * 30)),
        ("API Secret Key", "sk-" + ("D" * 20)),
        ("AWS Access Key", "AKIA" + ("E" * 16)),
        ("Cloud API Key", "AIza" + ("F" * 30)),
        ("Cloudflare API Token", "cfat_" + ("H" * 24)),
        ("Cloudflare User Token", "cfut_" + ("L" * 24)),
        ("Groq API Key", "gsk_" + ("J" * 20)),
        ("Slack Token", "xoxb-" + ("G" * 10)),
        ("PEM Private Key", pem_marker),
    )
    for label, sample in samples:
        assert label in scan_text_for_secrets(sample)
    assert scan_text_for_secrets("documentation contains no credential") == []


def test_preflight_mutation_turns_red_for_c_drive_temp():
    project_temp = str(ROOT / "du_lieu" / "tam_me")
    issues = run_checks(
        ROOT,
        environ={"TEMP": "C:\\Temp", "TMP": project_temp},
        project_free_gb=46.0,
        c_free_gb=17.0,
    )
    assert "TEMP_khong_o_du_lieu_tam_me" in issues


def test_preflight_rejects_missing_temp_and_low_disk_space():
    project_temp = str(ROOT / "du_lieu" / "tam_me")
    issues = run_checks(
        ROOT,
        environ={"TEMP": project_temp},
        project_free_gb=10.0,
        c_free_gb=15.0,
    )
    assert "TMP_chua_duoc_dat" in issues
    assert any(issue.startswith("O_du_an_duoi_10GB:") for issue in issues)
    assert any(issue.startswith("Canh_bao_o_C_duoi_15GB:") for issue in issues)


def test_empty_shell_gate_finds_stubs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "real.py").write_text("def ready():\n    return True\n", encoding="utf-8")
    (tmp_path / "tests" / "stub.py").write_text("raise NotImplementedError\n", encoding="utf-8")
    issues = find_empty_shells(tmp_path)
    assert any("chua_cai_dat" in item for item in issues)


def test_empty_shell_gate_detects_noop_callable_beside_working_code(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    module = "def ready():\n    return True\n\ndef unfinished():\n    pass\n"
    (tmp_path / "src" / "mixed.py").write_text(module, encoding="utf-8")
    issues = find_empty_shells(tmp_path)
    assert any("vo_rong_callable:src\\mixed.py:unfinished" in item for item in issues)


def test_empty_shell_gate_reports_syntax_errors(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    issues = find_empty_shells(tmp_path)
    assert any("khong_hop_le:src\\broken.py:SyntaxError" in item for item in issues)


def test_preflight_rejects_missing_gitignore_rules(tmp_path):
    (tmp_path / "du_lieu").mkdir()
    (tmp_path / "BAT_DAU.md").write_text("guide\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.wav\n", encoding="utf-8")
    (tmp_path / "du_lieu" / "SO_VIEC.md").write_text("## 🎯 CON TRỎ\n", encoding="utf-8")
    (tmp_path / "du_lieu" / "YEU_CAU_C2.md").write_text(
        "C2-M01 900 giây 15 phút C2-M02 Huy Tưởng Xuân Công nguồn "
        "C2-M03 c172 C2-200 HandRig C2-M04 C2-188 Windows ổ C "
        "du_lieu/khoa/ du_lieu/tam_me/",
        encoding="utf-8",
    )
    temp_dir = str(tmp_path / "du_lieu" / "tam_me")
    issues = run_checks(
        tmp_path,
        environ={"TEMP": temp_dir, "TMP": temp_dir},
        project_free_gb=20,
        c_free_gb=20,
    )
    assert "thieu_gitignore_rule:/du_lieu/khoa/" in issues
    assert "thieu_gitignore_rule:/du_lieu/SO_VIEC.md" in issues
    assert "thieu_gitignore_rule:/du_lieu/YEU_CAU_C2.md" in issues
    assert "thieu_gitignore_rule:/du_lieu/LENH_BAN_GIAO_AI.md" in issues
    assert "thieu_gitignore_rule:/du_lieu/tam_me/" in issues
    assert "thieu_gitignore_rule:*.env" in issues


def test_preflight_rejects_project_outside_e_drive():
    assert check_project_drive("C:") == ["du_an_khong_nam_tren_o_E:C:"]
    assert check_project_drive("E:") == []


def test_preflight_checks_line_cap_and_all_four_authority_anchors(tmp_path):
    (tmp_path / "du_lieu").mkdir()
    (tmp_path / "du_lieu" / "SO_VIEC.md").write_text(
        "## 🎯 CON TRỎ\n" + "x\n" * 400,
        encoding="utf-8",
    )
    (tmp_path / "du_lieu" / "YEU_CAU_C2.md").write_text(
        "C2-M01 C2-M02 C2-M03",
        encoding="utf-8",
    )
    tmp_dir = str(tmp_path / "du_lieu" / "tam_me")
    issues = run_checks(
        tmp_path,
        environ={"TEMP": tmp_dir, "TMP": tmp_dir},
        project_free_gb=20,
        c_free_gb=20,
    )
    assert any("SO_VIEC_vuot_400_dong" in issue for issue in issues)
    assert any(issue.startswith("thieu_neo:C2-M04:") for issue in issues)


def test_start_guide_and_gitignore_match_handoff_contract():
    guide = (ROOT / "BAT_DAU.md").read_text(encoding="utf-8").splitlines()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    rules = {line.strip() for line in ignore if line.strip() and not line.lstrip().startswith("#")}
    assert len(guide) <= 25
    assert any("du_lieu/LENH_BAN_GIAO_AI.md" in line for line in guide)
    assert any("Không xóa/di chuyển/tải dữ liệu" in line for line in guide)
    assert "$projectRoot = (Get-Location).Path" in "\n".join(guide)
    assert "$env:TEMP = Join-Path $projectRoot 'du_lieu\\tam_me'" in "\n".join(guide)
    assert "$env:TMP = $env:TEMP" in "\n".join(guide)
    assert "/du_lieu/khoa/" in rules
    assert "/du_lieu/SO_VIEC.md" in rules
    assert "/du_lieu/YEU_CAU_C2.md" in rules
    assert "/du_lieu/LENH_BAN_GIAO_AI.md" in rules
    assert "/du_lieu/tam_me/" in rules
    assert "/du_lieu/san_xuat/" in rules
    assert "*.wav" in rules
    assert "*.mp4" in rules
    assert "/khoa/" in rules
    assert ".env" in rules
    assert ".env.*" in rules
    assert "*.env" in rules
    assert "*.pem" in rules
    assert "*.key" in rules
    assert "*.p12" in rules
    assert "*.pfx" in rules
    assert "*.jks" in rules
    assert "*.keystore" in rules
    assert "*.crt" in rules
    assert "*.cer" in rules
    assert "*.token" in rules
    assert "*credentials*.json" in rules
    assert all(not ("#" in line and not line.lstrip().startswith("#")) for line in ignore)


def test_python_files_configure_utf8_at_startup():
    python_files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
    assert python_files
    for path in python_files:
        header = path.read_text(encoding="utf-8").splitlines()[:3]
        normalized = " ".join(header).replace("'", "\"")
        assert "sys.stdout.reconfigure(encoding=\"utf-8\", errors=\"replace\")" in normalized


def test_full_project_secret_scan_finds_credentials_in_env_file(tmp_path):
    project = tmp_path / "tam_me" / "copied-project"
    project.mkdir(parents=True)
    env_file = project / ".env"
    fake_token = "ghp_" + ("A" * 24)
    env_file.write_text("TOKEN=" + fake_token, encoding="utf-8")
    findings = scan_project_for_secrets(project)
    assert any("GitHub Token:.env" in item for item in findings)


def test_full_project_secret_scan_checks_named_env_files(tmp_path):
    project = tmp_path / "workspace"
    project.mkdir()
    named_env = project / "settings.env"
    named_env.write_text("TOKEN=" + "gsk_" + ("K" * 24), encoding="utf-8")
    findings = scan_project_for_secrets(project)
    assert any("Groq API Key:settings.env" in item for item in findings)


def test_full_project_secret_scan_does_not_skip_project_named_like_temp_dir(tmp_path):
    project = tmp_path / "tam_me" / "copied-project"
    project.mkdir(parents=True)
    target = project / "settings.ini"
    target.write_text("token=" + ("sk-" + ("Z" * 24)), encoding="utf-8")
    findings = scan_project_for_secrets(project)
    assert any("API Secret Key:settings.ini" in item for item in findings)


def test_full_preflight_fails_for_fake_token_in_project_copy(tmp_path):
    project = tmp_path / "copied-project"
    data = project / "du_lieu"
    data.mkdir(parents=True)
    (project / "BAT_DAU.md").write_text("guide", encoding="utf-8")
    (project / ".gitignore").write_text(
        "/du_lieu/khoa/\n/du_lieu/tam_me/\n/du_lieu/san_xuat/\n*.wav\n*.mp4\n",
        encoding="utf-8",
    )
    (data / "SO_VIEC.md").write_text("## 🎯 CON TRỎ\n", encoding="utf-8")
    (data / "YEU_CAU_C2.md").write_text(
        "C2-M01 900 giây 15 phút C2-M02 Huy Tưởng Xuân Công nguồn "
        "C2-M03 c172 C2-200 HandRig C2-M04 C2-188 Windows ổ C "
        "du_lieu/khoa/ du_lieu/tam_me/",
        encoding="utf-8",
    )
    (project / ".env").write_text("TOKEN=" + "ghp_" + ("Q" * 24), encoding="utf-8")
    temp_dir = str(data / "tam_me")
    issues = run_checks(
        project,
        environ={"TEMP": temp_dir, "TMP": temp_dir},
        project_free_gb=20,
        c_free_gb=20,
    )
    assert any(issue.startswith("GitHub Token:") for issue in issues)


def test_workspace_has_no_empty_shells():
    assert find_empty_shells(ROOT) == []

def test_ledger_invariants_accept_limit_and_reject_overflow_or_duplicate_pointer():
    valid = "## 🎯 CON TRỎ\n" + "entry\n" * 399
    assert check_ledger_invariants(valid) == []

    invalid = "## 🎯 CON TRỎ\n## 🎯 CON TRỎ\n" + "entry\n" * 400
    issues = check_ledger_invariants(invalid)
    assert any(issue.startswith("SO_VIEC_vuot_400_dong:") for issue in issues)
    assert "CON_TRO_phai_xuat_hien_dung_mot_lan" in issues



def test_master_command_builder_separates_markdown_fence_from_unterminated_source(tmp_path):
    import hashlib

    from src.studio_backend_8760 import MASTER_COMMAND_SOURCES, build_master_all_in_one_command_prompt

    for relative_name in MASTER_COMMAND_SOURCES:
        target = tmp_path / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"safe synthetic content")
    prompt = build_master_all_in_one_command_prompt(tmp_path)
    assert "safe synthetic content\n```\n\n\n### `.gitignore` — SHA-256" in prompt
    digest = hashlib.sha256(b"safe synthetic content").hexdigest()
    assert f"### `BAT_DAU.md` — SHA-256 `{digest}`" in prompt


def test_health_endpoint_rejects_dns_rebinding_host(monkeypatch):
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from src.studio_backend_8760 import StudioBackend8760, StudioHttpHandler, create_server

    monkeypatch.setattr(StudioHttpHandler, "backend", StudioBackend8760())
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/health"
        request = Request(url, headers={"Host": f"attacker.example:{server.server_address[1]}"})
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=5)
        assert error.value.code == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "localhost", "::1", ""])
def test_dashboard_server_refuses_non_ipv4_loopback_bind(host):
    from src.studio_backend_8760 import create_server

    with pytest.raises(ValueError, match="IPv4 loopback"):
        create_server(host, 0)


def test_dashboard_server_binds_only_requested_loopback_address():
    from src.studio_backend_8760 import create_server

    server = create_server("127.0.0.1", 0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


@pytest.mark.parametrize("path", ["/api/master-command", "/api/health", "/media/video"])
def test_api_rejects_duplicate_host_headers(monkeypatch, path):
    import http.client
    import threading

    from src.studio_backend_8760 import StudioBackend8760, StudioHttpHandler, create_server

    monkeypatch.setattr(StudioHttpHandler, "backend", StudioBackend8760())
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.putrequest("GET", path, skip_host=True)
        connection.putheader("Host", f"127.0.0.1:{server.server_port}")
        connection.putheader("Host", f"attacker.example:{server.server_port}")
        connection.endheaders()
        response = connection.getresponse()
        try:
            assert response.status == 403
            response.read()
        finally:
            connection.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -float("inf"), -1])
def test_duration_gate_rejects_nonfinite_or_negative_values(duration):
    from src.monetization.seo_and_compliance import ComplianceViolation, SeoAndComplianceGate

    with pytest.raises(ComplianceViolation):
        SeoAndComplianceGate().verify_duration_floor(duration)


def test_seo_export_omits_local_paths_and_invalid_urls_from_public_description():
    from src.monetization.seo_and_compliance import SeoAndComplianceGate

    bundle = SeoAndComplianceGate().export_four_platform_seo(
        "Synthetic topic",
        [{"title": "Chapter", "duration_sec": 900, "dialogue_excerpt": "Draft text"}],
        {
            "topic_id": "../../outside\\escape",
            "sources": [
                {"local_ref": "src/private/internal.py", "locator": "internal#L1"},
                {"url": "javascript:alert(1)", "locator": "bad-url"},
                {"url": "https://user:secret@example.com/private", "locator": "credential-url"},
                {"url": "https://example.com/reference?access_token=test-token-12345", "locator": "query-token"},
            ],
        },
    )
    description = bundle["packages"]["youtube"]["description"]

    assert "src/private/internal.py" not in description
    assert "None (" not in description
    assert "javascript:" not in description
    assert "user@" not in description
    assert "access_token" not in description
    assert "test-token-12345" not in description
    assert "Chưa có URL nguồn công khai" in description
    assert bundle["packages"]["website"]["slug"] == "outside-escape"


def test_seo_export_includes_only_valid_public_http_source_urls():
    from src.monetization.seo_and_compliance import SeoAndComplianceGate

    bundle = SeoAndComplianceGate().export_four_platform_seo(
        "Synthetic topic",
        [{"title": "Chapter", "duration_sec": 900, "dialogue_excerpt": "Draft text"}],
        {
            "topic_id": "synthetic",
            "sources": [
                {"url": "https://example.com/reference", "locator": "section-1"},
                {"local_ref": "src/private/internal.py", "locator": "internal#L1"},
            ],
        },
    )
    description = bundle["packages"]["youtube"]["description"]

    assert "- https://example.com/reference" in description
    assert "section-1" not in description
    assert "src/private/internal.py" not in description


def test_seo_export_marks_outputs_as_unpublished_drafts():
    from src.monetization.seo_and_compliance import SeoAndComplianceGate

    bundle = SeoAndComplianceGate().export_four_platform_seo(
        "Synthetic topic",
        [{"title": "Chapter", "duration_sec": 900, "dialogue_excerpt": "Draft text"}],
        {"topic_id": "synthetic", "sources": [{"url": "https://example.com", "locator": "spec"}]},
    )
    assert bundle["status"] == "success"
    assert bundle["artifact_type"] == "draft_metadata_only"
    assert bundle["media_created"] is False
    assert bundle["published"] is False
    assert "chạy thử nghiệm thực tế" not in bundle["packages"]["facebook"]["post_text"]
    assert "Bản nháp" in bundle["packages"]["facebook"]["post_text"]


def test_dashboard_streams_allowlisted_media_with_single_byte_ranges(tmp_path, monkeypatch):
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    import src.studio_backend_8760 as studio

    video_path = tmp_path / "approved.mp4"
    audio_path = tmp_path / "approved.wav"
    video_path.write_bytes(b"approved-video-bytes")
    audio_path.write_bytes(b"approved-audio-bytes")
    monkeypatch.setattr(studio.StudioHttpHandler, "backend", studio.StudioBackend8760(tmp_path))
    monkeypatch.setattr(studio, "MEDIA_ASSET_PATHS", {
        "/media/video": video_path,
        "/media/audio": audio_path,
    })
    server = studio.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
        assert '<video controls preload="metadata" playsinline' in page
        assert '<audio controls preload="metadata"' in page
        assert 'src="/media/video"' in page and 'src="/media/audio"' in page

        request = Request(base + "/media/video", headers={"Range": "bytes=2-7"})
        with urlopen(request, timeout=5) as response:
            assert response.status == 206
            assert response.headers["Content-Type"] == "video/mp4"
            assert response.headers["Content-Range"] == f"bytes 2-7/{video_path.stat().st_size}"
            assert response.headers["Accept-Ranges"] == "bytes"
            assert response.read() == b"proved"

        with urlopen(base + "/media/audio", timeout=5) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "audio/wav"
            assert response.read() == b"approved-audio-bytes"

        invalid = Request(base + "/media/video", headers={"Range": "bytes=0-1,3-4"})
        with pytest.raises(HTTPError) as error:
            urlopen(invalid, timeout=5)
        assert error.value.code == 416

        with pytest.raises(HTTPError) as missing:
            urlopen(base + "/media/not-allowlisted", timeout=5)
        assert missing.value.code == 404
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_dashboard_defaults_to_dedicated_loopback_port_8765():
    from src.studio_backend_8760 import DEFAULT_PORT, create_server

    server = create_server()
    try:
        assert DEFAULT_PORT == 8765
        assert server.server_address == ("127.0.0.1", 8765)
    finally:
        server.server_close()
