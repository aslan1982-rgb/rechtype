"""Clipboard-based fallback for applications that reject Unicode input."""

import ctypes
import time
from ctypes import wintypes

from voiceflow.paste import KEYEVENTF_KEYUP, _keyboard_input, _send_inputs


CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_OpenClipboard = _user32.OpenClipboard
_OpenClipboard.argtypes = [wintypes.HWND]
_OpenClipboard.restype = wintypes.BOOL

_EmptyClipboard = _user32.EmptyClipboard
_EmptyClipboard.argtypes = []
_EmptyClipboard.restype = wintypes.BOOL

_SetClipboardData = _user32.SetClipboardData
_SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_SetClipboardData.restype = wintypes.HANDLE

_CloseClipboard = _user32.CloseClipboard
_CloseClipboard.argtypes = []
_CloseClipboard.restype = wintypes.BOOL

_GlobalAlloc = _kernel32.GlobalAlloc
_GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_GlobalAlloc.restype = wintypes.HGLOBAL

_GlobalLock = _kernel32.GlobalLock
_GlobalLock.argtypes = [wintypes.HGLOBAL]
_GlobalLock.restype = wintypes.LPVOID

_GlobalUnlock = _kernel32.GlobalUnlock
_GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_GlobalUnlock.restype = wintypes.BOOL

_GlobalFree = _kernel32.GlobalFree
_GlobalFree.argtypes = [wintypes.HGLOBAL]
_GlobalFree.restype = wintypes.HGLOBAL


def _raise_last_error(message: str) -> None:
    error_code = ctypes.get_last_error()
    if error_code:
        raise ctypes.WinError(error_code, message)
    raise OSError(message)


def _open_clipboard_with_retry(attempts: int = 10, delay: float = 0.02) -> None:
    for _ in range(attempts):
        if _OpenClipboard(None):
            return
        time.sleep(delay)
    _raise_last_error("Could not open the Windows clipboard")


def set_clipboard_text(text: str) -> None:
    """Put Unicode text on the Windows clipboard using pointer-safe WinAPI calls."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    data = text.encode("utf-16-le") + b"\x00\x00"
    memory = _GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not memory:
        _raise_last_error("GlobalAlloc failed while preparing clipboard text")

    ownership_transferred = False
    try:
        pointer = _GlobalLock(memory)
        if not pointer:
            _raise_last_error("GlobalLock failed while preparing clipboard text")
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            _GlobalUnlock(memory)

        _open_clipboard_with_retry()
        try:
            if not _EmptyClipboard():
                _raise_last_error("EmptyClipboard failed")
            if not _SetClipboardData(CF_UNICODETEXT, memory):
                _raise_last_error("SetClipboardData failed")
            ownership_transferred = True
        finally:
            _CloseClipboard()
    finally:
        if not ownership_transferred:
            _GlobalFree(memory)


def paste_text_clipboard(text: str) -> int:
    """Copy *text* and inject Ctrl+V; return the number of key events sent."""
    set_clipboard_text(text)
    time.sleep(0.05)
    return _send_inputs(
        [
            _keyboard_input(virtual_key=VK_CONTROL),
            _keyboard_input(virtual_key=VK_V),
            _keyboard_input(virtual_key=VK_V, flags=KEYEVENTF_KEYUP),
            _keyboard_input(virtual_key=VK_CONTROL, flags=KEYEVENTF_KEYUP),
        ]
    )
