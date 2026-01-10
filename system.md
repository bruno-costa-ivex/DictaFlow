# Real-Time Transcription Tool - System Design

## Overview

The Real-Time Transcription Tool is a modular Python application that provides push-to-talk audio transcription using OpenAI's Whisper model via `faster-whisper`. The system allows users to record audio by pressing and holding a keyboard shortcut (default: Alt+W) and automatically transcribes the audio when the keys are released. The transcribed text can be automatically inserted at the current cursor position in any application, making it a powerful dictation tool.

## Architecture

The system is designed with a modular architecture, separating concerns into distinct components:

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
│              (Application Orchestrator)                      │
└────────────┬──────────────┬──────────────┬──────────────────┘
             │              │              │
    ┌────────▼──────┐ ┌─────▼──────┐ ┌─────▼──────────┐
    │  config.py    │ │keyboard_   │ │  audio_         │
    │  (Config      │ │handler.py  │ │  recorder.py    │
    │   Manager)    │ │(Keyboard   │ │  (Audio         │
    │               │ │ Events)    │ │  Recording)     │
    └───────┬───────┘ └────────────┘ └────────┬────────┘
            │                                  │
            │                          ┌──────▼──────────┐
            │                          │  transcriber.py │
            │                          │  (Whisper       │
            │                          │   Model)        │
            │                          └────────┬────────┘
            │                                    │
            │                          ┌────────▼──────────┐
            │                          │  text_inserter.py  │
            │                          │  (Text Input      │
            │                          │   Simulation)     │
            │                          └───────────────────┘
            │
    ┌───────▼────────┐
    │  config.yaml   │
    │  (Settings)    │
    └────────────────┘
```

## Components

### 1. Configuration System (`config.py` + `config.yaml`)

**Purpose**: Centralized configuration management

**Responsibilities**:
- Load configuration from YAML file
- Validate configuration values
- Provide type-safe access to configuration sections

**Key Features**:
- YAML-based configuration for easy editing
- Validation of model sizes, devices, and compute types
- Support for nested configuration access

**Configuration Sections**:
- `audio`: Audio recording parameters (sample rate, channels, output file)
- `model`: Whisper model settings (size, device, compute type, language)
- `keyboard`: Keyboard shortcut configuration (modifier and trigger keys)
- `app`: Application behavior settings (verbose mode, file cleanup)
- `text_insertion`: Text insertion settings (enabled, method, typing delay, auto-capitalize)

### 2. Audio Recorder (`audio_recorder.py`)

**Purpose**: Handle audio input and recording

**Responsibilities**:
- Start/stop audio recording using `sounddevice`
- Manage audio stream lifecycle
- Convert audio data formats (float32 → int16)
- Save audio to WAV files

**Key Features**:
- Thread-safe recording operations
- Real-time audio capture via callbacks
- Automatic format conversion for Whisper compatibility
- WAV file generation with proper headers

**Technical Details**:
- Uses `sounddevice` for cross-platform audio I/O
- Records at 16kHz sample rate (optimal for Whisper)
- Mono channel audio (1 channel)
- 16-bit integer format for file storage

### 3. Transcriber (`transcriber.py`)

**Purpose**: Perform speech-to-text transcription

**Responsibilities**:
- Load and manage Whisper model
- Transcribe audio files
- Handle model initialization errors
- Format and return transcription results

**Key Features**:
- Automatic fallback to CPU if GPU unavailable
- Support for multiple model sizes (tiny to large-v3)
- Language detection and specification
- Configurable beam search size

**Technical Details**:
- Uses `faster-whisper` (CTranslate2 backend) for fast inference
- Supports multiple compute types (int8, float16, float32)
- Handles both CPU and CUDA devices
- Suppresses verbose output during transcription

### 4. Keyboard Handler (`keyboard_handler.py`)

**Purpose**: Monitor keyboard events for recording trigger

**Responsibilities**:
- Detect modifier + trigger key combinations
- Trigger recording start/stop callbacks
- Support multiple modifier keys (Alt, Ctrl, Shift, Super)

**Key Features**:
- Configurable keyboard shortcuts
- Support for left/right modifier keys
- Thread-safe event handling
- Clean separation of keyboard logic from recording logic

**Technical Details**:
- Uses `pynput` for cross-platform keyboard monitoring
- Tracks modifier and trigger key states separately
- Triggers callbacks on key press/release events

### 5. Text Inserter (`text_inserter.py`)

**Purpose**: Insert transcribed text at the current cursor position

**Responsibilities**:
- Simulate keyboard input to type text
- Support multiple insertion methods (direct typing, clipboard)
- Handle special characters and formatting
- Auto-capitalize sentences

**Key Features**:
- Works in any application (browser, text editor, etc.)
- Two insertion methods: direct typing or clipboard (Ctrl+V)
- Configurable typing delay for reliability
- Automatic sentence capitalization
- Optional period insertion

**Technical Details**:
- Uses `pynput.keyboard.Controller` for keyboard simulation
- Character-by-character typing for maximum compatibility
- Optional clipboard method using `pyperclip` (if available)
- Handles special characters (newlines, tabs) correctly
- Small delays between keystrokes for reliability

**Insertion Methods**:
- **Direct**: Types character by character (works everywhere)
- **Clipboard**: Uses Ctrl+V (faster, but may not work in all apps)

### 6. Main Application (`main.py`)

**Purpose**: Orchestrate all components and provide application entry point

**Responsibilities**:
- Initialize all components with configuration
- Coordinate between keyboard events and recording
- Manage recording lifecycle (record → save → transcribe)
- Handle temporary file management
- Provide user interface and error handling

**Key Features**:
- Clean separation of concerns
- Command-line argument support
- Graceful shutdown handling
- Comprehensive error reporting

## Data Flow

### Recording Flow

```
1. User presses Alt+W
   ↓
