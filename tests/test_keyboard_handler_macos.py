"""
Tests for the macOS "cmd" modifier added to KeyboardHandler.

The diff registered a `"cmd"` modifier (mapped to the left/right Command keys)
so macOS users can bind Command-based shortcuts. We verify the mapping plus the
press/release state machine that fires the start/stop callbacks.
"""

import pytest

from pynput.keyboard import Key
from keyboard_handler import KeyboardHandler


class _CharKey:
    """Stand-in for a printable pynput key (has a `.char` attribute)."""

    def __init__(self, char):
        self.char = char


def test_cmd_modifier_maps_to_command_keys():
    assert "cmd" in KeyboardHandler.MODIFIER_KEYS
    assert KeyboardHandler.MODIFIER_KEYS["cmd"] == [Key.cmd_l, Key.cmd_r]


def test_cmd_handler_initializes_with_command_keys():
    handler = KeyboardHandler(modifier_key="cmd", trigger_key="r")
    assert handler.modifier_keys == [Key.cmd_l, Key.cmd_r]


def test_invalid_modifier_raises():
    with pytest.raises(ValueError):
        KeyboardHandler(modifier_key="hyper", trigger_key="r")


def test_cmd_r_press_and_release_fires_callbacks_once():
    started = []
    stopped = []
    handler = KeyboardHandler(
        modifier_key="cmd",
        trigger_key="r",
        on_start=lambda: started.append(True),
        on_stop=lambda: stopped.append(True),
    )

    # Press Cmd alone -> nothing happens yet.
    handler._on_key_press(Key.cmd_l)
    assert started == []

    # Press 'r' while Cmd held -> recording starts exactly once.
    handler._on_key_press(_CharKey("r"))
    assert started == [True]
    assert handler.is_recording is True

    # A redundant press must not re-trigger start.
    handler._on_key_press(_CharKey("r"))
    assert started == [True]

    # Release the trigger -> recording stops exactly once.
    handler._on_key_release(_CharKey("r"))
    assert stopped == [True]
    assert handler.is_recording is False


def test_releasing_modifier_stops_recording():
    stopped = []
    handler = KeyboardHandler(
        modifier_key="cmd",
        trigger_key="r",
        on_start=lambda: None,
        on_stop=lambda: stopped.append(True),
    )
    handler._on_key_press(Key.cmd_r)
    handler._on_key_press(_CharKey("r"))
    assert handler.is_recording is True

    handler._on_key_release(Key.cmd_r)
    assert stopped == [True]
    assert handler.is_recording is False


def test_trigger_key_is_case_insensitive():
    started = []
    handler = KeyboardHandler(
        modifier_key="cmd",
        trigger_key="r",
        on_start=lambda: started.append(True),
    )
    handler._on_key_press(Key.cmd_l)
    handler._on_key_press(_CharKey("R"))  # uppercase
    assert started == [True]


def test_darwin_intercept_swallows_trigger_key_press_and_release():
    """The combo's own keystroke must not leak to the frontmost app."""
    handler = KeyboardHandler(modifier_key="ctrl", trigger_key="w")

    handler._on_key_press(Key.ctrl_l)
    assert handler._darwin_intercept("keyDown", "ctrl-event") == "ctrl-event"

    handler._on_key_press(_CharKey("w"))
    assert handler._darwin_intercept("keyDown", "w-event") is None

    handler._on_key_release(_CharKey("w"))
    assert handler._darwin_intercept("keyUp", "w-event") is None

    handler._on_key_release(Key.ctrl_l)
    assert handler._darwin_intercept("keyUp", "ctrl-event") == "ctrl-event"


def test_darwin_intercept_passes_through_plain_typing():
    """Typing the trigger character without the modifier must not be eaten."""
    handler = KeyboardHandler(modifier_key="ctrl", trigger_key="w")

    handler._on_key_press(_CharKey("w"))
    assert handler._darwin_intercept("keyDown", "w-event") == "w-event"

    handler._on_key_release(_CharKey("w"))
    assert handler._darwin_intercept("keyUp", "w-event") == "w-event"


def test_darwin_intercept_swallows_release_even_if_modifier_lifted_first():
    """User can release the modifier before the trigger key; both keystrokes
    of the combo must still be suppressed."""
    handler = KeyboardHandler(modifier_key="ctrl", trigger_key="w")

    handler._on_key_press(Key.ctrl_l)
    handler._on_key_press(_CharKey("w"))
    assert handler._darwin_intercept("keyDown", "w-event") is None

    # Modifier released first, while trigger key is still held.
    handler._on_key_release(Key.ctrl_l)
    assert handler._darwin_intercept("keyUp", "ctrl-event") == "ctrl-event"

    handler._on_key_release(_CharKey("w"))
    assert handler._darwin_intercept("keyUp", "w-event") is None


def test_solo_key_maps_to_right_cmd():
    assert "right_cmd" in KeyboardHandler.SOLO_KEYS
    assert KeyboardHandler.SOLO_KEYS["right_cmd"] == Key.cmd_r


def test_solo_mode_activates_when_trigger_key_is_empty():
    handler = KeyboardHandler(modifier_key="right_cmd", trigger_key="")
    assert handler.solo_mode is True
    assert handler.solo_key == Key.cmd_r


def test_invalid_solo_key_raises():
    with pytest.raises(ValueError):
        KeyboardHandler(modifier_key="ctrl", trigger_key="")


def test_solo_mode_press_and_release_fires_callbacks_once():
    started = []
    stopped = []
    handler = KeyboardHandler(
        modifier_key="right_cmd",
        trigger_key="",
        on_start=lambda: started.append(True),
        on_stop=lambda: stopped.append(True),
    )

    handler._on_key_press(Key.cmd_r)
    assert started == [True]
    assert handler.is_recording is True

    # A redundant press must not re-trigger start.
    handler._on_key_press(Key.cmd_r)
    assert started == [True]

    handler._on_key_release(Key.cmd_r)
    assert stopped == [True]
    assert handler.is_recording is False


def test_solo_mode_ignores_other_keys():
    started = []
    handler = KeyboardHandler(
        modifier_key="right_cmd",
        trigger_key="",
        on_start=lambda: started.append(True),
    )

    # Left Cmd, or any other key, must not trigger the right-Cmd-only solo key.
    handler._on_key_press(Key.cmd_l)
    handler._on_key_press(_CharKey("c"))
    assert started == []
    assert handler.is_recording is False


def test_solo_mode_never_touches_suppression_state():
    """Solo mode has nothing to suppress — the darwin_intercept flag must
    stay untouched so start() can safely skip the blocking event tap."""
    handler = KeyboardHandler(modifier_key="right_cmd", trigger_key="")

    handler._on_key_press(Key.cmd_r)
    handler._on_key_release(Key.cmd_r)

    assert handler._suppress_current_event is False
    assert handler._darwin_intercept("keyDown", "event") == "event"
