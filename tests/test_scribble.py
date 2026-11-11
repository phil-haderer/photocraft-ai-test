"""pccomfy/scribble.py: finding the scribble (own layer, green first, red; minimum size) and putting the result back only
there, exactly as the blind test rounds 5 to 7 did it in tests/live_sketch.py (docs/sketch-plan.md, 9.11. evening)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from pccomfy import imaging, scribble  # noqa: E402
try:
    import live_sketch as ls  # noqa: E402
except ImportError:          # tests/live_sketch.py stays in the private repo (it names the user's picture folders)
    if __name__ == "__main__":
        print("skipped: tests/live_sketch.py is only in the private working repo")
        sys.exit(0)
    raise

PHOTO = (90, 120, 80)


def _scribbled(colour=scribble.RED, size=(900, 600), at=(0.4, 0.5)):
    clean = Image.new("RGB", size, PHOTO)
    red = ls.draw_scribble(clean, "ball", at[0], at[1], 0.2, "outline", 3)
    return clean, (red if colour == scribble.RED else ls.recolour(red, clean, colour))


def _t(box):
    return (box.x, box.y, box.w, box.h)


def test_colour_search_as_in_the_test_rounds():
    clean, red = _scribbled()
    found = scribble.find_by_colour(red)
    assert found.how == "red" and _t(found.box) == ls.scribble_box(red)
    _, green = _scribbled(scribble.GREEN)
    found = scribble.find_by_colour(green)
    assert found.how == "green" and _t(found.box) == ls.scribble_box(green, colour=ls.SCRIBBLE_GREEN)
    assert scribble.find_by_colour(clean) is None


def test_green_wins_over_a_red_wall():
    """Round 7: on the red neon photo the wall is far larger than the green scribble; green still counts."""
    _, green = _scribbled(scribble.GREEN)
    d = ImageDraw.Draw(green)
    d.rectangle((0, 0, 899, 150), fill=scribble.RED)        # a red wall, much larger than the scribble
    found = scribble.find_by_colour(green)
    assert found.how == "green" and found.box.y > 150


def test_tiny_red_specks_are_no_scribble():
    """Clean photos had red specks of 107 and 314 pixels; a scribble needs MIN_SHARE of the picture."""
    im = Image.new("RGB", (1732, 1155), PHOTO)              # 2 MP: the minimum is about 1000 pixels
    ImageDraw.Draw(im).rectangle((600, 700, 617, 717), fill=scribble.RED)      # 324 pixels
    assert scribble.find_by_colour(im) is None
    ImageDraw.Draw(im).rectangle((600, 700, 650, 750), fill=scribble.RED)      # 2601 pixels
    assert scribble.find_by_colour(im).how == "red"


def test_a_thin_frame_round_an_area_is_a_scribble():
    """Writer round 10.11., picture 8: a 2 px red rectangle round a facade (481 pixels in 1.5 MP, the minimum is 762) was
    not found; a thin frame counts with half the pixels when its box covers 1 % of the picture. A speck still does not."""
    im = Image.new("RGB", (1543, 988), PHOTO)                # 1.5 MP: the minimum is 762 pixels
    ImageDraw.Draw(im).rectangle((230, 420, 400, 600), outline=scribble.RED, width=1)      # 684 pixels, box 3 %
    assert scribble.MIN_SHARE * im.width * im.height > 684
    found = scribble.find_by_colour(im)
    assert found and found.how == "red" and found.box.x < 230 and found.box.x + found.box.w > 400
    speck = Image.new("RGB", (1543, 988), PHOTO)
    ImageDraw.Draw(speck).rectangle((600, 700, 621, 721), fill=scribble.RED)  # 484 pixels, a small box
    assert scribble.find_by_colour(speck) is None


def _stroke_layer(size=(900, 600), colour=(30, 30, 220)):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((300, 200, 480, 380), outline=colour + (255,), width=6)
    d.line((300, 290, 480, 290), fill=colour + (255,), width=6)
    return layer


def test_scribble_layer_any_colour():
    layer = _stroke_layer()
    found = scribble.find_on_layer(layer)
    assert found and found.how == "layer"
    assert found.box.x < 300 and found.box.x + found.box.w > 480 and found.box.y < 200
    # a stray dot far away on the same layer does not stretch the box
    ImageDraw.Draw(layer).ellipse((850, 20, 856, 26), fill=(30, 30, 220, 255))
    assert scribble.find_on_layer(layer).box == found.box
    # the layer wins over red in the picture (a red car under it)
    pic = Image.new("RGB", layer.size, scribble.RED)
    assert scribble.find(pic, layer).how == "layer"


def test_a_plain_cut_out_is_no_scribble_layer():
    """One colour alone is not enough: a plain one-coloured shape cut out onto its own layer is solid, not thin."""
    cut = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    ImageDraw.Draw(cut).ellipse((300, 200, 480, 380), fill=(200, 200, 200, 255))
    assert not scribble.is_scribble_layer(cut)


def test_a_cut_out_or_a_photo_layer_is_no_scribble_layer():
    rng = np.random.default_rng(1)
    noise = Image.fromarray(rng.integers(0, 255, (600, 900, 3), dtype=np.uint8))
    cut = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    alpha = Image.new("L", (900, 600), 0)
    ImageDraw.Draw(alpha).ellipse((200, 100, 600, 500), fill=255)
    cut.paste(noise, (0, 0), alpha)                          # a cut-out: many colours
    assert not scribble.is_scribble_layer(cut)
    assert not scribble.is_scribble_layer(noise.convert("RGBA"))       # a photo layer covers the canvas
    assert not scribble.is_scribble_layer(Image.new("RGBA", (900, 600), (0, 0, 0, 0)))     # empty
    # without a scribble layer the colours of the picture decide
    _, red = _scribbled()
    assert scribble.find(red, cut).how == "red"
    assert scribble.find(Image.new("RGB", (900, 600), PHOTO), cut) is None


def test_put_back_as_round_7():
    """The layer and its mask equal what round 7 built (colour match in the ring, mask fading to the crop): outside the
    crop the photo stays pixel-identical."""
    clean, red = _scribbled()
    found = scribble.find_by_colour(red)
    reg = scribble.region(found, red.size)
    assert _t(reg) == _t(imaging.grow_box(found.box, red.size, ls.R5_CONTEXT))
    rng = np.random.default_rng(2)
    result = Image.fromarray(rng.integers(0, 255, (reg.h * 2, reg.w * 2, 3), dtype=np.uint8))
    layer, mask = scribble.put_back(red, result, found, reg)
    # the same steps as cmd_round7
    old = red.copy()
    old.paste(result.resize((reg.w, reg.h), Image.LANCZOS), (reg.x, reg.y))
    ring = ls.context_ring(red.size, reg, ls.scribble_mask(red.size, _t(found.box20)))
    want_layer = ls.colour_match(old, red, ring)
    want_mask = ls.fade_mask(red.size, _t(found.box), reg)
    assert np.array_equal(np.asarray(layer), np.asarray(want_layer))
    assert np.array_equal(np.asarray(mask), np.asarray(want_mask))
    out = Image.composite(layer, red, mask)
    assert ls.outside_diff(red, out, mask) == 0
    m = np.asarray(mask)
    assert m[found.box.y + 2, found.box.x + 2] == 255           # opaque over the box
    assert m[:reg.y].sum() == 0 and m[:, :reg.x].sum() == 0      # nothing outside the crop


def test_real_round6_scribbles_when_present():
    """On the user's round 6 photos (when the test data is on this PC): green found at the scribble on every one, also on
    the red neon wall; red found except on the neon wall (there it takes the wall). Slow (~15 s): only with
    PCCOMFY_SLOW_TESTS=1."""
    if os.environ.get("PCCOMFY_SLOW_TESTS") != "1":
        print("   (skipped: real round 6 photos only with PCCOMFY_SLOW_TESTS=1)")
        return
    if not ls.R6_DIR.is_dir():
        print("   (skipped: no round 6 photos on this PC)")
        return
    for s in ls.r6_items():
        green = ls.recolour(s["pic"], s["clean"])
        f = scribble.find_by_colour(green)
        assert f.how == "green" and ls.box_overlap(_t(f.box), s["box"]) > 0.9, s["desc"]
        assert scribble.find_by_colour(s["clean"]) is None or s["num"] == "1710980", s["desc"]
        # the same strokes on their own layer (ink colour, soft edges in alpha) are a scribble layer; an ellipse of the
        # photo cut out onto its own layer is not (the plain one of the container photo was, before the thinness rule)
        a, b = np.asarray(s["pic"].convert("RGB")).astype(float), np.asarray(s["clean"].convert("RGB")).astype(float)
        d = np.abs(a - b).sum(-1)
        ink = np.median(a[d > 120], axis=0)
        near = np.asarray(Image.fromarray(((d > 50) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
        alpha = np.clip(d / np.maximum(np.abs(ink - b).sum(-1), 1), 0, 1) * (near & (d > 25))
        alpha[d > 50] = 1
        rgba = np.dstack([np.broadcast_to(ink, a.shape), alpha * 255]).astype(np.uint8)
        f = scribble.find_on_layer(Image.fromarray(rgba, "RGBA"))
        assert f and ls.box_overlap(_t(f.box), s["box"]) > 0.9, s["desc"]
        x, y, w, h = s["box"]
        m = Image.new("L", s["clean"].size, 0)
        ImageDraw.Draw(m).ellipse((x, y, x + w, y + h), fill=255)
        cut = Image.new("RGBA", s["clean"].size, (0, 0, 0, 0))
        cut.paste(s["clean"], (0, 0), m)
        assert not scribble.is_scribble_layer(cut), s["desc"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
