"""Desktop shortcut (user 28.10., option B): "PhotoCraft AI" starts PhotoCraft with the control channel like the starter
.bat, then the bridge window, without a console window. The shortcut itself is made in a temporary folder here, never
on the desktop.

    python tests/test_launcher.py
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import launcher  # noqa: E402

EXE = r"C:\apps\photocraft-0.17.0-windows-x64-portable\photocraft.exe"


def cfg(tmp):
    return {"photocraft": {"host": "127.0.0.1", "port": 7878, "token_file": str(tmp / "photocraft.token"),
                           "exchange_dir": str(tmp / "exchange")}}


def args_checks():
    tmp = Path(tempfile.mkdtemp())
    args = launcher.photocraft_args(EXE, cfg(tmp))
    assert args == [EXE, "--control", "7878", "--control-token-file", str(tmp / "photocraft.token"),
                    "--automation-read-root", str(tmp / "exchange"), "--automation-write-root", str(tmp / "exchange")]
    # the same flags as the starter .bat (that file is only in the private working repo, not in a release)
    bat_file = ROOT / "test new user.bat"
    if bat_file.exists():
        bat = bat_file.read_text(encoding="utf-8", errors="replace")
        for flag in args[1::2]:
            assert flag in bat, flag


def tilde_checks():
    """Linux (found in the VM 4.11.): the exchange folder is "~/.cache/pccomfy/exchange"; PhotoCraft gets the real path, and no
    folder named "~" appears in the working directory."""
    home = Path(tempfile.mkdtemp())
    old = os.environ.get("HOME"), os.environ.get("USERPROFILE")
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
    try:
        c = {"photocraft": {"host": "127.0.0.1", "port": 7878, "token_file": "~/.config/pccomfy/photocraft.token",
                            "exchange_dir": "~/.cache/pccomfy/exchange"}}
        args = launcher.photocraft_args(EXE, c)
        want = str(home / ".cache" / "pccomfy" / "exchange")
        assert args[args.index("--automation-read-root") + 1] == want and args[args.index("--automation-write-root") + 1] == want
        assert args[args.index("--control-token-file") + 1] == str(home / ".config" / "pccomfy" / "photocraft.token")
        assert not any("~" in a for a in args)
        exe = home / "photocraft"
        exe.write_bytes(b"")
        launcher.start_photocraft(str(exe), c, is_open=lambda: True)             # running already: nothing is made
        launcher.start_photocraft(str(exe), c, is_open=iter([False, True]).__next__, popen=lambda *a, **k: None, sleep=lambda s: None)
        assert (home / ".cache" / "pccomfy" / "exchange").is_dir() and not (ROOT / "~").exists()
    finally:
        for k, v in zip(("HOME", "USERPROFILE"), old):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def start_checks():
    tmp = Path(tempfile.mkdtemp())
    exe = tmp / "photocraft.exe"
    exe.write_bytes(b"")
    c = cfg(tmp)
    started = []
    # running with the control channel already: nothing is started
    assert launcher.start_photocraft(str(exe), c, is_open=lambda: True, popen=lambda *a, **k: started.append(a)) is False
    assert started == []
    # not running: started once, then the port opens
    state = {"open": False, "polls": 0}

    def is_open():
        state["polls"] += 1
        return state["open"]

    def popen(args, **kw):
        started.append(args)
        state["open"] = True
    assert launcher.start_photocraft(str(exe), c, is_open=is_open, popen=popen, sleep=lambda s: None) is True
    assert started == [launcher.photocraft_args(str(exe), c)] and (tmp / "exchange").is_dir()
    # the port never opens: a clear message
    try:
        launcher.start_photocraft(str(exe), c, is_open=lambda: False, popen=lambda *a, **k: None, sleep=lambda s: None, wait_s=0.05)
        raise AssertionError("no error")
    except launcher.LaunchError as e:
        assert "7878" in str(e)
    # no PhotoCraft at that path
    try:
        launcher.start_photocraft(str(tmp / "missing.exe"), c, is_open=lambda: False)
        raise AssertionError("no error")
    except launcher.LaunchError as e:
        assert "not found" in str(e)


def shortcut_checks():
    spec = launcher.shortcut_spec(EXE)
    assert spec["name"] == "PhotoCraft AI" and spec["icon"] == EXE + ",0"
    assert str(launcher.SCRIPT) in spec["args"] and f'--photocraft "{EXE}"' in spec["args"] and launcher.SCRIPT.exists()
    if sys.platform != "win32":
        return
    assert spec["target"].lower().endswith("pythonw.exe")             # no console window
    folder = tempfile.mkdtemp()
    lnk = launcher.create_shortcut(EXE, folder=folder)
    assert lnk == Path(folder) / "PhotoCraft AI.lnk" and lnk.exists()
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
          "$s.TargetPath; $s.Arguments; $s.IconLocation; $s.WorkingDirectory")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout
    target, args, icon, workdir = out.strip().splitlines()
    assert target.lower() == spec["target"].lower() and args == spec["args"], (target, args)
    assert re.sub(r",\s*0$", "", icon).lower() == EXE.lower() and workdir.lower() == str(launcher.ROOT).lower()


def cli_checks():
    from pccomfy import __main__ as cli
    called = []
    old = launcher.main_shortcut
    launcher.main_shortcut = lambda exe, name: called.append((exe, name)) or 0
    try:
        assert cli.main(["shortcut", "--photocraft", EXE]) == 0
    finally:
        launcher.main_shortcut = old
    assert called == [(EXE, "PhotoCraft AI")]


def find_checks():
    tmp = Path(tempfile.mkdtemp())
    assert launcher.find_photocraft([tmp]) is None
    for name in ("photocraft-0.16.0-windows-x64-portable", "photocraft-0.17.0-windows-x64-portable", "photocraft-comfyui-bridge"):
        (tmp / name).mkdir()
    for name in ("photocraft-0.16.0-windows-x64-portable", "photocraft-0.17.0-windows-x64-portable"):
        (tmp / name / launcher.exe_name()).write_bytes(b"")
        (tmp / name / launcher.exe_name()).chmod(0o755)
    (tmp / "photocraft-0.99.0-nothing-here").mkdir()          # no exe inside: ignored
    assert launcher.find_photocraft([tmp / "missing", tmp]) == str(tmp / "photocraft-0.17.0-windows-x64-portable" / launcher.exe_name())
    # no --photocraft: found, then used (the .lnk itself is not made here)
    made = []
    old = launcher.create_shortcut, launcher.find_photocraft, launcher.ask_photocraft
    launcher.find_photocraft = lambda: EXE
    launcher.create_shortcut = lambda exe, name=launcher.NAME, folder=None: made.append(exe) or Path("x.lnk")
    try:
        if sys.platform == "win32":
            assert launcher.main_shortcut(None) in (0, 1) and (made == [EXE] or not Path(EXE).exists())
        launcher.find_photocraft, launcher.ask_photocraft = (lambda: None), (lambda: None)
        assert launcher.main_shortcut(None) == 1               # nothing found, nothing chosen: a message, no crash
    finally:
        launcher.create_shortcut, launcher.find_photocraft, launcher.ask_photocraft = old


def linux_find_checks():
    """The Linux search runs on every system (os.access finds a file executable on Windows)."""
    tmp = Path(tempfile.mkdtemp())
    assert launcher._find_photocraft_linux([tmp]) is None
    for name in ("photocraft-0.18.0-linux-x64", "photocraft-0.19.0-linux-x64"):
        (tmp / name).mkdir()
        (tmp / name / "photocraft").write_bytes(b"")
        (tmp / name / "photocraft").chmod(0o755)
    (tmp / "photocraft-0.99.0-not-executable").mkdir()
    (tmp / "photocraft-0.99.0-not-executable" / "photocraft").write_bytes(b"")
    (tmp / "photocraft-0.99.0-not-executable" / "photocraft").chmod(0o644)
    (tmp / "photocraft-comfyui-bridge").mkdir()                  # this plugin's own folder: no binary inside
    found = launcher._find_photocraft_linux([tmp / "missing", tmp])
    assert found in (str(tmp / "photocraft-0.19.0-linux-x64" / "photocraft"),
                     str(tmp / "photocraft-0.99.0-not-executable" / "photocraft")), found
    if sys.platform != "win32":                                   # Windows treats every file as executable
        assert found == str(tmp / "photocraft-0.19.0-linux-x64" / "photocraft")
    # without roots (what main_shortcut and launch use) $PHOTOCRAFT and PATH count: find_photocraft must not skip them on Linux
    fake = tmp / "my-photocraft"
    fake.write_bytes(b"")
    old_env = os.environ.get("PHOTOCRAFT")
    os.environ["PHOTOCRAFT"] = str(fake)
    try:
        assert launcher._find_photocraft_linux() == str(fake)
        if sys.platform != "win32":
            assert launcher.find_photocraft() == str(fake)
    finally:
        if old_env is None:
            del os.environ["PHOTOCRAFT"]
        else:
            os.environ["PHOTOCRAFT"] = old_env
    tmp2 = Path(tempfile.mkdtemp())
    app =tmp2 / "PhotoCraft-0.20.0-x86_64.AppImage"
    app.write_bytes(b"")
    app.chmod(0o755)
    assert launcher._find_photocraft_linux([tmp2]) == str(app)


def desktop_checks():
    # quoting: spaces stay in one argument; " ` $ \ are escaped and backslashes doubled; % is doubled
    assert launcher._desktop_arg("/a b/c") == '"/a b/c"'
    assert launcher._desktop_arg('x"y') == '"x\\\\"y"'
    assert launcher._desktop_arg("50%") == '"50%%"'
    assert launcher._desktop_arg("a$b") == '"a\\\\$b"'
    text = launcher.desktop_entry("/opt/photo craft/photocraft", python="/home/u/my app/.venv/bin/python")
    lines = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    assert text.startswith("[Desktop Entry]\n") and text.endswith("\n")
    assert lines["Type"] == "Application" and lines["Name"] == "PhotoCraft AI" and lines["Terminal"] == "false"
    assert lines["StartupWMClass"] == "pccomfy" and lines["Path"] == str(launcher.ROOT)
    assert lines["Exec"].startswith('"/home/u/my app/.venv/bin/python" ') and lines["Exec"].endswith(' "/opt/photo craft/photocraft"')
    assert '"--photocraft"' in lines["Exec"]
    folder = tempfile.mkdtemp()
    path = launcher.create_desktop_entry("/x/photocraft", folder=folder)
    assert path == Path(folder) / "photocraft-ai.desktop" and "Exec=" in path.read_text(encoding="utf-8")


def launch_checks():
    tmp = Path(tempfile.mkdtemp())
    c = cfg(tmp)
    # no path at all: a clear message instead of starting "" (Path("") exists: it is the current folder)
    try:
        launcher.start_photocraft("", c, is_open=lambda: False)
        raise AssertionError("no error")
    except launcher.LaunchError as e:
        assert "--photocraft" in str(e)
    # Linux starts PhotoCraft in its own session; Windows gets exactly the arguments it always got
    exe = tmp / launcher.exe_name()
    exe.write_bytes(b"")
    seen = []
    state = {"open": False}
    launcher.start_photocraft(str(exe), c, is_open=lambda: state["open"],
                              popen=lambda args, **kw: (seen.append(kw), state.update(open=True)), sleep=lambda s: None)
    expected = {"cwd": str(launcher.ROOT), "close_fds": True}
    if sys.platform != "win32":
        expected["start_new_session"] = True
    assert seen == [expected], seen


def main():
    args_checks()
    tilde_checks()
    find_checks()
    linux_find_checks()
    desktop_checks()
    launch_checks()
    start_checks()
    shortcut_checks()
    cli_checks()
    print("ALL OK (launcher)")


if __name__ == "__main__":
    main()
