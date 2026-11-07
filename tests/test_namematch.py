"""The "similar name" hint under a missing model file (pccomfy/namematch.py, user 7.11.): same model in another precision or spelling is
suggested; another size or generation, and the other files the plugin knows, are not.

    python tests/test_namematch.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402,F401  (installs the Tk stub and a temporary PCCOMFY_HOME)
from pccomfy import manifest, namematch as nm, ui_settings  # noqa: E402

Q8 = "qwen3vl_8b_int8_convrot.safetensors"


def main():
    # scores: other precision / spelling high, other size or generation capped, unrelated low
    assert nm.confidence(Q8, "qwen3vl_8b_fp8.safetensors") >= 0.94
    assert nm.confidence(Q8, "Qwen3VL-8B-bf16.safetensors") >= 0.94
    assert nm.confidence(Q8, "qwen3vl_4b_int8_convrot.safetensors") <= nm.CONFLICT_CAP
    assert nm.confidence("qwen2_8b.safetensors", "qwen3_8b.safetensors") <= nm.CONFLICT_CAP
    assert nm.confidence("flux2-vae.safetensors", "flux2_vae.safetensors") == 1.0       # only separators differ
    assert nm.confidence("krea2_turbo_int8_convrot.safetensors", "flux3-image-klein-int8-convrot.safetensors") < nm.SUGGEST_MIN
    assert nm.confidence("a\\b\\x_fp8.safetensors", "x.safetensors") >= 0.94              # the folder does not count
    assert nm.family_tokens("model q4 k m") == ["model"] and nm.family_tokens("flux1 dev fp8 e4m3fn") == ["flux1", "dev"]
    # suggest: the best at or over the minimum, "" otherwise
    cands = ["qwen3vl_4b_int8_convrot.safetensors", "qwen3vl_8b_fp8.safetensors", "other.safetensors"]
    assert nm.suggest(Q8, cands) == "qwen3vl_8b_fp8.safetensors"
    assert nm.suggest(Q8, ["qwen3vl_4b_int8_convrot.safetensors", "other.safetensors"]) == ""
    assert nm.suggest(Q8, []) == ""
    # files the plugin knows are no stand-ins: flux2-vae_small is its own file, not a copy of flux2-vae
    assert nm.suggest("flux2-vae.safetensors", ["flux2-vae_small.safetensors"], exclude=["flux2-vae_small.safetensors"]) == ""
    known = "qwen3.5_9b_int8_convrot.safetensors"      # same family as the w4a8 file, but another manifest file
    assert nm.suggest("qwen3.5_9b_w4a8_gptq.safetensors", [known], exclude=[known]) == ""
    assert nm.suggest("qwen3.5_9b_w4a8_gptq.safetensors", [known]) == known
    # in the settings window: under a missing file, only when there is no renamed copy; nothing when the file is found
    class Stub(ui_settings.SettingsMixin):
        def __init__(self, lists):
            self.inv = type("Inv", (), {"lists": lists})()
            self.models_dir = lambda ask=False: None
            self._dl, self._dl_restart, self.dl_log = {}, set(), []

    f = manifest.FILES["moss_image_sft_int8_convrot.safetensors"]
    st = Stub({"unet": ["moss_image_sft_fp8.safetensors", "qwen_image_2.1_int8_convrot.safetensors"]})
    assert st._similar_file(f) == "moss_image_sft_fp8.safetensors", st._similar_file(f)
    # a file of the plugin's own list never stands in (qwen_image_2.1_int8 is the Qwen model, however alike the names)
    assert Stub({"unet": ["qwen_image_2.1_int8_convrot.safetensors"]})._similar_file(f) == ""
    assert Stub({"unet": []})._similar_file(f) == ""
    data = st._file_data(f, None, "required")
    assert data["similar"] == "moss_image_sft_fp8.safetensors" and data["probable"] == "", data
    assert st._file_data(f, "moss_image_sft_int8_convrot.safetensors", "required")["similar"] == ""      # found: no hint
    assert (Path(__file__).resolve().parent.parent / "pccomfy" / "assets" / "LICENSE-model-linker.txt").is_file()
    assert any(n == "kianxyzw" for n, _w, _u in manifest.CONTRIBUTORS)
    print("test_namematch: ok")


if __name__ == "__main__":
    main()
