"""The window of the chain symbol (Settings, "Models"): a search field over the files ComfyUI lists for the kind of the expected file.
Typing narrows the list (every word, any case), the list is alphabetical, files that equal the expected file come first with a
line below them (user 7.11.). The mouse wheel scrolls the list and never closes the window; Escape, a pick or a click into
another window closes it. A tk.Menu could do none of this (no search, the wheel closed it, a long list ran off the screen).

``order`` is plain Python (no Tk) and is what the tests pin."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from . import hostos
from .gui_common import ACCENT, DONE_GREEN, FG, MUTED, PANEL, bind_wheel, font, wheel_up

SEPARATOR = "─" * 24         # the unselectable row between the matches of the expected file and the rest
ROWS = 16                    # rows shown before the list scrolls
HOT_FG = "#1b1b1b"
NL = chr(10)


def _key(name: str) -> str:
    return name.replace("\\", "/").lower()


def order(cands, pinned=(), typed: str = "") -> tuple[list[str], list[str]]:
    """(top, rest): the files whose name holds every word of ``typed`` (any case); ``top`` = those in ``pinned`` (the likely right files:
    the expected one, copies of it, the one in use, similar names), in the order ``pinned`` has them; ``rest`` = all others,
    alphabetical (sub-folder as part of the name)."""
    words = typed.lower().split()
    keep = {n for n in cands if all(w in n.lower() for w in words)}
    top = [n for n in dict.fromkeys(pinned) if n in keep]
    return top, sorted((n for n in keep if n not in set(top)), key=_key)


def rows(cands, pinned=(), typed: str = "") -> list[str | None]:
    """The names to show, ``None`` for the line between the two groups (only when both have files)."""
    top, rest = order(cands, pinned, typed)
    return [*top, *([None] if top and rest else []), *rest]


class LinkPicker:
    """``on_pick(name)`` is called with the chosen file ("" for "Use the expected file again", only offered when ``unlink`` is set)."""

    def __init__(self, root, anchor_xy, cands: list[str], pinned=(), hints: dict | None = None, mapped: str | None = None,
                 explain: str = "", unlink: str = "", on_pick: Callable[[str], None] | None = None, scale: float = 1.0,
                 strong=(), note: str = ""):
        self.root, self.cands, self.pinned, self.hints = root, list(cands), list(pinned), dict(hints or {})
        self.strong = set(strong)      # files shown in green with a dot (the one in use): easy to see in a long list
        self.mapped, self.on_pick, self.closed, self.shown = mapped, on_pick, False, []
        px = lambda n: round(n * scale)  # noqa: E731
        top = self.top = tk.Toplevel(root, **hostos.TOP_KW)
        top.wm_overrideredirect(True)
        top.configure(bg=PANEL, highlightthickness=1, highlightbackground="#5c5c5c")
        self.v = tk.StringVar()
        if note:          # nothing to choose from: a calm note instead of a list (no red error in the status line, user 7.11.)
            self.entry = self.lb = None
            tk.Label(top, text=note, bg=PANEL, fg=FG, font=font(9), justify="left", anchor="w",
                     wraplength=px(380)).pack(padx=px(14), pady=px(12))
            self._finish(top, anchor_xy, px, top)
            return
        self.entry = tk.Entry(top, textvariable=self.v, bg="#1f1f1f", fg=FG, insertbackground=FG, relief="flat", font=font(9),
                              highlightthickness=1, highlightbackground="#454545", highlightcolor=ACCENT)
        self.entry.pack(fill="x", padx=px(8), pady=(px(8), px(4)))
        if explain:
            tk.Label(top, text=explain, bg=PANEL, fg=MUTED, font=font(9), justify="left", anchor="w",
                     wraplength=px(420)).pack(fill="x", padx=px(8), pady=(0, px(4)))
        body = tk.Frame(top, bg=PANEL)
        body.pack(fill="both", expand=True, padx=px(8), pady=(0, px(4)))
        self.lb = tk.Listbox(body, height=ROWS, width=self._chars(root, px),
                             exportselection=False, activestyle="none", bg=PANEL, fg=FG, selectbackground=ACCENT,
                             selectforeground=HOT_FG, relief="flat", highlightthickness=0, font=font(9))
        sb = tk.Scrollbar(body, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lb.pack(side="left", fill="both", expand=True)
        if unlink:
            b = tk.Label(top, text=unlink, bg=PANEL, fg=MUTED, font=font(9), cursor="hand2", anchor="w", padx=px(10), pady=px(4))
            b.bind("<Button-1>", lambda e: self._take(""))
            b.pack(fill="x", padx=px(8), pady=(0, px(6)))
        self.entry.bind("<KeyRelease>", lambda e: self.refill() if e.keysym not in ("Up", "Down", "Return", "Escape") else None)
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Return>", lambda e: self._pick_selected())
        self.lb.bind("<ButtonRelease-1>", lambda e: self._pick_clicked(e))
        self.lb.bind("<Return>", lambda e: self._pick_selected())
        # the wheel only moves the list: "break" keeps it from reaching the window under the pointer (the old menu closed here)
        bind_wheel(self.lb, lambda e: (self.lb.yview_scroll(-3 if wheel_up(e) else 3, "units"), "break")[1])
        self.refill()
        self._finish(top, anchor_xy, px, self.entry)

    def _finish(self, top, anchor_xy, px, focus_widget):
        """Closing (Escape, lost focus, a click outside), place the window inside the screen, take the keyboard."""
        root = self.root
        top.bind("<Escape>", lambda e: self.close())
        top.bind("<FocusOut>", lambda e: root.after(200, self._lost_focus))
        self._outside_id = None
        root.after(200, self._watch_clicks)      # not at once: the click that opened the window must not close it
        top.update_idletasks()
        x, y = anchor_xy
        try:                            # inside the screen
            w, h = top.winfo_reqwidth(), top.winfo_reqheight()
            x = max(root.winfo_vrootx(), min(x, root.winfo_vrootx() + root.winfo_vrootwidth() - w - px(8)))
            y = max(root.winfo_vrooty(), min(y, root.winfo_vrooty() + root.winfo_vrootheight() - h - px(48)))
        except (tk.TclError, TypeError):
            pass
        top.wm_geometry(f"+{x}+{y}")
        top.lift()
        top.focus_force()
        focus_widget.focus_force()

    def _chars(self, root, px) -> int:
        """The list is as wide as its longest line (names are never cut), at most the screen less a margin."""
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(root=root, font=font(9))
            longest = max((f.measure(self._line(n)) for n in self.cands), default=0)
            room = root.winfo_vrootwidth() - px(120)
            return max(40, int(min(longest + px(40), room) / max(1, f.measure("0"))) + 1)
        except (tk.TclError, TypeError, ValueError):
            return max(40, min(120, max((len(self._line(n)) for n in self.cands), default=40) + 8))

    def _line(self, n: str) -> str:
        tag = f"   ({self.hints[n]})" if n in self.hints else ""
        return ("● " if n in self.strong else "✓ " if n == self.mapped else "") + n + tag

    # ---------- the list ----------

    def refill(self):
        self.shown = rows(self.cands, self.pinned, self.v.get())
        self.lb.delete(0, "end")
        for n in self.shown:
            if n is None:
                self.lb.insert("end", SEPARATOR)
                self.lb.itemconfigure("end", foreground=MUTED, selectforeground=MUTED, selectbackground=PANEL)
                continue
            self.lb.insert("end", self._line(n))
            if n in self.strong:
                self.lb.itemconfigure("end", foreground=DONE_GREEN)
        first = next((i for i, n in enumerate(self.shown) if n is not None), None)
        if first is not None:
            self.lb.selection_clear(0, "end")
            self.lb.selection_set(first)
            self.lb.activate(first)

    def _move(self, step: int):
        sel = self.lb.curselection()
        i = sel[0] if sel else -1
        while True:
            i += step
            if i < 0 or i >= len(self.shown):
                return "break"
            if self.shown[i] is not None:
                break
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.activate(i)
        self.lb.see(i)
        return "break"

    def _pick_selected(self):
        sel = self.lb.curselection()
        if sel and self.shown[sel[0]] is not None:
            self._take(self.shown[sel[0]])
        return "break"

    def _pick_clicked(self, e):
        i = self.lb.nearest(e.y)
        if 0 <= i < len(self.shown) and self.shown[i] is not None:
            self._take(self.shown[i])

    # ---------- closing ----------

    def _watch_clicks(self):
        """A click anywhere in the plugin outside this window closes it (user 7.11.; the window has no title bar, so the lost focus alone
        does not always say it). A click in another program is covered by the lost focus."""
        if self.closed:
            return
        try:
            self._outside_id = self.root.bind_all("<ButtonPress>", self._outside, add="+")
        except tk.TclError:
            self._outside_id = None

    def _outside(self, e):
        if self.closed:
            return
        if not str(e.widget).startswith(str(self.top)):
            self.close()

    def _unwatch_clicks(self):
        fid, self._outside_id = self._outside_id, None
        if not fid:
            return
        try:      # remove only our own line of the binding on "all" (other parts of the plugin bind there too)
            keep = [ln for ln in str(self.root.tk.call("bind", "all", "<ButtonPress>")).split(NL) if fid not in ln]
            self.root.tk.call("bind", "all", "<ButtonPress>", NL.join(keep))
            self.root.deletecommand(fid)
        except tk.TclError:
            pass

    def _take(self, name: str):
        self.close()
        if self.on_pick:
            self.on_pick(name)

    def _lost_focus(self):
        if self.closed:
            return
        try:
            if self.top.focus_displayof() is not None:
                return
        except Exception:  # noqa: BLE001
            pass
        self.close()

    def close(self):
        self.closed = True
        self._unwatch_clicks()
        try:
            self.top.destroy()
        except Exception:  # noqa: BLE001
            pass
