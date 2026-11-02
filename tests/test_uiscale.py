"""The Linux display scale (pccomfy/uiscale.py): parsing, the order of the sources, PhotoCraft's uiScale in an answer.

    python tests/test_uiscale.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import uiscale  # noqa: E402


class FakePC:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def call(self, method, params=None):
        assert method == "ui.inspect"
        if self.error:
            raise self.error
        return self.result


def main():
    p = uiscale.parse_scale
    assert p(1.5) == 1.5 and p("1.5") == 1.5 and p(150) == 1.5 and p("150") == 1.5 and p("150%") == 1.5 and p(" 200 ") == 2.0
    assert p(1) == 1.0 and p("0.75") == 0.75
    for bad in (None, "", "abc", True, 0, "0", 9.9 / 100, 500, "500%", -1):
        assert p(bad) is None, bad

    # PhotoCraft 0.19 (measured on Linux): ui.inspect has window.pixelsPerPoint; it wins over a uiScale
    assert uiscale.find_ui_scale({"window": {"height": 1384.0, "pixelsPerPoint": 1.5, "width": 2560.0}}) == 1.5
    assert uiscale.find_ui_scale({"window": {"pixelsPerPoint": 2.0}, "prefs": {"interface": {"uiScale": 150}}}) == 2.0
    assert uiscale.find_ui_scale({"window": {"pixelsPerPoint": 1.0}}) == 1.0
    assert uiscale.find_ui_scale({"window": {"pixelsPerPoint": "x"}, "prefs": {"uiScale": 125}}) == 1.25

    # PhotoCraft's answer: the key may sit anywhere
    assert uiscale.find_ui_scale({"prefs": {"interface": {"uiScale": 150}}}) == 1.5
    assert uiscale.find_ui_scale({"windows": [{"x": 1}], "prefs": [{"path": "interface.uiScale", "value": 200}]}) == 2.0
    assert uiscale.find_ui_scale({"interface.uiScale": "125"}) == 1.25
    assert uiscale.find_ui_scale({"interface": {"uiFontSize": "large"}}) is None
    assert uiscale.find_ui_scale(None) is None

    # Xft.dpi
    assert uiscale.xft_dpi("Xft.antialias:\t1\nXft.dpi:\t144\n") == 144.0
    assert uiscale.xft_dpi("") is None and uiscale.xft_dpi("Xft.dpi: abc") is None

    # the order: environment, config, PhotoCraft
    assert uiscale.pick_scale("2", 1.5, 1.25) == 2.0
    assert uiscale.pick_scale(None, 1.5, 1.25) == 1.5
    assert uiscale.pick_scale("junk", None, 150) == 1.5
    assert uiscale.pick_scale(None, None, None) is None

    # detect(): the explicit sources win; PhotoCraft not reachable is no error
    uiscale._read_xrdb = lambda: "Xft.dpi:\t192\n"
    pc = FakePC({"prefs": {"interface": {"uiScale": 150}}})
    assert uiscale.detect({"PCCOMFY_SCALE": "2"}, {}, pc, 96) == 2.0
    assert uiscale.detect({}, {"window": {"scale": 1.25}}, pc, 96) == 1.25
    assert uiscale.detect({}, {}, pc, 96) == 1.5
    down = FakePC(error=OSError("refused"))
    assert uiscale.detect({}, {}, down, 96) == 2.0          # Xft.dpi 192 against Tk's 96
    assert uiscale.detect({}, {}, down, 192) is None        # Tk already follows it
    uiscale._read_xrdb = lambda: ""
    assert uiscale.detect({}, {}, down, 96) is None

    assert abs(uiscale.tk_scaling(1.5) - 2.0) < 1e-9 and abs(uiscale.tk_scaling(1.0) - 96 / 72) < 1e-9
    print("uiscale ok")


if __name__ == "__main__":
    main()
