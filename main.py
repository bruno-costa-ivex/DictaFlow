#!/usr/bin/env python3
"""
Real-Time Transcription Tool - Main Entry Point
Press and hold Alt+W (or configured shortcut) to record, release to transcribe.
"""

import tempfile
import os
import sys
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
    import shutil
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

from config import Config
from audio_recorder import AudioRecorder
from transcriber import Transcriber
from keyboard_handler import KeyboardHandler
from text_inserter import TextInserter
from notifier import Notifier
from visual_indicator import get_indicator


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
            on_level_update=self._on_audio_level_update
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

    def _on_audio_level_update(self, level: float):
        """Callback for real-time audio level updates."""
        if self.visual_indicator:
            self.visual_indicator.set_audio_level(level)

    def _on_recording_start(self):
        """Callback when recording should start."""
        # Show visual indicator immediately
        if self.visual_indicator:
            self.visual_indicator.show("recording")

        self.recorder.start_recording()
    
    def _on_recording_stop(self):
        """Callback when recording should stop."""
        # Change visual indicator to processing state
        if self.visual_indicator:
            self.visual_indicator.set_state("processing")

        self._process_recording()
    
    def _process_recording(self):
        """Process the recorded audio: save and transcribe."""
        audio_data = self.recorder.stop_recording()
        
        if audio_data is None or len(audio_data) == 0:
            print("⚠️  No audio recorded.")
            return
        
        # Save to temporary file for transcription
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
            
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

            # Hide visual indicator
            if self.visual_indicator:
                self.visual_indicator.set_state("complete")
                # Hide after a brief moment
                import time
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
        
        print(f"Press and hold {modifier}+{trigger} to record")
        print(f"Release {modifier}+{trigger} to stop and transcribe")
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
        print("\n✅ Ready! Press {}+{} to start recording...".format(modifier, trigger))
        print("-" * 60)
        
        # Start keyboard listener
        self.keyboard_handler.start()
        
        try:
            # Keep the program running
            self.keyboard_handler.join()
        except KeyboardInterrupt:
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

