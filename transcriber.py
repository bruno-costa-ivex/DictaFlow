#!/usr/bin/env python3
"""
Transcriber Module
Handles audio transcription using faster-whisper
"""

import contextlib
import io
from faster_whisper import WhisperModel
from typing import Tuple


class Transcriber:
    """Audio transcription using Whisper model."""
    
    def __init__(self, model_size: str, device: str = "cpu", compute_type: str = "int8"):
        """
        Initialize transcriber with Whisper model.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use ("cpu" or "cuda")
            compute_type: Compute type ("int8", "float16", "float32")
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model with fallback to CPU if needed."""
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            print("✅ Model loaded!")
        except ValueError as e:
            if "unsupported device" in str(e).lower():
                print("⚠️  Device not supported, falling back to CPU...")
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                print("✅ Model loaded on CPU!")
            else:
                raise
    
    def transcribe(
        self,
        audio_file: str,
        language: str = "en",
        beam_size: int = 5,
        verbose: bool = False
    ) -> Tuple[str, dict]:
        """
        Transcribe audio file.
        
        Args:
            audio_file: Path to audio file
            language: Language code (e.g., "en", "es", "fr", "auto" for auto-detect)
            beam_size: Beam search size
            verbose: Whether to show verbose output
            
        Returns:
            Tuple of (transcribed_text, info_dict)
        """
        print("📝 Transcribing...")
        
        # Suppress output during transcription if not verbose
        if not verbose:
            stdout_redirect = contextlib.redirect_stdout(io.StringIO())
            stderr_redirect = contextlib.redirect_stderr(io.StringIO())
        else:
            stdout_redirect = contextlib.nullcontext()
            stderr_redirect = contextlib.nullcontext()
        
        with stdout_redirect, stderr_redirect:
            try:
                segments, info = self.model.transcribe(
                    audio_file,
                    beam_size=beam_size,
                    language=language if language != "auto" else None,
                    verbose=verbose
                )
            except TypeError:
                # verbose parameter might not be available in some versions
                segments, info = self.model.transcribe(
                    audio_file,
                    beam_size=beam_size,
                    language=language if language != "auto" else None
                )
        
        # Collect text from segments
        text_parts = []
        try:
            for segment in segments:
                text = segment.text.strip()
                if text:
                    text_parts.append(text)
        except RuntimeError as e:
            error_msg = str(e)
            if "libcublas.so.12" in error_msg or "cublas" in error_msg.lower():
                print("\n❌ CUDA Library Error:")
                print("   faster-whisper requires libcublas.so.12 but your system has CUDA 13.0")
                print("   Run the setup script to create compatibility symlink:")
                print("   ./setup_cuda_libs.sh")
                print("   Or manually create: sudo ln -s /usr/local/cuda-13.0/targets/x86_64-linux/lib/libcublas.so.13 /usr/local/cuda-13.0/targets/x86_64-linux/lib/libcublas.so.12")
                raise RuntimeError("CUDA library compatibility issue. See instructions above.") from e
            raise
        
        transcribed_text = " ".join(text_parts).strip()
        
        print("✅ Transcription complete!")
        print(f"   Detected language: {info.language} (probability: {info.language_probability:.2f})")
        print(f"   Transcribed text: {transcribed_text}")
        print("-" * 60)
        
        return transcribed_text, {
            'language': info.language,
            'language_probability': info.language_probability
        }

