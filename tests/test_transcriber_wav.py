"""
Tests for the ffmpeg-free WAV decode path added for Apple Silicon / mlx-whisper.

`Transcriber._load_wav_as_array` lets mlx-whisper receive a numpy array directly
so it never has to shell out to ffmpeg. These tests use real numpy + the stdlib
`wave` module (no stubbing) to verify the decode and the format guards.
"""

import sys
import types
import wave

import numpy as np
import pytest

from transcriber import Transcriber


def _write_wav(path, samples_int16, framerate=16000, channels=1, sampwidth=2):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(samples_int16.astype("<i2").tobytes())


def test_decodes_16k_mono_pcm_to_normalized_float32(tmp_path):
    # A handful of known int16 values, including the extremes.
    samples = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
    wav = tmp_path / "mono16k.wav"
    _write_wav(wav, samples)

    audio = Transcriber._load_wav_as_array(str(wav))

    assert audio is not None
    assert audio.dtype == np.float32
    assert audio.shape == (5,)
    # int16 / 32768 normalization
    expected = samples.astype(np.float32) / 32768.0
    np.testing.assert_allclose(audio, expected, rtol=0, atol=1e-7)
    # Stays within the [-1, 1) range whisper expects.
    assert audio.max() < 1.0
    assert audio.min() >= -1.0


def test_rejects_non_16k_samplerate(tmp_path):
    samples = np.zeros(10, dtype=np.int16)
    wav = tmp_path / "44k.wav"
    _write_wav(wav, samples, framerate=44100)
    assert Transcriber._load_wav_as_array(str(wav)) is None


def test_rejects_stereo(tmp_path):
    # Interleaved stereo: 2 channels, 4 frames.
    samples = np.zeros(8, dtype=np.int16)
    wav = tmp_path / "stereo.wav"
    _write_wav(wav, samples, channels=2)
    assert Transcriber._load_wav_as_array(str(wav)) is None


def test_rejects_8bit_samplewidth(tmp_path):
    wav = tmp_path / "8bit.wav"
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)  # 8-bit
        wf.setframerate(16000)
        wf.writeframes(bytes([128, 128, 130]))
    assert Transcriber._load_wav_as_array(str(wav)) is None


def test_returns_none_for_non_wav_file(tmp_path):
    bogus = tmp_path / "not_audio.txt"
    bogus.write_text("this is not a wav file")
    assert Transcriber._load_wav_as_array(str(bogus)) is None


def test_returns_none_for_empty_file(tmp_path):
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    assert Transcriber._load_wav_as_array(str(empty)) is None


# --- _transcribe_mlx: array vs. path fallback -------------------------------


def _make_mlx_stub():
    """A fake mlx_whisper that records the `audio` argument it was handed."""
    mod = types.ModuleType("mlx_whisper")
    calls = {}

    def transcribe(audio, path_or_hf_repo=None, language=None, verbose=False):
        calls["audio"] = audio
        return {"text": "  hello world  ", "language": "en"}

    mod.transcribe = transcribe
    mod._calls = calls
    return mod


@pytest.fixture
def mlx_stub(monkeypatch):
    mod = _make_mlx_stub()
    monkeypatch.setitem(sys.modules, "mlx_whisper", mod)
    return mod


def _mlx_transcriber():
    # device="mlx" only configures the repo string; it does not import mlx here.
    return Transcriber(model_size="tiny", device="mlx")


def test_transcribe_mlx_passes_decoded_array_for_standard_wav(tmp_path, mlx_stub):
    samples = np.array([0, 1000, -1000], dtype=np.int16)
    wav = tmp_path / "ok.wav"
    _write_wav(wav, samples)

    transcriber = _mlx_transcriber()
    text, info = transcriber.transcribe(str(wav), language="en")

    # mlx-whisper got a numpy array, not a path -> no ffmpeg needed.
    assert isinstance(mlx_stub._calls["audio"], np.ndarray)
    assert text == "hello world"
    assert info["language"] == "en"


def test_transcribe_mlx_falls_back_to_path_for_non_wav(tmp_path, mlx_stub):
    bogus = tmp_path / "weird.m4a"
    bogus.write_bytes(b"\x00\x01\x02not-a-wav")

    transcriber = _mlx_transcriber()
    transcriber.transcribe(str(bogus), language="en")

    # Undecodable -> hand mlx-whisper the path so it can use ffmpeg itself.
    assert mlx_stub._calls["audio"] == str(bogus)
    assert isinstance(mlx_stub._calls["audio"], str)
