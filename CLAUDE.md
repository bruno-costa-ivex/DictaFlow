# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DictaFlow is a Python-based real-time speech-to-text transcription tool that functions as a push-to-talk dictation utility. It captures audio via keyboard shortcut (Alt+W by default), transcribes it using OpenAI's Whisper model via faster-whisper, and automatically inserts the transcribed text at the cursor position.

## Development Commands

```bash
# Setup virtual environment and install dependencies
python3 -m venv dicta_env
source dicta_env/bin/activate
pip install -r requirements.txt

# Run the application
python main.py

# Run with custom configuration
python main.py --config custom_config.yaml
```

**Note:** There are no test, lint, or build commands configured for this project.

## Architecture

The application follows a modular architecture with clear separation of concerns:

```
main.py (TranscriptionApp - Orchestrator)
    ├── config.py        → Loads and validates config.yaml
    ├── keyboard_handler.py → Monitors Alt+W trigger via pynput
    ├── audio_recorder.py   → Captures audio via sounddevice (16kHz, mono)
    ├── transcriber.py      → Whisper model via faster-whisper (GPU/CPU)
    ├── text_inserter.py    → Types text at cursor via pynput
    └── notifier.py         → Desktop notifications via desktop-notifier
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
- **model.device**: cpu, cuda
- **model.compute_type**: int8, float16, float32
- **keyboard.modifier_key**: alt, ctrl, shift, super
- **text_insertion.method**: direct (character-by-character), clipboard (Ctrl+V)
- **notifications.enabled**: enable/disable desktop notifications

## Key Dependencies

- **faster-whisper**: Whisper model via CTranslate2 backend
- **sounddevice**: Cross-platform audio I/O
- **pynput**: Keyboard monitoring and simulation (requires X11/Wayland display)
- **PyYAML**: Configuration parsing
- **desktop-notifier**: Desktop notifications (falls back to notify-send CLI)

## Platform Notes

- Linux-focused (pynput requires display server)
- Optional CUDA 13.0+ for GPU acceleration (falls back to CPU automatically)
- Python 3.11+ required
