"""
Tests for the pure-logic parts of visual_indicator.py worth unit testing.

WaveIndicator's canvas-drawing methods and FloatingPanelIndicator's
_tick_body/_apply_state_ui are wired directly to a live Tk canvas or real
NSPanel/NSTextField/NSView instances — testing them "for real" needs a live
windowing session, and mocking the full AppKit object graph would drift
silently from real AppKit behavior without meaningfully verifying the UI
works. So this file only covers the isolable pure math/logic: memory-usage
formatting and the get_indicator() factory dispatch.
"""

import sys

import visual_indicator


def test_process_memory_mb_darwin_reports_bytes(monkeypatch):
    monkeypatch.setattr(visual_indicator, "HAS_RESOURCE", True)
    monkeypatch.setattr(sys, "platform", "darwin")

    class _FakeUsage:
        ru_maxrss = 200 * 1024 * 1024  # 200 MB, in bytes as macOS reports

    monkeypatch.setattr(
        visual_indicator.resource, "getrusage", lambda who: _FakeUsage()
    )

    assert visual_indicator._process_memory_mb() == 200.0


def test_process_memory_mb_linux_reports_kilobytes(monkeypatch):
    monkeypatch.setattr(visual_indicator, "HAS_RESOURCE", True)
    monkeypatch.setattr(sys, "platform", "linux")

    class _FakeUsage:
        ru_maxrss = 200 * 1024  # 200 MB, in KB as Linux reports

    monkeypatch.setattr(
        visual_indicator.resource, "getrusage", lambda who: _FakeUsage()
    )

    assert visual_indicator._process_memory_mb() == 200.0


def test_process_memory_mb_returns_none_when_resource_unavailable(monkeypatch):
    monkeypatch.setattr(visual_indicator, "HAS_RESOURCE", False)

    assert visual_indicator._process_memory_mb() is None


def test_process_memory_mb_returns_none_on_exception(monkeypatch):
    monkeypatch.setattr(visual_indicator, "HAS_RESOURCE", True)

    def _raise(who):
        raise OSError("getrusage failed")

    monkeypatch.setattr(visual_indicator.resource, "getrusage", _raise)

    assert visual_indicator._process_memory_mb() is None


def _reset_indicator_singleton(monkeypatch):
    monkeypatch.setattr(visual_indicator, "_indicator", None)


def test_get_indicator_returns_floating_panel_on_darwin_with_appkit(monkeypatch):
    _reset_indicator_singleton(monkeypatch)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(visual_indicator, "HAS_APPKIT", True)

    indicator = visual_indicator.get_indicator()

    assert isinstance(indicator, visual_indicator.FloatingPanelIndicator)


def test_get_indicator_returns_wave_indicator_on_darwin_without_appkit(monkeypatch):
    _reset_indicator_singleton(monkeypatch)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(visual_indicator, "HAS_APPKIT", False)

    indicator = visual_indicator.get_indicator()

    assert isinstance(indicator, visual_indicator.WaveIndicator)


def test_get_indicator_returns_wave_indicator_on_linux(monkeypatch):
    _reset_indicator_singleton(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(visual_indicator, "HAS_APPKIT", True)  # shouldn't matter

    indicator = visual_indicator.get_indicator()

    assert isinstance(indicator, visual_indicator.WaveIndicator)


def test_get_indicator_is_a_singleton(monkeypatch):
    _reset_indicator_singleton(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")

    first = visual_indicator.get_indicator()
    second = visual_indicator.get_indicator()

    assert first is second
