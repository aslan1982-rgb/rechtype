"""Native Windows global hotkey support.

``RegisterHotKey`` consumes the registered combination before it reaches the
active application. ``MOD_NOREPEAT`` also prevents keyboard auto-repeat from
generating extra toggle events while the keys are held down.
"""

import ctypes
import threading
import traceback
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

VK_SPACE = 0x20
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
HOTKEY_ID = 0xB006


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: int
    virtual_key: int
    canonical: str


_MODIFIERS = {
    "ctrl": (MOD_CONTROL, "ctrl"),
    "control": (MOD_CONTROL, "ctrl"),
    "alt": (MOD_ALT, "alt"),
    "shift": (MOD_SHIFT, "shift"),
}

_NAMED_KEYS = {
    "space": VK_SPACE,
}


def parse_hotkey(value: str) -> HotkeySpec:
    """Parse combinations such as ``ctrl+space`` or ``alt+f2``."""
    if not isinstance(value, str):
        raise TypeError("hotkey must be a string")

    tokens = [token.strip().lower() for token in value.split("+") if token.strip()]
    if not tokens:
        raise ValueError("горячая клавиша не задана")

    modifiers = 0
    modifier_names: list[str] = []
    key_tokens: list[str] = []

    for token in tokens:
        modifier = _MODIFIERS.get(token)
        if modifier:
            bit, canonical_name = modifier
            if not modifiers & bit:
                modifiers |= bit
                modifier_names.append(canonical_name)
        else:
            key_tokens.append(token)

    if not modifiers:
        raise ValueError("добавьте Ctrl, Alt или Shift")
    if len(key_tokens) != 1:
        raise ValueError("укажите ровно одну основную клавишу")

    key_name = key_tokens[0]
    virtual_key = _NAMED_KEYS.get(key_name)
    if virtual_key is None and len(key_name) == 1 and key_name.isascii() and key_name.isalnum():
        virtual_key = ord(key_name.upper())
    if virtual_key is None and key_name.startswith("f") and key_name[1:].isdigit():
        function_number = int(key_name[1:])
        if 1 <= function_number <= 24:
            virtual_key = 0x70 + function_number - 1
    if virtual_key is None:
        raise ValueError(f"неподдерживаемая клавиша: {key_name}")

    canonical = "+".join([*modifier_names, key_name])
    return HotkeySpec(modifiers, virtual_key, canonical)


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_RegisterHotKey = _user32.RegisterHotKey
_RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_RegisterHotKey.restype = wintypes.BOOL

_UnregisterHotKey = _user32.UnregisterHotKey
_UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_UnregisterHotKey.restype = wintypes.BOOL

_GetMessageW = _user32.GetMessageW
_GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_GetMessageW.restype = wintypes.BOOL

_PeekMessageW = _user32.PeekMessageW
_PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
_PeekMessageW.restype = wintypes.BOOL

_PostThreadMessageW = _user32.PostThreadMessageW
_PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_PostThreadMessageW.restype = wintypes.BOOL

_GetCurrentThreadId = _kernel32.GetCurrentThreadId
_GetCurrentThreadId.argtypes = []
_GetCurrentThreadId.restype = wintypes.DWORD


class GlobalHotkeyListener(threading.Thread):
    """Receive one callback for each physical press of a registered hotkey."""

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        super().__init__(name="RechTypeHotkey", daemon=True)
        self.spec = parse_hotkey(hotkey)
        self.callback = callback
        self._ready = threading.Event()
        self._thread_id: int | None = None
        self._registration_error: BaseException | None = None

    def start_and_wait(self, timeout: float = 3.0) -> "GlobalHotkeyListener":
        self.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Windows не ответила при регистрации горячей клавиши")
        if self._registration_error is not None:
            raise self._registration_error
        return self

    def run(self) -> None:
        self._thread_id = _GetCurrentThreadId()
        message = wintypes.MSG()
        # Force creation of this thread's message queue before another thread
        # can request shutdown through PostThreadMessageW.
        _PeekMessageW(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)

        modifiers = self.spec.modifiers | MOD_NOREPEAT
        if not _RegisterHotKey(None, HOTKEY_ID, modifiers, self.spec.virtual_key):
            error_code = ctypes.get_last_error()
            self._registration_error = ctypes.WinError(
                error_code,
                f"Не удалось зарегистрировать {self.spec.canonical}. "
                "Возможно, сочетание занято другой программой",
            )
            self._ready.set()
            return

        self._ready.set()
        try:
            while True:
                result = _GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error(), "GetMessageW failed")
                if result == 0:
                    break
                if message.message == WM_HOTKEY and message.wParam == HOTKEY_ID:
                    try:
                        self.callback()
                    except Exception:
                        traceback.print_exc()
        finally:
            _UnregisterHotKey(None, HOTKEY_ID)

    def stop(self, timeout: float = 3.0) -> None:
        if self._thread_id is not None and self.is_alive():
            _PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self.join(timeout)
