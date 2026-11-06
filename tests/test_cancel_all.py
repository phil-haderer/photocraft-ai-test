"""Cancel and Cancel all with variants that run one after the other (Bridge._run_sequence, user 3.11.): Cancel ends only the
variant that is running, Cancel all ends it and the ones still to come. Also the buttons of the window.

    python tests/test_cancel_all.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-ca-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
from pccomfy.comfy import Cancelled  # noqa: E402

REFINE = ROOT / "workflows" / "flux3-klein-refine.json"


class CancelAt(T.FakeComfy):
    """Raises Cancelled in the wait of the given runs (0-based), as the real wait does once the cancel flag is set."""
    def __init__(self, bridge, at, how):
        super().__init__()
        self.bridge, self.at, self.how, self.n = bridge, set(at), how, 0

    def wait(self, pid, on_progress=None, cancelled=None, timeout=0, on_preview=None):
        k, self.n = self.n, self.n + 1
        if k in self.at:
            getattr(self.bridge, self.how)()
            assert cancelled()
            raise Cancelled()
        return super().wait(pid, on_progress, cancelled, timeout, on_preview)


def run(at, how, variants=3):
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = CancelAt(b, at, how)
    req = Request(mode="refine", workflow=str(REFINE), scale=1.0, variants=variants)
    req.params = workflows.GenParams(prompt="", seed=7)
    try:
        return b, b.run(req)
    except Cancelled:
        return b, None


def bridge_tests():
    b, res = run({1}, "cancel")                     # Cancel in the middle one: the first and the last still come
    assert res and len(res["layers"]) == 2 and not b.cancel_all_requested(), res
    b, res = run({1}, "cancel_all")                 # Cancel all: nothing after it
    assert res is None and b.cancel_all_requested() and len(b.comfy.graphs) == 2, len(b.comfy.graphs)   # the third never starts
    b, res = run({0, 1, 2}, "cancel")               # every variant cancelled one by one: the run is cancelled
    assert res is None
    b, res = run({2}, "cancel")                     # the last one cancelled, two results stay
    assert res and len(res["layers"]) == 2
    b, res = run({0}, "cancel", variants=1)         # a single run: Cancel ends it
    assert res is None
    b.reset_cancel_all()
    assert not b.cancel_all_requested()


def window_tests():
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception as e:
        print(f"(window part skipped: no Tk window: {e})")
        return
    import time
    from pccomfy import config as cfgmod, gui
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    for _ in range(25):
        app.root.update()
        time.sleep(0.02)
    assert not app.b_stop_all.winfo_manager()                       # not shown at rest
    app._show_stop_all(True)
    app.root.update()
    assert app.b_stop_all.winfo_manager() == "pack"
    assert app.b_stop_all.winfo_x() > app.b_stop.winfo_x()          # right of Cancel
    from tkinter import font as tkfont
    assert app.b_stop_all.winfo_width() >= tkfont.Font(root=app.root, font=gui.font(9)).measure("Cancel all") + 10   # the whole text shows
    used = app.b_redo.winfo_x() + app.b_redo.winfo_width()
    assert used <= app.f_go.winfo_width(), (used, app.f_go.winfo_width())    # the row still fits the window with Undo and Redo
    calls = []
    app.bridge.cancel_all = lambda: calls.append("all")
    app.bridge.cancel = lambda: calls.append("one")
    app.worker = type("W", (), {"is_alive": lambda self: True})()
    app.stop()
    app.stop_all()
    assert calls == ["one", "all"], calls
    app.worker = None
    app._show_stop_all(False)
    app.root.update()
    assert not app.b_stop_all.winfo_manager()
    app.root.destroy()


if __name__ == "__main__":
    bridge_tests()
    window_tests()
    print("ALL OK (cancel all)")
