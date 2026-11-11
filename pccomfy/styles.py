"""Style prompts for the "Styles" button beside the prompt (gui_prompt.py), without Tk.

The data is pccomfy/assets/styles.json, built by tools/build_styles.py from the Krea 2 Style Explorer (ThetaCursed, MIT,
licence in pccomfy/assets/LICENSE-krea-style-explorer.txt). It can be extended by hand. Format:

    {"modes": {"<mode>": {"groups": [{"name": "...", "styles": [{"name": "...", "text": "..."}]}]}}}

A mode that has no entry gets no Styles button; Text to image ("txt2img") is the first one, another mode (e.g. "edit")
only needs its own key under "modes". A broken file means no styles, never a crash.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = Path(__file__).resolve().parent / "assets" / "styles.json"


def load(path: Path | str | None = None) -> dict[str, list[dict]]:
    """{mode: [group, ...]} with group = {"name": str, "styles": [{"name": str, "text": str}, ...]}; entries without a
    name or text and empty groups are left out."""
    try:
        data = json.loads(Path(path or FILE).read_text(encoding="utf-8"))
        modes = data["modes"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out: dict[str, list[dict]] = {}
    for mode, spec in (modes.items() if isinstance(modes, dict) else ()):
        groups = []
        for g in (spec.get("groups", []) if isinstance(spec, dict) else []):
            if not isinstance(g, dict) or not str(g.get("name", "")).strip():
                continue
            styles = [{"name": str(s["name"]).strip(), "text": str(s["text"])} for s in g.get("styles", [])
                      if isinstance(s, dict) and str(s.get("name", "")).strip() and str(s.get("text", "")).strip()]
            if styles:
                groups.append({"name": str(g["name"]).strip(), "styles": styles})
        if groups:
            out[str(mode)] = groups
    return out


def subject_of(text: str, templates, mark: str) -> str | None:
    """What stands at the place of ``mark`` in ``text`` when ``text`` is one of ``templates`` with the mark filled in (plan B,
    10.11.: a new style keeps what was typed for <WHAT IT SHOWS>); the mark itself when it is still there; None for any
    other text."""
    text = text.strip()
    for tpl in templates:
        if mark not in tpl:
            continue
        head, _, tail = tpl.strip().partition(mark)
        if text.startswith(head) and text.endswith(tail) and len(text) >= len(head) + len(tail):
            return text[len(head):len(text) - len(tail)]
    return None


def fill(template: str, subject: str | None, mark: str) -> str:
    """The style's text with the subject put in at ``mark`` (the mark stays when there is no subject)."""
    return template.replace(mark, subject) if subject else template
