"""
Tests for TranscriptionApp's orchestration logic in main.py.

Real Config/AudioRecorder/Transcriber/KeyboardHandler are never constructed
here — they'd read a real config.yaml, touch real audio hardware, and load a
real Whisper model. Instead, a bare TranscriptionApp is built via
object.__new__() with plain Mock/stub collaborators, exercising only the
orchestration code in main.py itself.
"""

import os
import threading
import time

import numpy as np
import pytest
from unittest.mock import MagicMock

from main import TranscriptionApp


class _FakeConfig:
    def __init__(self, model, audio):
        self.model = model
        self.audio = audio


def make_app(
    *,
    text_insertion_method="direct",
    save_recordings=False,
    cleanup_temp_files=True,
    transcribe_side_effect=None,
    transcribe_return=("hello world", {}),
):
    """Build a TranscriptionApp with real orchestration logic but fully
    stubbed collaborators, bypassing __init__ (which would construct real
    AudioRecorder/Transcriber/KeyboardHandler instances)."""
    app = object.__new__(TranscriptionApp)

    app.config = _FakeConfig(
        model={"language": "en", "beam_size": 5},
        audio={"output_file": "test_audio.wav"},
    )
    app.app_config = {
        "save_recordings": save_recordings,
        "cleanup_temp_files": cleanup_temp_files,
        "verbose": False,
    }

    app.recorder = MagicMock()
    app.recorder.stop_recording.return_value = np.array([1, 2, 3], dtype=np.int16)
    app.recorder.stream_hung = False

    app.transcriber = MagicMock()
    if transcribe_side_effect is not None:
        app.transcriber.transcribe.side_effect = transcribe_side_effect
    else:
        app.transcriber.transcribe.return_value = transcribe_return

    app.text_inserter = MagicMock()
    app.text_insertion_enabled = True
    app.text_insertion_method = text_insertion_method
    app.text_insertion_add_period = False

    app.notifier = None
    app.notifications_config = {}

    app.visual_indicator = MagicMock()

    app._transcription_lock = threading.Lock()

    return app


# --- Lock serialization -----------------------------------------------------

def test_transcription_lock_serializes_overlapping_recordings():
    """The exact regression this lock fixes: two overlapping presses must
    never call into the transcriber concurrently (mlx_whisper crashes with
    "There is no Stream(cpu, 1) in current thread" if they do)."""
    order = []
    call_count = [0]
    first_entered = threading.Event()
    release_first = threading.Event()

    def fake_transcribe(audio_file, language, beam_size, verbose):
        call_count[0] += 1
        my_call = call_count[0]
        order.append(("enter", my_call))
        if my_call == 1:
            first_entered.set()
            assert release_first.wait(timeout=2), "test setup deadlocked"
        order.append(("exit", my_call))
        return f"call {my_call}", {}

    app = make_app(transcribe_side_effect=fake_transcribe)

    t1 = threading.Thread(target=app._process_recording)
    t1.start()
    assert first_entered.wait(timeout=2), "first call never entered transcribe"

    t2 = threading.Thread(target=app._process_recording)
    t2.start()
    # Give t2 a real chance to run and attempt to acquire the lock. If the
    # lock were missing/broken, t2 would enter fake_transcribe and append
    # ("enter", 2) during this window.
    time.sleep(0.2)
    assert order == [("enter", 1)], "second call ran concurrently with the first"

    release_first.set()
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert order == [("enter", 1), ("exit", 1), ("enter", 2), ("exit", 2)]


# --- No-audio short-circuit --------------------------------------------------

@pytest.mark.parametrize("stop_recording_value", [None, np.array([], dtype=np.int16)])
def test_process_recording_skips_transcription_when_no_audio(stop_recording_value):
    app = make_app()
    app.recorder.stop_recording.return_value = stop_recording_value

    app._process_recording()

    app.transcriber.transcribe.assert_not_called()


# --- Restart after a hung audio stream ---------------------------------------

def test_hung_audio_stream_transcribes_then_restarts_process(monkeypatch):
    app = make_app()
    app.recorder.stream_hung = True
    execv = MagicMock()
    monkeypatch.setattr(os, "execv", execv)

    app._process_recording()

    app.transcriber.transcribe.assert_called_once()
    execv.assert_called_once()


def test_healthy_audio_stream_does_not_restart_process(monkeypatch):
    app = make_app()
    execv = MagicMock()
    monkeypatch.setattr(os, "execv", execv)

    app._process_recording()

    execv.assert_not_called()


# --- Non-blocking dispatch ---------------------------------------------------

