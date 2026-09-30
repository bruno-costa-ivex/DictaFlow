#!/usr/bin/env python3
"""
Real-Time Transcription Tool - Main Entry Point
Press and hold the configured shortcut (default: Right Command, held alone) to record, release to transcribe.
"""

import tempfile
import os
import sys
import threading
import time
from pathlib import Path

# Setup CUDA library paths before importing faster-whisper
def setup_cuda_library_path():
    """Ensure CUDA libraries are accessible."""
    cuda_paths = [
        "/usr/local/cuda-13.0/targets/x86_64-linux/lib",
        "/usr/local/cuda/targets/x86_64-linux/lib",
        "/usr/local/cuda-13/targets/x86_64-linux/lib",
        "/usr/local/cuda/lib64",
    ]
    
    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    ld_paths = [p for p in current_ld_path.split(":") if p] if current_ld_path else []
    
    for cuda_path in cuda_paths:
        if os.path.exists(cuda_path) and cuda_path not in ld_paths:
            ld_paths.insert(0, cuda_path)
    
    if ld_paths:
        os.environ["LD_LIBRARY_PATH"] = ":".join(ld_paths)
        # Also try to create compatibility symlink if possible (user-writable location)
        _create_local_cuda_symlink()

def _create_local_cuda_symlink():
    """Create a local symlink in user space if possible."""
    local_lib_dir = Path.home() / ".local" / "lib"
    local_lib_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to find libcublas.so.13
    cuda_lib_paths = [
        "/usr/local/cuda-13.0/targets/x86_64-linux/lib/libcublas.so.13",
        "/usr/local/cuda/targets/x86_64-linux/lib/libcublas.so.13",
    ]
    
    for cuda_lib in cuda_lib_paths:
        if os.path.exists(cuda_lib):
            local_symlink = local_lib_dir / "libcublas.so.12"
            if not local_symlink.exists():
                try:
                    os.symlink(cuda_lib, str(local_symlink))
                    # Add to LD_LIBRARY_PATH
                    current = os.environ.get("LD_LIBRARY_PATH", "")
                    new_path = str(local_lib_dir)
                    if new_path not in current.split(":"):
                        os.environ["LD_LIBRARY_PATH"] = f"{new_path}:{current}" if current else new_path
                except (OSError, PermissionError):
                    pass  # Can't create symlink, will rely on system paths
            break

# Setup CUDA paths before any imports
setup_cuda_library_path()

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# These must come after setup_cuda_library_path() and the sys.path insert
# above, so they're intentionally not at the top of the file.
from config import Config  # noqa: E402
from audio_recorder import AudioRecorder  # noqa: E402
from transcriber import Transcriber  # noqa: E402
from keyboard_handler import KeyboardHandler  # noqa: E402
from text_inserter import TextInserter  # noqa: E402
from notifier import Notifier  # noqa: E402
from visual_indicator import get_indicator  # noqa: E402


