"""
Tests for the macOS paste behavior in text_inserter.

The diff added platform-aware paste: Cmd+V on macOS, Ctrl+V elsewhere. The
chosen key is frozen at import time in `_PASTE_KEY`, so we reimport the module
under a patched `sys.platform` to verify both branches.
"""

import importlib
import sys

import pytest

import text_inserter
from pynput.keyboard import Key


class _RecordingController:
    """Records press/release/type calls, regardless of real-vs-stub pynput."""

    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))

    def type(self, text):
        self.events.append(("type", text))


def _reload_under_platform(monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    return importlib.reload(text_inserter)


@pytest.fixture(autouse=True)
def _restore_module():
    # Ensure other tests/modules see the module in its native state afterwards.
    yield
    importlib.reload(text_inserter)


def test_paste_key_is_cmd_on_macos(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "darwin")
    assert mod._PASTE_KEY is Key.cmd


def test_paste_key_is_ctrl_on_linux(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "linux")
    assert mod._PASTE_KEY is Key.ctrl


def test_paste_key_is_ctrl_on_windows(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "win32")
    assert mod._PASTE_KEY is Key.ctrl


def test_clipboard_paste_uses_cmd_on_macos(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "darwin")
    inserter = mod.TextInserter(typing_delay=0)
    inserter.keyboard = _RecordingController()

    inserter.insert_with_shortcut("hello", use_ctrl_v=True)

    events = inserter.keyboard.events
    # Cmd pressed, then 'v' pressed+released, then Cmd released.
    assert ("press", Key.cmd) in events
    assert ("press", "v") in events
    assert ("release", "v") in events
    assert ("release", Key.cmd) in events
    # Ctrl must NOT be involved on macOS.
    assert all(key is not Key.ctrl for _, key in events)


def test_clipboard_paste_copies_text_and_restores_clipboard(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "darwin")
    import pyperclip

    pyperclip.copy("original-clipboard")
    inserter = mod.TextInserter(typing_delay=0)

    inserter.insert_with_shortcut("  transcribed text  ", use_ctrl_v=True)

    # The original clipboard contents are restored after pasting.
    assert pyperclip.paste() == "original-clipboard"


def test_empty_text_is_a_noop(monkeypatch):
    mod = _reload_under_platform(monkeypatch, "darwin")
    inserter = mod.TextInserter(typing_delay=0)
    inserter.keyboard = _RecordingController()
    inserter.insert_with_shortcut("   ", use_ctrl_v=True)
    assert inserter.keyboard.events == []