2. KeyboardHandler detects key combination
   ↓
3. KeyboardHandler calls on_start callback
   ↓
4. AudioRecorder.start_recording() begins capturing audio
   ↓
5. Audio frames collected in real-time via callback
   ↓
6. User releases Alt+W
   ↓
7. KeyboardHandler detects key release
   ↓
8. KeyboardHandler calls on_stop callback
   ↓
9. AudioRecorder.stop_recording() stops capture and returns audio data
   ↓
10. Audio saved to temporary WAV file
   ↓
11. Transcriber.transcribe() processes audio file
   ↓
12. Transcription result obtained
   ↓
13. TextInserter.insert_text() types text at cursor position (if enabled)
   ↓
14. Transcription result displayed to user
   ↓
15. Temporary file cleaned up (if configured)
```

### Configuration Flow

```
1. Application starts
   ↓
2. Config.load_config() reads config.yaml
   ↓
3. Config validates all settings
   ↓
4. Components initialized with configuration:
   - AudioRecorder: audio.sample_rate, audio.channels
   - Transcriber: model.size, model.device, model.compute_type
   - KeyboardHandler: keyboard.modifier_key, keyboard.trigger_key
   - TextInserter: text_insertion.method, text_insertion.typing_delay (if enabled)
   ↓
5. Application ready for use
```

## Thread Safety

The system uses threading locks to ensure thread-safe operations:

- **AudioRecorder**: Uses `threading.Lock()` to protect recording state and audio frames
- **KeyboardHandler**: Uses `pynput`'s thread-safe listener mechanism
- **Transcriber**: Model operations are thread-safe (read-only after initialization)

## Error Handling

### Configuration Errors
- Missing configuration file → FileNotFoundError with helpful message
- Invalid model size/device/compute_type → ValueError with valid options
- Missing required sections → ValueError indicating missing section

### Runtime Errors
- Audio device unavailable → Handled by sounddevice (prints status)
- GPU unavailable → Automatic fallback to CPU with warning
- Transcription errors → Caught and displayed with traceback
- File I/O errors → Handled gracefully with cleanup
- Text insertion errors → Caught and displayed, falls back gracefully

## Configuration File Structure

```yaml
audio:
  sample_rate: 16000      # Hz
  channels: 1              # Mono
  dtype: "float32"        # Internal format
  output_file: "test_audio.wav"

