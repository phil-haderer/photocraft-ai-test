"""Tip of the day: a small popup when the window starts (PLAN.md point 16), and the matching tick in the settings window.
The tips are in tips.py. The shown ones and the tick are kept in settings.json (state.json is rewritten completely on every save)."""
from __future__ import annotations

import hashlib
import os
import random

from . import hostos, winlink
from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from .gui_theme import SMALL_ICON_PX
from .tips import TIPS

HIDE_KEY, SHOWN_KEY = "hide_tips", "shown_tips"
HIDE_TEXT = "Don’t show tips at startup"
POPUP_W, POPUP_WRAP = 380, 340           # popup width and text width in px at 100 %
# Until 3.11. the shown tips were kept as their numbers in tips.py; these are the ids of those 31 tips in that order, so an old
# list still counts after tips were removed (user 3.11.)
LEGACY_IDS = ("d8e18eec", "fd9fa9f1", "b2381b70", "4651d1b0", "7c7d08e0", "82093726", "8b0a92d5", "7d64edd8", "45558978",
              "e8e70a86", "e01328eb", "17db5250", "a43280ab", "f231a72e", "8c759488", "4448235d", "1f1daa2c", "1a3e9165",
              "c655512f", "8af57d8b", "4aa60104", "bbbecccb", "0f28f04f", "72447ec8", "3a23a8d5", "ed81616d", "435219da",
              "c887a3c2", "fc1131d9", "5ecc44e8", "1f6275ae")


def tip_log(text: str, fresh: bool = False) -> None:
    """A few lines about the start of the tip popup in data/exchange/tips.log (the popup was recorded as shown but not seen, user
    2.11.). A new start overwrites the file. Never raises."""
    try:
        import time
        path = cfgmod.EXCHANGE_DIR / "tips.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w" if fresh else "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {text}\n")
    except Exception:
        pass


def tips_hidden() -> bool:
    return bool(cfgmod.get_setting(HIDE_KEY, False))


