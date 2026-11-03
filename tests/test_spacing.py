"""The gaps follow the interface scale (spacing.py): at the reference scale nothing changes, below it they shrink in the same
proportion as the text, a value marked Keep is never scaled again, zero stays zero and a gap never vanishes.

    python tests/test_spacing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pccomfy import spacing  # noqa: E402


def main():
    spacing._factor = 1.0                                   # the reference scale (Windows 175 %, plugin 100 %)
    assert spacing.scale(10) == 10 and spacing.scale((2, 6)) == (2, 6) and spacing.scale([8, 0]) == [8, 0]
    spacing._factor = 1.0 / spacing.REF                     # plugin scale 1.0: 57 % of the gaps
    assert spacing.scale(10) == 6 and spacing.scale((0, 6)) == (0, 3) and spacing.scale(1) == 1 and spacing.scale(0) == 0
    assert spacing.scale("2m") == "2m" and spacing.scale(spacing.Keep(7)) == 7 and isinstance(spacing.scale(spacing.Keep(7)), spacing.Keep)
    spacing._factor = 2.0                                   # a bigger window: bigger gaps
    assert spacing.scale(6) == 12 and spacing.scale((4, 0)) == (8, 0)
    print("ok")


if __name__ == "__main__":
    main()
