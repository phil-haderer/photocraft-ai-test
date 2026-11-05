"""The ComfyUI dot shows the real state from the first moment (tester 5.11.): the start asks once before the window appears;
the dot is neither green nor red by assumption. A server that does not answer costs at most the short timeout.

    python tests/test_comfy_dot_initial.py
"""
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import comfyaddr, gui_state  # noqa: E402


class Var:
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v


class Dot:
    def __init__(self):
        self.style = None

    def configure(self, **kw):
        self.style = kw.get("style")


def start(answer):
    app = types.SimpleNamespace(comfy=types.SimpleNamespace(url="http://127.0.0.1:59999"), v_conn=Var(), lbl_dot=Dot())
    seen = []
    old_probe, old_env = comfyaddr.probe, os.environ.pop("PCCOMFY_NO_WATCH", None)
    comfyaddr.probe = lambda url, timeout=3.0: (seen.append((url, timeout)), (answer, "x"))[1]
    try:
        gui_state.StateMixin._initial_comfy_state(app)
    finally:
        comfyaddr.probe = old_probe
        if old_env is not None:
            os.environ["PCCOMFY_NO_WATCH"] = old_env
    return app, seen


app, seen = start(True)
assert app.v_conn.value == "ComfyUI connected" and app.lbl_dot.style == "ConnOk.TLabel" and app._comfy_up is True
assert seen == [("http://127.0.0.1:59999", 0.5)], seen                  # one question, short timeout, the plugin's own address
app, _ = start(False)
assert app.v_conn.value == "ComfyUI not connected" and app.lbl_dot.style == "ConnBad.TLabel" and app._comfy_up is False

# in the test runs (PCCOMFY_NO_WATCH) nothing is asked
app = types.SimpleNamespace(comfy=types.SimpleNamespace(url="x"), v_conn=Var(), lbl_dot=Dot())
os.environ["PCCOMFY_NO_WATCH"] = "1"
gui_state.StateMixin._initial_comfy_state(app)
assert app.v_conn.value is None and app.lbl_dot.style is None

# the window calls it right after building the footer
src = (ROOT / "pccomfy" / "gui.py").read_text(encoding="utf-8")
assert src.index("self._build(d)") < src.index("self._initial_comfy_state()") < src.index("self._set_loras(")
print("ALL OK (comfy dot initial)")
