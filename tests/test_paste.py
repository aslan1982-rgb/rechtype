"""Regression tests for Windows text injection."""

import ctypes

import pytest

from voiceflow import paste


def test_input_structure_matches_windows_abi():
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(paste.INPUT) == expected_size


def test_paste_text_sends_utf16_key_down_and_key_up(monkeypatch):
    calls = []

    def fake_send_input(count, event_array, input_size):
        calls.append(
            (
                count,
                input_size,
                [
                    (event_array[index].ki.wScan, event_array[index].ki.dwFlags)
                    for index in range(count)
                ],
            )
        )
        return count

    monkeypatch.setattr(paste, "_SendInput", fake_send_input)

    sent = paste.paste_text("Я😀")

    # Я is one UTF-16 unit; the emoji is a surrogate pair. Each unit gets
    # a key-down and key-up event.
    assert sent == 6
    assert calls[0][0] == 6
    assert calls[0][1] == ctypes.sizeof(paste.INPUT)
    assert calls[0][2] == [
        (0x042F, paste.KEYEVENTF_UNICODE),
        (0x042F, paste.KEYEVENTF_UNICODE | paste.KEYEVENTF_KEYUP),
        (0xD83D, paste.KEYEVENTF_UNICODE),
        (0xD83D, paste.KEYEVENTF_UNICODE | paste.KEYEVENTF_KEYUP),
        (0xDE00, paste.KEYEVENTF_UNICODE),
        (0xDE00, paste.KEYEVENTF_UNICODE | paste.KEYEVENTF_KEYUP),
    ]


def test_paste_text_raises_when_windows_rejects_input(monkeypatch):
    monkeypatch.setattr(paste, "_SendInput", lambda *_args: 0)

    with pytest.raises(OSError, match="SendInput sent 0 of 2 events"):
        paste.paste_text("я")


def test_paste_text_accepts_empty_string_without_calling_windows(monkeypatch):
    monkeypatch.setattr(
        paste,
        "_SendInput",
        lambda *_args: pytest.fail("SendInput must not be called"),
    )

    assert paste.paste_text("") == 0
