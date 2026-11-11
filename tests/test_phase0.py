"""Phase 0 (gui.py split, models fields, Expand off for Flux 3 / Krea 2, footer without document count).
Run: python tests/test_phase0.py"""
import queue
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets  # noqa: F401  (installs the tkinter stubs)
from pccomfy import gui, models
from pccomfy import gui_lora, gui_modes, gui_prompt, gui_run, gui_state, gui_theme

# 1. App is assembled from the six mixins and no method is defined twice
mixins = (gui_theme.ThemeMixin, gui_prompt.PromptMixin, gui_lora.LoraMixin, gui_modes.ModeMixin, gui_state.StateMixin, gui_run.RunMixin)
from pccomfy import ui_settings
# L1: SettingsMixin and (L2) RefSlotsMixin stand in front on purpose: they wrap some methods and call super(), so they are left out of the "defined twice" check
# (SettingsMixin brings the download buttons as its own base, DownloadMixin: it stands right behind it)
assert gui.App.__mro__[1] is ui_settings.SettingsMixin and gui.App.__mro__[2].__name__ == "DownloadMixin", gui.App.__mro__
assert gui.App.__mro__[3].__name__ == "RefSlotsMixin" and gui.App.__mro__[4:10] == mixins, gui.App.__mro__
names = [n for m in mixins + (gui.App,) for n in vars(m) if callable(vars(m)[n]) and not n.startswith("__")]
dup = sorted({n for n in names if names.count(n) > 1})
assert not (set(vars(gui.RefSlotsMixin)) & set(names) - {"_on_mode_ui", "_request", "generate"}), "RefSlotsMixin wraps only these three (with super())"
assert not dup, f"defined twice: {dup}"
assert len(names) == 226, len(names)      # + _prompt_focus_back (the prompt field takes clicks again after the Save box, window test F 11.11.); + _match_styles_height (Styles as high as Generate) and _model_label (the run keeps its model name), window test E 11.11.; + _cp_tag, _cp_load, _refresh_custom_menu, _cp_use, save_prompt, _cp_edit, _cp_delete, _cp_finish and _cp_dialog (the Prompt-Saver, 11.11.); + _llm_wanted, _tiles_on, _prompt_margin, _styles_button_look and _styles_icon (the row over the prompt field, 10.11. evening); + _gen_wanted (the size row of MiniMax H3 Image, PLAN 2.0b, 10.11.); + _set_style and _sketch_style_fill (Sketch to image takes a style, plan B 10.11.); - _update_std_switch (the "v10 graph" tick of MOSS Fill, dead since MOSS has only Text to image, 10.11.); + _show_status_line (an empty status line takes no room, 8.11.); + _stage_row and _show_stage_row (the stages in one row of the Upscale / Refine box, Fibo, 8.11.); + _on_edit_fn (the Edit button opens on the tab Edit canvas, 7.11.); - _restore_away_prompt (Easy Mode removed, 7.11.); + _factor_ok (a factor within the model's largest one: Fibo 2x, 6.11.), + _update_factor_buttons, _sync_fac, _on_scale_fn and _on_factor (one function button "Upscale / Refine" with the factor None, 6.11.), + _cutout_ok, _cutout_rows and _cutout_menu (the scissors' model menu, 6.11.), + _build_prompt_placeholder, _prompt_placeholder and _prompt_placeholder_poll ("Prompt" inside the empty field, 6.11.), + _opts_in_advanced (the switch box in the Advanced settings for Flux 3 Upscale and Qwen, 6.11.), + _initial_comfy_state (the ComfyUI dot is right from the first picture, 5.11.), + cut_background, _cutout_available and _update_cut_button (the scissors in the footer, 5.11.); earlier: + _generating_word (status line "<model> is generating", 4.11.), + _start_fresh (standard settings at every start, 4.11.), + _update_native_text (label and tip follow the function, 4.11.), + _native_wanted, _native_mp and _on_native ("Original size", 4.11.); 106 methods of the old App (without __init__), + _on_body_size and _max_height (scroll bar), + _clear_prompt, + _dialog, + _icon and _spin_arrows, - _scale_clicks (Slider), + _show_pl_line, + _place_window, _place_at_owner and _remember_pos, + _function_icon, _custom_workflow, _update_model_chips, _model_for_mode and _remember_model_for_mode (function first), + toggle_feather_preview, _refresh_feather_preview and _feather_done (feather preview), + _mode_denoise (Reset), + _on_context and _show_context (Context slider), + _pack_post (Context under Edge feather), + _on_density (Mask density), + _lora_strength and _lora_strength_text (LoRA fields), + _needs_description and describe_scene (Krea 2 / MOSS Expand), + _seam_mode (seam correction per model), + _checkbox_look (PhotoCraft checkbox), + _show_variants and _variants_menu (Variants on Generate), + toggle_minimize (header), + _on_turbo (LoRA switch sets steps), + _chip_menu and _set_model_hidden (right-click on the model chips), + copy_canvas (header), + _show_preview and _hide_preview (live preview), + _switch_missing and _enforce_switch_files (switches grey while their files are missing), + _save_page and _load_default_page (chip menu: saved settings per page), + _drop_focus (no focus ring after a click), + _llm_file, _update_llm_button and describe_canvas (LLM button), + _history_begin, _history_end, _history_menu, _history_rows, erase_history and load_history (the last runs), + _below_prompt (LLM row under the prompt), + _llm_row_wanted (row only with a text model), + _drag_start and _drag_move (no title bar), + _set_last_seed and use_last_seed (icon beside the seed), + _reset_click and _reset_settings (Shift + Reset page), + _build_styles_menus, _update_styles_button, _styles_menu, _apply_style, _style_text_at, _style_preview and _style_tip_hide (Styles button), + _monitor_at, _place_native and _menu_span (hover box beside the real menu), + _update_std_switch (Std nodes tick, test A2), + _on_stage (stage with its own sampler values: MOSS 4-step), + _on_scale_pick (mix by upscale factor); - the preset functions (removed 1.11.: refresh_presets, save_preset, save_preset_as, _write_preset, _preset_path, load_preset, delete_preset, preset_blocked; the hidden preset bar), + _flat_tabs (flat settings tabs), + _update_negative_box (the negative prompt row only where it has an effect), + _restore_away_prompt (your own text comes back after Easy mode), + _apply_linux_scale (Linux display scale), + stop_all and _show_stop_all (Cancel all), + _screen_span and _scroll_into_view (the body scrolls when the screen is too small); - _fit_top, _move_top and _max_height (the window no longer moves itself, 4.11.), + _copy_menu (right-click copies a text or link), + _watch_comfy and _comfy_alive (the ComfyUI dot follows the server), + _keep (a gap already scaled, spacing.py), + _watch_photocraft and _photocraft_alive (the window closes with PhotoCraft on Linux)

