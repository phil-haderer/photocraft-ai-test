"""The visible app name lives only in pccomfy/appname.py (PLAN.md point 20): no other module holds it as a string literal,
and the places that show it take it from there.

    python tests/test_appname.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import appname, launcher  # noqa: E402


def test_values_unchanged():
    assert appname.APP_NAME == "PhotoCraft AI" and appname.WINDOW_TITLE == "PhotoCraft × ComfyUI"
    assert launcher.NAME == appname.APP_NAME


def test_no_other_literal():
    names = {appname.APP_NAME, appname.WINDOW_TITLE}
    for f in sorted((ROOT / "pccomfy").glob("*.py")):
        if f.name == "appname.py":
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value in names:
                # a module docstring or a docstring is an Expr; only count real uses
                raise AssertionError(f"{f.name}:{node.lineno} holds the app name as a literal")


if __name__ == "__main__":
    test_values_unchanged()
    test_no_other_literal()
    print("ok")
