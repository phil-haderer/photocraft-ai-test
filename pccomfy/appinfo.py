"""The plugin's version, and the report that "Copy report" (Other settings) puts on the clipboard. No Tk here.

The version lives in `pccomfy/__init__.py` (`__version__`); the release export sets it from the tag (`v0.21-test` -> `0.21-test`).
config.py stamps it into state.json and settings.json, so a changed version is noticed at the next start (`version_change`).
The report is for a bug report: where the plugin lives, which Python, which config files and what they override, what the
window was set to and what ComfyUI and PhotoCraft said. It never contains prompts, tokens or the user's home folder name."""
from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path

from . import __version__


def parse_version(v) -> tuple:
    """"0.21-test" -> (0, 21); "0.20.2" -> (0, 20, 2); () when it does not start with a number (a suffix is cut off)."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", str(v or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def version_change(stored, current: str = __version__, had_files: bool = True) -> tuple[str, str]:
    """(kind, text) for the start: kind "" (nothing to say), "updated" or "newer". `stored` is what the config files held,
    None when they hold none: a first start (no files at all) says nothing, files without a version come from before it."""
    if stored is None:
        return ("updated", f"Updated to version {current}.") if had_files else ("", "")
    a, b = parse_version(stored), parse_version(current)
    if str(stored) == str(current) or not a or not b:
        return "", ""
    if a > b:
        return "newer", (f"These settings were saved by a newer version ({stored}); this is {current}. "
                         "If something looks odd, update the plugin.")
    if a < b or str(stored) != str(current):
        return "updated", f"Updated from {stored} to {current}."
    return "", ""


def redact(text: str) -> str:
    """The user's home folder becomes "~" (both slash styles, any case): a report can be pasted into a chat."""
    out = str(text)
    home = str(Path.home())
    for h in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
        if len(h) > 3:
            out = re.sub(re.escape(h), "~", out, flags=re.IGNORECASE)
    return out


def git_commit(root: Path) -> str:
    """The short commit of a git checkout, read from the files (no git program needed); "" for a ZIP."""
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(None, 1)[1]
            p = root / ".git" / ref
            if p.exists():
                return p.read_text(encoding="utf-8").strip()[:7]
            for line in (root / ".git" / "packed-refs").read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return line.split()[0][:7]
            return ""
        return head[:7]
    except OSError:
        return ""


def _json_version(path: Path) -> str:
    import json
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return str(d.get("_version", "no version")) if isinstance(d, dict) else "not a settings file"
    except OSError:
        return "not found"
    except ValueError:
        return "unreadable"


def _overrides(cfgmod) -> list[str]:
    """The keys of config.toml that differ from the plugin's own defaults, as "section.key = value"."""
    try:
        cfg = cfgmod.load()
    except Exception as e:      # a broken config.toml is exactly what a report should show
        return [f"config.toml cannot be read ({type(e).__name__}: {e})"]
    out = []
    for sec, vals in cfg.items():
        for k, v in (vals.items() if isinstance(vals, dict) else ()):
            if cfgmod.DEFAULTS.get(sec, {}).get(k) != v:
                out.append(f"{sec}.{k} = {v}")
    return out


def build_report(app=None) -> str:
    """The report as text. `app` is the window (None: only what does not need it, for tests and the command line)."""
    from . import config as cfgmod
    root = Path(__file__).resolve().parent.parent
    lines = ["PhotoCraft x ComfyUI plugin report"]
    commit = git_commit(root)
    lines.append(f"Plugin: {__version__}" + (f" (git {commit})" if commit else " (no git checkout)"))
    lines.append(f"Installed in: {root}")
    tk = ""
    try:
        import tkinter
        tk = f", Tk {tkinter.TkVersion}"
    except Exception:
        pass
    lines.append(f"Python: {platform.python_version()}{tk} ({sys.executable})")
    lines.append(f"System: {platform.platform()}")
    lines.append(f"Config folder: {cfgmod.CONFIG_DIR}" + ("  (PCCOMFY_HOME)" if os.environ.get("PCCOMFY_HOME") else ""))
    toml = cfgmod.CONFIG_FILE
    lines.append(f"config.toml: {'found' if toml.exists() else 'not found'}; settings.json: {_json_version(cfgmod.SETTINGS_FILE)}; "
                 f"state.json: {_json_version(cfgmod.STATE_FILE)}")
    over = _overrides(cfgmod)
    if over:
        lines.append("config.toml changes: " + "; ".join(over))
    try:
        cfg = cfgmod.load()
    except Exception:          # a broken config.toml (already named above): the report goes on with the plugin's defaults
        cfg = cfgmod.DEFAULTS
    wdir, note = cfgmod.effective_workflows_dir(cfg["comfyui"]["workflows_dir"])
    count = len(list(wdir.glob("*.json"))) if wdir.is_dir() else 0
    lines.append(f"Workflows: {wdir} ({count} files)" + ("  [config.toml folder replaced by the plugin's own]" if note else ""))
    err = cfgmod.write_error()
    if err:
        lines.append(f"Settings could not be saved: {err}")
    if app is not None:
        lines += _window_lines(app)
    return redact("\n".join(lines))


def _window_lines(app) -> list[str]:
    """What only the running window knows."""
    g = lambda name, default="": getattr(app, name, default)          # noqa: E731
    out = []
    try:
        up, read = g("_comfy_up", None), g("_comfy_read", None)
        state = "connected" if (up and read) else "answers, lists not read" if up else "not reachable"
        out.append(f"ComfyUI: {app.comfy.url} - {state}")
    except Exception:
        pass
    try:
        pc = g("pc", None)
        out.append(f"PhotoCraft: port {pc.port if pc is not None else '?'}, version {g('_pc_version_seen', None) or 'unknown'}")
    except Exception:
        pass
    try:
        out.append(f"Window: model {app.v_model.get() or '-'}, function {app.v_mode.get()}, workflow {app.v_workflow.get()}")
        out.append(f"Status line: {app.v_status.get()}")
    except Exception:
        pass
    inv = g("inv", None)
    if inv is not None:
        from . import models
        parts = []
        for m in models.MODELS:
            try:
                st = inv.tab_status(m.key)
            except Exception:
                continue
            if st.state == "ready":
                parts.append(f"{m.key}: ready")
            else:
                names = [getattr(f, "name", str(f)) for f in st.missing][:3]
                more = f" (+{len(st.missing) - 3})" if len(st.missing) > 3 else ""
                nodes = f", nodes {', '.join(st.nodes[:3])}" if st.nodes else ""
                parts.append(f"{m.key}: missing {', '.join(names)}{more}{nodes}")
        out.append("Models: " + "; ".join(parts))
    else:
        out.append("Models: not read yet (ComfyUI not connected?)")
    try:
        import json
        runs = (Path(app.bridge.exchange) / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-3:]
        rows = []
        for r in runs:
            d = json.loads(r)
            if "workflow" in d:
                rows.append(f"{d.get('time', '')} {d.get('mode', '')} {d.get('workflow', '')} v{d.get('version', '?')}")
        if rows:
            out.append("Last runs (no prompts): " + " | ".join(rows))
    except (OSError, ValueError, AttributeError):
        pass
    return out
