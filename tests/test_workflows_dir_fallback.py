"""An old config.toml can point workflows_dir at a folder without the plugin's workflows (the former Linux default
~/.config/pccomfy/workflows, nobody filled it); then no model had a workflow and the window ran the built-in SD1.5 graph
(tester 7.11.). The plugin's own folder is used instead, with a note. No Tk.

    python tests/test_workflows_dir_fallback.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-wd-")
sys.path.insert(0, str(ROOT))

from pccomfy import config as cfgmod  # noqa: E402

eff = cfgmod.effective_workflows_dir
tmp = Path(tempfile.mkdtemp(prefix="pccomfy-wd-f-"))

p, note = eff(str(cfgmod.WORKFLOWS_DIR))                  # the default: untouched, no note
assert p == cfgmod.WORKFLOWS_DIR and note == ""

p, note = eff(str(tmp / "gone"))                           # a folder that does not exist
assert p == cfgmod.WORKFLOWS_DIR and "config.toml" in note and "gone" in note, note

(tmp / "empty").mkdir()                                    # an empty folder (the old default)
p, note = eff(str(tmp / "empty"))
assert p == cfgmod.WORKFLOWS_DIR and note

(tmp / "mine").mkdir()                                     # only your own workflows: the models cannot run, same fallback
(tmp / "mine" / "my-own.json").write_text("{}", encoding="utf-8")
assert eff(str(tmp / "mine"))[0] == cfgmod.WORKFLOWS_DIR

(tmp / "copy").mkdir()                                     # a folder that holds the plugin's workflows (and more): kept
for f in cfgmod.WORKFLOWS_DIR.glob("*.json"):
    shutil.copy(f, tmp / "copy" / f.name)
(tmp / "copy" / "my-own.json").write_text("{}", encoding="utf-8")
p, note = eff(str(tmp / "copy"))
assert p == tmp / "copy" and note == "", (p, note)

# the window uses it
src = (ROOT / "pccomfy" / "gui.py").read_text(encoding="utf-8")
assert "cfgmod.effective_workflows_dir(cc[" in src
print("ALL OK (workflows dir fallback)")
