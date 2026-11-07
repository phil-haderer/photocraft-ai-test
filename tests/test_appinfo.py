"""The version in the config files and the report of "Copy report" (user 7.11., tester: a version number in the configs).
Parts: version compare, the start check, unwritable folder, the report text (no prompts, home folder as ~), the export's
version stamp, the run log's version, and "Copy report" in a hidden Tk window.

    python tests/test_appinfo.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(tempfile.mkdtemp(prefix="pccomfy-ai-"))
os.environ["PCCOMFY_HOME"] = str(HOME)
sys.path.insert(0, str(ROOT))

from pccomfy import appinfo, config as cfgmod, __version__  # noqa: E402

# ---- compare ----
pv = appinfo.parse_version
assert pv("0.21-test") == (0, 21) and pv("v0.20.2") == (0, 20, 2) and pv("dev") == () and pv(None) == ()
vc = appinfo.version_change
assert vc(None, "0.21", had_files=False) == ("", "")                                  # a first start says nothing
assert vc(None, "0.21", had_files=True) == ("updated", "Updated to version 0.21.")       # files from before the version stamp
assert vc("0.21", "0.21") == ("", "") and vc("0.21-test", "0.21-dev") == ("updated", "Updated from 0.21-test to 0.21-dev.")
assert vc("0.20-test", "0.21-test") == ("updated", "Updated from 0.20-test to 0.21-test.")
kind, text = vc("0.30", "0.21")
assert kind == "newer" and "newer version (0.30)" in text and "this is 0.21" in text
assert vc("weird", "0.21") == ("", "")                                                # not a version: no noise

# ---- the start check and the stamp ----
assert cfgmod.check_version() == "" and cfgmod.load_settings()["_version"] == __version__      # fresh folder: silent, stamped
assert cfgmod.check_version() == ""                                                          # same version again: silent
cfgmod.save_state({"mode": "edit"})
assert json.loads(cfgmod.STATE_FILE.read_text(encoding="utf-8"))["_version"] == __version__
cfgmod.set_setting("model_map", {"a": "b"})
assert cfgmod.get_setting("_version") == __version__ and cfgmod.model_map() == {"a": "b"}
s = cfgmod.load_settings()
s["_version"] = "0.01-test"
cfgmod.SETTINGS_FILE.write_text(json.dumps(s), encoding="utf-8")
assert cfgmod.check_version() == f"Updated from 0.01-test to {__version__}." and cfgmod.get_setting("_version") == __version__
s["_version"] = "99.0"
cfgmod.SETTINGS_FILE.write_text(json.dumps(s), encoding="utf-8")
assert "newer version (99.0)" in cfgmod.check_version() and cfgmod.get_setting("_version") == __version__
s.pop("_version")                                                                            # settings from before the stamp
cfgmod.SETTINGS_FILE.write_text(json.dumps(s), encoding="utf-8")
assert cfgmod.check_version() == f"Updated to version {__version__}."

# ---- a folder that cannot be written says so (it used to lose every setting silently) ----
blocker = HOME / "blocker"
blocker.write_text("x", encoding="utf-8")                                                    # a file where the folder should be
real = cfgmod.SETTINGS_FILE
cfgmod.SETTINGS_FILE = blocker / "settings.json"
assert cfgmod.load_settings() == {} and "could not be saved" in cfgmod.check_version() and cfgmod.write_error()
assert "Settings could not be saved" in appinfo.build_report()
cfgmod.SETTINGS_FILE = real
cfgmod.save_settings({"x": 1})
assert cfgmod.write_error() == ""                                                            # a good write clears it

# ---- the report ----
(HOME / "config.toml").write_text('[comfyui]\nworkflows_dir = "~/gone-folder"\n', encoding="utf-8")
rep = appinfo.build_report()
assert rep.startswith("PhotoCraft x ComfyUI plugin report") and f"Plugin: {__version__}" in rep
assert "config.toml: found" in rep and "config.toml changes: comfyui.workflows_dir" in rep, rep
assert "[config.toml folder replaced by the plugin's own]" in rep and "settings.json: " + __version__ in rep, rep
assert "prompt" not in rep.lower() and "token" not in rep.lower()
home = str(Path.home())
red = appinfo.redact(f"{home}{chr(92)}data and {home.replace(chr(92), '/')}/x and {home.upper()}")
assert home.lower() not in red.lower() and red.count("~") == 3, red
(HOME / "config.toml").write_text("this is [not toml", encoding="utf-8")
assert "config.toml cannot be read" in appinfo.build_report()
(HOME / "config.toml").unlink()

# ---- the export stamps the version of a release ----
spec = importlib.util.spec_from_file_location("export_release", ROOT / "tools" / "export_release.py")
er = importlib.util.module_from_spec(spec)
spec.loader.exec_module(er)
init = er.stamp_version("pccomfy/__init__.py", b'"""doc"""\n\n__version__ = "0.21-dev"      # x\nOTHER = "1"\n', "0.22-test").decode()
assert '__version__ = "0.22-test"' in init and 'OTHER = "1"' in init
assert b'version = "0.22"' in er.stamp_version("pyproject.toml", b'[project]\nname = "a"\nversion = "0.21"\n', "0.22-test")
try:
    er.stamp_version("pccomfy/__init__.py", b"nothing here\n", "1.0")
    raise AssertionError("a missing version line must raise")
except ValueError:
    pass
real_init = (ROOT / "pccomfy" / "__init__.py").read_bytes()
assert b'__version__ = "' + __version__.encode() + b'"' in er.stamp_version("pccomfy/__init__.py", real_init, __version__)   # the real file has the line
assert b"version" in er.stamp_version("pyproject.toml", (ROOT / "pyproject.toml").read_bytes(), "0.99")

# ---- every run line carries the version ----
assert '"version": __version__' in (ROOT / "pccomfy" / "bridge.py").read_text(encoding="utf-8")

# ---- "Copy report" in the window ----
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"(no Tk window for the button: {e})")
else:
    from pccomfy import gui
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    for _ in range(15):
        app.root.update()
        time.sleep(0.02)
    app._copy_report()
    got = app.root.clipboard_get()
    assert got.startswith("PhotoCraft x ComfyUI plugin report") and "Window: model" in got and "ComfyUI: http://127.0.0.1:1" in got, got
    assert "Report copied" in app.v_status.get()
    app.root.destroy()
print("ALL OK (appinfo)")
