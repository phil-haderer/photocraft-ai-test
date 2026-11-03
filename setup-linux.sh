#!/usr/bin/env bash
# Sets up the bridge on Linux (Linux counterpart of setup-windows.bat): finds a Python 3.11+ with tkinter and venv, makes
# .venv, installs the packages and writes the menu entry "PhotoCraft AI". It never installs system packages: when
# something is missing it prints the command for your distribution and stops.
#
#   ./setup-linux.sh [--no-menu]
#
# Environment: PYTHON (interpreter to use), VENV_DIR (default: .venv next to this script)
# Use the Python of your distribution (python3-tk), not one from uv or pyenv: only its Tk draws the Inter font.

PACKAGES="pillow numpy websocket-client tkinterdnd2"

# Command that installs Python with tkinter and venv. $1 = ID, $2 = ID_LIKE of /etc/os-release.
install_hint() {
    case " $1 $2 " in
        *" debian "*|*" ubuntu "*) echo "sudo apt install python3 python3-tk python3-venv" ;;
        *" fedora "*|*" rhel "*|*" centos "*) echo "sudo dnf install python3 python3-tkinter" ;;
        *" arch "*) echo "sudo pacman -S python tk" ;;
        *" suse "*|*" opensuse "*|*" opensuse-leap "*|*" opensuse-tumbleweed "*) echo "sudo zypper install python3 python3-tk" ;;
        *" alpine "*) echo "sudo apk add python3 py3-tkinter" ;;
        *) echo "" ;;
    esac
}

# Command for the clipboard helpers. $1 = ID, $2 = ID_LIKE.
clipboard_hint() {
    case " $1 $2 " in
        *" debian "*|*" ubuntu "*) echo "sudo apt install wl-clipboard xclip" ;;
        *" fedora "*|*" rhel "*|*" centos "*) echo "sudo dnf install wl-clipboard xclip" ;;
        *" arch "*) echo "sudo pacman -S wl-clipboard xclip" ;;
        *" suse "*|*" opensuse "*|*" opensuse-leap "*|*" opensuse-tumbleweed "*) echo "sudo zypper install wl-clipboard xclip" ;;
        *" alpine "*) echo "sudo apk add wl-clipboard xclip" ;;
        *) echo "" ;;
    esac
}

# Prints the first interpreter that is Python 3.11+ with tkinter, venv and ensurepip; nothing if there is none.
pick_python() {
    local c
    for c in "${PYTHON:-}" python3.13 python3.12 python3.11 python3 python; do
        [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 || continue
        if "$c" -c 'import sys, tkinter, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
            command -v "$c"
            return 0
        fi
    done
    return 1
}

# What is missing in python3 (for the message).
diagnose() {
    local c=python3
    command -v "$c" >/dev/null 2>&1 || { echo "python3 is not installed."; return; }
    "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || echo "python3 is older than 3.11."
    "$c" -c 'import tkinter' 2>/dev/null || echo "python3 has no tkinter."
    "$c" -c 'import venv, ensurepip' 2>/dev/null || echo "python3 has no venv/ensurepip."
}

main() {
    local menu=1 here py venv os_id os_like hint
    [ "$1" = "--no-menu" ] && menu=0
    here="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)" || exit 1
    cd "$here" || exit 1
    venv="${VENV_DIR:-$here/.venv}"
    os_id="" os_like=""
    if [ -r /etc/os-release ]; then
        os_id="$(. /etc/os-release; echo "${ID:-}")"
        os_like="$(. /etc/os-release; echo "${ID_LIKE:-}")"
    fi

    if ! py="$(pick_python)"; then
        echo "No Python 3.11+ with tkinter and venv found."
        diagnose
        hint="$(install_hint "$os_id" "$os_like")"
        if [ -n "$hint" ]; then echo "Install it with:  $hint"; else echo "Install Python 3.11+ with tkinter and venv from your distribution, then run this again."; fi
        exit 1
    fi
    echo "Using Python: $py"
    case "$(readlink -f "$py")" in
        /usr/*|/bin/*) ;;
        *) echo "Note: this is not the distribution's Python. Tk without Xft draws no Inter font (the window still works)." ;;
    esac

    [ -x "$venv/bin/python" ] || "$py" -m venv "$venv" || { echo "Could not create $venv"; exit 1; }
    if ! "$venv/bin/python" -c 'import tkinter' >/dev/null 2>&1; then
        echo "The virtual environment has no tkinter. Remove $venv and run this again."
        exit 1
    fi
    "$venv/bin/python" -m pip install $PACKAGES || { echo "pip install failed. Check the messages above."; exit 1; }

    if ! command -v wl-paste >/dev/null 2>&1 && ! command -v xclip >/dev/null 2>&1; then
        hint="$(clipboard_hint "$os_id" "$os_like")"
        echo
        echo "Optional: pasting pictures from the clipboard needs wl-clipboard (Wayland) or xclip (X11)."
        [ -n "$hint" ] && echo "  $hint"
    fi

    if [ "$menu" = 1 ]; then
        echo
        echo "Creating the menu entry \"PhotoCraft AI\" ..."
        if ! "$venv/bin/python" -m pccomfy shortcut; then
            echo "No menu entry yet. Make it later with:  $venv/bin/python -m pccomfy shortcut --photocraft <path to the photocraft binary>"
            menu=0
        fi
    fi
    echo
    echo "One ComfyUI custom node pack is needed: ComfyUI-KJNodes (Flux 3 Upscale uses its Color Match node)."
    echo "Install it from the ComfyUI Manager or from https://github.com/kijai/ComfyUI-KJNodes . If you have it already, do nothing."
    echo
    if [ "$menu" = 1 ]; then
        echo "Setup done. Start PhotoCraft from the application menu (\"PhotoCraft AI\") or with ./photocraft-ai.sh"
    else
        echo "Setup done. Start PhotoCraft with ./photocraft-ai.sh (set PHOTOCRAFT if the photocraft binary is not found)."
    fi
}

# Run main only when the file is executed, not when a test sources it.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
