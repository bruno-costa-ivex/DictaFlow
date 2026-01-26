# DictaFlow - System Design & Architecture

## Project Overview

**DictaFlow** is a real-time speech-to-text transcription tool that enables push-to-talk dictation into any application. Users press and hold a keyboard shortcut (default: Alt+W) to record audio, then release to automatically transcribe and insert the text at the cursor position.

### Core Value Proposition
- **Hands-free text input** for any application
- **Local processing** (no cloud dependencies)
- **GPU-accelerated** transcription
- **Fully configurable** via YAML
- **Modular architecture** for extensibility

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.11+ | Core application |
| **Audio I/O** | `sounddevice` | Cross-platform audio capture |
| **Transcription** | `faster-whisper` | Optimized Whisper inference |
| **Keyboard I/O** | `pynput` | Global keyboard monitoring & simulation |
| **Configuration** | `PyYAML` | YAML config file parsing |
| **Data Processing** | `numpy` | Audio array manipulation |
| **Clipboard** | `pyperclip` (optional) | Alternative text insertion method |

### Hardware Requirements
- **Minimum**: 2GB RAM, modern CPU
- **Recommended**: 4GB+ RAM, NVIDIA GPU with CUDA 13.0+
- **Microphone**: Any standard audio input device

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│              TranscriptionApp (main.py)                  │
│         Application Orchestrator & Lifecycle Manager     │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
    ┌────▼───┐   ┌─────▼──┐   ┌──────▼────┐
    │Config  │   │Keyboard│   │   Audio   │
    │Manager │   │Handler │   │  Recorder │
    └────┬───┘   └────────┘   └──────┬────┘
         │                           │
         │              ┌────────────▼──────┐
         │              │  Transcriber      │
         │              │  (Whisper Model)  │
         │              └────────────┬──────┘
         │                           │
         │              ┌────────────▼──────┐
         │              │  Text Inserter    │
         │              │  (Keyboard Sim)   │
         │              └───────────────────┘
         │
    ┌────▼──────────┐
    │ config.yaml   │
    │  (Settings)   │
    └───────────────┘
```

---

## Component Details

### 1. Configuration System (`config.py` + `config.yaml`)

**Purpose**: Centralized settings management and validation

**Responsibilities**:
- Load YAML configuration file
- Validate all configuration values
- Provide type-safe property access
- Support dotted key notation (e.g., `config.get('audio.sample_rate')`)

**Configuration Sections**:

```yaml
audio:                  # Audio recording parameters
  sample_rate: 16000    # Samples per second (16kHz optimal for Whisper)
  channels: 1           # 1=mono, 2=stereo
  dtype: "float32"      # Internal audio format
  output_file: "test_audio.wav"  # Save location

model:                  # Whisper model configuration
  size: "large-v2"      # tiny, base, small, medium, large-v2, large-v3
  device: "cuda"        # cpu or cuda (GPU)
  compute_type: "float16"  # int8 (fast), float16 (balanced), float32 (best)
  language: "en"        # en, es, fr, de, etc. or "auto"
  beam_size: 5          # Decoding beam search width

keyboard:               # Hotkey configuration
  modifier_key: "alt"   # alt, ctrl, shift, super
  trigger_key: "w"      # Single character to combine with modifier

app:                    # Application behavior
  verbose: true         # Show detailed transcription output
  save_recordings: false # Save audio files
  cleanup_temp_files: true  # Remove temporary files

text_insertion:         # Text output configuration
  enabled: true         # Enable automatic text insertion
  method: "direct"      # direct (type) or clipboard (paste)
  typing_delay: 0.01    # Delay between keystrokes (seconds)
  auto_capitalize: true # Capitalize first letter
  add_period: false     # Add period if no punctuation
