"""The model files and their links live in pccomfy/models.json (user 7.11.), read by manifest.py at start.

    python tests/test_models_json.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import manifest  # noqa: E402


def bad(doc, text):
    """load_files must refuse this document with a message holding ``text``."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.json"
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
        try:
            manifest.load_files(p)
        except ValueError as e:
            assert text in str(e), (text, str(e))
            return
        raise AssertionError("accepted: " + str(doc)[:80])


def main():
    assert manifest.MODELS_JSON.is_file() and manifest.MODELS_JSON.parent == ROOT / "pccomfy"
    files = manifest.load_files()
    assert files == manifest._LIST and len(files) == len(manifest.FILES) == 33, len(files)      # + the three MiniMax H3 Image files (PLAN 2.0b)
    for f in files:
        assert f.kind in manifest.KINDS, f
        assert f.url == "" or f.url.startswith("https://"), f
        assert f.sha256 == "" or (len(f.sha256) == 64 and set(f.sha256) <= set("0123456789abcdef")), f
        assert f.size >= 0
    # the entries the rest of the plugin counts on
    m = manifest.FILES["moss_image_sft_int8_convrot.safetensors"]
    assert m.kind == "unet" and m.size == 5413698958 and "Comfy-Org/MOSS-Image" in m.url and m.sha256.startswith("b4d1475b")
    assert manifest.FILES["seedvr2_ema_vae_fp16.safetensors"].aliases == ("ema_vae_fp16.safetensors",)
    assert "Moss\\lora_dmd2.safetensors" in manifest.FILES      # the sub-folder spelling of a LoRA survives the JSON
    # every file a tab names is in the list
    for key, t in manifest.TABS.items():
        names = set(t.required) | set(t.optional)
        for ms in t.modes.values():
            names |= set(ms.requires) | set(ms.optional)
        assert names <= set(manifest.FILES), (key, names - set(manifest.FILES))
    # a broken file stops the start with a message
    bad("{not json", "cannot read")
    bad({"files": [{"name": "a.safetensors", "kind": "nope"}]}, "kind must be")
    bad({"files": [{"kind": "unet"}]}, "needs a name")
    bad({"files": [{"name": "a", "kind": "unet", "urll": "x"}]}, "unknown field")
    bad({"files": [{"name": "a", "kind": "unet", "size": "5"}]}, "size must be")
    bad({"files": [{"name": "a", "kind": "unet"}, {"name": "a", "kind": "vae"}]}, "twice")
    # "comment" is allowed and ignored
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.json"
        p.write_text(json.dumps({"files": [{"name": "a", "kind": "vae", "comment": "for the reader"}]}), encoding="utf-8")
        assert manifest.load_files(p) == [manifest.File("a", "vae")]
    print("test_models_json: ok")


if __name__ == "__main__":
    main()
