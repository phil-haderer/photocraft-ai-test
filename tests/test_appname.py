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
    assert appname.HEADER_TITLE == ("PhotoCraft", "×", "ComfyUI")
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


def test_header_title():
    """The header shows HEADER_TITLE: the names white and thin, the sign blue and bold, all at 12 pt (user 3.11.)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
    from pccomfy.gui_common import ACCENT, font
    app = t.gui.App(t.cfgmod.load())
    assert tuple(w["text"] for w in app.lbl_title) == appname.HEADER_TITLE
    assert [w["foreground"] for w in app.lbl_title] == ["#ffffff", ACCENT, "#ffffff"]
    assert [w["font"] for w in app.lbl_title] == [font(12), font(12, bold=True), font(12)]


if __name__ == "__main__":
    test_values_unchanged()
    test_no_other_literal()
    test_header_title()
    print("ok")