```

**Validation**:
- Ensures required sections exist (audio, model, keyboard)
- Validates model sizes against allowed options
- Confirms device is "cpu" or "cuda"
- Checks compute type is int8, float16, or float32
- Raises clear error messages if configuration invalid

---

### 2. Audio Recorder (`audio_recorder.py`)

**Purpose**: Capture audio from microphone and save to WAV files

**Key Features**:
- Real-time audio capture via callback mechanism
- Thread-safe recording state using `threading.Lock()`
- Automatic format conversion (float32 → int16)
- Proper WAV file generation with headers

**Technical Specifications**:
- Sample Rate: 16kHz (optimal for Whisper)
- Channels: Mono (1 channel)
- Format: 16-bit signed integer (int16) in files
- Stream Format: float32 (internal processing)

**Key Methods**:

```python
start_recording()        # Begin capturing audio
stop_recording()         # End capture, return audio array
save_wav(audio, file)    # Write audio to WAV file
is_recording()           # Check current recording state
```

**Audio Processing Pipeline**:
1. Audio stream created with callback
2. Microphone frames captured at 16kHz
3. Frames accumulated as float32 arrays
4. On stop: frames concatenated into single array
5. Array scaled from float32 (-1.0 to 1.0) to int16 (-32768 to 32767)
6. WAV headers written and frames encoded

---

### 3. Transcriber (`transcriber.py`)

**Purpose**: Convert audio files to text using OpenAI's Whisper model

**Key Features**:
- Lazy model loading on first use
- Automatic CPU fallback if GPU unavailable
- Support for 6 model sizes (tiny to large-v3)
- Configurable language detection
- Graceful error handling with helpful messages

**Model Size Comparison**:

| Size | Parameters | Speed | Accuracy | Best For |
|------|-----------|-------|----------|----------|
| tiny | 39M | ⚡⚡⚡ Very Fast | Low | Real-time, CPU |
| base | 74M | ⚡⚡ Fast | Good | Balanced use |
| small | 244M | ⚡ Moderate | Better | Accuracy focus |
| medium | 769M | Slow | High | Professional |
| large-v2 | 1550M | Very Slow | Excellent | Maximum accuracy |
| large-v3 | 1550M | Very Slow | Excellent | Latest version |

**Compute Type Options**:

| Type | Speed | Accuracy | Requirements |
|------|-------|----------|--------------|
| int8 | Fastest | Good | CPU or GPU |
| float16 | Balanced | Better | CUDA required |
| float32 | Slowest | Best | CUDA required |

**Key Methods**:

```python
transcribe(audio_file, language, beam_size, verbose)
  # Returns: (transcribed_text, info_dict)
  # info_dict contains: language, language_probability
```

**Error Handling**:
- GPU unavailable → Automatic fallback to CPU with int8
- CUDA library errors → Helpful setup instructions
- Runtime errors → Graceful failure with error message

---

### 4. Keyboard Handler (`keyboard_handler.py`)

**Purpose**: Monitor global keyboard events to trigger recording

**Key Features**:
- Global keyboard monitoring (works across all applications)
- Configurable modifier + trigger key combinations
- Support for Alt, Ctrl, Shift, Super modifiers
- Thread-safe event handling

**Supported Key Combinations**:
- Alt+W (default)
- Ctrl+W, Shift+W, Super+W
- Any modifier + single character trigger

**State Machine**:

```
Initial State:
  - modifier_pressed: False
  - trigger_pressed: False
  - is_recording: False

Recording Starts When:
  - modifier_pressed AND trigger_pressed AND NOT is_recording
  - Calls on_start callback

Recording Stops When:
  - Either modifier OR trigger key released while recording
  - Calls on_stop callback
```

**Key Methods**:

```python
start()                           # Begin listening
stop()                            # Stop listening
join()                            # Wait for listener thread
```

**Internal Methods** (called on key events):

```python
_on_key_press(key)                # Handle key down
_on_key_release(key)              # Handle key up
```

---

### 5. Text Inserter (`text_inserter.py`)

**Purpose**: Simulate keyboard input to insert transcribed text at cursor

**Key Features**:
- Two insertion methods (direct typing or clipboard)
- Automatic text formatting
- Special character handling
- Configurable typing speed

**Insertion Methods**:

**Method 1: Direct Typing** (default)
- Types character by character
- Works in any application
- Speed: Slower but more compatible
- Uses `pynput.keyboard.Controller.type()`

**Method 2: Clipboard** (optional)
- Copies text to clipboard
- Presses Ctrl+V
- Speed: Faster but app-dependent
- Requires `pyperclip` library

**Text Processing**:

```python
insert_text(text, add_period=False)
  # 1. Strip whitespace
  # 2. Auto-capitalize first letter (if configured)
  # 3. Add period (if configured and text doesn't end with punctuation)
  # 4. Type character by character with delay
