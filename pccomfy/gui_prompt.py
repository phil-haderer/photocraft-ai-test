"""The prompt field: editor keys, hints, ready-made prompts, enhance and negative boxes. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from . import custom_prompts, hostos, manifest, styles
from .refslots import BBOX_TIP
from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401

REFINE_DEFAULT_TIP = "Refine with the default prompt: same size, as a new layer."


def put_in_front(t, text: str) -> None:
    """A generated text (Describe, the LLM button) goes in front of the prompt, followed by a line break; an empty prompt
    gets just the text (user 3.11.). One undo step: Ctrl+Z in the field takes it away."""
    t.edit_separator()
    rest = t.get("1.0", "end").strip()
    t.delete("1.0", "end")
    t.insert("1.0", text + ("\n" + rest if rest else ""))
    t.edit_separator()


class PromptMixin:
    def _editor_keys(self, t):
        """Text-editor keys in a prompt field: Ctrl+Left/Right jump by word (Shift selects), Ctrl+Backspace/Delete delete a
        word, Ctrl+A selects all, Ctrl+Z / Ctrl+Y undo and redo. Ctrl+Enter generates and writes no line break."""
        def cursor(extend, idx):
            proc = "tk::TextKeySelect" if extend else "tk::TextSetCursor"
            try:
                t.tk.call(proc, str(t), idx)
            except tk.TclError:
                t.mark_set("insert", idx)
            t.see("insert")
            return "break"

        def jump(direction, extend):
            def h(_e=None):
                if direction < 0:
                    n = word_left(t.get("1.0", "insert"))
                    return cursor(extend, f"insert-{n}c")
                n = word_right(t.get("insert", "end-1c"))
                return cursor(extend, f"insert+{n}c")
            return h

        def kill(direction):
            def h(_e=None):
                if t.tag_ranges("sel"):
                    t.delete("sel.first", "sel.last")
                elif direction < 0:
                    t.delete(f"insert-{word_left(t.get('1.0', 'insert'))}c", "insert")
                else:
                    t.delete("insert", f"insert+{word_right(t.get('insert', 'end-1c'))}c")
                return "break"
            return h

        def select_all(_e=None):
            t.tag_add("sel", "1.0", "end-1c")
            t.mark_set("insert", "end-1c")
            return "break"

        def history(redo):
            def h(_e=None):
                try:
                    (t.edit_redo if redo else t.edit_undo)()
                except tk.TclError:
                    pass
                return "break"
            return h

        def generate(_e=None):
            self.generate()
            return "break"          # the Text's own Return binding must not add a line break

        for seq, fn in (("<Control-Left>", jump(-1, False)), ("<Control-Right>", jump(1, False)),
                        ("<Control-Shift-Left>", jump(-1, True)), ("<Control-Shift-Right>", jump(1, True)),
                        ("<Control-BackSpace>", kill(-1)), ("<Control-Delete>", kill(1)),
                        ("<Control-a>", select_all), ("<Control-A>", select_all),
                        ("<Control-z>", history(False)), ("<Control-Z>", history(True)), ("<Control-y>", history(True)),
                        ("<Control-Return>", generate), ("<Control-KP_Enter>", generate)):
            t.bind(seq, fn)

    def _show_enhance_box(self, on: bool):
        """The "Enhance prompt with LLM" row (with the copy button): not in Expand, Remove, Refine and Upscale (NO_LLM_MODES). It sits directly under the negative
        prompt, above the Upscale factor and the LoRA switches (user 30.10.)."""
        shown = bool(self.f_enh.winfo_manager())
        if on and not shown:
            self.f_enh.pack(fill="x", padx=10, pady=(6, 0), after=self.f_neg)
        elif not on and shown:
            self.f_enh.pack_forget()
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _below_prompt(self):
        """What the next box under the prompt goes after: the LLM row when it is shown, else the negative prompt."""
        return self.f_enh if self.f_enh.winfo_manager() else self.f_neg

    def _prompt_text(self) -> str:
        """The prompt to save: in Remove object the field is empty, the user's own text is kept aside."""
        if str(self.t_prompt.cget("state")) == "disabled":
            return getattr(self, "_prompt_kept", "")
        return self.t_prompt.get("1.0", "end").strip()

    def _grip_drag(self, grip, t):
        """The strip under the prompt field: drag it to change the field's height (in lines)."""
        st: dict = {}

        def line_h():
            try:
                return max(8, int(t.tk.call("font", "metrics", t.cget("font"), "-linespace")))
            except Exception:
                return self._px(16)

        def press(e):
            st.update(y=e.y_root, h=self._prompt_lines(), lh=line_h())

        def move(e):
            if "y" not in st:
                return
            n = max(3, min(30, st["h"] + round((e.y_root - st["y"]) / st["lh"])))
            if n != self._prompt_lines():
                t.configure(height=n)
                self._fit_height()
        grip.bind("<ButtonPress-1>", press)
        grip.bind("<B1-Motion>", move)

    def _prompt_lines(self) -> int:
        try:
            return int(self.t_prompt.cget("height"))
        except (TypeError, ValueError, tk.TclError):
            return PROMPT_LINES

    def _update_prompt_hint(self):
        """The prompt field turns orange with a hint under it: Expand (an empty prompt often fills best), and the modes whose
        prompt starts with the workflow's own text (Upscale / Refine: describe the image in front of it)."""
        mode = self.v_mode.get()
        m = self._model()
        spec = m.modes.get(mode) if m else None
        text = (spec.prompt_tip if spec and spec.prompt_tip else "") or (EXPAND_HINT if mode == "outpaint" else "")
        if mode == "multi_edit" and getattr(self, "v_bbox", None) is not None and self._bbox_on():
            text = BBOX_TIP              # BBOX ticked: its tip instead of the Multi Image Edit one, only here (user 3.11.)
        if mode in ("sketch", "scribble") and self._written_active():
            text = models.WRITTEN_TIP    # a written prompt from the history: no upsampler (user 10.11.)
        if "{tag}" in text:      # Multi Image Edit: the example names the first reference the way this model does
            text = text.replace("{tag}", m.tag_style.format(n=2, i=1) if m and m.tag_style else "the reference image")
        on = bool(text)
        self._hint_text = text
        self._update_llm_button()
        self._update_styles_button()
        self.t_prompt.configure(highlightbackground=ACCENT if on else "#454545", highlightthickness=2 if on else 1)
        if on:
            self.lbl_hint.configure(text=text)
            self.f_hint.pack(fill="x", padx=10, after=self.grip)      # the text with its info icon (gui.py)
        else:
            self.f_hint.pack_forget()
        b = getattr(self, "b_describe", None)
        if b is not None:
            if self._needs_description():
                b.pack(anchor="w", padx=10, pady=(4, 0), after=self.f_hint)
            else:
                b.pack_forget()

    def _needs_description(self) -> bool:
        """Krea 2 / MOSS Expand: the model needs a prompt (an empty one fills the margin with unrelated things)."""
        m = self._model()
        spec = m.modes.get(self.v_mode.get()) if m else None
        return bool(spec and spec.describe)

    def describe_scene(self):
        """The Describe button: Qwen 3.5 9B describes the surroundings of the picture in PhotoCraft (Bridge.describe_scene);
        the text replaces the field's content in one undo step (Ctrl+Z in the field brings the old text back)."""
        import threading
        if getattr(self, "_describing", False) or (self.worker and self.worker.is_alive()):
            return
        self._describing = True
        self.b_describe.configure(state="disabled")
        self.b_stop.configure(state="normal")          # Cancel stops the text model too (user 2.11.)
        self._status("Describing the surroundings …")
        box: dict = {}

        def work():
            try:
                box["text"] = self.bridge.describe_scene()
            except Cancelled:
                box["error"] = "Cancelled."
            except Exception as e:   # PhotoCraft or ComfyUI not running, no text model ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()

        def check():
            if "text" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._describing = False
            self.b_describe.configure(state="normal")
            self.b_stop.configure(state="disabled")
            if "error" in box:
                self._status(box["error"] if box["error"] == "Cancelled." else "Describe failed: " + box["error"], error=box["error"] != "Cancelled.")
                return
            put_in_front(self.t_prompt, box["text"])
            self._status("Described. Edit the text as you like, then Generate.")
        self.root.after(200, check)

    def _llm_file(self) -> str:
        """The text model file the LLM button uses: the first of the model's describe writers that ComfyUI lists ("" = none)."""
        m = self._model()
        if m is None or self.inv is None:
            return ""
        for name in manifest.describe_writers(m.key):
            found = self.inv.found(name)
            if found:
                return found
        return ""

    def _llm_wanted(self) -> bool:
        """Where Describe Canvas is shown (user 10.11. evening, P4): Text to image, and Upscale / Refine while the picture is not
        made in tiles (every tile gets the whole prompt, so a description puts its objects into every tile, P8). Hidden in
        every other function."""
        mode = self.v_mode.get()
        if mode == "txt2img":
            return True
        return mode in SCALE_MODES and not self._tiles_on()

    def _tiles_on(self) -> bool:
        """The selected workflow makes the picture in tiles: it has a tile split (SplitImageToTileList) that is not part of a
        stage switched off. Flux 3 Upscale always tiles; Flux 2 and Fibo have the stage "Tiles". (Fibo also tiles by itself
        above 3 MP; the window does not know the picture's size before the run, so that case is not counted.)"""
        try:
            templates = self._wf_templates()
        except Exception:
            return False
        split = {nid for t in templates for nid, node in t.items()
                 if isinstance(node, dict) and node.get("class_type") == "SplitImageToTileList"}
        if not split:
            return False
        stages = self._stages()
        for i, st in enumerate(stages):
            if "tile" in str(st.get("label", "")).lower() and i < len(getattr(self, "stage_vars", ())):
                return bool(self.stage_vars[i].get())
        return True

    def _prompt_margin(self):
        """The text keeps a margin on the right over the whole height, as wide as the bin in the corner (P5): a tag with a
        right margin over all of the text, set again after every change (typed text at the very start would miss it)."""
        t = getattr(self, "t_prompt", None)
        b = getattr(self, "b_clear", None)
        if t is None or b is None:
            return
        try:
            t.tag_configure("pc_margin", rmargin=int(b.winfo_reqwidth() or 0) + self._px(2))
            t.tag_add("pc_margin", "1.0", "end")
            t.tag_lower("pc_margin")
        except (tk.TclError, TypeError, ValueError):
            pass

    def _update_llm_button(self):
        """The LLM button is grey while no function is chosen, the prompt is switched off (Remove object) or the model's text
        model is missing; the tooltip says which file."""
        b = getattr(self, "b_llm", None)
        if b is None:
            return
        want = self._llm_wanted()
        if want != getattr(self, "_llm_shown", True):
            if want:
                b.pack(side="left", padx=(self._px(8), 0), after=self.b_save)     # right of Save (11.11.)
            else:
                b.pack_forget()
            self._llm_shown = want
        m = self._model()
        off = str(self.t_prompt.cget("state")) == "disabled"
        if m is None or off:
            b.configure(state="disabled")
            self.tt_llm.text = LLM_TIP
        elif self.inv is not None and not self._llm_file():
            b.configure(state="disabled")
            self.tt_llm.text = LLM_TIP + f"\n\nNeeds {manifest.describe_writers(m.key)[0]}: download it in the settings (gear)."
        else:
            b.configure(state="normal")
            self.tt_llm.text = LLM_TIP

    def describe_canvas(self):
        """The LLM button: the model's text model describes the picture in PhotoCraft (Bridge.describe_canvas); the text goes
        in front of the prompt, followed by a line break, in one undo step (Ctrl+Z in the field takes it away)."""
        import threading
        if getattr(self, "_describing", False) or (self.worker and self.worker.is_alive()):
            return
        clip = self._llm_file()
        self._describing = True
        self.b_llm.configure(state="disabled")
        self.b_stop.configure(state="normal")          # Cancel stops the text model too (user 2.11.)
        self._status("Describing the picture …")
        box: dict = {}

        def work():
            try:
                box["text"] = self.bridge.describe_canvas(clip)
            except Cancelled:
                box["error"] = "Cancelled."
            except Exception as e:   # PhotoCraft or ComfyUI not running, no text model ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()

        def check():
            if "text" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._describing = False
            self._update_llm_button()
            self.b_stop.configure(state="disabled")
            if "error" in box:
                self._status(box["error"] if box["error"] == "Cancelled." else "Describe failed: " + box["error"], error=box["error"] != "Cancelled.")
                return
            put_in_front(self.t_prompt, box["text"])
            self._status("Described. The text is at the start of the prompt.")
        self.root.after(200, check)

    def _copy_enhanced(self):
        """The prompt the text model wrote in the last run goes to the clipboard."""
        text = (self._last_vgl or "").strip()
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            self._status("Copied to the clipboard.")
        except tk.TclError as e:
            self._status(f"Could not copy: {e}", error=True)

    def _update_prompt_choices(self):
        """The Refine row under the Upscale factor (user 6.11.): one small switch per ready-made prompt of the model's Refine
        (Flux 2: Default, Neutral, Studio portrait; Flux 3: Default, Restore), a lone "Default" for the others. The lit one is the
        Refine button that was chosen (v_fac); the prompt may be edited afterwards."""
        m = self._model()
        spec = m.modes.get("refine") if m else None
        choices = (spec.prompts or (("Default", None, REFINE_DEFAULT_TIP),)) if spec else ()
        key = (m.key, tuple(c[0] for c in choices)) if m else None
        if key != self._pchoice_key:
            self._pchoice_key = key
            self._rpick = ""
            for w in (self.f_refine.winfo_children() or []):
                w.destroy()
            self.rb_refine = {}
            for label, _text, tip in choices:
                rb = ttk.Radiobutton(self.f_refine, text=label, value="r:" + label, variable=self.v_fac,
                                     command=self._on_factor, style="Small.Toolbutton")
                rb.pack(side="left", padx=(0 if not self.rb_refine else 4, 0))
                Tooltip(rb, tip)
                self.rb_refine[label] = rb
        self._sync_fac()
        self._update_factor_buttons()

    def _insert_prompt(self, text: str):
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        t.delete("1.0", "end")
        t.insert("1.0", text)

    # ---------- Styles (styles.json) ----------

    def _build_styles_menus(self):
        """One menu per mode that has styles: a submenu per group, an entry per style (its name). The whole text shows in a box
        right of the menu while the mouse is on an entry (user 1.11.; a menu entry has no tooltip of its own)."""
        self._styles = styles.load()
        self.m_styles: dict = {}
        self._style_texts: dict = {}        # (submenu, entry number) -> the style's text
        self._style_tip = None
        self._style_menus: list = []        # kept, so the submenus (and their names) stay alive
        kw = dict(tearoff=0, bg=PANEL, fg=FG, activebackground=ACCENT, activeforeground="#1b1b1b", bd=0, font=font(9))
        self._mode_styles: dict = {}        # mode -> {style name: text} (Edit canvas and Sketch to image remember the style chosen last)
        self._custom_kw = kw
        self.m_custom: dict = {}            # mode -> its "Custom prompts" submenu (filled again each time the menu opens)
        self._custom_menus: dict = {}       # mode -> the menus below it (one per saved prompt), destroyed on refresh
        for mode in dict.fromkeys([k for k, _l in MODE_LABELS] + list(self._styles)):
            groups = self._styles.get(mode, [])
            top = tk.Menu(self.root, **kw)
            cm = tk.Menu(top, **kw)
            self.m_custom[mode] = cm
            self._custom_menus[mode] = []
            top.add_cascade(label="Custom prompts", menu=cm)     # at the very top (user 11.11.); the style groups follow
            cm.bind("<<MenuSelect>>", lambda e, m=cm: self._style_preview(m), add="+")
            cm.bind("<Unmap>", lambda e: self._style_tip_hide(), add="+")
            self._refresh_custom_menu(mode, entries=[])
            if groups:
                top.add_separator()
            self._mode_styles[mode] = {s["name"]: s["text"] for g in groups for s in g["styles"]}
            if mode in SET_STYLE_MODES:     # a whole sentence: the window may replace it like a stock text when the tab changes
                models.STOCK_PROMPTS.update(self._mode_styles[mode].values())
            for g in groups:
                sub = tk.Menu(top, **kw)
                self._style_menus.append(sub)
                for i, s in enumerate(g["styles"]):
                    sub.add_command(label=s["name"], command=lambda t=s["text"], n=s["name"]: self._apply_style(t, n))
                    self._style_texts[(str(sub), i)] = s["text"]
                sub.bind("<<MenuSelect>>", lambda e, m=sub: self._style_preview(m), add="+")
                sub.bind("<Unmap>", lambda e: self._style_tip_hide(), add="+")
                top.add_cascade(label=g["name"], menu=sub)
            top.bind("<<MenuSelect>>", lambda e: self._style_tip_hide(), add="+")
            self.m_styles[mode] = top

    def _build_prompt_placeholder(self):
        """The word "Prompt" in grey inside the empty field; it goes when the field has the focus or any text (user 6.11.)."""
        from .gui_common import MUTED, PANEL
        t = self.t_prompt
        self._ph = tk.Label(t, text="Prompt", fg=MUTED, bg=PANEL, bd=0, font=font(10), cursor="xterm")
        self._ph.bind("<Button-1>", lambda e: (t.focus_set(), "break")[1])
        self._ph_on = False
        t.bind("<FocusIn>", lambda e: self._prompt_placeholder(focused=True), add="+")
        for ev in ("<FocusOut>", "<KeyRelease>"):
            t.bind(ev, lambda e: self._prompt_placeholder(), add="+")
        self._prompt_placeholder_poll()

    def _prompt_placeholder(self, focused: bool | None = None):
        t = self.t_prompt
        self._prompt_margin()          # the margin for the bin covers any text set by the program or typed (P5)
        word = models.SKETCH_PLACEHOLDER if self.v_mode.get() == "sketch" else "Prompt"    # Sketch to image: plan B, 10.11.
        if self._ph.cget("text") != word:
            self._ph.configure(text=word)
        try:
            if focused is None:
                focused = self.root.focus_get() is t
            empty = not t.get("1.0", "end-1c")
        except (tk.TclError, KeyError):
            return
        want = empty and not focused
        if want and not self._ph_on:
            self._ph.place(x=self._px(7), y=self._px(5))
            self._ph_on = True
        elif not want and self._ph_on:
            self._ph.place_forget()
            self._ph_on = False

    def _prompt_placeholder_poll(self):
        """Text set by the program (a style, Describe, history, a new function) does not fire a key event: look again now and then."""
        self._prompt_placeholder()
        try:
            self.root.after(300, self._prompt_placeholder_poll)
        except Exception:
            pass

    def _update_styles_button(self):
        """The Styles button is there in every function (its menu starts with Custom prompts, then come the style groups of
        the modes that have them: Text to image, Edit canvas, Sketch to image), in the middle of the row over the field (P2,
        10.11. evening; user 11.11.). Grey, like Save, while the prompt field is off (Remove)."""
        b = getattr(self, "b_styles", None)
        if b is None:
            return
        want = self.v_mode.get() in self.m_styles
        if want and not self._styles_shown:
            b.pack(side="left", before=self.b_save)       # first on the left, as high as Generate (window tests E and F, 11.11.)
            self._styles_shown = True
        elif not want and self._styles_shown:
            b.pack_forget()
            self._styles_shown = False
        off = str(self.t_prompt.cget("state")) == "disabled"
        for w in (b, getattr(self, "b_save", None)):
            if w is not None:
                w.configure(state="disabled" if off else "normal")

    def _match_styles_height(self):
        """Styles looks like Generate: the same height (window tests E and F, 11.11.: first lower, then higher than Generate).
        Its vertical padding is whatever its own height lacks of Generate's; the row keeps that height."""
        try:
            self.root.update_idletasks()
            want = max(int(w.winfo_reqheight() or 0) for w in (self.b_go, self.w_variants, self.b_stop))   # Generate's real height: its row
            s = ttk.Style(self.root)
            pad_x = self._px(10)
            s.configure("Styles.TButton", padding=(pad_x, 0))
            self.root.update_idletasks()
            lack = max(0, want - int(self.b_styles.winfo_reqheight() or 0))
            s.configure("Styles.TButton", padding=(pad_x, lack // 2, pad_x, lack - lack // 2))
            self.f_ptop.rowconfigure(0, minsize=want)
        except (tk.TclError, AttributeError, ValueError):
            pass

    def _styles_menu(self):
        """A click on the Styles button: Custom prompts, then the groups, opening under the button."""
        mode = self.v_mode.get()
        m = self.m_styles.get(mode)
        if m is None or str(self.t_prompt.cget("state")) == "disabled":
            return
        self._refresh_custom_menu(mode)
        b = self.b_styles
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            try:
                m.grab_release()
            except Exception:
                pass
            self._style_tip_hide()
            # window test E (11.11.): after Append the field took no clicks for a moment. A hover box made in the menu's last
            # moments could outlive the menu, topmost over the field: look once more when the menu is surely gone
            for ms in (60, 300):
                try:
                    self.root.after(ms, self._style_tip_hide)
                except Exception:
                    pass

    # ---------- Custom prompts (custom_prompts.py, docs/prompt-saver-konzept.md; user 11.11.) ----------

    def _cp_tag(self) -> tuple:
        """(model, function) as the window shows them, for the tag of a saved prompt."""
        m = self._model()
        mode = self.v_mode.get()
        fn = "Edit canvas" if mode == "edit" else SCALE_FN_LABEL if mode in SCALE_MODES else dict(MODE_LABELS).get(mode, mode)
        return (m.label if m else "Own workflow"), fn

    def _cp_load(self) -> list:
        entries = custom_prompts.load()
        note = custom_prompts.load_note()
        if note:
            custom_prompts.clear_note()
            self._status(note, error=True)
        return entries

    def _refresh_custom_menu(self, mode: str, entries: list | None = None):
        """Fills the Custom prompts submenu of `mode` from the file (a normal Tk submenu): each saved prompt is a submenu of its
        own with Use, Append, Edit and Delete; no prompts: one greyed-out line."""
        cm = self.m_custom.get(mode)
        if cm is None:
            return
        if entries is None:
            entries = self._cp_load()
        cm.delete(0, "end")
        for old in self._custom_menus.get(mode, []):
            self._style_texts = {k: v for k, v in self._style_texts.items() if k[0] != str(old)}
            try:
                old.destroy()
            except Exception:
                pass
        self._custom_menus[mode] = []
        if not entries:
            cm.add_command(label=custom_prompts.EMPTY_LABEL, state="disabled")
            return
        for e in entries:
            sub = tk.Menu(cm, **self._custom_kw)
            self._custom_menus[mode].append(sub)
            n = e["name"]
            sub.add_command(label="Use", command=lambda n=n: self._cp_use(n))
            sub.add_command(label="Append", command=lambda n=n: self._cp_use(n, append=True))
            sub.add_command(label="Edit", command=lambda n=n: self._cp_edit(n))
            sub.add_command(label="Delete", command=lambda n=n: self._cp_delete(n))
            for i in (0, 1):
                self._style_texts[(str(sub), i)] = e["text"]      # the hover box shows the whole text
            sub.bind("<<MenuSelect>>", lambda ev, m=sub: self._style_preview(m), add="+")
            sub.bind("<Unmap>", lambda ev: self._style_tip_hide(), add="+")
            cm.add_cascade(label=custom_prompts.label(e), menu=sub)

    def _cp_use(self, name: str, append: bool = False):
        """Use: the saved text replaces the prompt; Append: it goes to the end after a line break. One undo step each."""
        self._style_tip_hide()           # the hover box (topmost) must not stay over the field (window test E, 11.11.)
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        entries = self._cp_load()
        i = custom_prompts.find(entries, name)
        if i < 0:
            return
        text = entries[i]["text"]
        auto = t.cget("autoseparators")      # Tk would otherwise split delete + insert into two undo steps
        t.configure(autoseparators=False)
        appended = False
        try:
            t.edit_separator()
            old = t.get("1.0", "end").rstrip()
            if append and old:
                t.insert("end-1c", ("" if t.get("end-2c", "end-1c") == "\n" else "\n") + text)
                appended = True
            else:
                t.delete("1.0", "end")
                t.insert("1.0", text)
            t.edit_separator()
        finally:
            t.configure(autoseparators=auto)
        self._written_for = ""
        t.focus_set()
        self._update_prompt_hint()
        self._status(f"Prompt “{name}” {'appended' if appended else 'set'}. Ctrl+Z in the field brings the text before back.")

    def save_prompt(self):
        """The Save button: asks for a name and keeps the text of the field (user 11.11.)."""
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        text = t.get("1.0", "end").strip()
        if not text:
            self._status("Write a prompt first")
            return
        model, fn = self._cp_tag()

        def done(name, _text):
            entries = self._cp_load()
            r = custom_prompts.add(entries, name, text, model, fn)
            if r == "exists":
                if not messagebox.askyesno("Save prompt", f"“{name.strip()}” exists. Replace it?", parent=self.root):
                    return False
                r = custom_prompts.add(entries, name, text, model, fn, replace=True)
            return self._cp_finish(r, entries, f"Prompt saved as “{name.strip()[:custom_prompts.MAX_NAME]}”. Find it under Styles > Custom prompts.")
        self._cp_dialog("Save prompt", "", None, done)

    def _cp_edit(self, name: str):
        entries = self._cp_load()
        i = custom_prompts.find(entries, name)
        if i < 0:
            return

        def done(new_name, new_text):
            entries = self._cp_load()
            j = custom_prompts.find(entries, name)
            if j < 0:
                return True
            r = custom_prompts.edit(entries, j, new_name, new_text)
            if r == "exists":
                if not messagebox.askyesno("Edit prompt", f"“{new_name.strip()}” exists. Replace it?", parent=self.root):
                    return False
                r = custom_prompts.edit(entries, j, new_name, new_text, replace=True)
            return self._cp_finish(r, entries, f"Prompt “{new_name.strip()[:custom_prompts.MAX_NAME]}” changed.")
        self._cp_dialog("Edit prompt", entries[i]["name"], entries[i]["text"], done)

    def _cp_delete(self, name: str):
        if not messagebox.askyesno("Delete prompt", f"Delete “{name}”?", parent=self.root):
            return
        entries = self._cp_load()
        i = custom_prompts.find(entries, name)
        if i < 0:
            return
        custom_prompts.delete(entries, i)
        self._cp_finish("", entries, f"Prompt “{name}” deleted.")

    def _cp_finish(self, result: str, entries: list, ok_text: str) -> bool:
        """Writes the list after add/edit/delete and says what happened in the status line; True = the dialog may close."""
        msgs = {"name": "Give the prompt a name.", "text": "The text is empty.",
                "full": f"{custom_prompts.MAX_ENTRIES} prompts are saved: delete one first."}
        if result:
            self._status(msgs.get(result, "Not saved."), error=True)
            return False
        if not custom_prompts.save(entries):
            self._status(f"Could not write {custom_prompts.path()}.", error=True)
            return False
        self._refresh_custom_menu(self.v_mode.get(), entries)
        self._status(ok_text)
        return True

    def _cp_dialog(self, title: str, name: str, text, done):
        """A small window in the style of the gear windows: Name (40 characters at most) and, when `text` is not None, the
        text; Save / Cancel. `done(name, text)` returns False to keep it open. It does not block (the tests drive
        self._cp_win.ok())."""
        old = getattr(self, "_cp_win", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root, **hostos.TOP_KW)
        win.withdraw()                   # placed first, then shown: a shown window without a title bar ignored the move (window test F)
        win.title(title)
        win.wm_overrideredirect(True)
        win.configure(bg=BG, highlightthickness=1, highlightbackground="#5c5c5c")
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=self._keep(14), pady=self._keep(12))
        ttk.Label(box, text=title, font=font(10, bold=True), foreground="#ffffff").pack(anchor="w")
        ttk.Label(box, text="Name", style="Muted.TLabel").pack(anchor="w", pady=(self._keep(8), 0))
        v_name = tk.StringVar(value=name)
        e = ttk.Entry(box, textvariable=v_name, width=44)
        e.pack(fill="x")
        mx = custom_prompts.MAX_NAME
        v_name.trace_add("write", lambda *_a: v_name.set(v_name.get()[:mx]) if len(v_name.get()) > mx else None)
        t = None
        if text is not None:
            ttk.Label(box, text="Text", style="Muted.TLabel").pack(anchor="w", pady=(self._keep(8), 0))
            t = tk.Text(box, height=7, width=44, wrap="word", bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                        highlightthickness=1, highlightbackground="#454545", highlightcolor=ACCENT, font=font(10), padx=6, pady=4,
                        undo=True)
            t.pack(fill="both", expand=True)
            t.insert("1.0", text)
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(self._keep(12), 0))

        def close():
            self._cp_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass
            # the keyboard goes back to the plugin and its prompt field (window test F, 11.11.: after Save the field took no
            # clicks for a moment: Windows had left no window of the plugin active)
            try:
                self.root.after_idle(self._prompt_focus_back)
            except tk.TclError:
                pass

        def ok(_e=None):
            if done(v_name.get(), t.get("1.0", "end").strip() if t is not None else ""):
                close()
        win.ok, win.close, win.v_name, win.t_text = ok, close, v_name, t     # for the tests
        ttk.Button(row, text="Cancel", command=close, style="TipOk.TButton").pack(side="right")
        ttk.Button(row, text="Save", command=ok, style="TipOk.TButton").pack(side="right", padx=(0, self._keep(8)))
        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Escape>", lambda ev: close())
        if t is None:
            win.bind("<Return>", ok)
        self._cp_win = win
        try:
            win.transient(self.root)
            win.update_idletasks()
            w, h = max(self._px(360), win.winfo_reqwidth()), win.winfo_reqheight()
            # beside the window, top edges level, like the settings window (window test E, 11.11.); no room on the right of
            # the screen: on the left of the window
            x = self.root.winfo_rootx() + self.root.winfo_width() + 8
            try:
                vx0, _vy0, vx1, _vy1 = self._monitor_at(self.root.winfo_rootx(), self.root.winfo_rooty(), work=True)
                if x + w > vx1:
                    x = max(vx0, self.root.winfo_rootx() - w - 8)
            except Exception:
                pass
            y = self.root.winfo_rooty()
            self._cp_pos = (x, y)                # (a hidden test window reports +0+0, so the tests read this)
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.deiconify()
            win.lift()
            win.focus_force()
            e.focus_set()
            e.selection_range(0, "end")
        except tk.TclError:
            pass

    def _prompt_focus_back(self):
        try:
            self.root.focus_force()
            if str(self.t_prompt.cget("state")) != "disabled":
                self.t_prompt.focus_set()
        except tk.TclError:
            pass

    def _apply_style(self, text: str, name: str = ""):
        """A style entry is added to the prompt after a line break (user 1.11.; an empty field just gets the style), in one undo
        step: Ctrl+Z in the field takes it away again. In Edit canvas and Sketch to image the style is the whole sentence (plan B, 10.11.)."""
        self._style_tip_hide()
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        if self.v_mode.get() in SET_STYLE_MODES:
            self._set_style(text, name)
            return
        auto = t.cget("autoseparators")      # Tk would otherwise split delete + insert into two undo steps
        t.configure(autoseparators=False)
        try:
            t.edit_separator()
            old = t.get("1.0", "end").rstrip()
            if old:
                t.insert("end-1c", ("" if t.get("end-2c", "end-1c") == "\n" else "\n") + text)
            else:
                t.delete("1.0", "end")
                t.insert("1.0", text)
            t.edit_separator()
        finally:
            t.configure(autoseparators=auto)
        t.focus_set()
        self._status("Style added to the prompt. Ctrl+Z in the field takes it away again.")

    def _set_style(self, text: str, name: str = ""):
        """Edit canvas and Sketch to image (plan B, 10.11.): the style replaces the whole field; what was typed for <WHAT IT SHOWS>
        in the style before goes along into the new one. The style is remembered (settings.json); only Sketch to image puts it
        back into the field on opening (_sketch_style_fill; Edit canvas stays as it was, user 10.11.)."""
        t = self.t_prompt
        mode = self.v_mode.get()
        subject = styles.subject_of(t.get("1.0", "end"), self._mode_styles.get(mode, {}).values(), models.SKETCH_MARK)
        new = styles.fill(text, None if subject == models.SKETCH_MARK else subject, models.SKETCH_MARK)
        self._written_for = ""              # a style: the writer runs again (Sketch from the history)
        auto = t.cget("autoseparators")
        t.configure(autoseparators=False)
        try:
            t.edit_separator()
            t.delete("1.0", "end")
            t.insert("1.0", new)
            t.edit_separator()
        finally:
            t.configure(autoseparators=auto)
        if name:
            cfgmod.set_setting(STYLE_KEY + mode, name)
        t.focus_set()
        self._update_prompt_hint()
        self._status(f"Style “{name or 'chosen'}” set. Ctrl+Z in the field brings the text before back.")

    def _sketch_style_fill(self):
        """Opening Sketch to image: an empty field (or one with a stock text of another tab) gets the style chosen last, with
        <WHAT IT SHOWS> to replace; without one it stays empty and shows "Choose a style under Styles" (plan B, 10.11.)."""
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        cur = t.get("1.0", "end").strip()
        if cur and cur not in models.STOCK_PROMPTS:
            return
        texts = getattr(self, "_mode_styles", {}).get("sketch", {})
        name = cfgmod.get_setting(STYLE_KEY + "sketch", "")
        new = texts.get(name, "") if isinstance(name, str) else ""
        if new == cur:
            return
        t.edit_separator()
        t.delete("1.0", "end")
        if new:
            t.insert("1.0", new)
        t.edit_separator()

    def _style_text_at(self, menu, active):
        """The text of entry number `active` of a style submenu ("" for none)."""
        return self._style_texts.get((str(menu), active), "") if isinstance(active, int) else ""

    def _style_preview(self, menu):
        """<<MenuSelect>> of a group menu: the whole text of the entry under the mouse in a small box right of the menu (left
        of it when there is no room)."""
        self._style_tip_hide()
        try:
            text = self._style_text_at(menu, menu.index("active"))
            if not text:
                return
            # a native Windows menu reports no position (x = y = 0, width 1: the box sat at the screen's top left, user 1.11.),
            # so the box goes level with the mouse and beside the menu's real window (found under the mouse)
            px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
            left, right = self._menu_span(menu, px, py)
            x, y = right + 4, py - 12
            tip = tk.Toplevel(self.root, **hostos.TOP_KW)
            tip.withdraw()                       # not shown at 0,0 first: inside the native menu's loop a later move is ignored
            tip.wm_overrideredirect(True)
            tk.Label(tip, text=text, justify="left", wraplength=340, background="#ffffe0", foreground="#000000",
                     relief="solid", borderwidth=1, padx=6, pady=4, font=font(9)).pack()
            tip.update_idletasks()
            vx0, vy0, vx1, vy1 = self._monitor_at(px, py)
            if x + tip.winfo_reqwidth() > vx1:
                x = max(vx0, left - tip.winfo_reqwidth() - 4)
            y = max(vy0, min(y, vy1 - tip.winfo_reqheight()))
            tip.wm_geometry(f"+{x}+{y}")
            self._style_tip_pos = (x, y)         # (a tip of a hidden window reports +0+0, so the tests read this)
            tip.wm_attributes("-topmost", True)
            tip.deiconify()
            tip.update_idletasks()
            self._style_tip = tip
            self._place_native(tip, x, y)
        except tk.TclError:
            self._style_tip_hide()

    def _place_native(self, tip, x: int, y: int):
        """Moves the box with the Windows API as well (SWP_NOSIZE | SWP_NOACTIVATE, topmost): while a native menu is open Tk's
        own move does not always reach the window."""
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = u.GetParent(tip.winfo_id()) or tip.winfo_id()
            u.SetWindowPos(hwnd, -1, int(x), int(y), 0, 0, 0x0001 | 0x0010)
        except Exception:
            pass

    def _monitor_at(self, px: int, py: int, work: bool = False) -> tuple:
        """(x0, y0, x1, y1) of the monitor under the point (Windows API); the window may sit on a second monitor, where Tk's
        screen size (the first monitor) is wrong. Falls back to Tk's screen. ``work``: the work area, i.e. without the
        taskbar (as Windows reports it, whatever its height or side); without the API a guessed taskbar is taken off."""
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            u.MonitorFromPoint.restype = wintypes.HANDLE

            class MI(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]
            mi = MI()
            mi.cbSize = ctypes.sizeof(MI)
            hm = u.MonitorFromPoint(wintypes.POINT(px, py), 2)       # 2 = the nearest monitor
            if hm and u.GetMonitorInfoW(hm, ctypes.byref(mi)):
                r = mi.rcWork if work else mi.rcMonitor
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight() - (self._px(56) if work else 0)

    def _menu_span(self, menu, px: int, py: int) -> tuple:
        """(left, right) screen x of a posted menu: Tk's own numbers when it has some, else the window under the mouse (Windows
        API), else a guess around the mouse."""
        try:
            if menu.winfo_width() > 1 and menu.winfo_rootx() > 0:
                return menu.winfo_rootx(), menu.winfo_rootx() + menu.winfo_width()
        except tk.TclError:
            pass
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            u.WindowFromPoint.argtypes = [wintypes.POINT]
            u.WindowFromPoint.restype = wintypes.HWND
            hwnd = u.WindowFromPoint(wintypes.POINT(px, py))
            rc = wintypes.RECT()
            if hwnd and u.GetWindowRect(hwnd, ctypes.byref(rc)) and rc.left <= px <= rc.right and rc.right - rc.left < 1200:
                return rc.left, rc.right
        except Exception:
            pass
        return px - 100, px + 100

    def _style_tip_hide(self):
        tip, self._style_tip = getattr(self, "_style_tip", None), None
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass

    def _clear_prompt(self):
        """The bin next to "Prompt": empties the field (one undo step, so Ctrl+Z in the field brings the text back)."""
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        t.edit_separator()
        t.delete("1.0", "end")
        t.edit_separator()
        t.focus_set()

    def _sync_prompt_field(self, mode: str):
        """Remove object ignores the text: the field is emptied and greyed out, the typed text comes back afterwards."""
        t = self.t_prompt
        m = self._model()
        spec = m.modes.get(mode) if m else None
        if mode == "remove" and not (spec is not None and spec.remove_text):
            if str(t.cget("state")) != "disabled":
                self._prompt_kept = t.get("1.0", "end").strip()
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.configure(state="disabled")
        elif str(t.cget("state")) == "disabled":
            t.configure(state="normal")
            t.delete("1.0", "end")
            if getattr(self, "_prompt_kept", ""):
                t.insert("1.0", self._prompt_kept)
            self._prompt_kept = ""
        self._update_styles_button()        # Styles and Save are grey while the field is off

    def _show_negative(self):
        opened = bool(self.v_neg_open.get())
        self.btn_neg.configure(text="Negative prompt", compound="left",
                               image=self._icon("chevron-down" if opened else "chevron-right", MUTED))
        self.neg_body.pack_forget()          # never shown (user 2.11.)

    def _toggle_negative(self):
        self.v_neg_open.set(not self.v_neg_open.get())
        self._show_negative()
        self._fit_height()
