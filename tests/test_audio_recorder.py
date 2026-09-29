"""
Tests for AudioRecorder's input-device resolution and audio-buffer handling.

These construct AudioRecorder directly and drive its pure logic (device
resolution, buffer conversion) without ever opening a real sd.InputStream —
start_recording() itself (which touches real audio hardware) is not exercised
here.
"""

import threading
import time
import wave

import numpy as np
import pytest

import audio_recorder as audio_recorder_module
from audio_recorder import AudioRecorder


def _fake_devices():
    return [
        {"name": "Bruno's iPhone Microphone", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "MacBook Pro Microphone", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "MacBook Pro Speakers", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "MI BT 18I", "max_input_channels": 1, "max_output_channels": 0},
    ]


def test_empty_input_device_short_circuits_without_querying_devices(monkeypatch):
    called = []
    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", lambda: called.append(True))

    recorder = AudioRecorder(input_device="")

    assert recorder._device_index is None
    assert called == []  # query_devices() must never be called


def test_substring_match_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", _fake_devices)

    recorder = AudioRecorder(input_device="macbook pro microphone")

    assert recorder._device_index == 1


def test_output_only_device_with_matching_name_is_skipped(monkeypatch):
    """'MacBook Pro Speakers' shares the 'MacBook Pro' substring but has no
    input channels, so a search for it must not match the speakers entry."""
    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", _fake_devices)

    recorder = AudioRecorder(input_device="MacBook Pro Speakers")

    assert recorder._device_index is None


def test_no_match_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", _fake_devices)

    recorder = AudioRecorder(input_device="Nonexistent Device XYZ")

    assert recorder._device_index is None


def test_query_devices_exception_is_swallowed(monkeypatch):
    def _raise():
        raise OSError("no audio backend available")

    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", _raise)

    recorder = AudioRecorder(input_device="MacBook Pro Microphone")

    assert recorder._device_index is None


def test_stop_recording_returns_none_when_never_started():
    recorder = AudioRecorder()
    assert recorder.stop_recording() is None


def test_stop_recording_returns_none_when_no_frames_buffered():
    recorder = AudioRecorder()
    recorder.recording = True
    recorder.audio_frames = []

    assert recorder.stop_recording() is None
    assert recorder.recording is False


def test_stop_recording_converts_and_concatenates_frames():
    recorder = AudioRecorder()
    recorder.recording = True
    # Two float32 frames, as sounddevice's callback would append them.
    recorder.audio_frames = [
        np.array([[0.5], [-0.5]], dtype=np.float32),
        np.array([[1.0], [0.0]], dtype=np.float32),
    ]

    result = recorder.stop_recording()

    assert result is not None
    assert result.dtype == np.int16
    assert len(result) == 4
    # float32 -> int16 scaling is `* 32767`.
    expected = (np.array([0.5, -0.5, 1.0, 0.0], dtype=np.float32) * 32767).astype(np.int16)
    np.testing.assert_array_equal(result.flatten(), expected)
    assert recorder.recording is False


def test_is_recording_reflects_state():
    recorder = AudioRecorder()
    assert recorder.is_recording() is False
    recorder.recording = True
    assert recorder.is_recording() is True


def test_save_wav_writes_expected_header_and_data(tmp_path):
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    audio_data = np.array([0, 100, -100, 32767], dtype=np.int16)
    out_path = tmp_path / "test.wav"

    recorder.save_wav(audio_data, str(out_path))

    with wave.open(str(out_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == len(audio_data)
        frames = wf.readframes(wf.getnframes())
        assert np.frombuffer(frames, dtype=np.int16).tolist() == audio_data.tolist()


@pytest.mark.parametrize("input_device", ["", "Nonexistent"])
def test_construction_does_not_touch_real_hardware(input_device, monkeypatch):
    """Guard against a future change accidentally calling start_recording()
    (or otherwise opening a stream) from __init__."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("InputStream must not be created during __init__")

    monkeypatch.setattr(audio_recorder_module.sd, "InputStream", _fail_if_called)
    monkeypatch.setattr(audio_recorder_module.sd, "query_devices", _fake_devices)

    AudioRecorder(input_device=input_device)


# --- Hung CoreAudio stop ------------------------------------------------------


class _HangingStream:
    """Stands in for an sd.InputStream whose stop() deadlocks inside CoreAudio."""

    def __init__(self):
        self.release = threading.Event()

    def stop(self):
        self.release.wait()

    def close(self):
        pass


def _recording_recorder(stream, monkeypatch):
    monkeypatch.setattr(AudioRecorder, "STOP_TIMEOUT_S", 0.2)
    recorder = AudioRecorder()
    recorder.recording = True
    recorder.stream = stream
    recorder.audio_frames = [np.full((4, 1), 0.5, dtype=np.float32)]
    return recorder


def test_hung_stream_stop_still_returns_audio_and_flags_it(monkeypatch):
    stream = _HangingStream()
    recorder = _recording_recorder(stream, monkeypatch)

    audio = recorder.stop_recording()
    stream.release.set()

    assert audio is not None and len(audio) == 4
    assert recorder.stream_hung is True


def test_hung_stream_stop_does_not_hold_the_lock(monkeypatch):
    """start_recording() runs on the keyboard listener's thread; if the lock
    were held while stop() hangs, the next hotkey press would freeze it."""
    stream = _HangingStream()
    recorder = _recording_recorder(stream, monkeypatch)
    stopper = threading.Thread(target=recorder.stop_recording, daemon=True)
    stopper.start()
    time.sleep(0.05)  # stop() is now blocked inside the hung stream

    acquired = recorder.lock.acquire(timeout=0.1)
    if acquired:
        recorder.lock.release()
    stream.release.set()

    assert acquired


def test_healthy_stream_stop_does_not_flag_a_hang(monkeypatch):
    stream = _HangingStream()
    stream.release.set()
    recorder = _recording_recorder(stream, monkeypatch)

    recorder.stop_recording()

    assert recorder.stream_hung is False