model:
  size: "base"            # tiny, base, small, medium, large-v2, large-v3
  device: "cpu"           # cpu or cuda
  compute_type: "int8"    # int8, float16, float32
  language: "en"          # Language code or "auto"
  beam_size: 5           # Beam search size

keyboard:
  modifier_key: "alt"     # alt, ctrl, shift, super
  trigger_key: "w"        # Single character

app:
  verbose: true           # Show detailed output
  save_recordings: true   # Save to output_file
  cleanup_temp_files: true # Remove temp files after transcription

text_insertion:
  enabled: true           # Enable automatic text insertion
  method: "direct"        # "direct" or "clipboard"
  typing_delay: 0.01      # Delay between keystrokes (seconds)
  auto_capitalize: true   # Capitalize first letter
  add_period: false       # Add period at end if no punctuation
```

## Dependencies

### Core Dependencies
- `numpy`: Audio data manipulation
- `sounddevice`: Cross-platform audio I/O
- `faster-whisper`: Whisper model inference
- `pynput`: Keyboard event monitoring and simulation
- `PyYAML`: Configuration file parsing
- `pyperclip` (optional): Clipboard operations for text insertion

### Python Standard Library
- `wave`: WAV file I/O
- `threading`: Thread synchronization
- `tempfile`: Temporary file management
- `contextlib`: Output suppression
- `io`: String I/O for output redirection

## Usage

### Basic Usage
```bash
python main.py
```

### Custom Configuration
```bash
python main.py --config custom_config.yaml
```

### Workflow
1. Start the application
2. Wait for model to load
3. Position cursor in any text field (browser, editor, etc.)
4. Press and hold Alt+W (or configured shortcut)
5. Speak into microphone
6. Release Alt+W
7. Transcribed text automatically appears at cursor position
8. View transcription result in console
9. Repeat as needed

## Extensibility

The modular design allows for easy extension:

### Adding New Features
- **New audio formats**: Extend `AudioRecorder` with additional format support
- **Different models**: Create new transcriber class implementing same interface
- **GUI interface**: Replace `keyboard_handler.py` with GUI event handlers
- **Cloud transcription**: Add cloud-based transcriber as alternative to local model
- **Real-time streaming**: Modify `AudioRecorder` to support streaming transcription
- **Text formatting**: Extend `TextInserter` with formatting options (bold, italic, etc.)
- **Multiple languages**: Add language-specific formatting rules

### Customization Points
- Keyboard shortcuts: Modify `config.yaml`
- Model settings: Adjust model size, device, compute type in `config.yaml`
- Audio settings: Change sample rate, channels in `config.yaml`
- Output format: Extend `Transcriber` to support different output formats

## Performance Considerations

### Model Size vs. Speed
- **tiny**: Fastest, lowest accuracy (~39M parameters)
- **base**: Good balance (~74M parameters)
- **small**: Better accuracy, slower (~244M parameters)
- **medium**: High accuracy (~769M parameters)
- **large-v2/v3**: Best accuracy, slowest (~1550M parameters)

### Compute Type
- **int8**: Fastest, works on CPU, slightly lower accuracy
- **float16**: Good balance, requires CUDA
- **float32**: Best accuracy, slowest, requires CUDA

### Recommendations
- **CPU only**: Use `tiny` or `base` with `int8`
- **GPU available**: Use `base` or `small` with `float16`
- **Best accuracy**: Use `large-v3` with `float32` (requires GPU)

## Security Considerations

- No network communication (all processing local)
- Temporary files cleaned up after use
- No sensitive data stored (audio files optional)
- Keyboard monitoring requires appropriate permissions (Linux: input group)

## Future Enhancements

Potential improvements:
1. **Real-time streaming transcription**: Transcribe while recording
2. **Multiple language support**: Auto-detect and transcribe multiple languages
3. **GUI interface**: Graphical user interface for easier use
4. **Audio preprocessing**: Noise reduction, normalization
5. **Output formats**: JSON, SRT, VTT subtitle formats
6. **Batch processing**: Process multiple audio files
7. **Cloud backup**: Optional cloud storage for transcriptions
8. **Hotkey customization**: GUI for configuring shortcuts

