"""The Styles button in the real Tk window (hidden): it sits in the middle of the row over the field (Describe Canvas and Save on the left) in every function with a prompt field, and
the menu starts with the submenu Custom prompts (user 11.11.), a separator and a submenu per group (only where the mode has styles), an entry is ADDED to the prompt after a line break in one undo step (Ctrl+Z takes it away),
and the hover box shows the whole text. Skipped when Tk cannot open a window.

    python tests/test_styles_gui.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-stylesgui-")
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
from pccomfy import gui, models, styles  # noqa: E402


def shown(w) -> bool:
    return bool(w.winfo_manager())


def row_checks(app):
    """The row over the field (user 10.11. evening, docs/plan-vorschlaege-10-11.md P2, P3, P5): Describe Canvas on the left, the
    blue Styles button in the middle (palette left of the text, as high as Generate), the bin inside the field, bottom right,
    and the text keeps a right margin as wide as the bin."""
    app.root.update()
    row = app.f_ptop
    assert app.b_styles.master is app.f_pleft and app.f_pleft.master is row
    assert str(app.b_styles.cget("style")) == "Styles.TButton" and str(app.b_styles.cget("compound")) == "left"
    assert app.b_styles.winfo_rootx() - row.winfo_rootx() <= 2                     # first on the left (window test E, 11.11.)
    assert app.b_styles.winfo_rootx() < app.b_save.winfo_rootx() < app.b_llm.winfo_rootx()     # Styles, Save, Describe
    assert app.b_styles.winfo_height() == app.b_go.winfo_height(), (app.b_styles.winfo_height(), app.b_go.winfo_height())   # window test F
    assert app.b_styles.winfo_reqheight() == app.b_go.winfo_height()          # its own height, not stretched by the row
    assert str(app.b_stop.cget("text")) == "" and app.b_stop.cget("image") and app.b_stop.winfo_height() == app.b_go.winfo_height()   # Cancel: a stop square
    assert app.b_styles.winfo_width() < app.b_go.winfo_width() * 2           # width from its text, not stretched
    t, b = app.t_prompt, app.b_clear
    assert b.master is t and b.winfo_manager() == "place"
    assert t.winfo_width() - (b.winfo_x() + b.winfo_width()) <= 6 and t.winfo_height() - (b.winfo_y() + b.winfo_height()) <= 6
    t.delete("1.0", "end")
    t.insert("1.0", "word " * 200)
    app._prompt_placeholder()
    assert "pc_margin" in t.tag_names("1.0") and "pc_margin" in t.tag_names("end-2c")
    assert int(t.tag_cget("pc_margin", "rmargin")) >= b.winfo_reqwidth()
    t.delete("1.0", "end")


def describe_checks(app):
    """Describe Canvas only in Text to image and in Upscale / Refine while the picture is not made in tiles (P4)."""
    def at(model, mode):
        app.v_model.set(model)
        app.v_mode.set(mode)
        app._on_model()
        app.root.update()
        return shown(app.b_llm)
    assert at("flux3", "txt2img")
    for mode in ("edit", "multi_edit", "outpaint", "inpaint", "remove"):
        assert not at("qwen", mode), mode
    assert not at("flux3", "upscale")               # Flux 3 Upscale always works in tiles
    assert not at("flux2", "upscale")               # Flux 2 Upscale: the stage "Tiles" is on at the start
    i = next(i for i, st in enumerate(app._stages()) if "tile" in st["label"].lower())
    app.stage_vars[i].set(False)
    app._on_stage(i)
    assert shown(app.b_llm)                         # tiles off: the description goes to the whole picture
    app.stage_vars[i].set(True)
    app._on_stage(i)
    assert not shown(app.b_llm)
    assert at("flux2", "refine") and at("qwen", "upscale")


def custom_checks(app):
    """The Prompt-Saver (user 11.11.): Save next to Describe Canvas (in its place where that is hidden), Styles in every function,
    Custom prompts at the top; Use replaces, Append appends, one undo step each; the label has model and function."""
    from unittest import mock
    from pccomfy import custom_prompts, gui_prompt
    app.v_model.set("flux3")
    app.v_mode.set("txt2img")
    app._on_model()
    app.root.update()
    assert shown(app.b_save) and shown(app.b_llm) and app.b_save.winfo_rootx() < app.b_llm.winfo_rootx()
    app.v_mode.set("edit")
    app._on_model()
    app.root.update()
    assert not shown(app.b_llm) and shown(app.b_save)
    assert app.b_styles.winfo_rootx() < app.b_save.winfo_rootx() <= app.f_pchoice.winfo_rootx()
    for mode in ("txt2img", "outpaint", "inpaint", "remove", "edit", "multi_edit", "upscale", "refine"):
        assert mode in app.m_styles and app.m_styles[mode].entrycget(0, "label") == "Custom prompts", mode
    t = app.t_prompt
    # an empty field: the status line, no window
    t.configure(state="normal")
    t.delete("1.0", "end")
    app.save_prompt()
    assert app.v_status.get() == "Write a prompt first" and getattr(app, "_cp_win", None) is None
    # save, replace
    t.insert("1.0", "Summer meadow")
    app.save_prompt()
    win = app._cp_win
    assert win.t_text is None
    app.root.update()
    assert win.wm_geometry().endswith(f"+{app._cp_pos[0]}+{app._cp_pos[1]}"), win.wm_geometry()   # really moved there (window test F)
    x, y = app._cp_pos                       # beside the window, top edges level, like the settings (window test E, 11.11.)
    assert y == app.root.winfo_rooty() and (x >= app.root.winfo_rootx() + app.root.winfo_width() or x < app.root.winfo_rootx()), (x, y)
    win.v_name.set("x" * 60)
    assert len(win.v_name.get()) == custom_prompts.MAX_NAME
    win.v_name.set("Meadow")
    win.ok()
    assert getattr(app, "_cp_win", None) is None
    saved = custom_prompts.load()
    assert len(saved) == 1 and saved[0]["name"] == "Meadow" and saved[0]["text"] == "Summer meadow", saved
    assert saved[0]["function"] == "Edit canvas" and saved[0]["model"] == app._cp_tag()[0] and saved[0]["model"]
    app.save_prompt()
    app._cp_win.v_name.set("MEADOW")
    with mock.patch.object(gui_prompt.messagebox, "askyesno", return_value=False) as ask:
        app._cp_win.ok()
        assert ask.called and "Replace it?" in ask.call_args[0][1]
    assert app._cp_win is not None and len(custom_prompts.load()) == 1
    t.delete("1.0", "end")
    t.insert("1.0", "Winter meadow")
    app._cp_win.close()
    app.save_prompt()
    app._cp_win.v_name.set("MEADOW")
    with mock.patch.object(gui_prompt.messagebox, "askyesno", return_value=True):
        app._cp_win.ok()
    assert [e["text"] for e in custom_prompts.load()] == ["Winter meadow"]
    # the menu: normal submenu, label with model and function, Use / Append / Edit / Delete
    app._refresh_custom_menu("edit")
    cm = app.m_custom["edit"]
    lab = cm.entrycget(0, "label")
    assert lab == "[" + app._cp_tag()[0] + " · Edit canvas] MEADOW", lab
    sub = cm.nametowidget(cm.entrycget(0, "menu"))
    assert [sub.entrycget(i, "label") for i in range(4)] == ["Use", "Append", "Edit", "Delete"]
    t.configure(undo=True)
    t.delete("1.0", "end")
    t.insert("1.0", "old text")
    t.edit_reset()
    sub.invoke(0)
    assert t.get("1.0", "end").strip() == "Winter meadow"
    t.edit_undo()
    assert t.get("1.0", "end").strip() == "old text"
    sub.invoke(1)
    assert t.get("1.0", "end").rstrip("\n") == "old text\nWinter meadow"
    t.edit_undo()
    assert t.get("1.0", "end").strip() == "old text"
    # Edit: name and text
    sub.invoke(2)
    w = app._cp_win
    assert w.t_text is not None and w.t_text.get("1.0", "end").strip() == "Winter meadow"
    w.v_name.set("Snow")
    w.t_text.delete("1.0", "end")
    w.t_text.insert("1.0", "Snowy field")
    w.ok()
    assert [(e["name"], e["text"]) for e in custom_prompts.load()] == [("Snow", "Snowy field")]
    # Delete asks first
    app._refresh_custom_menu("edit")
    cm = app.m_custom["edit"]
    sub = cm.nametowidget(cm.entrycget(0, "menu"))
    with mock.patch.object(gui_prompt.messagebox, "askyesno", return_value=False) as ask:
        sub.invoke(3)
        assert "Delete" in ask.call_args[0][1]
    assert len(custom_prompts.load()) == 1
    with mock.patch.object(gui_prompt.messagebox, "askyesno", return_value=True):
        sub.invoke(3)
    assert custom_prompts.load() == []
    assert app.m_custom["edit"].entrycget(0, "label") == "No saved prompts yet" and str(app.m_custom["edit"].entrycget(0, "state")) == "disabled"
    # a field that is off (no function does it today; Remove keeps its field since remove_text): Save and Styles are grey
    t.configure(state="disabled")
    app._update_styles_button()
    assert str(app.b_save.cget("state")) == "disabled" and str(app.b_styles.cget("state")) == "disabled"
    app.save_prompt()
    assert getattr(app, "_cp_win", None) is None
    t.configure(state="normal")
    app._update_styles_button()
    assert str(app.b_save.cget("state")) != "disabled" and str(app.b_styles.cget("state")) != "disabled"


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("flux3")
    app.v_mode.set("multi_edit")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles) and shown(app.b_save)                # in every function since 11.11. (was: not in Multi image edit)
    assert app.m_styles["multi_edit"].index("end") == 0 and app.m_styles["multi_edit"].entrycget(0, "label") == "Custom prompts"
    app.v_mode.set("edit")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles)                                      # Edit canvas has styles since plan B (10.11.)
    assert app.m_styles["edit"].index("end") == len(styles.load()["edit"]) + 1     # + Custom prompts and a separator (11.11.)
    app.v_mode.set("txt2img")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles) and shown(app.b_llm)
    row_checks(app)

    # the menu: a submenu per group, an entry per style, names only
    top = app.m_styles["txt2img"]
    groups = styles.load()["txt2img"]
    assert top.index("end") == len(groups) + 1
    assert top.entrycget(0, "label") == "Custom prompts" and top.type(1) == "separator"     # Custom prompts at the very top (11.11.)
    assert [top.entrycget(i + 2, "label") for i in range(len(groups))] == [g["name"] for g in groups]
    sub = top.nametowidget(top.entrycget(2, "menu"))
    assert [sub.entrycget(i, "label") for i in range(len(groups[0]["styles"]))] == [s["name"] for s in groups[0]["styles"]]

    # an entry is added after a line break; one Ctrl+Z takes it away again; an empty field just gets the style
    app.t_prompt.configure(undo=True)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red bicycle")
    app.t_prompt.edit_reset()
    sub.invoke(2)
    want = groups[0]["styles"][2]["text"]
    assert app.t_prompt.get("1.0", "end").rstrip("\n") == "a red bicycle\n" + want, repr(app.t_prompt.get("1.0", "end"))
    app.t_prompt.edit_undo()
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle", repr(app.t_prompt.get("1.0", "end"))
    app.t_prompt.delete("1.0", "end")
    sub.invoke(2)
    assert app.t_prompt.get("1.0", "end").strip() == want
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red bicycle\n")        # already ends in a line break: no empty line in between
    sub.invoke(2)
    assert app.t_prompt.get("1.0", "end").rstrip("\n") == "a red bicycle\n" + want

    # the hover box: shown for an active entry, gone for none and after a hide. (A real posted menu is a native Windows menu that
    # a test cannot drive reliably, so the active entry is faked: a menu that says entry 1 is active.)
    class Active:
        def __init__(self, real, active):
            self.real, self.active = real, active

        def __str__(self):
            return str(self.real)

        def index(self, what):
            return self.active

        def yposition(self, i):
            return 5

        def __getattr__(self, name):
            return getattr(self.real, name)
    app._style_preview(Active(sub, 1))
    assert app._style_tip is not None
    labels = [w for w in app._style_tip.winfo_children() if w.winfo_class() == "Label"]
    assert labels and labels[0].cget("text") == groups[0]["styles"][1]["text"]
    app._style_tip_hide()
    assert app._style_tip is None
    app._style_preview(Active(sub, "none"))
    assert app._style_tip is None

    # the hover box sits beside the mouse, not at the screen's top left (a native menu reports x = y = 0, width 1)
    app.root.update()
    app._style_preview(Active(sub, 1))
    app.root.update()
    px, py = app.root.winfo_pointerx(), app.root.winfo_pointery()
    gx, gy = app._style_tip_pos
    vx0, vy0, vx1, _vy1 = app._monitor_at(px, py)           # the mouse's screen: left of the main one its x is negative
    assert abs(gy - (py - 12)) < 80 and vx0 <= gx < vx1 and (gx, gy) != (vx0, vy0), (gx, gy, px, py, vx0, vy0, vx1)
    app._style_tip_hide()

    app.v_mode.set("outpaint")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles) and app.m_styles["outpaint"].index("end") == 0     # no styles there: only Custom prompts (11.11.; was: no button)
    app.v_mode.set("txt2img")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles)
    row_checks(app)
    describe_checks(app)
    custom_checks(app)
    app.root.destroy()
    print("ALL OK (styles gui)")


if __name__ == "__main__":
    main()