class TranscriptionApp:
    """Main application class for real-time transcription."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the transcription application.
        
        Args:
            config_path: Path to configuration YAML file
        """
        # Load configuration
        self.config = Config(config_path)
        
        # Initialize components
        audio_cfg = self.config.audio
        model_cfg = self.config.model
        app_cfg = self.config.app
        
        self.recorder = AudioRecorder(
            sample_rate=audio_cfg['sample_rate'],
            channels=audio_cfg['channels'],
            on_level_update=self._on_audio_level_update,
            input_device=audio_cfg.get('input_device', '')
        )
        
        self.transcriber = Transcriber(
            model_size=model_cfg['size'],
            device=model_cfg['device'],
            compute_type=model_cfg['compute_type']
        )
        
        keyboard_cfg = self.config.keyboard
        self.keyboard_handler = KeyboardHandler(
            modifier_key=keyboard_cfg['modifier_key'],
            trigger_key=keyboard_cfg['trigger_key'],
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop
        )
        
        # Initialize text inserter if enabled
        text_insertion_cfg = self.config.get('text_insertion', {})
        if text_insertion_cfg.get('enabled', True):
            self.text_inserter = TextInserter(
                typing_delay=text_insertion_cfg.get('typing_delay', 0.01),
                auto_capitalize=text_insertion_cfg.get('auto_capitalize', True)
            )
            self.text_insertion_enabled = True
            self.text_insertion_method = text_insertion_cfg.get('method', 'direct')
            self.text_insertion_add_period = text_insertion_cfg.get('add_period', False)
        else:
            self.text_inserter = None
            self.text_insertion_enabled = False

        # Initialize notifier if enabled
        self.notifications_config = self.config.get('notifications', {})
        if self.notifications_config.get('enabled', True):
            self.notifier = Notifier(enabled=True)
        else:
            self.notifier = None

        # Initialize visual indicator
        visual_config = self.config.get('visual_indicator', {})
        if visual_config.get('enabled', True):
            self.visual_indicator = get_indicator(
                position=visual_config.get('position', 'top-center'),
                width=visual_config.get('width', 340),
                height=visual_config.get('height', 80)
            )
        else:
            self.visual_indicator = None

        self.app_config = app_cfg

        # Each recording is transcribed on its own throwaway thread (see
        # _on_recording_stop). Without this lock, pressing the trigger again
        # before a previous transcription finishes lets two threads call
        # into mlx_whisper concurrently — MLX's per-thread execution context
        # doesn't support that and crashes with "There is no Stream(cpu, 1)
        # in current thread." Serializing the whole save/transcribe/insert
        # body also avoids two recordings' text getting inserted interleaved
        # or out of order.
        self._transcription_lock = threading.Lock()

    def _on_audio_level_update(self, level: float):
        """Callback for real-time audio level updates."""
        if self.visual_indicator:
            self.visual_indicator.set_audio_level(level)

    def _on_recording_start(self):
        """Callback when recording should start."""
        # This runs directly on the pynput listener's callback thread (see
        # keyboard_handler.py), not on a background thread — an uncaught
        # exception here (e.g. AudioRecorder.start_recording() raising a
        # PortAudioError because the input device was disconnected/changed)
        # propagates into pynput's own callback wrapper, which silently
        # stops the whole listener. The trigger key would then do nothing
        # at all afterward, with no indication why. Catch and report instead.
        try:
            # Show visual indicator immediately
            if self.visual_indicator:
                self.visual_indicator.show("recording")
            if self.notifier and self.notifications_config.get('on_recording_start', True):
                self.notifier.notify_recording_started()

            self.recorder.start_recording()
        except Exception as e:
            print(f"⚠️  Could not start recording: {e}")
            if self.visual_indicator:
                self.visual_indicator.hide()

    def _on_recording_stop(self):
        """Callback when recording should stop."""
        try:
            # Change visual indicator to processing state
            if self.visual_indicator:
                self.visual_indicator.set_state("processing")
            if self.notifier and self.notifications_config.get('on_recording_stop', True):
                self.notifier.notify_recording_stopped()

            # Run off the keyboard listener's thread: in combo mode (see
            # keyboard_handler.py) that thread drives a blocking CGEventTap
            # needed to swallow the hotkey before it reaches other apps, so
            # anything slow here — like Whisper transcription — would otherwise
            # stall system-wide keyboard input until it returns. Actual
            # transcription work is serialized via _transcription_lock so
            # overlapping presses can't run concurrently (see _process_recording).
            threading.Thread(target=self._process_recording, daemon=True).start()
        except Exception as e:
            print(f"⚠️  Could not process recording: {e}")
            if self.visual_indicator:
                self.visual_indicator.hide()
    
    def _process_recording(self):
        """Process the recorded audio: save and transcribe."""
        audio_data = self.recorder.stop_recording()

        try:
            if audio_data is None or len(audio_data) == 0:
                print("⚠️  No audio recorded.")
                return

            with self._transcription_lock:
                self._transcribe_and_insert(audio_data)
        finally:
            if self.recorder.stream_hung:
                self._restart()

    def _restart(self):
        """Re-exec the process. A CoreAudio hang can't be recovered from
        in-process, and the next recording would likely hang on it too."""
        print("🔄 Restarting to recover from the audio hang...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _transcribe_and_insert(self, audio_data):
        """Save, transcribe, and insert text for one recording. Must run
        under self._transcription_lock — see _process_recording."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            # Save temporary file
            self.recorder.save_wav(audio_data, tmp_filename)

            # Also save to main output file if configured
            if self.app_config.get('save_recordings', True):
                output_file = self.config.audio['output_file']
                self.recorder.save_wav(audio_data, output_file)

            # Transcribe
            model_cfg = self.config.model
            transcribed_text, info = self.transcriber.transcribe(
                audio_file=tmp_filename,
                language=model_cfg['language'],
                beam_size=model_cfg['beam_size'],
                verbose=self.app_config.get('verbose', False)
            )

            # Insert text at cursor position if enabled
            if self.text_insertion_enabled and transcribed_text:
                print("⌨️  Inserting text at cursor position...")
                try:
                    if self.text_insertion_method == 'clipboard':
                        self.text_inserter.insert_with_shortcut(
                            transcribed_text,
                            use_ctrl_v=True
                        )
                    else:
                        self.text_inserter.insert_text(
                            transcribed_text,
                            add_period=self.text_insertion_add_period
                        )
                    print("✅ Text inserted!")
                except Exception as e:
                    print(f"⚠️  Error inserting text: {e}")

            if self.notifier and self.notifications_config.get('on_transcription_complete', True):
                self.notifier.notify_transcription_complete()

            # Only mark "complete" (green checkmark) on the success path —
            # showing it after a failure below would be misleading.
            if self.visual_indicator:
                self.visual_indicator.set_state("complete")
        except Exception as e:
            # Covers save_wav/transcribe failures (e.g. a Whisper model
            # download failing with no internet) that previously weren't
            # caught at all — without this, the visual indicator would be
            # left stuck showing "processing" forever with no feedback.
            print(f"⚠️  Error transcribing recording: {e}")
        finally:
            # Hide visual indicator whether transcription succeeded or not —
            # on failure this hides straight from "processing" rather than
            # from "complete".
            if self.visual_indicator:
                time.sleep(0.3)
                self.visual_indicator.hide()

            # Clean up temporary file if configured
            if self.app_config.get('cleanup_temp_files', True):
                try:
                    os.unlink(tmp_filename)
                except OSError:
                    pass
    
    def run(self):
        """Run the application."""
        print("=" * 60)
        print("🎙️  Real-Time Transcription Tool")
        print("=" * 60)
        
        keyboard_cfg = self.config.keyboard
        modifier = keyboard_cfg['modifier_key'].upper()
        trigger = keyboard_cfg['trigger_key'].upper()
        shortcut = modifier if self.keyboard_handler.solo_mode else f"{modifier}+{trigger}"

        print(f"Press and hold {shortcut} to record")
        print(f"Release {shortcut} to stop and transcribe")
        if self.text_insertion_enabled:
            print("📝 Transcribed text will be inserted at cursor position")
        if self.visual_indicator and self.visual_indicator.enabled:
            print("🎵 Visual wave indicator enabled")
        print("Press Ctrl+C to exit")
        print("=" * 60)
        
        # Show model info
        model_cfg = self.config.model
        print(f"\nLoading Whisper model: {model_cfg['size']}...")
        print(f"   Device: {model_cfg['device']}, Compute: {model_cfg['compute_type']}")
        
        # Model is already loaded in Transcriber.__init__
        print(f"\n✅ Ready! Press {shortcut} to start recording...")
        print("-" * 60)
        
        # Start keyboard listener
        self.keyboard_handler.start()

        try:
            if self.visual_indicator and self.visual_indicator.enabled:
                # Both visual_indicator backends (Tk's WaveIndicator and the
                # native macOS FloatingPanelIndicator built on AppKit) must
                # run their event loop on the main thread.
                self.visual_indicator.start_mainloop()
            else:
                self.keyboard_handler.join()
        except KeyboardInterrupt:
            pass
        finally:
            print("\n🛑 Shutting down...")
            if self.recorder.is_recording():
                self.recorder.stop_recording()
            self.keyboard_handler.stop()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Real-Time Transcription Tool"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    args = parser.parse_args()
    
    try:
        app = TranscriptionApp(config_path=args.config)
        app.run()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

