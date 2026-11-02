#!/usr/bin/env bash
# Starts PhotoCraft with the control channel for the ComfyUI bridge, then opens the bridge window (Linux counterpart of
# the Windows shortcut). Close PhotoCraft first if it is already running without --control.
# Environment: PHOTOCRAFT (path to the photocraft binary; else it is searched), PYTHON (interpreter if there is no .venv)
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
else
    PY="${PYTHON:-python3}"
fi
exec "$PY" photocraft-ai.pyw "$@"
