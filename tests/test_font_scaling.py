"""``font`` on Linux: untouched (points) until set_font_scaling gives a scaling, then pixel sizes (points x scaling), so the text
follows the interface scale there (a later ``tk scaling`` does not reach fonts in points on X11).

    python tests/test_font_scaling.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pccomfy import gui_common as gc  # noqa: E402


def main():
    gc.set_font_scaling(0.0)
    plain = gc.font(9)
    assert plain[1] > 0 and gc.font(9, bold=True)[1] == plain[1]
    gc.set_font_scaling(96 / 72)                    # the usual 100 %: 8 pt (Inter 9 - 1) = 10.67 px -> 11
    px = gc.font(9)
    assert px[1] == -11 if gc.FONT == "Inter" else px[1] == -12, px
    gc.set_font_scaling(2.3333)                     # 175 %
    big = gc.font(9)
    assert big[1] < px[1] and abs(big[1] / px[1] - 1.75) < 0.1, (px, big)
    assert gc.font(9, bold=True)[1] == big[1] and gc.font(1)[1] <= -5              # bold keeps the size; never tiny
    gc.set_font_scaling(0.0)
    assert gc.font(9) == plain
    print("ok")


if __name__ == "__main__":
    main()
