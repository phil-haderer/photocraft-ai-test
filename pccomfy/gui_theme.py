"""Look and sizing: ttk style, scaling, small widget builders, content size. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

import os
import re

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from PIL import Image

from . import config as cfgmod, hostos, icons, spacing, uiscale

ICON_PX = 20       # the window's button icons (vector, icons.py) before the display scaling; the slot icons have their own (19, refslots.py)
FOOT_BTN_PX = round(ICON_PX * 0.85 * 0.9)   # the clock and Copy canvas in the footer: 90 % of the small header icon (user 4.11.)
SMALL_ICON_PX = round(ICON_PX * 0.85)   # flat header icons, the bin and the Styles button: 85 % of the usual icon (user 1.11.)
HINT_ICON_PX = 14  # the info icon in front of the tip under the prompt: about one text line high
FN_GAP = 8         # room between a function symbol and its text (ttk has no gap option: the symbol gets it on its right)
SPIN_PX = 19       # the chevrons of the spin boxes (90 % of the former 21, user 30.10.): cut flat, so the field keeps its height
SPIN_GAP = 3       # px between the up and the down chevron (user 30.10.: 2 to 3)
CHECK_PX = 16      # the checkbox square (PhotoCraft's, measured from docs/design/photocraft-checkbox.png at 150 %)
CHECK_GAP = 6      # room between the checkbox and its text


def stack_height(root) -> int:
    """The height the window's pieces ask for: what the packed children request, plus their gaps and the window's border. Used
    instead of ``root.winfo_reqheight()``: with Tk 9 (PC C, Python with Tk 9.0.4, 5 Nov) that value keeps the size
    ``geometry()`` set and does not follow a child that became higher, so the window never grew when Advanced opened."""
    root.update_idletasks()
    slaves = root.pack_slaves()
    if not slaves:                  # a stand-in window of the tests
        return root.winfo_reqheight()
    total = 0
    for w in slaves:
        info = w.pack_info()
        pady, ipady = (
            [int(float(str(x))) for x in (v if isinstance(v, (tuple, list)) else root.tk.splitlist(str(v)))] or [0]
            for v in (info.get("pady", 0), info.get("ipady", 0)))
        total += (sum(pady) if len(pady) == 2 else pady[0] * 2) + 2 * ipady[0] + w.winfo_reqheight()
    try:
        total += 2 * (int(float(str(root.cget("highlightthickness")))) + int(float(str(root.cget("bd")))))
    except (tk.TclError, ValueError):
        pass
    return total


class ThemeMixin:
    # ---------- UI ----------

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        try:        # Tk's own fonts (menus, the list of a drop-down, entries without a font of their own): ours too
            import tkinter.font as tkfont
            family, size = font(9)[:2]
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                         "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
                tkfont.nametofont(name, root=self.root).configure(family=family, size=size)
        except Exception:
            pass
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#454545",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=font(10))
        s.configure("TLabel", background=BG, foreground=FG)
        # a clicked button keeps no orange focus outline (user 30.10.): after the click the focus goes back to the window
        for cls in ("TButton", "TRadiobutton", "TCheckbutton"):
            self.root.bind_class(cls, "<ButtonRelease-1>", self._drop_focus, add="+")
        self.root.bind_class("TLabel", "<Button-3>", self._copy_menu, add="+")        # every text and link: right-click copies it (user 3.11.)
        self.root.bind_class("TButton", "<Button-3>", self._copy_menu, add="+")       # a link symbol copies its address
        s.configure("Muted.TLabel", foreground=MUTED, font=font(9))
        # the rows of the settings window (ui_settings.py): a bold model line, green / red / orange marks, grey details
        # only the headings are bold; everything else in the window is one size smaller (user 31.10.)
        s.configure("SetHead.TLabel", foreground="#ffffff", font=font(10, bold=True))
        s.configure("SetText.TLabel", foreground="#ffffff", font=font(9))
        s.configure("SetText.TCheckbutton", font=font(9))
        s.configure("SetSmall.TButton", padding=(8, 2), width=0, font=font(9))      # Undo and Reset: small, not stretched
        s.configure("TipOk.TButton", padding=(22, 7), width=0, font=font(11, bold=True))      # "OK" of the tip popup: easy to hit
        for name, colour in (("SetOk", "#ffffff"), ("SetBad", "#ffffff"), ("SetNote", "#ffffff"), ("SetMuted", "#ffffff")):      # all text in the settings is white (user 1.11.)
            s.configure(f"{name}.TLabel", foreground=colour, font=font(9))
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0), bordercolor=BG, lightcolor=BG, darkcolor=BG)     # the tabs of the settings window
        s.configure("TNotebook.Tab", background=BG, foreground="#ffffff", padding=(14, 4), borderwidth=0, expand=(0, 0, 0, 0))
        s.map("TNotebook.Tab", background=[("selected", BG), ("active", BG)], foreground=[("selected", "#ffffff"), ("active", "#ffffff")],
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))],
              padding=[("selected", (14, 4))])      # the theme moves a chosen tab's text (6 4 6 2): the text must stay put
        s.configure("Inner.TNotebook", background=BG, borderwidth=0, tabmargins=(0, 2, 0, 0), bordercolor=BG, lightcolor=BG, darkcolor=BG)       # the model tabs inside "Models"
        s.configure("Inner.TNotebook.Tab", background=BG, foreground="#ffffff", padding=(8, 3), borderwidth=0, expand=(0, 0, 0, 0), font=font(9))
        s.map("Inner.TNotebook.Tab", background=[("selected", BG), ("active", BG)], foreground=[("selected", "#ffffff"), ("active", "#ffffff")],
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))],
              padding=[("selected", (8, 3))])
        for name, colour in (("ConnOk", DONE_GREEN), ("ConnBad", ERROR), ("ConnWait", MUTED)):     # the ComfyUI dot
            s.configure(f"{name}.TLabel", foreground=colour, font=font(9))
        s.configure("Badge.TLabel", background=ERROR, foreground="white", font=font(10, bold=True))
        s.configure("Error.TLabel", foreground=ERROR_TEXT)
        s.configure("TLabelframe", background=BG, bordercolor="#454545")
        s.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        s.configure("TRadiobutton", background=BG, foreground=FG)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        for w in ("TRadiobutton", "TCheckbutton"):
            s.map(w, background=[("active", BG)], indicatorbackground=[("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("selected", "#1b1b1b")])
        s.configure("TButton", background=PANEL, foreground=FG, padding=6)
        s.map("TButton", background=[("active", "#5f5f5f")])
        s.configure("Icon.TButton", padding=(6, 4))
        s.configure("Tab.Toolbutton", background=PANEL, foreground=FG, padding=(8, 5), anchor="w", relief="flat",
                    borderwidth=0, font=font(10))
        s.map("Tab.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", ON_ACCENT)], font=[("selected", font(10, bold=True))])
        # the model buttons of the settings window: the look of the function buttons, a size smaller, centred
        s.configure("Set.Tab.Toolbutton", padding=(8, 3), anchor="center", font=font(9))
        s.map("Set.Tab.Toolbutton", font=[("selected", font(9, bold=True))])
        s.configure("Link.TButton", background=BG, foreground=MUTED, padding=(0, 2), borderwidth=0, relief="flat",
                    width=0)   # as wide as its text: clam's minimum width would centre "Advanced" and push it right
        s.map("Link.TButton", foreground=[("active", FG)], background=[("active", BG)])
        s.configure("Llm.TButton", padding=(4, 1), width=0, font=font(9))     # the "LLM" button at the prompt: short, not stretched
        s.configure("Small.TButton", padding=(8, 2), font=font(9))   # "Show feather" beside the layer mask menu: a button in the size of the slider texts
        # small switches in the look of "Show feather", the chosen one filled orange like the functions (Upscale factor)
        s.configure("Small.Toolbutton", background=PANEL, foreground=FG, padding=(8, 2), font=font(9), anchor="center",
                    relief="flat", borderwidth=0)
        s.map("Small.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", ON_ACCENT)], font=[("selected", font(9, bold=True))])
        # the Easy Mode switch in the header (user 31.10.): no fill, never orange; only its icon turns from grey to orange
        s.configure("Switch.Toolbutton", background=BG, foreground=FG, padding=(4, 2), font=font(9), relief="flat", borderwidth=0)
        s.map("Switch.Toolbutton", background=[("selected", BG), ("active", BG)], foreground=[("selected", FG), ("active", FG)])
        # the model chips under the functions: outlined, no fill; chosen = filled blue with white text (user 3.11.; Tab.Toolbutton is the
        # look of the functions above them)
        s.configure("Chip.Toolbutton", background=BG, foreground=FG, padding=(2, 3), anchor="center", relief="solid",
                    borderwidth=1, bordercolor="#686868", lightcolor=BG, darkcolor=BG, font=font(9))
        s.map("Chip.Toolbutton", foreground=[("disabled", DISABLED), ("selected", ON_ACCENT)],
              bordercolor=[("disabled", "#4a4a4a"), ("selected", ACCENT)], background=[("selected", ACCENT), ("active", "#5f5f5f")],
              font=[("selected", font(9, bold=True))])
        s.configure("Missing.Chip.Toolbutton", foreground=NA_RED)
        s.configure("Accent.TButton", background=ACCENT, foreground=ON_ACCENT, font=font(10, bold=True))
        s.map("Accent.TButton", background=[("active", "#5ba3f5"), ("disabled", "#5a6678")])
        s.configure("Fit.TButton", padding=(5, 6), width=0)     # "Cancel all": as wide as its text (a fixed width cut the last letter)
        s.configure("Split.Accent.TButton", padding=(6, 6))     # the narrow "×2 ▾" piece on the right of Generate
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        s.configure("TCheckbutton", indicatorbackground=PANEL, indicatorforeground=FG)
        s.configure("TRadiobutton", indicatorbackground=PANEL)
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG, arrowsize=self._px(18))   # up/down arrows 50 % larger
        s.configure("Horizontal.TProgressbar", background=ACCENT)
        s.configure("Grip.TFrame", background="#454545")
        s.configure("Hint.TLabel", foreground=ACCENT_TEXT)
        s.configure("Sep.TFrame", background="#9a9a9a")
        s.configure("SepWhite.TFrame", background="#ffffff")       # the line above the model tabs of the settings window (user 1.11.)
        s.configure("SetGreen.TLabel", foreground=DONE_GREEN, font=font(10, bold=True))      # the tick behind a ready model
        s.configure("SetWarn.TLabel", foreground="#f5c542", font=font(9))      # a hint that is no error (unencrypted connection)
        s.configure("SetRed.TLabel", foreground=ERROR_TEXT, font=font(10, bold=True))        # the X behind a model that is not yet available
        s.configure("SetHead9.TLabel", foreground="#ffffff", font=font(9, bold=True))        # "Covers these modes:", the same line height as the list
        s.configure("Done.TLabel", foreground=DONE_GREEN, font=font(10, bold=True))      # the word "Done"
        s.configure("DoneRest.TLabel", foreground=FG, font=font(10, bold=True))        # what follows it (seed, layers, time)
        # greyed out must be visible on the dark theme (clam keeps nearly the normal text colour)
        for w in ("TCheckbutton", "TRadiobutton", "TLabel"):
            s.map(w, foreground=[("disabled", DISABLED)])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.map(w, indicatorbackground=[("disabled", BG), ("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("disabled", DISABLED), ("selected", "#1b1b1b")])
        s.map("TSpinbox", foreground=[("disabled", DISABLED)], fieldbackground=[("disabled", BG)],
              arrowcolor=[("disabled", DISABLED)])
        s.map("TCombobox", foreground=[("disabled", DISABLED), ("readonly", FG)], fieldbackground=[("disabled", BG), ("readonly", PANEL)],
              arrowcolor=[("disabled", DISABLED)])
        # the value of a slider (Slider, gui_common.py) sits in a small dark box on its right, as in PhotoCraft
        s.configure("Value.TLabel", background=PANEL, foreground=FG, padding=(4, 1), font=font(9))
        s.configure("Value.TEntry", fieldbackground=PANEL, foreground=FG, padding=(4, 1), bordercolor=PANEL,
                    lightcolor=PANEL, darkcolor=PANEL, insertcolor=FG)       # the same box, and you can type into it (ValueBox)
        s.map("Value.TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              foreground=[("disabled", DISABLED)], fieldbackground=[("disabled", BG)])
        s.map("TButton", foreground=[("disabled", DISABLED)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self._spin_arrows(s)
        self._checkbox_look(s)
        self._flat_tabs(s)

    def _checkbox_look(self, s):
        """Every checkbox in PhotoCraft's look (docs/design/photocraft-checkbox.png): a rounded square with a light grey
        border on a darker field; ticked = filled orange with a white tick (PhotoCraft's is blue); a lighter border under
        the mouse, grey when greyed out. Without image support clam's own indicator stays."""
        try:
            px = self._px(CHECK_PX)
            looks = {"off": ("#454545", "#a0a0a0", None), "off-hover": ("#454545", FG, None),
                     "on": (ACCENT, ACCENT, "#ffffff"), "off-grey": (BG, "#6e6e6e", None),
                     "on-grey": ("#5a6678", "#5a6678", "#a8a8a8")}
            imgs = {}
            for k, v in looks.items():      # the gap to the text is part of the picture (an image element ignores padding)
                wide = Image.new("RGBA", (px + self._px(CHECK_GAP), px), (0, 0, 0, 0))
                wide.paste(icons.checkbox(*v, px), (0, 0))
                imgs[k] = icons.photo(self.root, None, "", px, image=wide)
            self._check_imgs = imgs         # Tk drops an image Python no longer holds
            if "PC.Checkbutton.indicator" not in s.element_names():
                s.element_create("PC.Checkbutton.indicator", "image", imgs["off"],
                                 ("disabled", "selected", imgs["on-grey"]), ("disabled", imgs["off-grey"]),
                                 ("selected", imgs["on"]), ("active", imgs["off-hover"]), sticky="")
            s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("PC.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Checkbutton.label", {"sticky": "nswe"})]})]})])
        except Exception:
            pass

    def _flat_tabs(self, s):
        """The tabs of the settings window (user 1.11.): no fill, white text; the chosen tab has a blue line under it, a
        tab under the mouse a grey line. The line is a picture element (clam has no bottom-only border). Without
        image support the plain tabs stay."""
        try:
            line = max(1, self._px(2))
            imgs = {}
            for k, colour in (("off", None), ("hot", "#8e8e8e"), ("on", ACCENT)):
                im = Image.new("RGBA", (8, 8 + line), (0, 0, 0, 0))
                if colour:
                    im.paste(colour, (0, 8, 8, 8 + line))
                imgs[k] = icons.photo(self.root, None, "", 8, image=im)
            self._tab_imgs = imgs           # Tk drops an image Python no longer holds
            if "Flat.tab" not in s.element_names():
                s.element_create("Flat.tab", "image", imgs["off"], ("selected", imgs["on"]), ("active", imgs["hot"]),
                                 border=(2, 2, 2, line), sticky="nswe")
            for name in ("TNotebook.Tab", "Inner.TNotebook.Tab"):
                s.layout(name, [("Flat.tab", {"sticky": "nswe", "children": [
                    ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                        ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
        except Exception:
            pass

    def _drop_focus(self, event):
        """After a mouse click a button gives the focus up (its orange ring goes), unless the click opened something that has
        the focus now (a list, a dialog). Keyboard use (Tab, Space) keeps the ring."""
        w = event.widget
        if isinstance(w, str):
            return              # Tk gave a path name, not a widget (seen on Linux, e.g. a combobox pop-down): nothing to do

        def back():
            try:
                if w.winfo_exists() and self.root.focus_get() is w:
                    w.winfo_toplevel().focus_set()
            except Exception:
                pass
        w.after_idle(back)

    def _spin_arrows(self, s):
        """The spin boxes' up/down arrows: thin chevrons (icons.py) instead of clam's big filled triangles; orange under the
        mouse, grey when greyed out. Without image support the theme's own arrows stay."""
        try:
            px = self._px(SPIN_PX)
            imgs = {(up, c): icons.photo(self.root, "", c, px, icons.spin_arrow(up, c, px))
                    for up in (True, False) for c in (FG, ACCENT, DISABLED)}
            self._spin_imgs = imgs          # Tk drops an image Python no longer holds
            gap = self._px(SPIN_GAP)
            for up, name in ((True, "Chev.uparrow"), (False, "Chev.downarrow")):
                if name not in s.element_names():
                    # the gap between the two chevrons sits below the upper one; left, top, right, bottom
                    pad = (self._px(3), self._px(1), self._px(3), gap if up else self._px(1))
                    s.element_create(name, "image", imgs[(up, FG)], ("disabled", imgs[(up, DISABLED)]),
                                     ("pressed", imgs[(up, ACCENT)]), ("active", imgs[(up, ACCENT)]), padding=pad)
            s.layout("TSpinbox", [("Spinbox.field", {"side": "top", "sticky": "we", "children": [
                ("null", {"side": "right", "sticky": "", "children": [
                    ("Chev.uparrow", {"side": "top", "sticky": "e"}), ("Chev.downarrow", {"side": "bottom", "sticky": "e"})]}),
                ("Spinbox.padding", {"sticky": "nswe", "children": [("Spinbox.textarea", {"sticky": "nswe"})]})]})])
        except Exception:
            pass

    def _icon(self, kind: str, color: str = FG, px: int = ICON_PX):
        """A button icon (icons.py) at px before the display scaling, as a ttk image spec: `color`, grey when the button is
        greyed out, orange under the mouse (like the slot icons)."""
        cache = self.__dict__.setdefault("_icon_cache", {})

        def img(c):
            if (kind, c, px) not in cache:
                cache[(kind, c, px)] = icons.photo(self.root, kind, c, self._px(px))
            return cache[(kind, c, px)]
        return (img(color), "disabled", img(DISABLED), "active", img(ACCENT))

    def _function_icon(self, key: str):
        """The symbol of a function button: the user's picture pccomfy/assets/functions/<key>.png when it is there, else the
        shape fn-<key> (icons.py), else a placeholder, with FN_GAP of room on its right. Light on the dark button, dark on the orange (selected) one, grey when
        greyed out."""
        from pathlib import Path
        path = Path(__file__).resolve().parent / "assets" / "functions" / f"{key}.png"
        cache = self.__dict__.setdefault("_icon_cache", {})

        def img(c):
            k = ("fn", key, c)
            if k not in cache:
                px = self._px(ICON_PX)
                pic = None
                if path.exists():
                    try:
                        pic = icons.from_file(path, c, px)
                    except OSError:
                        pic = None
                if pic is None:
                    pic = icons.render(f"fn-{key}" if f"fn-{key}" in icons.SHAPES else "placeholder", c, px)
                wide = Image.new("RGBA", (px + self._px(FN_GAP), px), (0, 0, 0, 0))
                wide.paste(pic, (0, 0))
                cache[k] = icons.photo(self.root, None, c, px, image=wide)
            return cache[k]
        return (img(FG), "selected", img(ON_ACCENT), "disabled", img(DISABLED))

    def _slider_row(self, frame):
        """Sharpen, Edge feather and Mix source/new share one layout: the label takes the room on the left,
        the slider (SLIDER_W) and its value box sit on the right, so all bars are equally long and end at the same place
        (the LoRA sliders beside their checkboxes too)."""
        frame.columnconfigure(0, weight=1)

    def _open_on_click(self, cb):
        def post(_e=None):
            try:
                if str(cb.cget("state")) == "disabled":
                    return None
                cb.focus_set()
                cb.tk.call("ttk::combobox::Post", str(cb))
            except Exception:
                return None
            return "break"
        cb.bind("<Button-1>", post)

    def _copy_menu(self, event):
        """Right-click on a label (error messages, hints) or on a link symbol: a menu with "Copy" / "Copy link". Text of its own
        wins (`copy_text`, set on link symbols); an empty or one-character label (dot, badge) shows nothing."""
        w = event.widget
        text = getattr(w, "copy_text", "")
        link = bool(text)
        if not text:
            try:
                var = str(w.cget("textvariable"))
                text = str(w.getvar(var)) if var else str(w.cget("text"))
            except tk.TclError:
                return None
        text = text.strip()
        if len(text) < 2:
            return None
        menu = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=FG, activebackground=ACCENT, activeforeground="#1b1b1b", bd=0, font=font(10))

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        menu.add_command(label="Copy link" if link else "Copy", command=copy)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _text(self, parent, height):
        t = tk.Text(parent, height=height, width=10, wrap="word", bg=PANEL, fg=FG, insertbackground=FG,
                    relief="flat", highlightthickness=1, highlightbackground="#454545", highlightcolor=ACCENT,
                    font=font(10), padx=6, pady=4, undo=True, maxundo=200)
        self._editor_keys(t)
        return t

    def _spin(self, parent, var, frm, to, inc=1.0, width=6, typed=None):
        """A number box with arrows; `typed` is a key check (gui_common.steps_typed_ok and the like) for what can be typed."""
        sp = ttk.Spinbox(parent, textvariable=var, from_=frm, to=to, increment=inc, width=width)
        if typed is not None:
            sp.configure(validate="key", validatecommand=(sp.register(typed), "%d", "%S", "%P"))
        return sp

    def _px(self, n: int) -> int:
        return round(n * getattr(self, "ui", 1.0))

    def _keep(self, n: int):
        """``_px`` for a gap of pack or grid: marked as final, so spacing.py does not scale it again."""
        return spacing.Keep(self._px(n))

    def _apply_linux_scale(self) -> None:
        """Sets Tk's scaling; fonts (in points) and ``self.ui`` follow. Linux (uiscale.py): Tk often reports 96 dpi on a scaled
        display, so the first source that names a scale is used. Windows follows its display by itself: only the user's own
        choice (PCCOMFY_SCALE, Other settings > Interface scale) is applied, relative to the display's scale (100 % = as
        Windows says, 120 % = a fifth bigger), "Auto" changes nothing. Nothing found: Tk's own
        value stays. ``self._own_scale`` is that choice (it may be below 100 %)."""
        own = uiscale.pick_scale(os.environ.get("PCCOMFY_SCALE"), cfgmod.get_setting("ui_scale"))
        self._own_scale = own
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
            if hostos.IS_LINUX:
                scale = uiscale.detect(os.environ, self.cfg, self.pc, dpi, cfgmod.get_setting("ui_scale"))
            else:
                scale = own * dpi / 96 if own else None      # relative to Windows' own display scale: 120 % = 20 % bigger than Auto
            if scale:
                start = float(self.root.tk.call("tk", "scaling"))
                self.root.tk.call("tk", "scaling", uiscale.tk_scaling(scale))
                now = float(self.root.tk.call("tk", "scaling"))
                set_font_scaling(now if hostos.IS_LINUX and abs(now / start - 1.0) > 0.01 else 0.0)      # Linux: the fonts follow the scale (gui_common.set_font_scaling)
        except Exception:
            pass

    def _on_content_size(self, _event=None):
        """The content changed its size (a section appeared, text wrapped): fit the window again, once, a moment later."""
        if not getattr(self, "_sized", False) or self._fit_job is not None:
            return

        def fit():
            self._fit_job = None
            try:
                self._fit_height()
            except tk.TclError:
                pass
        self._fit_job = self.root.after(60, fit)

    def _on_body_size(self, _event=None):
        """The scrolled body changed its size (Advanced opened, a slot row appeared): its scroll area and the window follow."""
        cv = getattr(self, "cv_body", None)
        if cv is not None:
            try:
                cv.configure(scrollregion=cv.bbox("all"))
            except tk.TclError:
                pass
        self._on_content_size()

    def _screen_span(self) -> tuple[int, int, int]:
        """(top, bottom, monitor top) the window's content may use on the monitor it is on: it starts at the window's own top
        edge (the window never moves, it only grows downwards; user 4.11.), bottom is the bottom of the work area, i.e.
        above the taskbar whatever its height (user 5.11., PC C: a fixed guess of 56 px let the window run under it)."""
        try:
            x = int(self.root.winfo_rootx()) + int(self.root.winfo_width()) // 2
            y = max(0, int(self.root.winfo_rooty()))
            _, top, _, bottom = self._monitor_at(x, y, work=True)
            return max(int(top), y), int(bottom) - self._px(4), int(top)
        except (AttributeError, TypeError, ValueError, tk.TclError):
            return 0, 10 ** 6, 0

    def _fit_height(self, width: int | None = None):
        """The window is MIN_W wide (fixed) and exactly as high as its content needs. It never moves by itself (user 4.11.: it
        used to jump up to fit); it grows downwards. Only when the content does not fit between the window's top edge and the
        bottom of the screen, the body under the tabs gets the room that is left and scrolls (mouse wheel or the thin bar), so
        the window is always shown completely (user 4.11., PC C: Advanced settings were cut off at the bottom)."""
        self.root.update_idletasks()
        if getattr(self, "_minimized", False):          # only the header: exactly its height
            w, h = self._px(MIN_W), stack_height(self.root)
            if getattr(self, "_geom", None) != (w, h):
                self._geom = (w, h)
                self.root.geometry(f"{w}x{h}")
            return
        trace = ""                # one line for fit.log (written at the end of this method)
        lift = 0                  # how far the window has to move up when it starts so low that not even a strip of the body fits
        cv, sb = getattr(self, "cv_body", None), getattr(self, "sb_body", None)
        if cv is not None and sb is not None:
            body = self.f_body.winfo_reqheight()
            if isinstance(body, int) and body > 1:
                # the target height straight away: setting the full height first and then a smaller one changed the
                # canvas twice per call, and each change asked for the next fit (a loop every 60 ms: flicker, a jumping bar)
                try:      # what the canvas asks for now (not cget("height"): that gives "7c" until a number was set, and the fit then thought it was done)
                    cur = int(cv.winfo_reqheight())
                except (TypeError, ValueError, tk.TclError):
                    cur = -1
                others = stack_height(self.root) - cur          # everything but the scrolled body
                top, bottom, mon_top = self._screen_span()
                room = (bottom - top) - others if isinstance(others, int) else body    # from the window's top edge to the screen's bottom
                # The window always gets the height its content needs, even if that is more than the screen (user 5.11., PC C): no
                # scroll area, no limit by the screen, no moving. ``room`` is only written to fit.log.
                target = body
                if target != cur:
                    cv.configure(height=target)
                if target < body:
                    sb.show()
                else:
                    sb.hide()
                self.root.update_idletasks()
                try:      # a trace of how the room was worked out (exchange folder, fit.log; only when the body scrolls): finds a window that is cut off
                    line = (f"body={body} cur={cur} others={others} top={top} bottom={bottom} mon_top={mon_top} room={room} target={target} lift={lift} "
                            f"ui={self.ui:.2f} tk_screen={self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()} "
                            f"monitor={self._monitor_at(int(self.root.winfo_rootx()) + 50, max(0, int(self.root.winfo_rooty())))} "
                            f"work={self._monitor_at(int(self.root.winfo_rootx()) + 50, max(0, int(self.root.winfo_rooty())), work=True)} "
                            f"win_y={self.root.winfo_rooty()} win_h={self.root.winfo_height()}")
                    trace = line
                except Exception as e:
                    trace = f"trace failed: {e!r}"
        empty = bool(getattr(self, "start_state", lambda: "")())      # no model chosen: a small window (tabs, one sentence, footer)
        w, h = self._px(MIN_W), max(self._px(80 if empty else 320), stack_height(self.root))
        if lift:
            self._geom = (w, h)
            self.root.geometry(f"{w}x{h}+{int(self.root.winfo_rootx())}+{int(self.root.winfo_rooty()) - lift}")
        elif getattr(self, "_geom", None) != (w, h):
            self._geom = (w, h)
            self.root.geometry(f"{w}x{h}")
        if trace:
            try:
                self.root.update_idletasks()
                trace += (f" | set={w}x{h} req={self.root.winfo_reqheight()} stack={stack_height(self.root)} now={self.root.winfo_width()}x{self.root.winfo_height()} "
                          f"tk={self.root.tk.call('info', 'patchlevel')}")
                if trace != getattr(self, "_fit_line", ""):
                    self._fit_line = trace
                    f = cfgmod.EXCHANGE_DIR / "fit.log"
                    f.parent.mkdir(parents=True, exist_ok=True)
                    old = f.read_text(encoding="utf-8").splitlines()[-59:] if f.exists() else []
                    f.write_text("\n".join(old + [trace]) + "\n", encoding="utf-8")
            except Exception:
                pass

    def _pl_style(self, style: str):
        lbl = getattr(self, "lbl_pl", None)
        if lbl is not None and getattr(self, "_pl_style_now", "") != style:
            self._pl_style_now = style
            lbl.configure(style=style)
