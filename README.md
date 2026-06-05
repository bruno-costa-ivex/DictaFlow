# DictaFlow

Real-Time Speech-to-Text Transcription Tool with automatic text insertion.

## Features

- 🎙️ **Push-to-Talk Recording**: Press and hold Alt+W to record, release to transcribe
- ⌨️ **Automatic Text Insertion**: Transcribed text automatically appears at cursor position
- 🚀 **GPU Acceleration**: Supports CUDA (NVIDIA) and Apple Silicon MLX for fast transcription
- 🔧 **Configurable**: YAML-based configuration for all settings
- 📱 **Visual Feedback**: Desktop notifications and console indicators

## Requirements

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

2. Create and activate virtual environment:
```bash
python3 -m venv dicta_env
source dicta_env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure settings in `config.yaml`

## Usage

```bash
python main.py
```

Press and hold **Alt+W** to record, release to transcribe.

## Configuration

Edit `config.yaml` to customize:
- Model size (tiny, base, small, medium, large-v2, large-v3)
- Device (`cpu`, `cuda` for NVIDIA, or `mlx` for Apple Silicon)
- Keyboard shortcuts
- Text insertion settings

## Apple Silicon (MLX)

On Apple Silicon Macs, set `device: "mlx"` in `config.yaml` to use native MLX acceleration instead of CPU. The `mlx-whisper` package is installed automatically on macOS via `pip install -r requirements.txt`.

MLX models are downloaded on first run from the [mlx-community HuggingFace hub](https://huggingface.co/mlx-community). The `compute_type` setting is ignored for MLX — precision is determined by the model variant.

| config `size` | MLX model used |
|---|---|
| tiny | mlx-community/whisper-tiny-mlx |
| base | mlx-community/whisper-base-mlx |
| small | mlx-community/whisper-small-mlx |
| medium | mlx-community/whisper-medium-mlx |
| large-v2 | mlx-community/whisper-large-v2-mlx |
| large-v3 | mlx-community/whisper-large-v3-mlx |