```

**Special Character Handling**:
- Newlines ('\n') → Key.enter
- Tabs ('\t') → Key.tab
- Regular characters → typed directly
- Punctuation → handled as regular characters

**Key Methods**:

```python
insert_text(text, add_period)         # Type directly
insert_with_shortcut(text, use_ctrl_v) # Clipboard or fallback
```

---

### 6. Main Application (`main.py`)

**Purpose**: Orchestrate all components and manage application lifecycle

**Class: TranscriptionApp**

**Responsibilities**:
1. Load configuration
2. Initialize all components
3. Coordinate between components
4. Handle keyboard events
5. Manage recording-transcription-insertion flow
6. Handle errors and cleanup

**Initialization Sequence**:

```
1. Setup CUDA library paths (Linux-specific)
2. Load config.yaml file
3. Create AudioRecorder instance
4. Create Transcriber instance (loads Whisper model)
5. Create KeyboardHandler instance
6. Create TextInserter instance (if enabled)
7. Register callbacks
```

**Complete Recording Flow**:

```
User presses Alt+W
    ↓
KeyboardHandler detects both keys pressed
    ↓
Calls _on_recording_start()
    ↓
AudioRecorder.start_recording()
    ├─ Creates audio stream
    ├─ Begins capturing frames
    ├─ Prints "🎤 Recording started..."
    ↓
[User holds Alt+W and speaks]
    ↓
User releases Alt+W
    ↓
KeyboardHandler detects key release
    ↓
Calls _on_recording_stop()
    ↓
_process_recording() executes:
    ├─ AudioRecorder.stop_recording()
    │  └─ Concatenates frames, converts to int16
    ├─ Save to temporary WAV file
    ├─ [Optional] Save to output_file
    ├─ Transcriber.transcribe()
    │  ├─ Load model
    │  ├─ Run inference
    │  └─ Return text + metadata
    ├─ TextInserter.insert_text() [if enabled]
    │  └─ Type text at cursor position
    └─ Cleanup temporary files [if configured]
    ↓
Ready for next recording
```

**Key Methods**:

```python
__init__(config_path)              # Initialize application
run()                              # Start listening
_on_recording_start()              # Callback: start recording
_on_recording_stop()               # Callback: stop and process
_process_recording()               # Core: record→transcribe→insert
```

---

## Data Flow

### Detailed Signal Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  KEYBOARD SIGNAL FLOW                                           │
│  (Global, works across all applications)                        │
└─────────────────────────────────────────────────────────────────┘

pynput.keyboard.Listener
    ↓ [detects Alt pressed]
KeyboardHandler._on_key_press()
    ↓ [sets modifier_pressed = True]
[waits for trigger key]
    ↓ [detects W pressed]
KeyboardHandler._on_key_press()
    ↓ [detects modifier_pressed AND trigger_pressed]
TranscriptionApp._on_recording_start() [callback]


┌─────────────────────────────────────────────────────────────────┐
│  AUDIO SIGNAL FLOW                                              │
│  (Microphone → Memory → Disk)                                   │
└─────────────────────────────────────────────────────────────────┘

sounddevice.InputStream with callback
    ↓ [16kHz audio frames]
AudioRecorder.audio_callback()
    ↓ [appends frame to self.audio_frames list]
    ↓ [repeats until stop_recording() called]
AudioRecorder.stop_recording()
    ├─ np.concatenate(audio_frames)
    ├─ Scale float32 to int16 (multiply by 32767)
    └─ Return numpy array
    ↓
AudioRecorder.save_wav(audio_array, filename)
    └─ wave.open() → write WAV headers → write bytes


┌─────────────────────────────────────────────────────────────────┐
│  TRANSCRIPTION SIGNAL FLOW                                      │
│  (Disk → Model → Memory)                                        │
└─────────────────────────────────────────────────────────────────┘

Transcriber.transcribe(audio_file)
    ├─ Load audio from WAV file
    ├─ Pass to Whisper model
    ├─ Model processes audio frames
    ├─ Generate output segments
    ├─ Detect language + probability
    └─ Join segments into single string
    ↓
Return (transcribed_text, metadata_dict)


┌─────────────────────────────────────────────────────────────────┐
│  TEXT INSERTION SIGNAL FLOW                                     │
│  (Memory → Keyboard Events)                                     │
└─────────────────────────────────────────────────────────────────┘

TextInserter.insert_text(transcribed_text)
    ├─ Auto-capitalize first letter
    ├─ [Optional] Add period
    └─ For each character in text:
        ├─ pynput.keyboard.Controller.type(character)
        ├─ Sleep typing_delay milliseconds
        └─ Repeat
    ↓
Operating System
    ├─ Queues keyboard events
    └─ Sends to focused application
    ↓
Focused Application receives text input
```

