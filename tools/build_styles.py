"""Builds pccomfy/assets/styles.json (the style prompts of the Styles button) from the chosen selection.

    python tools/build_styles.py [data/styles/auswahl-2026-11-10.json [data/styles/krea_moodboards.json]]

The selection (groups with an `index` and a short name per style) and the text source (`krea_moodboards.json` of ThetaCursed/Krea2-Style-Explorer,
MIT, https://github.com/ThetaCursed/Krea2-Style-Explorer) live in data/styles (git-ignored). The texts are copied character for character
(`styleKeywords`); only the group and the short name come from the selection. Today only Text to image gets styles.
Since 10.11.2026 (plan B step 3, docs/stile-umbenennung-vorschlag.md) the selection is auswahl-2026-11-10.json: 84 styles with descriptive
names in 13 groups (each entry keeps its old name under "old"); auswahl-final.json (186 in 9 groups, 1.11.) stays as it was.
Own texts (not from Krea, user 10.11.) live in tools/styles-own.json (in the repo) and are added at the end of their group.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = "txt2img"
OWN = ROOT / "tools" / "styles-own.json"


def build(selection: Path, source: Path, own: Path = OWN) -> dict:
    texts = {e["index"]: e["styleKeywords"] for e in json.loads(source.read_text(encoding="utf-8"))}
    groups = []
    for g in json.loads(selection.read_text(encoding="utf-8"))["groups"]:
        groups.append({"name": g["name"], "styles": [{"name": s["name"], "text": texts[s["index"]]} for s in g["styles"]]})
    by_name = {g["name"]: g for g in groups}
    for g in (json.loads(own.read_text(encoding="utf-8"))["groups"] if own.exists() else []):
        if g["name"] not in by_name:
            by_name[g["name"]] = {"name": g["name"], "styles": []}
            groups.append(by_name[g["name"]])
        by_name[g["name"]]["styles"] += [{"name": s["name"], "text": s["text"]} for s in g["styles"]]
    return {
        "source": "ThetaCursed/Krea2-Style-Explorer, krea_moodboards.json, styleKeywords (MIT, see LICENSE-krea-style-explorer.txt); "
                  "except the own texts of tools/styles-own.json",
        "modes": {MODE: {"groups": groups}},
    }


def main(argv: list[str]) -> int:
    sel = Path(argv[0]) if argv else ROOT / "data" / "styles" / "auswahl-2026-11-10.json"
    src = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "styles" / "krea_moodboards.json"
    out = ROOT / "pccomfy" / "assets" / "styles.json"
    data = build(sel, src)
    try:        # the other modes' styles (Sketch to image, plan B 10.11.) are kept by hand in the file: never lost here
        old = json.loads(out.read_text(encoding="utf-8")).get("modes", {})
    except (OSError, ValueError, AttributeError):
        old = {}
    data["modes"].update({k: v for k, v in old.items() if k != MODE})
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(g["styles"]) for g in data["modes"][MODE]["groups"])
    print(f"{out}: {n} styles in {len(data['modes'][MODE]['groups'])} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
