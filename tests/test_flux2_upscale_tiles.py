"""Flux 2 Upscale with the stage "Tiles", on at the start (user 10.11.; upscale stage round, docs/tests/upscale-stufen-ergebnis.md:
2 of 3 good with tiles, 0 of 3 without). Off, the graph is the one before; Refine keeps that graph as its own file.

    python tests/test_flux2_upscale_tiles.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import models, workflows  # noqa: E402

UP = ROOT / "workflows" / "flux2-klein-upscale.json"
REFINE = ROOT / "workflows" / "flux2-klein-refine.json"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_the_stage_and_its_start_value():
    info = workflows.stage_info(load(UP))
    assert [(s["label"], s["default_on"], s["auto_mp"], s["excludes"]) for s in info] == [("Tiles", True, 0.0, [])]
    assert "KJNodes" in info[0]["tip"]
    up = models.BY_KEY["flux2"].modes["upscale"]
    assert up.workflow == "flux2-klein-upscale.json" and up.stage_row and "stage_on" not in up.settings


def test_off_is_the_graph_before():
    g = workflows.bypass_stage(load(UP))
    for n in g.values():
        n.get("_meta", {}).pop("pc_stage_off", None)
    assert g == load(REFINE)                                   # Tiles off = the old graph = Refine's graph
    assert models.BY_KEY["flux2"].modes["refine"].workflow == "flux2-klein-refine.json"
    assert not workflows.stage_info(load(REFINE))              # Refine has no stage


def test_on_runs_tile_by_tile_and_matches_the_colours():
    g = load(UP)
    by = {k: n["class_type"] for k, n in g.items()}
    split = next(k for k, c in by.items() if c == "SplitImageToTileList")
    merge = next(k for k, c in by.items() if c == "ImageMergeTileList")
    cm = next(k for k, c in by.items() if c == "ColorMatch")
    enc = next(k for k, c in by.items() if c == "VAEEncode")
    dec = next(k for k, c in by.items() if c == "VAEDecode")
    out = next(k for k, n in g.items() if n["_meta"]["title"].startswith("pc:output"))
    scaled = next(k for k, n in g.items() if n["_meta"]["title"].startswith("pc:upscale"))
    assert g[split]["inputs"]["image"] == [scaled, 0] and g[enc]["inputs"]["pixels"] == [split, 0]
    assert g[merge]["inputs"]["image_list"] == [dec, 0] and g[cm]["inputs"]["image_target"] == [merge, 0]
    assert g[out]["inputs"]["images"] == [cm, 0]
    for cls in ("EmptyFlux2LatentImage", "Flux2Scheduler"):    # latent and scheduler at the size of one tile
        n = next(n for n in g.values() if n["class_type"] == cls)
        assert n["inputs"]["width"] == [g[split]["inputs"]["tile_width"][0], 1]
    links = [v for n in g.values() for v in n["inputs"].values() if isinstance(v, list) and len(v) == 2 and isinstance(v[1], int)]
    assert all(str(v[0]) in g for v in links)
    f3 = load(ROOT / "workflows" / "flux3-klein-upscale.json")       # the same tile rule as Flux 3 Upscale (about 1280 px + 128 overlap)
    assert g["170"]["inputs"]["expression"] == f3["170"]["inputs"]["expression"] and g["100"]["inputs"]["overlap"] == 128


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
