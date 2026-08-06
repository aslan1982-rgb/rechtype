"""Tests for native hotkey parsing and toggle behavior."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from voiceflow.hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, VK_SPACE, parse_hotkey
from voiceflow.main import RechTypeApp
from voiceflow.overlay import format_recording_time


def test_parse_ctrl_space():
    spec = parse_hotkey("Ctrl + Space")

    assert spec.modifiers == MOD_CONTROL
    assert spec.virtual_key == VK_SPACE
    assert spec.canonical == "ctrl+space"


@pytest.mark.parametrize(
    ("value", "modifiers", "virtual_key"),
    [
        ("alt+f2", MOD_ALT, 0x71),
        ("ctrl+shift+k", MOD_CONTROL | MOD_SHIFT, ord("K")),
        ("control+7", MOD_CONTROL, ord("7")),
    ],
)
def test_parse_supported_combinations(value, modifiers, virtual_key):
    spec = parse_hotkey(value)
    assert spec.modifiers == modifiers
    assert spec.virtual_key == virtual_key


@pytest.mark.parametrize("value", ["", "space", "ctrl", "ctrl+space+k", "ctrl+escape"])
def test_reject_invalid_combinations(value):
    with pytest.raises(ValueError):
        parse_hotkey(value)


def test_first_toggle_starts_recording():
    app = SimpleNamespace(
        _processing=False,
        _recording=False,
        _start_recording=Mock(),
        _stop_recording=Mock(),
    )

    RechTypeApp._toggle_recording(app)

    app._start_recording.assert_called_once_with()
    app._stop_recording.assert_not_called()


def test_second_toggle_stops_recording():
    app = SimpleNamespace(
        _processing=False,
        _recording=True,
        _start_recording=Mock(),
        _stop_recording=Mock(),
    )

    RechTypeApp._toggle_recording(app)

    app._stop_recording.assert_called_once_with()
    app._start_recording.assert_not_called()


@pytest.mark.parametrize(
    ("seconds", "formatted"),
    [(0, "00:00"), (9.9, "00:09"), (59, "00:59"), (60, "01:00"), (3605, "60:05")],
)
def test_format_recording_time(seconds, formatted):
    assert format_recording_time(seconds) == formatted
