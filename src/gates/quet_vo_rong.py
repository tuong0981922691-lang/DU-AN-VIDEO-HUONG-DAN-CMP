import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ast
from pathlib import Path


def _is_empty_body(body):
    statements = list(body)
    if statements and isinstance(statements[0], ast.Expr):
        value = statements[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            statements.pop(0)
    if not statements:
        return True
    if len(statements) != 1:
        return False
    statement = statements[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return statement.value.value is Ellipsis
    if isinstance(statement, ast.Raise) and statement.exc is not None:
        exc = statement.exc.func if isinstance(statement.exc, ast.Call) else statement.exc
        return getattr(exc, "id", None) == "NotImplementedError" or getattr(exc, "attr", None) == "NotImplementedError"
    return False


def find_empty_shells(root):
    root = Path(root)
    issues = []
    for folder in (root / "src", root / "tests"):
        if not folder.exists():
            issues.append(f"thieu_thu_muc:{folder.relative_to(root)}")
            continue
        for path in folder.rglob("*.py"):
            if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
                continue
            relative = path.relative_to(root)
            if path.stat().st_size < 80:
                issues.append(f"vo_rong:{relative}")
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            except (UnicodeDecodeError, SyntaxError) as error:
                issues.append(f"khong_hop_le:{relative}:{error.__class__.__name__}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and _is_empty_body(node.body):
                    issues.append(f"vo_rong_callable:{relative}:{node.name}")
                if isinstance(node, ast.Raise) and node.exc is not None:
                    exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                    if getattr(exc, "id", None) == "NotImplementedError" or getattr(exc, "attr", None) == "NotImplementedError":
                        issues.append(f"chua_cai_dat:{relative}")
                        break
    return issues


def main():
    root = Path(__file__).resolve().parents[2]
    issues = find_empty_shells(root)
    if issues:
        for issue in issues:
            print(f"DO: {issue}")
        return 1
    print("XANH: 0 vỏ rỗng trong src/ và tests/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
