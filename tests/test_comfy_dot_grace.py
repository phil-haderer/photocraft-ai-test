"""The ComfyUI dot stays green over short stalls (a big model loading, user 11.11.): red only after 3 failed probes in a row,
a success resets the count, and during a run the poll never turns it red. Run against the stubbed Tk of test_gui_presets.

    python tests/test_comfy_dot_grace.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_settings_ui as ts  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

OK, BAD = "ConnOk.TLabel", "ConnBad.TLabel"


def green(app):
    return app.v_conn.get() == "ComfyUI connected" and app.lbl_dot.cget("style") == OK


def main():
    app = ts.make_app()
    app.refresh = lambda: None
    url = app.comfy.url
    app._comfy_read = True
    app._comfy_alive(url, True)
    assert green(app)
    # two misses keep it green, the third turns it red
    app._comfy_alive(url, False)
    app._comfy_alive(url, False)
    assert green(app)
    app._comfy_alive(url, False)
    assert app.v_conn.get() == "ComfyUI not connected" and app.lbl_dot.cget("style") == BAD
    # a success resets the count: two misses, a success, two misses stay green
    app._comfy_read = True
    app._comfy_alive(url, True)
    app._apply_refresh({"comfy": True})
    assert green(app)
    app._comfy_alive(url, False)
    app._comfy_alive(url, False)
    app._comfy_alive(url, True)
    app._comfy_alive(url, False)
    app._comfy_alive(url, False)
    assert green(app)
    # an active run: never red from the poll
    app._running = True
    for _ in range(10):
        app._comfy_alive(url, False)
    assert green(app)
    app._running = False
    app._comfy_alive(url, False)                      # the run is over and the misses go on: red at once
    assert app.lbl_dot.cget("style") == BAD
    # before any success (not up) a miss shows red at once, as before
    app2 = ts.make_app()
    app2._comfy_up = False
    app2._comfy_alive(app2.comfy.url, False)
    assert app2.lbl_dot.cget("style") == BAD
    print("ok")


if __name__ == "__main__":
    main()
