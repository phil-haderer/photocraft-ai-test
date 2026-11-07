"""Settings state: collect, apply, refresh from PhotoCraft, saved state. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

import os
import socket

from . import comfyaddr, photocraft
from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401


WATCH_MS = 1000       # how often the window asks PhotoCraft's control port (Linux: closing with PhotoCraft; 7.11.: 5 s took ~12 s, now ~2-3 s)
COMFY_WATCH_MS = 1000   # how often the ComfyUI dot asks the server whether it is still there (tester 5.11.: 5 s felt slow)


def show_comfy(app, up: bool, read):
    """The dot and its text. Green only when ComfyUI answered AND its lists were read (`read` True): the first quick question
    (/system_stats) alone said "connected" for a second before the real read failed (tester 7.11.). While the read is still
    to come (`read` None) the dot stays red with "connecting ..", never grey (user 3.11.)."""
    app.v_conn.set("ComfyUI connected" if up and read else "ComfyUI connecting …" if up and read is None else "ComfyUI not connected")
    set_dot(app.lbl_dot, bool(up and read))


class StateMixin:
    # ---------- connections ----------

    def _initial_comfy_state(self):
        """The dot and its text show the real state from the first picture: one short question before the window appears
        (0.5 s at most; a refused local connection answers at once), not green or red by assumption and corrected later
        (tester 5.11.). The watcher below keeps it current."""
        if os.environ.get("PCCOMFY_NO_WATCH"):
            return
        ok = comfyaddr.probe(self.comfy.url, 0.5)[0]
        self._comfy_up = ok
        self._comfy_read = None             # not read yet: the dot turns green when refresh() has read the lists
        show_comfy(self, ok, None)

    def _watch_comfy(self):
        """The dot at the bottom left follows ComfyUI while the window is open: every COMFY_WATCH_MS a short question on a fresh
        connection (in a thread), so a ComfyUI that was closed turns it red and a started one turns it green (user 4.11.)."""
        if os.environ.get("PCCOMFY_NO_WATCH"):
            return
        if not getattr(self, "_watching", False):
            self._watching, url = True, self.comfy.url

            def work():
                ok = comfyaddr.probe(url, 2.0)[0]
                self._watching = False
                self.events.put(("alive", (url, ok)))
            threading.Thread(target=work, daemon=True).start()
        self.root.after(COMFY_WATCH_MS, self._watch_comfy)

    def _comfy_alive(self, url: str, ok: bool):
        """The answer of _watch_comfy. A ComfyUI that comes back is read again (lists, files); an old address is ignored."""
        if url != self.comfy.url:
            return
        was = getattr(self, "_comfy_up", None)
        self._comfy_up = ok
        if not ok:
            self._comfy_read = None         # gone: when it comes back it is read again first
        show_comfy(self, ok, getattr(self, "_comfy_read", None))
        if ok and was is False:
            self.refresh()

    def _watch_photocraft(self):
        """Where the window cannot be linked to PhotoCraft's window (Linux), it still closes with PhotoCraft: every WATCH_MS (1 s) a
        plain connection to its control port (no login) in a thread; gone twice in a row after it was seen, the window quits."""
        if os.environ.get("PCCOMFY_NO_WATCH") or winlink.available():
            return
        if self.v_top.get() and not getattr(self, "_pc_probing", False):
            self._pc_probing, host, port = True, self.pc.host, self.pc.port

            def work():
                try:
                    socket.create_connection((host, port), timeout=2.0).close()
                    ok = True
                except OSError:
                    ok = False
                self._pc_probing = False
                self.events.put(("pc-alive", ok))
            threading.Thread(target=work, daemon=True).start()
        self.root.after(WATCH_MS, self._watch_photocraft)

    def _photocraft_alive(self, ok: bool):
        """The answer of _watch_photocraft (same rule as the Windows watchdog in gui._try_link: seen once, gone twice)."""
        if ok:
            self._pc_seen, self._pc_gone = True, 0
        elif getattr(self, "_pc_seen", False) and self.v_top.get():
            self._pc_gone = getattr(self, "_pc_gone", 0) + 1
            if self._pc_gone >= 2:
                self._quit()

    def refresh(self):
        def work():
            info = {}
            try:
                self.pc.close()
                self.pc.ping()
                info["pc_version"] = getattr(self.pc, "version", lambda: None)()
                if not winlink.available():
                    # seen at the start: the Linux watcher need not wait for its first probe (5 s), so PhotoCraft
                    # closed within the first seconds still closes the window
                    self.events.put(("pc-alive", True))
            except PhotoCraftError as e:
                info["err"] = str(e)         # shown as a message; the footer has no PhotoCraft mark
            try:
                info["ckpts"] = self.comfy.checkpoints()
                info["samplers"] = self.comfy.samplers()
                info["clips"] = self.comfy.clips()
                info["loras"] = self.comfy.loras()
                info["scheds"] = self.comfy.schedulers()
                info["comfy"] = True
            except ComfyError as e:
                info["comfy"] = False
                info.setdefault("err", str(e))
            self.events.put(("refresh", info))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh(self, info):
        if "comfy" in info:
            self._comfy_up = bool(info["comfy"])
        self._comfy_read = bool(info.get("comfy"))
        show_comfy(self, self._comfy_read, self._comfy_read)
        if info.get("ckpts") and self.v_ckpt.get() not in info["ckpts"]:
            self.v_ckpt.set(info["ckpts"][0])  # only used by the built-in graph; there is no picker any more
        if info.get("clips"):
            self.cb_clip["values"] = [CLIP_DEFAULT] + info["clips"]
            if self.v_clip.get() not in self.cb_clip["values"]:
                self.v_clip.set(CLIP_DEFAULT)
        if info.get("loras") is not None:
            self.all_loras = list(info["loras"])
        if info.get("samplers"):
            self.cb_sampler["values"] = info["samplers"]
        if info.get("scheds"):
            self._sched_names = list(info["scheds"])
        self.templates = [t for t in list_templates(self.workflows_dir) if t.name not in models.PARKED_WORKFLOWS]
        self.cb_workflow["values"] = [BUILTIN] + [t.name for t in self.templates]
        if self.v_workflow.get() not in self.cb_workflow["values"]:
            # gone (or parked): the chosen model's own workflow for this function, so the model stays
            m = self._model()
            spec = m.modes.get(self.v_mode.get()) if m else None
            self.v_workflow.set(spec.workflow if spec and spec.workflow in self.cb_workflow["values"] else BUILTIN)
        self._on_workflow()
        self._sync_model()
        if not self.v_model.get() and self.v_workflow.get() == BUILTIN:
            # nothing chosen yet (first start): open on the first model whose workflow is installed
            names = {t.name for t in self.templates}
            first = next((m for m in models.MODELS if set(m.workflows()) & names), None)
            if first:
                self.v_model.set(first.key)
                self._on_model()
        self._pc_version_seen = info.get("pc_version") or getattr(self, "_pc_version_seen", None)
        note = " ".join(n for n in (getattr(self, "_wf_dir_note", ""), getattr(self, "_version_note", ""),
                                    photocraft.version_note(info.get("pc_version"))) if n)
        if note and not getattr(self, "_pc_note_shown", False):
            self._pc_note_shown = True            # once per start
            self._status(note)
        if info.get("err"):
            self._status(info["err"], error=True)

    # ---------- collect / apply (history, saved pages) ----------

    def _collect(self) -> dict:
        """Every setting in the window, as plain JSON values."""
        clip = self.v_clip.get().strip()
        return {
            "mode": self.v_mode.get(), "workflow": self.v_workflow.get(),
            "clip": "" if clip in ("", CLIP_DEFAULT) else clip,
            "checkpoint": self.v_ckpt.get().strip(), "steps": int(self.v_steps.get()), "cfg": float(self.v_cfg.get()),
            "denoise": float(self.v_denoise.get()), "seed": int(self.v_seed.get()), "variants": int(self.v_variants.get()),
            "sampler": self.v_sampler.get(), "scheduler": self.v_scheduler.get(),
            "base_res": int(self.v_res.get()), "context": float(self.v_context.get()),
            "native": bool(self.v_native.get()), "native_mp": round(float(self.v_native_mp.get()), 1),
            "ref_native": bool(self.v_ref_native.get()), "ref_mp": round(float(self.v_ref_mp.get()), 1),
            "mask_grow": int(self.v_grow.get()), "mask_blur": int(self.v_blur.get()), "overlap": int(self.v_overlap.get()),
            "scale": self._scale(),
            "enhance": bool(self.v_enhance.get()),
            "turbo": bool(self.v_turbo.get()), "stage_on": bool(self.v_stage.get()), "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "loras": self._loras(), "sharpen": round(float(self.v_sharpen.get()), 2), "detail": round(float(self.v_detail.get()), 2),
            "lora_strength": round(float(self.v_lora_str.get()), 2),
            "layer_mask": layer_mask_key(self.v_lmask.get()),
            "feather_pct": round(float(self.v_feather.get()), 1),
            "mask_density": int(self.v_density.get()),
            "prompt": self._prompt_text(), "negative": self.t_neg.get("1.0", "end").strip(),
        }

    def _apply_settings(self, s: dict) -> list[str]:
        """Put a saved preset into the window. Returns notes about anything that could not be applied."""
        notes: list[str] = []

        def put(var, key, conv=lambda v: v):
            if key in s:
                try:
                    var.set(conv(s[key]))
                except (tk.TclError, ValueError, TypeError):
                    notes.append(key)

        put(self.v_mode, "mode", str)
        if self.v_mode.get() not in dict(MODE_LABELS):      # a mode that no longer exists (the old "reference"): the first one
            self.v_mode.set(MODE_LABELS[0][0])
        wf = s.get("workflow")
        if wf is not None:
            if wf == BUILTIN or wf in list(self.cb_workflow["values"]):
                self.v_workflow.set(wf)
            else:
                notes.append(f"workflow {wf} not found")
        if "clip" in s:
            clip, known = s["clip"], list(self.cb_clip["values"])
            if not clip:
                self.v_clip.set(CLIP_DEFAULT)
            elif not known or clip in known:
                self.v_clip.set(clip)
            else:
                self.v_clip.set(CLIP_DEFAULT)
                notes.append(f"text model {clip} not found")
        put(self.v_ckpt, "checkpoint", str)
        put(self.v_steps, "steps", int)
        put(self.v_cfg, "cfg", float)
        put(self.v_denoise, "denoise", float)
        put(self.v_seed, "seed", int)
        put(self.v_variants, "variants", int)
        put(self.v_sampler, "sampler", str)
        put(self.v_scheduler, "scheduler", str)
        put(self.v_res, "base_res", int)
        put(self.v_native, "native", bool)
        put(self.v_native_mp, "native_mp", float)
        put(self.v_ref_native, "ref_native", bool)
        put(self.v_ref_mp, "ref_mp", float)
        put(self.v_context, "context", float)
        put(self.v_grow, "mask_grow", int)
        put(self.v_blur, "mask_blur", int)
        put(self.v_overlap, "overlap", int)
        put(self.v_scale, "scale", scale_text)
        put(self.v_enhance, "enhance", bool)
        put(self.v_turbo, "turbo", bool)
        if "loras" in s:
            self._set_loras(s["loras"])
        put(self.v_stage, "stage_on", bool)
        put(self.v_stage2, "stage2_on", bool)
        put(self.v_stage3, "stage3_on", bool)
        if any(k in s for k in ("stage_on", "stage2_on", "stage3_on")):
            self._stage_wf = self.v_workflow.get()
        if isinstance(s.get("stage_strengths"), list):
            for var, v in zip(self.v_sstr, s["stage_strengths"]):
                try:
                    var.set(float(v))
                except (TypeError, ValueError, tk.TclError):
                    pass
            self._update_stage_scales()
        put(self.v_detail, "detail", float)
        put(self.v_sharpen, "sharpen", float)
        self._on_sharpen()
        if "lora_strength" in s:
            self._lora_wf = self.v_workflow.get()
            put(self.v_lora_str, "lora_strength", float)
            self._on_lora_str()
        self._on_detail()
        put(self.v_feather, "feather_pct", float)
        self._on_feather()
        put(self.v_density, "mask_density", int)
        self._on_density()
        if "layer_mask" in s:
            self.v_lmask.set(LAYER_MASKS[layer_mask_key(s["layer_mask"])])
        self._update_feather_state()
        notes += self._enforce_switch_files()
        for widget, key in ((self.t_prompt, "prompt"), (self.t_neg, "negative")):
            # an empty prompt in a preset means "not part of the preset": never wipe what was typed
            if str(s.get(key, "")).strip():
                widget.delete("1.0", "end")
                widget.insert("1.0", str(s[key]))
        self._on_mode_ui()
        self._on_workflow()
        self._sync_model()
        return notes

    def _save_state(self, req: Request):
        p = req.params
        cfgmod.save_state({
            "mode": self.v_mode.get(), "workflow": self.v_workflow.get(), "clip": p.clip, "checkpoint": p.checkpoint, "prompt": p.prompt,
            "negative": p.negative, "steps": p.steps, "cfg": p.cfg, "denoise": self.v_denoise.get(),
            "sampler": p.sampler, "scheduler": p.scheduler, "variants": req.variants, "base_res": req.base_res,
            "native": req.native, "native_mp": req.native_mp,
            "context": req.context, "mask_grow": req.mask_grow, "mask_blur": req.mask_blur, "overlap": req.overlap, "scale": req.scale,
            "on_top": bool(self.v_top.get()), "adv_open": bool(self.v_adv_open.get()), "model": self.v_model.get(), "neg_open": bool(self.v_neg_open.get()), "prompt_h": self._prompt_lines(), "enhance": bool(self.v_enhance.get()), "turbo": req.turbo, "layer_mask": req.layer_mask, "mask_density": req.mask_density,
            "stage_on": req.stage_on, "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "detail": req.detail, "sharpen": round(float(self.v_sharpen.get()), 2), "loras": [list(x) for x in req.loras], "lora_strength": req.lora_strength if req.lora_strength is not None else self.state.get("lora_strength", 1.0),
            "runs": dict(self.state.get("runs", {})),
            "model_by_mode": dict(getattr(self, "_mode_model", None) or self.state.get("model_by_mode") or {}),
            "win_pos": list(getattr(self, "_win_pos", None) or self.state.get("win_pos") or []) or None,
        })
