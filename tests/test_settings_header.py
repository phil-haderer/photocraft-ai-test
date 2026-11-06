"""The header of the settings window in the real Tk window (hidden): as high as the plugin's header, the title "Settings"
in the title size (H1: 12 pt, white, thin) at the plugin title's distance from the left edge, and a white line above the
tabs All models / Other settings / Credits (user 6.11.). Skipped when Tk cannot open a window.

    python tests/test_settings_header.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-sethead-")
os.environ["PCCOMFY_HOME"] = TMP
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    _r = tkinter.Tk()
    _r.destroy()
except Exception as e:                      # no display / no Tk
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui  # noqa: E402


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.root.update()
    app.open_settings()
    app._settings_win.update()
    bar, title = app._set_bar, [w for w in app._set_bar.winfo_children() if str(w.winfo_class()) == "TLabel"][0]
    # same height as the plugin's header (f_logo is as high as a function button); the windows are not mapped, so ask for the wanted size
    assert bar.winfo_reqheight() == app.f_logo.winfo_reqheight(), (bar.winfo_reqheight(), app.f_logo.winfo_reqheight())
    # same title size as the plugin's title, white, not bold
    assert str(title.cget("text")) == "Settings"
    assert str(title.cget("font")) == str(app.lbl_title[0].cget("font")), (title.cget("font"), app.lbl_title[0].cget("font"))
    assert str(title.cget("foreground")) == "#ffffff"
    # the white line sits above the notebook with the tabs, under the header
    sep, nb = app.sep_set_tabs, app.nb_settings
    assert str(sep.cget("style")) == "SepWhite.TFrame" and int(str(sep.cget("height"))) == 1
    order = app._settings_win.pack_slaves()
    assert order.index(bar) < order.index(sep) < order.index(nb), order
    app._settings_close()
    app.root.destroy()
    shutil.rmtree(TMP, ignore_errors=True)
    print("ok settings header")


if __name__ == "__main__":
    main()
