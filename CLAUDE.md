# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DictaFlow is a Python-based real-time speech-to-text transcription tool that functions as a push-to-talk dictation utility. It captures audio via a configurable keyboard shortcut: by default, a solo-key trigger (hold Right Command alone — `right_cmd`/`right_alt`/`right_ctrl`/`right_shift`/`left_cmd`/`left_alt`/`left_ctrl`/`left_shift` are supported), or alternatively a modifier+letter combo (`alt`/`ctrl`/`shift`/`super`/`cmd` + a trigger character). Solo mode exists because macOS may not reliably suppress a combo's raw keystroke from also reaching the frontmost app (see keyboard_handler.py). It transcribes audio using OpenAI's Whisper model via faster-whisper, and automatically inserts the transcribed text at the cursor position.

## Development Commands

```bash
# Install dependencies (Poetry manages the virtual environment)
poetry install

# Run the application
poetry run python main.py

# Run with custom configuration
poetry run python main.py --config custom_config.yaml

# Run tests
poetry run pytest tests/ -v

# Run lint
poetry run ruff check .
```

**Note:** There is no build/compile step (pure Python). CI (`.github/workflows/ci.yml`) runs the test suite and `ruff check .` on every PR to `main` and every push to `main`.

## Architecture

The application follows a modular architecture with clear separation of concerns:

```
main.py (TranscriptionApp - Orchestrator)
    ├── config.py            → Loads and validates config.yaml
    ├── keyboard_handler.py   → Monitors configured shortcut via pynput; solo-key mode (default) or modifier+letter combo mode
    ├── audio_recorder.py     → Captures audio via sounddevice (16kHz, mono); pinnable to a named input device
    ├── transcriber.py        → Whisper model via faster-whisper (GPU/CPU) or mlx-whisper (Apple Silicon)
    ├── text_inserter.py      → Types text at cursor via pynput
    ├── notifier.py           → Desktop notifications via desktop-notifier
    └── visual_indicator.py   → Recording/processing/complete overlay: Tkinter WaveIndicator (Linux) or a native AppKit FloatingPanelIndicator (macOS)
```

### Component Responsibilities

- **TranscriptionApp (main.py)**: Orchestrates lifecycle, initializes components, handles recording workflow
- **Config (config.py)**: YAML parsing, validation (model sizes, devices, compute types)
- **KeyboardHandler**: Callback-based keyboard events with configurable modifier+trigger
- **AudioRecorder**: Thread-safe audio capture with lock-protected state and frame buffer
- **Transcriber**: Whisper model loading with automatic CPU fallback if GPU unavailable
- **TextInserter**: Two insertion methods - direct typing or clipboard paste
- **Notifier**: Desktop notifications with fallback to notify-send CLI

### Data Flow

1. KeyboardHandler detects modifier+trigger press → calls `on_start` callback
2. AudioRecorder captures audio in real-time callback
3. On release, audio saved to temp WAV file
4. Transcriber processes via Whisper, returns text + metadata
5. TextInserter types transcribed text at cursor position
6. Temp file cleaned up

### Thread Safety

- AudioRecorder uses `threading.Lock()` for state and frame buffer
- KeyboardHandler uses pynput's thread-safe listener
- Transcriber is read-only after initialization

## Configuration

All settings in `config.yaml`:

- **model.size**: tiny, base, small, medium, large-v2, large-v3
- **model.device**: cpu, cuda, mlx (Apple Silicon)
- **model.compute_type**: int8, float16, float32 (ignored for mlx)
- **keyboard.modifier_key** / **keyboard.trigger_key**: two modes —
  - Solo-key mode (default): `trigger_key: ""`, `modifier_key` is `right_cmd`, `right_alt`, `right_ctrl`, `right_shift`, `left_cmd`, `left_alt`, `left_ctrl`, or `left_shift` — hold that key alone.
  - Combo mode: `trigger_key` is any single character, `modifier_key` is `alt`, `ctrl`, `shift`, `super`, or `cmd` — hold both together.
- **text_insertion.method**: direct (character-by-character), clipboard (Ctrl+V on macOS)
- **notifications.enabled**: enable/disable desktop notifications

## Key Dependencies

- **faster-whisper**: Whisper model via CTranslate2 backend
- **sounddevice**: Cross-platform audio I/O
- **pynput**: Keyboard monitoring and simulation (requires X11/Wayland display)
- **PyYAML**: Configuration parsing
- **desktop-notifier**: Desktop notifications (falls back to notify-send CLI)

## Platform Notes

- Supports Linux (pynput requires an X11/Wayland display server) and macOS (Apple Silicon gets MLX acceleration; visual_indicator.py uses a native AppKit overlay instead of Tkinter on macOS)
- Optional CUDA 13.0+ for GPU acceleration on Linux/NVIDIA (falls back to CPU automatically)
- Python 3.11+ required
