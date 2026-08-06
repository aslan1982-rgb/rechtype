"""Unicode text input through the Windows ``SendInput`` API.

The ``INPUT`` structure must contain the complete WinAPI union.  Defining it
with ``KEYBDINPUT`` alone makes ``ctypes.sizeof(INPUT)`` 32 bytes on 64-bit
Windows, while WinAPI expects 40 bytes, and ``SendInput`` silently rejects the
whole request.
"""

import ctypes
from ctypes import wintypes
from typing import Iterable


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("value", _INPUT_UNION),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_SendInput = _user32.SendInput
_SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
_SendInput.restype = wintypes.UINT


def _keyboard_input(*, virtual_key: int = 0, scan_code: int = 0, flags: int = 0) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.ki = KEYBDINPUT(
        wVk=virtual_key,
        wScan=scan_code,
        dwFlags=flags,
        time=0,
        dwExtraInfo=0,
    )
    return event


def _utf16_code_units(text: str) -> Iterable[int]:
    """Yield UTF-16 code units, including surrogate pairs for non-BMP text."""
    encoded = text.encode("utf-16-le")
    for index in range(0, len(encoded), 2):
        yield int.from_bytes(encoded[index:index + 2], "little")


def _send_inputs(events: list[INPUT]) -> int:
    """Send all events or raise instead of reporting a false success."""
    if not events:
        return 0

    event_array = (INPUT * len(events))(*events)
    ctypes.set_last_error(0)
    sent = _SendInput(len(events), event_array, ctypes.sizeof(INPUT))
    if sent != len(events):
        error_code = ctypes.get_last_error()
        detail = (
            f"SendInput sent {sent} of {len(events)} events "
            f"(INPUT size: {ctypes.sizeof(INPUT)} bytes)"
        )
        if error_code:
            raise ctypes.WinError(error_code, detail)
        raise OSError(detail + "; Windows may be blocking input into an elevated application")
    return sent


def paste_text(text: str) -> int:
    """Type *text* as Unicode keystrokes and return the event count sent."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    events: list[INPUT] = []
    for code_unit in _utf16_code_units(text):
        events.append(_keyboard_input(scan_code=code_unit, flags=KEYEVENTF_UNICODE))
        events.append(
            _keyboard_input(
                scan_code=code_unit,
                flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            )
        )

    return _send_inputs(events)