# 2. what the other tests and callers read from gui.py is still there
for name in ("BUILTIN", "MODE_LABELS", "SHORT_MODES", "LAYER_MASKS", "CLIP_DEFAULT", "ACCENT", "PROMPT_LINES", "FILL_CONTEXT",
             "word_left", "word_right", "sweep_requests", "duration_text", "scale_text", "parse_list", "winlink", "Tooltip", "run_gui", "DONE_GREEN"):
    assert hasattr(gui, name), name

# 3. models: Expand is on for Flux 3 (26.10.), off for Krea 2 and MOSS (blind test 29.10.); the new fields start neutral
by = models.BY_KEY
assert list(by["flux3"].modes) == ["txt2img", "edit", "multi_edit", "sketch", "scribble", "remove", "outpaint", "upscale", "refine"]
assert list(by["krea2"].modes) == ["txt2img"]
assert list(by["flux2"].modes) == ["txt2img", "edit", "multi_edit", "sketch", "scribble", "inpaint", "remove", "outpaint", "upscale", "refine"]
assert list(by["qwen"].modes) == ["txt2img", "edit", "multi_edit", "sketch", "scribble", "inpaint", "outpaint", "remove", "upscale", "refine"]
assert list(by["moss"].modes) == ["txt2img"]
assert [m.key for m in models.MODELS] == ["flux3", "flux2", "qwen", "fibo", "krea2", "moss", "minimax"]
for m in models.MODELS:
    assert isinstance(m.requires, tuple) and m.requires, m.key      # L1 filled requires (the file names per tab); test_detection.py checks them
    assert (m.max_refs == 0) == (m.tag_style == ""), m.key          # L2: a model with slots names its images
assert {k: (m.max_refs, m.tag_style) for k, m in by.items()} == {
    "qwen": (8, "<image{n}>"), "fibo": (2, "<image_{n}>"), "flux2": (3, "image {n}"), "flux3": (3, "<ref_image_{i}>"),
    "krea2": (0, ""), "moss": (3, "image {n}"), "minimax": (6, "<Picture {n}>")}   # MiniMax: Multi image edit (step 4)  # Multi Image Edit: slots per model
