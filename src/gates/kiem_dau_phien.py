import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import re
import shutil
from pathlib import Path

REQUIRED_AUTHORITY_ANCHORS = {
    "C2-M01": ("900 giây", "15 phút"),
    "C2-M02": ("Huy Tưởng", "Xuân Công", "nguồn"),
    "C2-M03": ("c172", "C2-200", "HandRig"),
    "C2-M04": ("C2-188", "Windows", "ổ C", "du_lieu/khoa/", "du_lieu/tam_me/"),
}

SECRET_PATTERNS = (
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("GitHub Fine-Grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("Telegram Bot Token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")),
    ("API Secret Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Cloud API Key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Cloudflare API Token", re.compile(r"\bcfat_[A-Za-z0-9_-]{20,}\b")),
    ("Cloudflare User Token", re.compile(r"\bcfut_[A-Za-z0-9_-]{20,}\b")),
    ("Groq API Key", re.compile(r"\bgsk_[A-Za-z0-9]{10,}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("PEM Private Key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def scan_text_for_secrets(text):
    return [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]


def check_temp_paths(root, environ):
    expected = (Path(root) / "du_lieu" / "tam_me").resolve()
    issues = []
    if not expected.is_dir():
        issues.append("thu_muc_du_lieu_tam_me_khong_ton_tai")
    for name in ("TEMP", "TMP"):
        value = environ.get(name)
        if not value:
            issues.append(f"{name}_chua_duoc_dat")
            continue
        actual = Path(value).resolve()
        if actual != expected:
            issues.append(f"{name}_khong_o_du_lieu_tam_me")
    return issues


def check_project_drive(drive):
    if str(drive).upper() != "E:":
        return [f"du_an_khong_nam_tren_o_E:{drive or 'khong_co_o'}"]
    return []


def check_ledger_invariants(content):
    """Validate the private work ledger's pointer and line-count contract."""
    lines = str(content).splitlines()
    issues = []
    if not lines or lines[0].strip() != "## 🎯 CON TRỎ":
        issues.append("CON_TRO_khong_o_dau_so_viec")
    if len(lines) > 400:
        issues.append(f"SO_VIEC_vuot_400_dong:{len(lines)}")
    if sum(line.strip().startswith("## 🎯 CON TRỎ") for line in lines) != 1:
        issues.append("CON_TRO_phai_xuat_hien_dung_mot_lan")
    return issues

def check_disk_thresholds(project_free_gb, c_free_gb):
    issues = []
    if project_free_gb <= 10:
        issues.append(f"O_du_an_duoi_10GB:{project_free_gb:.2f}")
    if c_free_gb <= 15:
        issues.append(f"Canh_bao_o_C_duoi_15GB:{c_free_gb:.2f}")
    return issues


def scan_project_for_secrets(root):
    root = Path(root).resolve()
    ignored = {".git", ".venv", "__pycache__", ".pytest_cache", "tam_me", "tam_ai", "khoa", "san_xuat"}
    extensions = {".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml", ".ini", ".cfg", ".conf", ".properties", ".env", ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".crt", ".cer", ".token"}
    findings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in ignored for part in relative.parts[:-1]):
            continue
        if path.suffix.lower() not in extensions and not (path.name == ".gitignore" or path.name == ".env" or path.name.startswith(".env.")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"khong_doc_duoc_utf8:{path.relative_to(root)}")
            continue
        for label in scan_text_for_secrets(text):
            findings.append(f"{label}:{path.relative_to(root)}")
    return findings


def run_checks(root, environ=None, project_free_gb=None, c_free_gb=None):
    root = Path(root).resolve()
    environ = os.environ if environ is None else environ
    issues = check_project_drive(root.drive)
    guide = root / "BAT_DAU.md"
    ignore_file = root / ".gitignore"
    start = root / "du_lieu" / "SO_VIEC.md"
    requirements = root / "du_lieu" / "YEU_CAU_C2.md"
    if not guide.is_file():
        issues.append("thieu_BAT_DAU")
    else:
        guide_lines = guide.read_text(encoding="utf-8").splitlines()
        if len(guide_lines) > 25:
            issues.append(f"BAT_DAU_vuot_25_dong:{len(guide_lines)}")
    if not ignore_file.is_file():
        issues.append("thieu_gitignore")
    else:
        ignore_lines = ignore_file.read_text(encoding="utf-8").splitlines()
        ignore_rules = {line.strip() for line in ignore_lines if line.strip() and not line.lstrip().startswith("#")}
        required_rules = {"/khoa/", "/du_lieu/khoa/", "/du_lieu/SO_VIEC.md", "/du_lieu/YEU_CAU_C2.md", "/du_lieu/LENH_BAN_GIAO_AI.md", ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", "*.crt", "*.cer", "*.token", "*credentials*.json", "/du_lieu/tam_me/", "/du_lieu/san_xuat/", "*.wav", "*.mp4"}
        for rule in sorted(required_rules - ignore_rules):
            issues.append(f"thieu_gitignore_rule:{rule}")
        if any("#" in line and not line.lstrip().startswith("#") for line in ignore_lines):
            issues.append("gitignore_inline_comment")
    if not start.is_file():
        issues.append("thieu_SO_VIEC")
    else:
        issues.extend(check_ledger_invariants(start.read_text(encoding="utf-8")))
    if not requirements.is_file():
        issues.append("thieu_YEU_CAU_C2")
    else:
        text = requirements.read_text(encoding="utf-8")
        for anchor, required_terms in REQUIRED_AUTHORITY_ANCHORS.items():
            missing = [term for term in required_terms if term not in text]
            if missing:
                issues.append(f"thieu_neo:{anchor}:{','.join(missing)}")
    issues.extend(check_temp_paths(root, environ))
    if project_free_gb is None:
        project_free_gb = shutil.disk_usage(root.drive + "\\").free / (1024 ** 3)
    if c_free_gb is None:
        c_free_gb = shutil.disk_usage("C:\\").free / (1024 ** 3)
    issues.extend(check_disk_thresholds(project_free_gb, c_free_gb))
    issues.extend(scan_project_for_secrets(root))
    return issues


def main():
    root = Path(__file__).resolve().parents[2]
    issues = run_checks(root)
    if issues:
        for issue in issues:
            print(f"DO: {issue}")
        return 1
    print("XANH CÁC KIỂM TRA ĐÃ ĐỊNH NGHĨA: BAT_DAU/gitignore/sổ; nội dung C2-M01..M04; TEMP/TMP; dung lượng E/C; các mẫu bí mật đã cấu hình. CHƯA THỂ XÁC MINH NEO L14 GỐC: gói bàn giao không cung cấp định nghĩa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
