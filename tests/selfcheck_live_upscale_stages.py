"""tests/live_upscale_stages.py (the upscale stage round cut to one hour, user 9.11.): 32 runs as planned, every graph's
links point at nodes, "today" is the plugin's own graph, and the stages are wired where they belong.
Retired from the standard run (10.11.: the round is finished; was tests/test_live_upscale_stages.py);
tests/run_all.py only collects test_*.py. Run by hand: python tests/selfcheck_live_upscale_stages.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import live_upscale_stages as lu  # noqa: E402
from pccomfy import workflows  # noqa: E402


def test_the_planned_runs():
    j = lu.jobs()
    assert len(j) == 32 and len(set(j)) == 32
    assert len(lu.jobs("F")) == 8 and {f for _, m, f, _ in lu.jobs("F")} == {3, 4} and {m for _, m, _, _ in lu.jobs("F")} == {"fibo"}
    assert len(lu.jobs("Q")) == 24 and {f for _, _, f, _ in lu.jobs("Q")} == {2}
    models_in_order = [m for _, m, _, _ in j]
    assert models_in_order == sorted(models_in_order, key=["fibo", "flux2", "qwen"].index)      # each model loaded once


def test_all_graphs_are_whole():
    for _, m, f, v in lu.jobs():
        g, out = lu.build(m, v, "x.png", f * f)
        assert not lu.links_ok(g), (m, v, lu.links_ok(g))
        assert out in g


def test_today_is_the_plugins_graph():
    for m in ("flux2", "qwen"):
        g, _ = lu.build(m, "today", "x.png", 4.0)
        assert not {"90", "100", "103"} & set(g), m
        plugin = workflows.bypass_stage(workflows.load_template(ROOT / "workflows" / lu.WF[m]))     # Flux 2: the graph before its Tiles stage (10.11.)
        assert {n["class_type"] for n in g.values()} == {n["class_type"] for n in plugin.values()}


def test_stages_are_wired():
    g, out = lu.build("flux2", "us_tiles", "x.png", 4.0)
    assert g["213"]["inputs"]["image"] == ["91", 0] and g[lu._of(g, "VAEEncode")]["inputs"]["pixels"] == ["100", 0]
    assert g[out]["inputs"]["images"] == ["103", 0]
    g, _ = lu.build("qwen", "us", "x.png", 4.0)
    assert g[lu._of(g, "TextEncodeQwenImage21")]["inputs"]["images.image_1"] == ["13", 0]       # with US it reads the big picture
    g, _ = lu.build("fibo", "tiles", "x.png", 9.0)
    assert lu.FIBO_US not in g and "100" in g                      # Fibo tiles alone: UltraSharp off
    g, _ = lu.build("fibo", "us_tiles", "x.png", 9.0)
    assert lu.FIBO_US in g and "100" in g


def test_rating_saved_only_for_result_pictures_and_summed_up():
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "03_father").mkdir()
        for stem in ("source", "flux2_2x_us", "flux2_2x_today"):
            Image.new("RGB", (4, 4)).save(run / "03_father" / f"{stem}.png")
        assert lu.save_rating(run, "03_father/flux2_2x_us", "gut") == {"03_father/flux2_2x_us": "gut"}
        lu.save_rating(run, "03_father/flux2_2x_today", "mittel")
        for bad in (("03_father/source", "gut"), ("03_father/flux2_2x_us", "super"), ("../x/flux2_2x_us", "gut"), ("03_father/nope", "gut")):
            try:
                lu.save_rating(run, *bad)
                raise AssertionError(bad)
            except ValueError:
                pass
        text = lu.summarize(run)
        assert "| flux2 | 2x | us | 1 | 0 | 0 | father |" in text and "| flux2 | 2x | today | 0 | 1 | 0 |" in text
        assert "Bewertet: 2 von 32" in text


def test_viewer_template_rating_is_optional():
    html = (ROOT / "tools" / "ab_viewer_template.html").read_text(encoding="utf-8")
    assert "window.RATE_CONF || null" in html and html.count("__SETS__") == 1   # the other viewers replace only __SETS__
    assert "<script>\nconst SETS" in html                                      # where the served page puts RATE_CONF


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
