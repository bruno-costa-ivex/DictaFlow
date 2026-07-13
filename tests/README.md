# DictaFlow unit tests

Unit tests covering the macOS / Apple Silicon support added on
`feature/apple-silicon-mlx-support`.

## What's covered

| File | Verifies |
|------|----------|
| `test_transcriber_wav.py` | `Transcriber._load_wav_as_array` decodes 16 kHz mono 16‑bit WAV to normalized `float32` and rejects other formats; `_transcribe_mlx` hands mlx‑whisper a decoded array (no ffmpeg) for standard WAVs and falls back to the file path otherwise. |
| `test_text_inserter_macos.py` | `_PASTE_KEY` is `Cmd` on macOS and `Ctrl` on Linux/Windows; clipboard paste presses Cmd+V on macOS and restores the previous clipboard. |
| `test_keyboard_handler_macos.py` | the new `"cmd"` modifier maps to the Command keys and the press/release state machine fires start/stop callbacks correctly. |

## Running

```bash
poetry install
poetry run pytest tests/ -v
```

The OS‑bound / heavy dependencies (`pynput`, `pyperclip`, `mlx-whisper`) are
**stubbed** in `conftest.py` when they aren't installed, so the suite runs fast
and deterministically without accessibility permissions or model downloads. If
those packages *are* installed, the tests run against the real ones instead
(except `mlx_whisper`, which is always stubbed to avoid a model download).
