"""Easy Mode, the logic without a window (PLAN.md point 17, docs/easymode-plan.md).

Easy Mode shows only the function buttons and the prompt; the plugin picks the model. This file holds what can be tested
without Tk: the seven functions, the priority of the models per function, the choice of the best installed model, the
visible texts and the saved switch. The window part lives in gui_easy.py.
"""
from __future__ import annotations

from typing import Callable, Iterable

from . import config as cfgmod
from . import models

# The functions Easy Mode offers (user 31.10.: six; Multi Image Edit is left out; Refine is back in since 2.11.).
EASY_MODES = ("txt2img", "edit", "inpaint", "remove", "outpaint", "upscale", "refine")

# The models per function, best first (user 31.10., from the "perfect" list and the ranking). Easy Mode uses the first one
# that is offered and not hidden. The favourite of a function (right-click menu of the model chip) goes first, the order below
# is the fallback (user 2.11.); saved pages do not count in Easy Mode.
PRIORITY = {
    "txt2img": ("flux3", "moss", "flux2", "qwen", "fibo"),
    "edit": ("flux3", "qwen", "flux2", "fibo"),
    "inpaint": ("fibo", "qwen"),
    "remove": ("fibo", "qwen"),
    "outpaint": ("flux2", "flux3", "qwen", "fibo"),
    "upscale": ("qwen", "flux3", "flux2", "fibo"),   # Fibo last: only 1.5x and 2x (6.11.)
    "refine": ("fibo", "flux2", "flux3", "qwen"),   # same order as the ranking
}

# Functions Easy Mode leaves out, with the models that do them best first (the list in the Easy Mode tab of the settings).
EXTRA_PRIORITY = {
    "multi_edit": ("flux3", "flux2", "qwen", "fibo"),
}

# The models the Easy Mode tab lists and gets (user 2.11.): Flux 3, and Qwen or Fibo. Necessary: Flux 3 and one of the other two.
STARTER_MODELS = ("flux3", "qwen", "fibo")
STARTER_NEEDED = ("flux3",)
STARTER_EITHER = ("qwen", "fibo")

# Visible texts (user 31.10.). Edit them here (user-edits.md).
SWITCH_TEXT = "Easy Mode"
SWITCH_TIP = ("Easy mode: only the basics. The plugin picks the best installed model and its tested settings. "
              "Click again for all settings.")
MODEL_LINE = "{name}"                         # in the footer, right of "Live preview"
MODEL_TIP = "The model Easy Mode picked for this function."
MODE_GREYED_TIP = "No model installed for this function. Get the starter models in the settings (gear) under Easy Mode."
MODE_MODEL_TIP = "Currently used for this mode: {model}."     # the tooltip of a function button in Easy Mode (user 3.11.)
NO_MODELS = "No models yet. Open the settings (gear) and get the starter models."
STATUS_ON = "Easy mode on: the plugin picks the model and settings."
TAB_TITLE = "Easy mode models"
TAB_HEAD = "Easy mode is a reduced mode that offers the most important functions with only 2 of the 3 models listed below."      # the headline of the tab (user 6.11.)
TAB_INFO = "To use Easy mode, download the model weights of Flux 3 Klein Edit and either Qwen 2.1 or Fibo 2.0 Edit Turbo."
TAB_READY = "You installed the necessary models for Easy mode - start creating now."      # below the models list, with TAB_MORE
TAB_BUTTON = "Get the starter models"
TAB_MORE = "The only function that is not available in Easy mode is Multi Image Edit. Switch Easy mode off to use it."
TAB_FLUX3_NOTE = "Flux 3 needs a free Hugging Face login once. The button opens its page."


def starter_ready(ready: Callable[[str], bool]) -> bool:
    """True when the models Easy Mode needs are there: Flux 3 and at least one of Qwen and Fibo (`ready(key)`: all files there)."""
    return all(ready(k) for k in STARTER_NEEDED) and any(ready(k) for k in STARTER_EITHER)


def best_model(mode: str, usable: Callable[[str], bool], hidden: Iterable[str] = (), favorite: str = "") -> str:
    """The best model for `mode`: the favourite when it has the function, is usable (all its files are there) and is not hidden,
    else the first of PRIORITY that does; '' when there is none (the function is greyed out)."""
    hidden = set(hidden)
    for key in ((favorite,) if favorite else ()) + PRIORITY.get(mode, ()):
        m = models.BY_KEY.get(key)
        if m is not None and mode in m.modes and key not in hidden and usable(key):
            return key
    return ""


def available_modes(usable: Callable[[str], bool], hidden: Iterable[str] = (), favorites: dict | None = None) -> dict:
    """Each Easy Mode function -> its model key ('' = greyed out)."""
    favorites = favorites or {}
    return {mode: best_model(mode, usable, hidden, favorites.get(mode, "")) for mode in EASY_MODES}


def model_line(model_key: str) -> str:
    """The model's name for the footer, right of "Live preview": 'Fibo 2.0 Edit Turbo' ('' without a model)."""
    m = models.BY_KEY.get(model_key)
    return MODEL_LINE.format(name=m.label) if m else ""


def is_on() -> bool:
    return bool(cfgmod.get_setting("easy_mode", False))


def set_on(on: bool) -> None:
    cfgmod.set_setting("easy_mode", True if on else None)


def save_return(values: dict) -> None:
    """The window state of the normal mode, kept while Easy Mode is on (model, function and the settings)."""
    cfgmod.set_setting("easy_return", dict(values))


def pop_return() -> dict:
    """The kept state of the normal mode, and forget it."""
    v = cfgmod.get_setting("easy_return", {})
    cfgmod.set_setting("easy_return", None)
    return dict(v) if isinstance(v, dict) else {}
