# DictaFlow

Real-Time Speech-to-Text Transcription Tool with automatic text insertion.

## Features

- 🎙️ **Push-to-Talk Recording**: Press and hold Alt+W to record, release to transcribe
- ⌨️ **Automatic Text Insertion**: Transcribed text automatically appears at cursor position
- 🚀 **GPU Acceleration**: Supports CUDA for fast transcription
- 🔧 **Configurable**: YAML-based configuration for all settings
- 📱 **Visual Feedback**: Desktop notifications and console indicators

## Requirements

- Python 3.11+
- CUDA 13.0+ (optional, for GPU acceleration)
- Microphone access

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
- Device (cpu or cuda)
- Keyboard shortcuts
- Text insertion settings
- Visual indicator