def tip_id(text: str) -> str:
    """A short id of a tip's text: the shown list keeps these, so removing or reordering tips does not mix it up; a tip
    whose wording changed counts as new."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def shown_indices(stored, tips=TIPS) -> list[int]:
    """The saved shown list as numbers in `tips`: ids, and the numbers of the old lists (LEGACY_IDS). Unknown ones are dropped."""
    if not isinstance(stored, list):
        return []
    where = {tip_id(t): i for i, t in enumerate(tips)}
    out = []
    for s in stored:
        if isinstance(s, int) and not isinstance(s, bool):
            s = LEGACY_IDS[s] if 0 <= s < len(LEGACY_IDS) else None
        i = where.get(s) if isinstance(s, str) else None
        if i is not None and i not in out:
            out.append(i)
    return out


def next_tip(tips=TIPS, rng=random) -> int:
    """Picks the next tip (pick_tip) and saves the shown list as ids."""
    i, shown = pick_tip(len(tips), shown_indices(cfgmod.get_setting(SHOWN_KEY, []), tips), rng)
    cfgmod.set_setting(SHOWN_KEY, [tip_id(tips[k]) for k in shown])
    return i


def first_start() -> bool:
    """No tip at the very first start (user 3.11.): it is the start without a shown list yet. It leaves an empty one, so the
    next start shows a tip."""
    if cfgmod.get_setting(SHOWN_KEY, None) is not None:
        return False
    cfgmod.set_setting(SHOWN_KEY, [])
    return True


def pick_tip(count: int, shown, rng=random) -> tuple[int, list[int]]:
    """A random tip index that was not shown yet; when all were shown, the round starts again. Returns it and the new shown list."""
    done = [i for i in shown if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < count] if isinstance(shown, list) else []
    left = [i for i in range(count) if i not in done]
    if not left:                                   # all shown: a new round (the tip just shown is not first again)
        last = done[-1] if done else -1
        done, left = [], [i for i in range(count) if i != last] or [0]
    i = rng.choice(left)
    return i, done + [i]


class TipsMixin:
    def _schedule_tip(self):
        """Called once at the end of start-up. Not in tests (PCCOMFY_NO_TIPS=1)."""
        if not os.environ.get("PCCOMFY_NO_TIPS"):
            self._tip_tries = 0
            tip_log("start-up done, popup scheduled", fresh=True)
            self.root.after(600, self._tip_when_ready)

    def _tip_when_ready(self):
        """The popup waits until the plugin window is tied to PhotoCraft (it moves to PhotoCraft's window then) and can be seen.
        Shown at a fixed 0.6 s after start-up it came while PhotoCraft was still loading, beside the plugin's first place or
        hidden with it, and was lost (user 2.11.). Gives up waiting after about 20 s (PhotoCraft not found)."""
        if getattr(self, "_closing", False):
            return
        self._tip_tries += 1
        try:
            seen = self.root.winfo_viewable() and self.root.state() == "normal"
        except tk.TclError:
            seen = False
        linked = not (self.v_top.get() and winlink.available()) or getattr(self, "_pc_seen", False)
        if self._tip_tries in (1, 5, 20, 40, 41):
            tip_log(f"try {self._tip_tries}: seen={seen} linked={linked} top={self.v_top.get()} pc_seen={getattr(self, '_pc_seen', None)}")
        if (seen and linked) or self._tip_tries > 40:
            if self._tip_tries <= 40 and linked:
                self.root.after(800, self._show_tip_popup)       # the window has just been placed at PhotoCraft
            else:
                self._show_tip_popup()
            return
        self.root.after(500, self._tip_when_ready)

    def _show_tip_popup(self):
        if getattr(self, "_closing", False) or getattr(self, "_tip_win", None) or tips_hidden() or not TIPS:
            return
        try:
            if self.root.state() in ("iconic", "withdrawn"):
                tip_log(f"not shown: the window is {self.root.state()}")
                return
        except tk.TclError:
            return
        if first_start():
            tip_log("not shown: first start")
            return
        i = next_tip()
        self._tip_hist, self._tip_pos = [i], 0
        self._build_tip_popup(TIPS[i])

    def _tip_step(self, step: int):
        """The arrows of the popup: back to the tip before, or on to the next one (a new one that was not shown yet when the
        end of this window's tips is reached). The tips shown are kept like the first one."""
        pos = self._tip_pos + step
        if pos < 0 or not getattr(self, "_tip_win", None):
            return
        if pos >= len(self._tip_hist):
            self._tip_hist.append(next_tip())
        self._tip_pos = pos
        self._tip_label.configure(text=TIPS[self._tip_hist[pos]])
        self._tip_back.configure(state="normal" if pos > 0 else "disabled")
        win = self._tip_win
        try:
            win.update_idletasks()
            win.geometry(f"{win.winfo_width()}x{win.winfo_reqheight()}")      # the text may be longer or shorter
        except tk.TclError:
            pass

    def _build_tip_popup(self, text: str):
        """The window: the tip, the arrows, the tick and "OK". The tick is saved at once, so it also holds when the window is just closed."""
        win = tk.Toplevel(self.root, **hostos.TOP_KW)
        win.title("Tip of the day")
        win.wm_overrideredirect(True)                  # no title bar (user 31.10.); the thin frame keeps it visible
        win.configure(bg=BG, highlightthickness=1, highlightbackground="#5c5c5c")
        self._tip_win = win
        v_hide = tk.BooleanVar(value=tips_hidden())
        self._tip_hide_var = v_hide

        def close():
            self._tip_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass

        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=self._keep(14), pady=self._keep(12))
        ttk.Label(box, text="Tip of the day", font=font(10, bold=True), foreground=ACCENT_TEXT).pack(anchor="w")
        self._tip_label = ttk.Label(box, text=text, wraplength=self._px(POPUP_WRAP), justify="left", font=font(10))
        self._tip_label.pack(anchor="w", pady=(self._keep(8), self._keep(12)))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ok = ttk.Button(row, text="OK", command=close, style="TipOk.TButton")
        ok.pack(side="right")
        nav = ttk.Frame(row)                           # the arrows browse the tips (user 2.11.)
        nav.pack(side="left", padx=(0, self._keep(6)))
        self._tip_back = ttk.Button(nav, image=self._icon("chevron-left", ACCENT_TEXT, px=SMALL_ICON_PX), style="Link.TButton", command=lambda: self._tip_step(-1))
        self._tip_back.pack(side="left")
        self._tip_back.configure(state="disabled")
        Tooltip(self._tip_back, "The tip before.")
        nxt = ttk.Button(nav, image=self._icon("chevron-right", ACCENT_TEXT, px=SMALL_ICON_PX), style="Link.TButton", command=lambda: self._tip_step(1))
        nxt.pack(side="left", padx=(self._keep(4), 0))
        Tooltip(nxt, "The next tip.")
        ttk.Checkbutton(row, text=HIDE_TEXT, variable=v_hide, style="SetText.TCheckbutton",
                        command=lambda: cfgmod.set_setting(HIDE_KEY, True if v_hide.get() else None)).pack(side="left")
        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Return>", lambda e: close())
        win.bind("<Escape>", lambda e: close())
        win.bind("<Left>", lambda e: self._tip_step(-1))
        win.bind("<Right>", lambda e: self._tip_step(1))
        try:
            win.transient(self.root)
            win.update_idletasks()
            w, h = max(self._px(POPUP_W), win.winfo_reqwidth()), win.winfo_reqheight()
            x, y = self._tip_position(w, h)
            # Like the plugin (gui._on_top): where the plugin is tied to PhotoCraft (Windows) the popup is owned by it (transient)
            # and lies above PhotoCraft only, not above every other program (user 4.11.). Without that link (Linux, or "always
            # on top" off) the popup is topmost only if the plugin is: the log of 2.11. showed it mapped beside the plugin yet
            # not seen, behind PhotoCraft.
            win.attributes("-topmost", bool(self.v_top.get()) and not winlink.available())
            self._tip_target = f"{w}x{h}+{x}+{y}"
            win.geometry(self._tip_target)             # after topmost: topmost first made it come up at the screen corner (user 2.11.)
            win.focus_force()
            ok.focus_set()
        except tk.TclError:
            pass
        tip_log(f"popup built: geometry={win.winfo_geometry()} plugin={self.root.winfo_geometry()} screen={self.root.winfo_vrootwidth()}x{self.root.winfo_vrootheight()}")
        for ms in (60, 250, 400):
            win.after(ms, lambda ms=ms: self._tip_check(win, ms))
        return win

    def _tip_check(self, win, ms: int):
        """Right after it was built the window may sit somewhere else (the screen corner): its place is set again when it
        differs. Logs whether the popup is really on the screen."""
        try:
            if not win.winfo_exists():
                return
            want = getattr(self, "_tip_target", "")
            at = win.winfo_geometry()
            if want and at.split("+", 1)[-1] != want.split("+", 1)[-1]:
                tip_log(f"popup after {ms} ms at {at}, set again to {want}")
                win.geometry(want)
            tip_log(f"popup after {ms} ms: mapped={win.winfo_ismapped()} viewable={win.winfo_viewable()} state={win.state()} "
                    f"geometry={win.winfo_geometry()} plugin_state={self.root.state()}")
        except tk.TclError as e:
            tip_log(f"popup after {ms} ms: {e}")

    def _tip_gap(self) -> int:
        """The room between the plugin and the popup: as high as a function button (user 4.11.)."""
        try:
            h = max(rb.winfo_reqheight() for rb in self.rb_modes.values())
        except (AttributeError, ValueError, tk.TclError):
            h = 0
        return max(self._px(8), h)

    def _tip_position(self, w: int, h: int) -> tuple[int, int]:
        """Beside the plugin where there is room (right first, then left), not on top of it; with no room on either side it
        goes to the screen edge on the side with more room. Always inside the screen."""
        r = self.root
        gap = self._tip_gap()
        left, top = r.winfo_vrootx(), r.winfo_vrooty()
        right, bottom = left + r.winfo_vrootwidth(), top + r.winfo_vrootheight()
        rl, rr = r.winfo_rootx(), r.winfo_rootx() + r.winfo_width()
        if right - rr >= w + gap:
            x = rr + gap
        elif rl - left >= w + gap:
            x = rl - gap - w
        else:
            x = right - w if right - rr >= rl - left else left
        y = r.winfo_rooty() + self._px(60)
        return max(left, min(x, right - w)), max(top, min(y, bottom - h))

    def _tips_setting_row(self, parent):
        """The same tick in the settings window (tab "Other settings")."""
        self._tips_setting_var = tk.BooleanVar(value=tips_hidden())
        cb = ttk.Checkbutton(parent, text=HIDE_TEXT, variable=self._tips_setting_var, style="SetText.TCheckbutton",
                             command=lambda: cfgmod.set_setting(HIDE_KEY, True if self._tips_setting_var.get() else None))
        cb.pack(side="top", anchor="w", padx=14, pady=(12, 4))
        Tooltip(cb, "Tick to stop the tip of the day when the plugin starts; untick to see the tips again.")
        return cb
