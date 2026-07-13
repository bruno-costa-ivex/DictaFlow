# DictaFlow

[![CI](https://github.com/bruno-costa-ivex/DictaFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/bruno-costa-ivex/DictaFlow/actions/workflows/ci.yml)

Real-Time Speech-to-Text Transcription Tool with automatic text insertion.

## Features

- 🎙️ **Push-to-Talk Recording**: Press and hold a configurable shortcut (default: Right Command, held alone) to record, release to transcribe
- ⌨️ **Automatic Text Insertion**: Transcribed text automatically appears at cursor position
- 🚀 **GPU Acceleration**: Supports CUDA (NVIDIA) and Apple Silicon MLX for fast transcription
- 🔧 **Configurable**: YAML-based configuration for all settings
- 📱 **Visual Feedback**: Desktop notifications and console indicators

## Requirements

- [Poetry](https://python-poetry.org/docs/#installation)
- Python 3.11+
- Microphone access
- CUDA 13.0+ (optional, for NVIDIA GPU acceleration)
- Apple Silicon Mac (optional, for MLX acceleration)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/brumocas/DictaFlow.git
cd DictaFlow
```

2. Install dependencies (Poetry creates and manages the virtual environment for you):
```bash
poetry install
```

3. Configure settings in `config.yaml`

## Usage

```bash
poetry run python main.py
```

Press and hold **Right Command** (default) to record, release to transcribe.

> **macOS note:** modifier+letter combos like `Alt+W` or `Ctrl+Q` are a poor choice on Mac. pynput's global listener can only *observe* keystrokes reliably — its ability to *suppress* one from also reaching the frontmost app is a known, unreliable limitation on modern macOS (see [pynput#515](https://github.com/moses-palmer/pynput/issues/515)). A "suppressed" combo can still leak through and trigger that app's own binding for it (e.g. Ctrl+W closing a browser tab, or built-in Cocoa text-editing shortcuts messing with your cursor/selection — these apply inside web page text fields too, not just native apps).
>
> The shipped `config.yaml` avoids this entirely with **solo-key mode**: hold one right-side modifier key (Right Command, by default) completely by itself — no letter, no combo, nothing for any app to intercept. Holding the *left* copy of a modifier alone happens constantly as a side effect of ordinary shortcuts (Cmd+C, Cmd+Tab...), but the *right* copy essentially never gets pressed alone, so this is safe. This is the same trick macOS's own built-in dictation trigger relies on.

## Configuration

Edit `config.yaml` to customize:
- Model size (tiny, base, small, medium, large-v2, large-v3)
- Device (`cpu`, `cuda` for NVIDIA, or `mlx` for Apple Silicon)
- Keyboard shortcut:
  - **Solo-key mode** (default, recommended on macOS): set `trigger_key: ""` and `modifier_key` to one of `right_cmd`, `right_alt`, `right_ctrl`, `right_shift`, `left_cmd`, `left_alt`, `left_ctrl`, `left_shift` — hold that key alone.
  - **Combo mode** (alternative): set `trigger_key` to a single character and `modifier_key` to `alt`, `ctrl`, `shift`, `super`, or `cmd` — hold both together. See the macOS note above for the tradeoff.
- Text insertion settings

## Apple Silicon (MLX)

On Apple Silicon Macs, set `device: "mlx"` in `config.yaml` to use native MLX acceleration instead of CPU. The `mlx-whisper` package installs automatically on macOS as part of `poetry install`.

MLX models are downloaded on first run from the [mlx-community HuggingFace hub](https://huggingface.co/mlx-community). The `compute_type` setting is ignored for MLX — precision is determined by the model variant.

| config `size` | MLX model used |
|---|---|
| tiny | mlx-community/whisper-tiny-mlx |
| base | mlx-community/whisper-base-mlx |
| small | mlx-community/whisper-small-mlx |
| medium | mlx-community/whisper-medium-mlx |
| large-v2 | mlx-community/whisper-large-v2-mlx |
| large-v3 | mlx-community/whisper-large-v3-mlx |