def test_on_recording_stop_returns_before_transcription_finishes(monkeypatch):
    """_on_recording_stop runs on the keyboard listener's own callback
    thread and must return immediately, spawning transcription on a
    separate thread rather than running it inline."""
    transcribe_started = threading.Event()
    release_transcribe = threading.Event()
    spawned_threads = []

    def slow_transcribe(audio_file, language, beam_size, verbose):
        transcribe_started.set()
        release_transcribe.wait(timeout=2)
        return "done", {}

    real_thread_class = threading.Thread

    def _tracking_thread(*args, **kwargs):
        t = real_thread_class(*args, **kwargs)
        spawned_threads.append(t)
        return t

    monkeypatch.setattr(threading, "Thread", _tracking_thread)

    app = make_app(transcribe_side_effect=slow_transcribe)

    start = time.monotonic()
    app._on_recording_stop()
    elapsed = time.monotonic() - start

    assert elapsed < 0.5, "_on_recording_stop blocked instead of returning immediately"
    assert transcribe_started.wait(timeout=2), "background thread never started transcription"

    release_transcribe.set()
    for t in spawned_threads:
        t.join(timeout=2)


def test_on_recording_stop_catches_exceptions_and_hides_indicator():
    app = make_app()
    app.visual_indicator.set_state.side_effect = RuntimeError("boom")

    app._on_recording_stop()  # must not raise

    app.visual_indicator.hide.assert_called()


def test_on_recording_start_catches_exceptions_and_hides_indicator():
    """The exact bug observed in practice: AudioRecorder.start_recording()
    raising a PortAudioError used to kill the whole pynput listener."""
    app = make_app()
    app.recorder.start_recording.side_effect = OSError("device unavailable")

    app._on_recording_start()  # must not raise

    app.visual_indicator.hide.assert_called()


# --- Text insertion method dispatch ------------------------------------------

def test_clipboard_method_calls_insert_with_shortcut():
    app = make_app(text_insertion_method="clipboard", transcribe_return=("hi there", {}))

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    app.text_inserter.insert_with_shortcut.assert_called_once_with("hi there", use_ctrl_v=True)
    app.text_inserter.insert_text.assert_not_called()


def test_direct_method_calls_insert_text():
    app = make_app(text_insertion_method="direct", transcribe_return=("hi there", {}))

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    app.text_inserter.insert_text.assert_called_once_with("hi there", add_period=False)
    app.text_inserter.insert_with_shortcut.assert_not_called()


def test_empty_transcribed_text_skips_insertion():
    app = make_app(transcribe_return=("", {}))

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    app.text_inserter.insert_text.assert_not_called()
    app.text_inserter.insert_with_shortcut.assert_not_called()


# --- save_recordings toggle ---------------------------------------------------

def test_save_recordings_true_writes_output_file_too():
    app = make_app(save_recordings=True)

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    assert app.recorder.save_wav.call_count == 2
    second_call_args = app.recorder.save_wav.call_args_list[1]
    assert second_call_args.args[1] == "test_audio.wav"


def test_save_recordings_false_writes_temp_file_only():
    app = make_app(save_recordings=False)

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    assert app.recorder.save_wav.call_count == 1


# --- Error handling and cleanup ------------------------------------------------

def test_text_insertion_error_is_caught_and_cleanup_still_runs():
    app = make_app(transcribe_return=("hello", {}), cleanup_temp_files=True)
    app.text_inserter.insert_text.side_effect = RuntimeError("keyboard simulation failed")

    written_paths = []
    app.recorder.save_wav.side_effect = lambda audio, path: written_paths.append(path)

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))  # must not raise

    tmp_path = written_paths[0]
    assert not os.path.exists(tmp_path)


def test_transcription_failure_is_caught_and_indicator_hidden_not_completed():
    app = make_app(transcribe_side_effect=RuntimeError("model download failed"))

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))  # must not raise

    app.visual_indicator.hide.assert_called()
    # "complete" (the success checkmark) must never be set on a failure path.
    assert ("complete",) not in [call.args for call in app.visual_indicator.set_state.call_args_list]


def test_transcription_failure_still_cleans_up_temp_file():
    app = make_app(transcribe_side_effect=RuntimeError("model download failed"), cleanup_temp_files=True)

    written_paths = []
    app.recorder.save_wav.side_effect = lambda audio, path: written_paths.append(path)

    app._transcribe_and_insert(np.array([1, 2, 3], dtype=np.int16))

    assert written_paths, "save_wav should have been attempted before the failure"
    assert not os.path.exists(written_paths[0])
