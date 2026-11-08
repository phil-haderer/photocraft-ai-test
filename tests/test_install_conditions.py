"""Install conditions found in the review of 5.11.2026 (PhotoCraft 0.20.2):
 - Python 3.10 (Ubuntu 22.04, Mint 21): no tomllib, tomli takes over; no source needs syntax newer than 3.10
 - the PhotoCraft search finds the MSI location (Programs\\ArtCraft\\PhotoCraft) and an AppImage in ~/.local/bin
 - the hint when the running PhotoCraft is not the tested version (never blocks)
 - "My settings" (settings.json) are never in git: git pull cannot touch them, the export leaves them out

    python tests/test_install_conditions.py
"""
import ast
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from pccomfy import launcher, photocraft  # noqa: E402


def python310_checks():
    # 1. syntax: nothing in the plugin or the tools needs a newer Python than 3.10
    bad = []
    for folder in ("pccomfy", "tools"):
        for f in sorted((ROOT / folder).glob("*.py")):
            try:
                ast.parse(f.read_text(encoding="utf-8"), feature_version=(3, 10))
            except SyntaxError as e:
                bad.append(f"{f.name}: {e}")
    assert not bad, bad
    # 2. config.py on a fake 3.10: tomllib is not looked at, tomli is used
    code = (
        "import sys, types\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "sys.version_info = (3, 10, 12, 'final', 0)\n"
        "sys.modules['tomllib'] = None\n"                           # an import of it would fail
        "sys.modules['tomli'] = types.SimpleNamespace(load=lambda f: {}, marker='tomli')\n"
        "from pccomfy import config\n"
        "assert config.tomllib.marker == 'tomli'\n"
        "print('ok')\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr
    # 3. the packaging says the same
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject and "tomli; python_version < '3.11'" in pyproject
    sh = (ROOT / "setup-linux.sh").read_text(encoding="utf-8")
    assert "python3.10" in sh and "(3, 10)" in sh and "pip install tomli" in sh and "(3, 11)" not in sh


def find_checks():
    # the Linux search without roots: ~/.local/bin holds a photocraft-*.AppImage
    home = Path(tempfile.mkdtemp())
    app = home / ".local" / "bin" / "photocraft-0.20.2-x86_64.AppImage"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"")
    app.chmod(0o755)
    keys = ("HOME", "USERPROFILE", "PHOTOCRAFT", "PATH")
    old = {k: os.environ.get(k) for k in keys}
    old_root = launcher.ROOT
    try:
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
        os.environ.pop("PHOTOCRAFT", None)
        os.environ["PATH"] = str(home / "empty")
        launcher.ROOT = home / "bridge" / "x"                    # ROOT.parent must not hold a PhotoCraft
        assert launcher._find_photocraft_linux() == str(app)
        # Windows: the MSI puts it at %LOCALAPPDATA%\Programs\ArtCraft\PhotoCraft\photocraft.exe
        if launcher.IS_WINDOWS:
            local = home / "AppData" / "Local"
            exe = local / "Programs" / "ArtCraft" / "PhotoCraft" / "photocraft.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            os.environ["LOCALAPPDATA"] = str(local)
            os.environ["ProgramFiles"] = os.environ["ProgramFiles(x86)"] = str(home / "pf")
            assert launcher.find_photocraft() == str(exe), launcher.find_photocraft()
    finally:
        launcher.ROOT = old_root
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def version_checks():
    note = photocraft.version_note
    assert note("0.20.1", "0.20.1") is None and note(None) is None and note("", "0.20.1") is None and note("dev", "0.20.1") is None
    assert "newer" in note("0.20.2", "0.20.1") and "0.20.2" in note("0.20.2", "0.20.1")
    assert "newer" in note("0.21.0", "0.20.9") and "newer" in note("1.0.0", "0.99.9")
    assert "older" in note("0.19.0", "0.20.1") and "older" in note("0.9.0", "0.10.0")     # compared as numbers, not as text
    assert "newer" in note("v0.20.2-beta", "0.20.1")                     # a prefix and a suffix are cut off
    # the client: currentVersion of updates.status; no answer or an error gives None
    pc = photocraft.PhotoCraft.__new__(photocraft.PhotoCraft)
    pc.execute = lambda cmd, params=None: {"supported": True, "currentVersion": "0.20.2", "result": {}}
    assert pc.version() == "0.20.2"
    pc.execute = lambda cmd, params=None: {}
    assert pc.version() is None
    def boom(cmd, params=None):
        raise photocraft.PhotoCraftError("unknown command")
    pc.execute = boom
    assert pc.version() is None


def my_settings_checks():
    """"Set as my settings" lives in settings.json (key saved_pages) in data/ (Windows) or ~/.config/pccomfy (Linux): never in git."""
    ignore = [l.strip() for l in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert "data/" in ignore
    if (ROOT / "tools" / "export_release.py").exists():                # private repo only (the release leaves it out)
        import export_release as ex
        for name in ("data/settings.json", "data/state.json", "data/history.json", "data/exchange/runs.jsonl"):
            assert ex.excluded(name) or "data/" in ignore, name
    try:
        tracked = subprocess.run(["git", "ls-files", "data", "settings.json", "state.json", "config.toml"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return                                                       # no git here (a ZIP copy): nothing to check
    if tracked.returncode == 0:
        assert tracked.stdout.strip() == "", f"tracked user data: {tracked.stdout}"
    from pccomfy import config
    assert config.SETTINGS_FILE.name == "settings.json"


def main():
    python310_checks()
    find_checks()
    version_checks()
    my_settings_checks()
    print("ALL OK (install conditions)")


if __name__ == "__main__":
    main()