---

## Thread Safety

### Threading Model

The application uses multiple threads:

| Thread | Purpose | Created By |
|--------|---------|-----------|
| Main | Orchestration | Python runtime |
| Keyboard Listener | Global key monitoring | pynput.Listener |
| Audio Stream | Microphone capture | sounddevice.InputStream |

### Synchronization Mechanisms

**AudioRecorder Thread Safety**:
```python
self.lock = threading.Lock()  # Protects shared state

# Protected by lock:
- self.recording (bool)       # Recording state flag
- self.audio_frames (list)    # Accumulated audio data
- self.stream (object)        # Audio stream object

# Lock acquired in:
- start_recording()           # Atomic state change
- stop_recording()            # Atomic state change + cleanup
- audio_callback()            # Append frames safely
```

**KeyboardHandler Thread Safety**:
```python
# Uses pynput's thread-safe listener
# Callbacks executed atomically
# Atomic integer operations for flags:
- self.modifier_pressed       # Atomic boolean
- self.trigger_pressed        # Atomic boolean
- self.is_recording           # Atomic boolean
```

**Transcriber Thread Safety**:
- Read-only after initialization
- No shared mutable state
- Inherently thread-safe

### Race Condition Prevention

1. **Audio Recording**: Main thread waits for stop_recording(); no concurrent access
2. **Keyboard Events**: Listener thread executes atomically
3. **Model Inference**: Single model instance, sequential transcription
4. **File I/O**: Sequential operations, no concurrent file access
5. **State Transitions**: Atomic boolean operations

---

## Error Handling

### Configuration Validation

```python
# Error: File not found
FileNotFoundError: Configuration file not found: config.yaml
→ Solution: Create config.yaml in application directory

# Error: Missing section
ValueError: Missing 'audio' section in config.yaml
→ Solution: Add [audio] section to config.yaml

# Error: Invalid model size
ValueError: Invalid model size: invalid_name
Valid options: tiny, base, small, medium, large-v2, large-v3
→ Solution: Use valid model size in config.yaml

# Error: Invalid device
ValueError: Invalid device: invalid_device
Valid options: cpu, cuda
→ Solution: Change to "cpu" or "cuda"
```

### Runtime Error Handling

```python
# Audio device issue
→ sounddevice prints status
→ Recording fails gracefully
→ User can retry

# GPU not available
→ Automatic fallback to CPU
→ Model reloaded with int8 compute type
→ Warning message printed

# CUDA library missing
→ Clear error message with solutions
→ Links to setup scripts
→ Suggests manual symlink creation

# Transcription error
→ Caught and displayed
→ Application continues running
→ User can record again

# Text insertion error
→ Error caught and displayed
→ Transcription still completed
→ Application continues running
```

### Cleanup on Error

- Temporary WAV files deleted even if error occurs
- Recording stopped if error during transcription
- Keyboard listener stopped on application exit
- Graceful shutdown via Ctrl+C

---

## Performance Optimization

### Model Selection Guide

**For Real-time/Responsive Experience**:
```yaml
model:
  size: "tiny"          # 39M parameters, ~300ms per second of audio (CPU)
  device: "cpu"
  compute_type: "int8"
```

**For Good Balance** (Recommended):
```yaml
model:
  size: "base"          # 74M parameters, ~500ms per second of audio
  device: "cuda"
  compute_type: "float16"
```

**For Maximum Accuracy**:
```yaml
model:
  size: "large-v3"      # 1550M parameters, best accuracy
  device: "cuda"
  compute_type: "float32"
```

### Performance Tips

1. **Typing Speed**: Increase `typing_delay` for less powerful systems
2. **Model Size**: Smaller models load faster on startup
3. **GPU Memory**: Ensure GPU has sufficient VRAM for selected model
4. **Audio Quality**: 16kHz mono is optimal (matches Whisper training)
5. **CPU Threads**: Whisper uses multiple threads automatically

