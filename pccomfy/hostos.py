"""Which system the plugin runs on: the one place every platform branch asks (PLAN.md 18c).

The Windows branches are the code that always ran; a Linux branch is added next to it, never in its place.
``tests/test_platform_pins.py`` pins what each system gets.
"""
from __future__ import annotations

import os
import sys

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")

# Tk window arguments. Windows gets none (the code that always ran). Elsewhere the window manager needs a WM_CLASS: Tk sets
# none that is usable and WSLg's Weston drops the window without it ("does not have appId").
ROOT_KW = {} if IS_WINDOWS else {"className": "pccomfy"}
TOP_KW = {} if IS_WINDOWS else {"class_": "Pccomfy"}
# The bottom-right resize grip: X11 has no "size_nw_se".
GRIP_CURSOR = "size_nw_se" if IS_WINDOWS else "bottom_right_corner"
