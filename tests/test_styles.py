"""The Styles button beside the prompt (user 1.11.): styles.json (style prompts of the Krea 2 Style Explorer, MIT; for Text to image
84 with descriptive names in 13 groups since plan B step 3, 10.11.; before 186 in 9 groups; + 7 own studio and stock styles), the loader (a broken file means no styles), the palette icon, the button (only in a mode that has styles), a click on an entry is ADDED to the prompt after a line break (Text to image; Edit canvas and Sketch to image set the whole sentence, 47 styles from tools/styles-looks.json), and the whole text of every entry is kept for the hover box.
Stubbed Tk.

    python tests/test_styles.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

from pccomfy import gui_common, icons, styles  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def data_checks():
    from pccomfy import models
    got = styles.load()
    assert list(got) == ["txt2img", "edit", "sketch"], list(got)    # Edit canvas and Sketch to image since plan B (10.11.)
    look_checks(got)
    sk = {s["name"]: s["text"] for g in got["sketch"] for s in g["styles"]}
    # a new style keeps what was typed for <WHAT IT SHOWS> (decision 8)
    mark = models.SKETCH_MARK
    filled = models.SKETCH_PHOTO.replace(mark, "a red barn")
    assert styles.subject_of(filled, sk.values(), mark) == "a red barn"
    assert styles.subject_of(models.SKETCH_PHOTO, sk.values(), mark) == mark
    assert styles.subject_of("make it night", sk.values(), mark) is None
    assert styles.fill(models.SKETCH_ILLUSTRATION, "a red barn", mark) == models.SKETCH_ILLUSTRATION.replace(mark, "a red barn")
    assert styles.fill(models.SKETCH_ILLUSTRATION, None, mark) == models.SKETCH_ILLUSTRATION
    groups = got["txt2img"]
    assert len(groups) == 13 and sum(len(g["styles"]) for g in groups) == 84 + 7  # renamed and thinned (plan B step 3, 10.11.) + own
    # the own texts (tools/styles-own.json, user 10.11.) stand at the end of their group, word for word
    own = json.loads((ROOT / "tools" / "styles-own.json").read_text(encoding="utf-8"))["groups"]
    own_styles = [(g["name"], s["name"], s["text"]) for g in own for s in g["styles"]]
    assert len(own_styles) == 7 and own_styles[0][:2] == ("Studio & product", "Studio portrait")
    studio = next(g for g in groups if g["name"] == "Studio & product")
    assert [("Studio & product", s["name"], s["text"]) for s in studio["styles"][-7:]] == own_styles
    assert [g["name"] for g in groups][:3] == ["Photo", "Studio & product", "Film look"], [g["name"] for g in groups]
    names = [s["name"] for g in groups for s in g["styles"]]
    assert len(set(names)) == len(names), "short names must be unique"
    assert all(s["text"].strip() and s["name"].strip() for g in groups for s in g["styles"])
    assert all(len(g["styles"]) <= 25 for g in groups)       # a menu that fits the screen
    assert all(len(n) <= 40 for n in names), max(names, key=len)   # descriptive, but short enough for the menu
    assert (ROOT / "pccomfy" / "assets" / "LICENSE-krea-style-explorer.txt").read_text(encoding="utf-8").startswith("Style texts")
    # the texts are the source's, character for character (the source lives in data/, not in the repo: only checked where it is)
    src = ROOT / "data" / "styles" / "krea_moodboards.json"
    sel = ROOT / "data" / "styles" / "auswahl-2026-11-10.json"
    if src.exists() and sel.exists():
        texts = {e["index"]: e["styleKeywords"] for e in json.loads(src.read_text(encoding="utf-8"))}
        want = [(g["name"], s["name"], texts[s["index"]]) for g in json.loads(sel.read_text(encoding="utf-8"))["groups"] for s in g["styles"]]
        have = [(g["name"], s["name"], s["text"]) for g in groups for s in g["styles"]
                if (g["name"], s["name"], s["text"]) not in own_styles]
        assert have == want
    else:
        print("  (source files not in data/styles: texts not compared)")


def look_checks(got):
    """Edit canvas and Sketch to image (plan B, 10.11.): styles.json is what tools/build_style_looks.py makes of
    tools/styles-looks.json; 11 tested styles of the pilot + 36 chosen by the user (10.11.), 3D only in Sketch to image."""
    from pccomfy import models
    sys.path.insert(0, str(ROOT / "tools"))
    import build_style_looks
    built = build_style_looks.build()
    data = json.loads((ROOT / "pccomfy" / "assets" / "styles.json").read_text(encoding="utf-8"))["modes"]
    assert {k: data[k] for k in ("edit", "sketch")} == built, "styles.json is behind tools/styles-looks.json: run tools/build_style_looks.py"
    src = json.loads((ROOT / "tools" / "styles-looks.json").read_text(encoding="utf-8"))["groups"]
    all_src = [s for g in src for s in g["styles"]]
    assert len(all_src) == 47 and sum(1 for s in all_src if s.get("tested")) == 11
    ed = {s["name"]: s["text"] for g in got["edit"] for s in g["styles"]}
    sk = {s["name"]: s["text"] for g in got["sketch"] for s in g["styles"]}
    assert len(ed) == 41 and len(sk) == 46, (len(ed), len(sk))
    three_d = {s["name"] for g in src if g["name"] == "3D & craft" for s in g["styles"]}
    assert len(three_d) == 6 and not three_d & set(ed) and three_d <= set(sk)      # 3D render 0/6 on photos (pilot)
    assert "Pencil gesture sketch" in ed and "Pencil gesture sketch" not in sk
    # the tested sentences stay word for word; every other text is look in its frame
    assert sk["Realistic photo"] == models.SKETCH_PHOTO and sk["Animated film"] == models.SKETCH_ILLUSTRATION
    mark = models.SKETCH_MARK
    assert all(t.count(mark) == 1 for t in sk.values()) and all(mark not in t for t in ed.values())
    for s in all_src:
        if "edit" in s["tabs"]:
            assert ed[s["name"]] == models.EDIT_FRAME.format(look=s["look"])
        if "sketch" in s["tabs"] and "fixed" not in s:
            assert sk[s["name"]] == models.SKETCH_FRAME.format(look=s["look"])
    # the same frames and looks as the style pilot (tests/live_style_round.py)
    pilot = (ROOT / "tests" / "live_style_round.py").read_text(encoding="utf-8")
    assert 'EDIT_FRAME = "' + models.EDIT_FRAME + '"' in pilot
    assert 'SKETCH_FRAME = "' + models.SKETCH_FRAME.replace(mark, "{subject}") + '"' in pilot
    assert all(len(g["styles"]) <= 25 for m in ("edit", "sketch") for g in got[m])
    assert all(len(n) <= 40 for n in list(ed) + list(sk))


def loader_checks():
    d = Path(tempfile.mkdtemp())

    def write(obj, name="s.json"):
        p = d / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
        return p
    assert styles.load(d / "missing.json") == {}
    assert styles.load(write("{not json")) == {}
    assert styles.load(write({"modes": []})) == {}
    assert styles.load(write({"x": 1})) == {}
    ok = styles.load(write({"modes": {
        "txt2img": {"groups": [{"name": "A", "styles": [{"name": "one", "text": "t1"}, {"name": "", "text": "x"}, {"name": "bad"}, 5]},
                               {"name": "empty", "styles": []}, {"name": " ", "styles": [{"name": "n", "text": "t"}]}]},
        "edit": {"groups": [{"name": "B", "styles": [{"name": "two", "text": "t2"}]}]},
        "broken": 7}}))
    assert ok == {"txt2img": [{"name": "A", "styles": [{"name": "one", "text": "t1"}]}],
                  "edit": [{"name": "B", "styles": [{"name": "two", "text": "t2"}]}]}, ok


def icon_checks():
    assert "palette" in icons.SHAPES
    im = icons.render("palette", "#ffffff", 40)
    assert im.size == (40, 40) and im.getchannel("A").getextrema()[1] == 255


def gui_checks():
    app = ra.make()
    assert set(app.m_styles) == {k for k, _l in gui_common.MODE_LABELS} | {"txt2img", "edit", "sketch"} and len(app._style_texts) == 84 + 7 + 41 + 46
    assert str(app.b_styles.cget("text")) == "Styles"           # "Styles" beside the palette (user 10.11.)
    # the button: only in Text to image, Edit canvas and Sketch to image
    ra.go(app, "flux3", "txt2img")
    app._on_mode_ui()
    assert app._styles_shown
    ra.go(app, "flux3", "multi_edit")
    app._on_mode_ui()
    assert app._styles_shown                        # every function has the button since 11.11. (Custom prompts); was: not in Multi image edit
    ra.go(app, "flux3", "edit")
    app._on_mode_ui()
    assert app._styles_shown
    ra.go(app, "flux3", "txt2img")
    app._on_mode_ui()
    assert app._styles_shown
    # an entry is added after a line break (an empty field just gets the style; one undo step in a real Tk)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red bicycle")
    first = styles.load()["txt2img"][0]["styles"][0]["text"]
    app._apply_style(first)
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle\n" + first
    assert "Ctrl+Z" in app.v_status.get()
    # a field that is switched off is left alone
    app.t_prompt.configure(state="disabled")
    app._apply_style("other")
    app.t_prompt.configure(state="normal")
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle\n" + first
    # the hover box: the whole text of an entry by (menu, number); nothing for a group entry or "none"
    key, text = next(iter(app._style_texts.items()))
    menu = type("M", (), {"__str__": lambda s: key[0]})()
    assert app._style_text_at(menu, key[1]) == text and text in {t for g in styles.load()["txt2img"] for t in [s["text"] for s in g["styles"]]}
    assert app._style_text_at(menu, "none") == "" and app._style_text_at(menu, None) == "" and app._style_text_at(menu, 999) == ""
    sketch_checks(app)
    edit_checks(app)


def edit_checks(app):
    """Edit canvas (plan B, 10.11.): Styles sets the whole sentence and is remembered, but opening the tab leaves the field as
    it was (user 10.11.), and an empty field still runs as before (no style message)."""
    from pccomfy import config as cfgmod, models
    text = lambda: app.t_prompt.get("1.0", "end").strip()
    st = {s["name"]: s["text"] for g in styles.load()["edit"] for s in g["styles"]}
    ra.go(app, "flux2", "edit")
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "make it winter")
    app._apply_style(st["Watercolor"], "Watercolor")
    assert text() == st["Watercolor"] and cfgmod.get_setting("style_edit") == "Watercolor"
    app._apply_style(st["Gouache"], "Gouache")
    assert text() == st["Gouache"]
    ra.go(app, "flux2", "txt2img")
    app.t_prompt.delete("1.0", "end")
    ra.go(app, "flux2", "edit")
    assert text() == ""                                         # not filled on opening
    app._prompt_placeholder()
    assert app._ph.cget("text") == "Prompt"
    app.v_status.set("")
    app.generate()
    assert app.v_status.get() != models.NO_STYLE
    cfgmod.set_setting("style_edit", "")


def sketch_checks(app):
    """Sketch to image (plan B, 10.11.): Styles sets the whole sentence, keeps what was typed for <WHAT IT SHOWS>, and is
    remembered; without a style the field stays empty and a run stops with a message."""
    from pccomfy import config as cfgmod, models
    mark = models.SKETCH_MARK
    cfgmod.set_setting("style_sketch", "")
    text = lambda: app.t_prompt.get("1.0", "end").strip()
    ra.go(app, "flux2", "sketch")
    assert text().startswith("a red bicycle")                  # your own text stays when the tab opens
    app.t_prompt.delete("1.0", "end")
    ra.go(app, "flux2", "txt2img")
    ra.go(app, "flux2", "sketch")
    app._on_mode_ui()
    assert app._styles_shown
    assert text() == ""                                         # no style chosen yet: empty, the grey placeholder
    app._prompt_placeholder()
    assert app._ph.cget("text") == models.SKETCH_PLACEHOLDER
    app.generate()
    assert app.v_status.get() == models.NO_STYLE                # no run without a style or text (decision 7)
    app._apply_style(models.SKETCH_PHOTO, "Realistic photo")
    assert text() == models.SKETCH_PHOTO and cfgmod.get_setting("style_sketch") == "Realistic photo"
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", models.SKETCH_PHOTO.replace(mark, "a red barn"))
    app._apply_style(models.SKETCH_ILLUSTRATION, "Animated film")          # the subject goes along (decision 8)
    assert text() == models.SKETCH_ILLUSTRATION.replace(mark, "a red barn")
    # the style chosen last comes back when the tab opens with an empty field (decision 7)
    ra.go(app, "flux2", "txt2img")
    app.t_prompt.delete("1.0", "end")
    ra.go(app, "flux2", "sketch")
    assert text() == models.SKETCH_ILLUSTRATION
    app._prompt_placeholder()
    assert app._ph.cget("text") == models.SKETCH_PLACEHOLDER        # the word follows the tab ("Prompt" elsewhere)
    ra.go(app, "flux2", "txt2img")
    app._prompt_placeholder()
    assert app._ph.cget("text") == "Prompt"
    cfgmod.set_setting("style_sketch", "")


def main():
    data_checks()
    loader_checks()
    icon_checks()
    gui_checks()
    print("ALL OK (styles)")


if __name__ == "__main__":
    main()
