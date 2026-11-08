"""The install matrix (.github/workflows/install-matrix.yml) and what it needs from the setup scripts.

    python tests/test_install_matrix.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "install-matrix.yml"
BAT = ROOT / "setup-windows.bat"
SMOKE = ROOT / "tests" / "ci_install_smoke.py"


def bat_checks():
    raw = BAT.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), "setup-windows.bat must keep CRLF (cmd labels)"
    text = raw.decode("utf-8")
    assert '"/nopause"' in text and "[/nopause]" in text
    # every wait for a key goes through :waitkey, which /nopause skips (an automatic run would hang otherwise)
    pauses = [ln.strip() for ln in text.splitlines() if ln.strip().lower().split("&")[0].strip() == "pause" or ln.strip().lower().endswith(" pause")]
    assert pauses == ["if not defined NOPAUSE pause"], pauses
    # PYTHON is tried before the py launcher
    assert text.index('if defined PYTHON call :try "%PYTHON%"') < text.index("call :tryv")
    # data\python.txt: written by Python as UTF-8, never by echo (the console code page breaks umlauts; 8.11.)
    assert "write_text(sys.executable, encoding='utf-8')" in text
    assert "python.txt" not in "".join(ln for ln in text.splitlines() if ln.lstrip().lower().startswith("(echo"))
    # every batch file that reads it switches to code page 65001 first
    for name in ("check-windows.bat", "test new user.bat"):
        p = ROOT / name
        if not p.exists():          # "test new user.bat" is private only
            continue
        t = p.read_text(encoding="utf-8")
        assert "chcp 65001" in t and t.index("chcp 65001") < t.index("set /p PY="), name


def autostart_reads_old_and_new():
    import sys
    import tempfile
    sys.path.insert(0, str(ROOT))
    from pccomfy import autostart, config
    old = config.CONFIG_DIR
    with tempfile.TemporaryDirectory() as d:
        try:
            config.CONFIG_DIR = Path(d)
            (Path(d) / "python.txt").write_text("D:\\Tools Jörg Ä\\py.exe\n", encoding="utf-8")
            assert autostart._python_txt() == "D:\\Tools Jörg Ä\\py.exe"
            enc = "oem" if sys.platform == "win32" else "latin-1"     # written by the old setup (echo)
            (Path(d) / "python.txt").write_bytes("D:\\Tools Jörg Ä\\py.exe\r\n".encode("cp850" if enc == "oem" else enc))
            got = autostart._python_txt()
            bs_py = "\\py.exe"
            assert got.startswith("D:\\Tools J") and got.endswith(bs_py), got
            (Path(d) / "python.txt").unlink()
            assert autostart._python_txt() == ""
        finally:
            config.CONFIG_DIR = old


def workflow_checks():
    text = WF.read_text(encoding="utf-8")
    for need in ("setup-windows.bat /nopause", "./setup-linux.sh", "tests\\ci_install_smoke.py --expect-shortcut",
                 "tests/ci_install_smoke.py --expect-shortcut", "Jörg Ä", "ubuntu-22.04", "ubuntu-24.04",
                 "debian:12", "fedora:latest", "archlinux:latest", "branches: [main]"):
        assert need in text, need
    # the hints the workflow expects are the ones setup-linux.sh prints
    sh = (ROOT / "setup-linux.sh").read_text(encoding="utf-8")
    for hint in ("sudo apt install python3 python3-tk python3-venv", "sudo dnf install python3 python3-tkinter", "sudo pacman -S python tk"):
        assert hint in text and hint in sh, hint
    assert "\t" not in text, "YAML must not contain tabs"


def smoke_checks():
    # not a test_*.py file: tests/run_all.py must not run it (it needs a display and an installed setup)
    assert not SMOKE.name.startswith("test_")
    text = SMOKE.read_text(encoding="utf-8")
    assert "8188" not in text and "comfy.ComfyClient" not in text      # never talks to ComfyUI


if __name__ == "__main__":
    bat_checks()
    autostart_reads_old_and_new()
    workflow_checks()
    smoke_checks()
    print("install matrix: ok")
