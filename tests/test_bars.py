"""The single progress bar must not touch Tk when nothing changed (that caused the blinking) and must never jump back.
Run: python tests/test_bars.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets  # noqa: F401  (installs the tkinter stubs)
from pccomfy import gui


class Bar:
    def __init__(self): self.calls = []
    def configure(self, **kw): self.calls.append(kw)


class V:
    def __init__(self): self.v = ""; self.sets = 0
    def get(self): return self.v
    def set(self, x): self.v = x; self.sets += 1


app = object.__new__(gui.App)
app.pb, app.v_pl, app._bar_value = Bar(), V(), 0.0

# prompt phase without a real fraction: label counts seconds, the bar stays where it is
for _ in range(20):
    app._set_progress(0.0, "Writing the prompt… 12 s", "prompt", -1.0, 12)
assert app.v_pl.v == "Expanding Prompt · 12 s" and app.pb.calls == [] and app.v_pl.sets == 1, (app.v_pl.v, app.pb.calls)

# the image phase moves the bar forward, repeated identical updates change nothing
for _ in range(20):
    app._set_progress(0.5, "Sampling 5/10…", "image", 0.5, 4)
assert app.v_pl.v == "Generating · Sampling 5/10" and app.pb.calls == [{"value": 0.5}], app.pb.calls

# unknown progress (-1) or a lower value never moves the bar back
app._set_progress(-1, "Generating the image… 6 s", "image", -1.0, 6)
assert app.v_pl.v == "Generating · 6 s"
app._set_progress(0.3, "Sampling 3/10…", "image", 0.3, 6)
assert app._bar_value == 0.5 and app.pb.calls == [{"value": 0.5}]

# a step other than sampling that lasts a while is named (user 30.10.); the bar stays where it is
app._set_progress(-1, "Loading models", "stage", -1.0, 5)
assert app.v_pl.v == "Loading models · 5 s" and app._bar_value == 0.5
app._set_progress(0.6, "tile 2 · step 3/15", "image", 0.2, 9)
assert app.v_pl.v == "Generating · tile 2 · step 3/15"

# with a model chosen the line names it (user 4.11.)
class _M:
    label = "Qwen Image 2.1"
app._model = lambda: _M()
app._set_progress(0.6, "Sampling 6/10…", "image", 0.6, 9)
assert app.v_pl.v == "Qwen Image 2.1 is generating · Sampling 6/10", app.v_pl.v
# a model chosen during the run does not rename it: the run keeps the label it started with (window test E, 11.11.)
app._running, app._run_label = True, "Qwen Image 2.1"
class _N:
    label = "Flux 3"
app._model = lambda: _N()
app._set_progress(0.7, "Sampling 7/10…", "image", 0.7, 10)
assert app.v_pl.v == "Qwen Image 2.1 is generating · Sampling 7/10", app.v_pl.v
app._running = False
app._model = lambda: None

# a new run starts from zero, a finished one is full
app._reset_progress()
assert app._bar_value == 0.0 and app.v_pl.v == ""
app._reset_progress(done=True)
assert app._bar_value == 1.0 and app.v_pl.v == "Done"      # clearly readable above the full bar
print("ALL OK (bars)")
