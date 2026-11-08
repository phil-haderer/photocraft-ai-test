"""setup-linux.sh: the file itself everywhere, its functions on Linux (the script is sourced, nothing is installed).

    python tests/test_setup_linux.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "setup-linux.sh"


def file_checks():
    data = SCRIPT.read_bytes()
    assert data.startswith(b"#!/usr/bin/env bash\n") and b"\r" not in data       # LF only, or bash cannot run it
    text = data.decode("utf-8")
    # the same packages as setup-windows.bat
    bat = (ROOT / "setup-windows.bat").read_text(encoding="utf-8", errors="replace")
    packages = text.split('PACKAGES="', 1)[1].split('"', 1)[0]
    assert packages in bat, packages
    # it never installs system packages itself
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        if "sudo" in code:
            assert code.strip().startswith(("*", "echo")) or 'echo "sudo' in code, line


def bash(code):
    return subprocess.run(["bash", "-c", f'source "{SCRIPT}"; {code}'], capture_output=True, text=True, timeout=60)


def function_checks():
    hints = {("ubuntu", "debian"): "apt install", ("debian", ""): "apt install", ("linuxmint", "ubuntu debian"): "apt install",
             ("fedora", ""): "dnf install", ("rocky", "rhel centos fedora"): "dnf install", ("arch", ""): "pacman -S",
             ("manjaro", "arch"): "pacman -S", ("opensuse-tumbleweed", "opensuse suse"): "zypper install",
             ("alpine", ""): "apk add"}
    for (os_id, like), cmd in hints.items():
        out = bash(f'install_hint "{os_id}" "{like}"').stdout.strip()
        assert cmd in out and "tk" in out, (os_id, out)
        assert cmd in bash(f'clipboard_hint "{os_id}" "{like}"').stdout and "xclip" in bash(f'clipboard_hint "{os_id}" "{like}"').stdout
        xc = bash(f'xcursor_hint "{os_id}" "{like}"').stdout
        assert cmd in xc and "xcursor" in xc.lower(), (os_id, xc)
    assert bash('install_hint "plan9" ""').stdout.strip() == ""
    assert bash('xcursor_hint "plan9" ""').stdout.strip() == ""
    assert bash('has_xcursor /nonexistent').returncode != 0
    # sourcing does not run main
    r = bash("true")
    assert r.returncode == 0 and r.stdout == ""
    # the interpreter check: the one running this test, when it has tkinter, is accepted by PYTHON=...
    try:
        import tkinter  # noqa: F401
        import venv  # noqa: F401
        import ensurepip  # noqa: F401
        ok = sys.version_info >= (3, 10)
    except ImportError:
        ok = False
    r = subprocess.run(["bash", "-c", f'source "{SCRIPT}"; PYTHON="{sys.executable}" pick_python'], capture_output=True, text=True)
    if ok:
        assert r.returncode == 0 and r.stdout.strip(), r.stderr
    r = subprocess.run(["bash", "-c", f'source "{SCRIPT}"; PYTHON=/nonexistent PATH=/nonexistent pick_python'], capture_output=True, text=True)
    assert r.returncode != 0 and r.stdout == ""
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    # --check shows the five steps and changes nothing (no venv is made); a wrong option stops with the usage
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "v"
        env = {**os.environ, "PYTHON": sys.executable, "VENV_DIR": str(venv)}
        r = subprocess.run(["bash", str(SCRIPT), "--check"], capture_output=True, text=True, env=env, timeout=60)
        if ok:
            assert r.returncode == 0 and not venv.exists(), (r.stdout, r.stderr)
            for n in range(1, 6):
                assert f"[{n}/5]" in r.stdout, r.stdout
            assert "nothing was changed" in r.stdout
    r = subprocess.run(["bash", str(SCRIPT), "--bogus"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "Usage:" in r.stdout
    r = subprocess.run(["bash", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "--check" in r.stdout


def main():
    file_checks()
    if sys.platform.startswith("linux") and shutil.which("bash"):
        function_checks()
    print("ALL OK (setup-linux)")


if __name__ == "__main__":
    main()