assert "Expand" in by["flux3"].tip and "Expand" not in by["krea2"].tip and "Expand" not in by["moss"].tip
assert set(models.PARKED_EXPAND) == {"krea2", "moss"} and all(m.describe for m in models.PARKED_EXPAND.values())   # kept for later


# 4. footer: only "ComfyUI" and its dot (no PhotoCraft mark, no document count)
class FakePC:
    def close(self): pass
    def ping(self): return {"documents": 3}


class FakeComfy:
    def open_events(self):
        return None

    def close_events(self, ws):
        pass

    def checkpoints(self): return ["a.safetensors"]
    def samplers(self): return ["euler"]
    def clips(self): return []
    def loras(self): return []
    def schedulers(self): return ["normal"]


app = object.__new__(gui.App)
app.pc, app.comfy, app.events = FakePC(), FakeComfy(), queue.Queue()
app.refresh()
kind, info = app.events.get(timeout=5)
if kind == "pc-alive":                  # Linux (no winlink): the start ping reports PhotoCraft as seen first
    assert info is True
    kind, info = app.events.get(timeout=5)
assert kind == "refresh" and info["comfy"] is True and "pc" not in info and "err" not in info, info
# "Original size" (user 4.11.): a crop above the model's size is kept up to the cap, a small one is handled as before
from pccomfy import imaging
from pccomfy.bridge import Request
assert Request().native is False and Request().native_mp == 4.0
assert imaging.gen_size(4000, 3000, imaging.native_base(4000, 3000, 1024, 4.0), 16) == (2304, 1728)      # 12 MP -> the 4 MP cap, same aspect
assert imaging.gen_size(1600, 1200, imaging.native_base(1600, 1200, 1024, 4.0), 16) == (1600, 1200)      # 1.9 MP: as it is
assert imaging.gen_size(400, 300, imaging.native_base(400, 300, 1024, 4.0), 16) == imaging.gen_size(400, 300, 1024, 16)   # small: as before
assert imaging.gen_size(800, 800, imaging.native_base(800, 800, 1536, 4.0), 16) == imaging.gen_size(800, 800, 1536, 16)   # never below base_res
# Text to image: the canvas size, at most the limit (4 MP at most), rounded down, never enlarged (user 4.11.)
assert imaging.canvas_size(800, 600, 4.0, 16) == (800, 592)                   # small canvas: not enlarged to the 1 MP base
_cw, _ch = imaging.canvas_size(3456, 2234, 4.0, 16)
assert _cw % 16 == 0 and _ch % 16 == 0 and _cw * _ch <= 4.0e6 and _cw * _ch > 3.8e6 and abs(_cw / _ch - 3456 / 2234) < 0.02, (_cw, _ch)
assert imaging.canvas_size(1920, 1080, 4.0, 16) == (1920, 1072)               # under the cap: the canvas, rounded down
assert imaging.canvas_size(64, 10, 4.0, 16) == (64, 16)                       # never below one multiple
from pccomfy import gui_common as _gc
assert [_gc.native_mp_default(m) for m in ("txt2img", "inpaint", "outpaint", "edit", "remove")] == [4.0, 2.0, 1.0, 2.0, 2.0]   # start limits (user 4.11.)
assert _gc.NATIVE_MAX_MP == 4.0 and _gc.NATIVE_MP <= _gc.NATIVE_MAX_MP
for key, m in models.BY_KEY.items():           # Text to image is generated in the canvas size, the editing functions start with the switch off
    for mode, spec in m.modes.items():
        want = mode == "txt2img"
        assert bool(spec.settings.get("native", False)) is want, (key, mode)
# _drop_focus: on Linux Tk can hand over a path name (a str) instead of a widget; that used to raise AttributeError at every start
from types import SimpleNamespace
assert gui.App._drop_focus(SimpleNamespace(), SimpleNamespace(widget=".!combobox.popdown")) is None
_calls = []
_w = SimpleNamespace(after_idle=lambda f: _calls.append(f))
gui.App._drop_focus(SimpleNamespace(), SimpleNamespace(widget=_w))
assert len(_calls) == 1, "a real widget still gets its after_idle"

import threading
for t in threading.enumerate():      # the refresh thread of the fake must end before the interpreter does (a race made the run abort sometimes)
    if t is not threading.current_thread():
        t.join(5)
print("test_phase0 ok")