---

## Security & Privacy

### Data Security

✅ **Local Processing Only**
- No cloud services used
- All audio processed on local machine
- Completely offline capable

✅ **No Authentication**
- Standalone tool, no accounts
- No telemetry or analytics
- No data collection

✅ **File Cleanup**
- Temporary files deleted automatically
- Optional to save recordings
- User controls file retention

✅ **No Network Communication**
- No data sent anywhere
- No DNS queries (except initial model download)
- Complete privacy

### System Permissions

⚠️ **Keyboard Monitoring**
- Requires read access to input devices
- Linux: User must be in `input` group

⚠️ **Microphone Access**
- Requires audio device permissions
- Typically allowed by default

⚠️ **Text Insertion**
- Simulates keyboard input
- Only works on focused window
- Cannot send keystrokes to unauthorized applications

---

## Extensibility Points

### Adding Features

**1. Alternative Transcription Provider**
```python
# Create new transcriber class
class CloudTranscriber:
    def transcribe(self, audio_file):
        # Call cloud API
        return (transcribed_text, metadata)

# Update config to select provider
# Update TranscriptionApp.__init__() to instantiate
```

**2. New Text Insertion Method**
```python
# Add method to TextInserter
def insert_via_dbus(self, text):
    # Use D-Bus to inject keystrokes

# Update insert_with_shortcut() to support new method
```

**3. GUI Interface**
```python
# Replace KeyboardHandler with GUI event handlers
# Replace config.yaml with GUI settings dialog
# Keep rest of architecture unchanged
```

**4. Real-time Streaming**
```python
# Modify AudioRecorder for streaming
# Implement segment-by-segment transcription
# Update main.py to display partial results
```

---

## Known Limitations

1. **Single Recording Type**: No simultaneous recording modes
2. **Linear Processing**: Complete recording before transcription
3. **No Real-time Feedback**: Can't see transcription while recording
4. **Keyboard-Dependent**: Only works with text fields accepting keyboard input
5. **No Background Tasks**: Cannot record while user does other work
6. **Memory Usage**: Large models require significant RAM
7. **No Batch Processing**: One recording at a time
8. **No Custom Models**: Only official Whisper models supported

---

## Typical Use Cases

### Use Case 1: Note Taking
```
1. Open note application
2. Click in text field
3. Press Alt+W and dictate note
4. Text appears automatically
5. Continue with next note
```

### Use Case 2: Email Composition
```
1. Open email client
2. Click in message body
3. Alt+W to dictate message
4. Release to send text
5. Edit as needed
```

### Use Case 3: Code Documentation
```
1. Position cursor in comment
2. Press Alt+W to dictate
3. Transcribed comment inserted
4. Continue coding
```

---

## Development Workflow

### Project Structure
```
DictaFlow/
├── main.py                 # Application entry point
├── config.py              # Configuration management
├── audio_recorder.py      # Audio capture
├── transcriber.py         # Speech-to-text
├── keyboard_handler.py    # Keyboard events
├── text_inserter.py       # Text insertion
├── config.yaml            # User configuration
├── requirements.txt       # Python dependencies
├── README.md              # User guide
├── system.md              # Detailed system documentation
└── LICENSE                # License file
```

### Adding New Features

1. **Design**: Plan the feature and identify component impact
2. **Implement**: Add functionality to appropriate module(s)
3. **Configure**: Add configuration options if user-tunable
4. **Validate**: Update Config class validation if needed
5. **Test**: Test with various audio and settings
6. **Document**: Update system.md and README
7. **Commit**: Create descriptive git commit

---

## Conclusion

DictaFlow is a well-architected application with:

- **Clear Separation of Concerns**: Each module has single responsibility
- **Modular Design**: Easy to extend or replace components
- **Thread-Safe**: Proper synchronization for concurrent operations
- **Robust Error Handling**: Graceful failures with helpful messages
- **Configurable**: YAML-based settings for user customization
- **Privacy-Focused**: All processing local, no network communication
- **Performance-Optimized**: GPU acceleration, multiple model sizes

The push-to-talk interface combined with automatic text insertion makes DictaFlow an accessible and practical tool for hands-free dictation into any application.
