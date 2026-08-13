"""TTY screen redraw helpers (Windows VT + ANSI)."""

from __future__ import annotations

import shutil
import sys

_CLEAR = "\x1b[2J\x1b[H"
_vt_enabled = False


def enable_windows_vt() -> None:
    """Turn on ANSI sequences in the Windows console. No-op elsewhere."""

    global _vt_enabled
    if _vt_enabled or sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        enable_virtual_terminal = 0x0004
        ctypes.windll.kernel32.SetConsoleMode(
            handle, mode.value | enable_virtual_terminal
        )
        _vt_enabled = True
    except (AttributeError, OSError):
        return


def terminal_columns() -> int:
    try:
        return max(72, shutil.get_terminal_size(fallback=(120, 30)).columns)
    except OSError:
        return 120


def render_screen(text: str) -> None:
    """Replace the visible terminal contents with ``text``."""

    enable_windows_vt()
    sys.stdout.write(_CLEAR)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
