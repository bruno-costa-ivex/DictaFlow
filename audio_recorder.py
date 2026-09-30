#!/usr/bin/env python3
"""
Audio Recorder Module
Handles audio recording using sounddevice
"""

import numpy as np
import wave
import sounddevice as sd
import threading
from typing import Optional


class AudioRecorder:
    """Thread-safe audio recorder."""

    # CoreAudio's AudioOutputUnitStop can deadlock forever inside the HAL, so
    # stopping the stream is bounded rather than waited on indefinitely.
    STOP_TIMEOUT_S = 3.0

    def __init__(self, sample_rate: int = 16000, channels: int = 1, on_level_update=None, input_device: str = ""):
        """
        Initialize audio recorder.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels (1 for mono, 2 for stereo)
            on_level_update: Callback function that receives audio level (0.0 to 1.0)
            input_device: Substring to match against sounddevice's input device
                names (e.g. "MacBook Pro Microphone"). Pins recording to that
                device regardless of which one macOS currently considers the
                system default — otherwise, connecting a Bluetooth headset or
                other mic can silently redirect recording to it. Empty string
                uses the system default input device.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.audio_frames = []
        self.stream = None
        self.stream_hung = False
        self.lock = threading.Lock()
        self._on_level_update = on_level_update
        self._current_level = 0.0
        self._device_index = self._resolve_input_device(input_device)

    def _resolve_input_device(self, input_device: str):
        """Find a sounddevice input device index by name substring, or None
        to fall back to the system default."""
        if not input_device:
            return None
        try:
            devices = sd.query_devices()
        except Exception as e:
            print(f"⚠️  Could not query audio devices ({e}), using system default input.")
            return None

        for index, device in enumerate(devices):
            if device.get('max_input_channels', 0) > 0 and input_device.lower() in device['name'].lower():
                print(f"🎙️  Using input device: {device['name']} (index {index})")
                return index

        print(f"⚠️  Input device matching '{input_device}' not found, using system default input.")
        return None

    def start_recording(self):
        """Start recording audio."""
        with self.lock:
            if self.recording:
                return

            self.recording = True
            self.audio_frames = []

            def audio_callback(indata, frames, time_info, status):
                if status:
                    print(f"Audio status: {status}")
                if self.recording:
                    self.audio_frames.append(indata.copy())
                    # Calculate audio level (RMS)
                    rms = np.sqrt(np.mean(indata ** 2))
                    # Normalize to 0-1 range (adjust multiplier for sensitivity)
                    level = min(1.0, rms * 4.0)
                    self._current_level = level
                    if self._on_level_update:
                        self._on_level_update(level)

            self.stream = sd.InputStream(
                device=self._device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=audio_callback
            )

            self.stream.start()
            print("🎤 Recording started...")
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """
        Stop recording and return audio data.
        
        Returns:
            Audio data as numpy array (int16), or None if no recording
        """
        with self.lock:
            if not self.recording:
                return None

            self.recording = False
            stream, self.stream = self.stream, None
            audio_frames = self.audio_frames

        # Stopped outside the lock: start_recording() runs on the keyboard
        # listener's thread and takes the same lock, so a hung stop() here
        # would otherwise freeze the hotkey on its next press.
        if stream:
            self._close_stream(stream)

        print("⏹️  Recording stopped.")

        if not audio_frames:
            return None

        # Convert to int16
        audio_data = np.concatenate(audio_frames, axis=0)
        audio_data = (audio_data * 32767).astype(np.int16)

        return audio_data

    def _close_stream(self, stream):
        """Stop and close a stream, abandoning it if CoreAudio hangs."""
        def close():
            stream.stop()
            stream.close()

        closer = threading.Thread(target=close, daemon=True)
        closer.start()
        closer.join(self.STOP_TIMEOUT_S)
        if closer.is_alive():
            self.stream_hung = True
            print("⚠️  Audio stream did not stop (CoreAudio hang), abandoning it.")

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording
    
    def save_wav(self, audio_data: np.ndarray, filename: str) -> str:
        """
        Save audio data to WAV file.
        
        Args:
            audio_data: Audio data as numpy array (int16)
            filename: Output filename
            
        Returns:
            Filename of saved file
        """
        print(f"💾 Saving to {filename}...")
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
        
        file_size = len(audio_data) * 2  # 2 bytes per sample
        duration = len(audio_data) / self.sample_rate
        print(f"✅ Saved! Size: {file_size} bytes, Duration: {duration:.2f} seconds")
        
        return filename

