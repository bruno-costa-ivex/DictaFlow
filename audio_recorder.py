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

    def __init__(self, sample_rate: int = 16000, channels: int = 1, on_level_update=None):
        """
        Initialize audio recorder.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels (1 for mono, 2 for stereo)
            on_level_update: Callback function that receives audio level (0.0 to 1.0)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.audio_frames = []
        self.stream = None
        self.lock = threading.Lock()
        self._on_level_update = on_level_update
        self._current_level = 0.0
    
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
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            print("⏹️  Recording stopped.")
            
            if not self.audio_frames:
                return None
            
            # Convert to int16
            audio_data = np.concatenate(self.audio_frames, axis=0)
            audio_data = (audio_data * 32767).astype(np.int16)
            
            return audio_data
    
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

