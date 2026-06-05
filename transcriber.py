#!/usr/bin/env python3
"""
Transcriber Module
Handles audio transcription using faster-whisper (CPU/CUDA) or mlx-whisper (Apple Silicon)
"""

import contextlib
import io
from typing import Tuple


# mlx-community HuggingFace repo mapping for each model size
_MLX_MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


class Transcriber:
    """Audio transcription using Whisper model."""

    def __init__(self, model_size: str, device: str = "cpu", compute_type: str = "int8"):
        """
        Initialize transcriber with Whisper model.

        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use ("cpu", "cuda", or "mlx" for Apple Silicon)
            compute_type: Compute type ("int8", "float16", "float32") — ignored for mlx
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._mlx_repo = None
        self._load_model()

    def _load_model(self):
        """Load Whisper model with fallback to CPU if needed."""
        if self.device == "mlx":
            self._mlx_repo = _MLX_MODEL_REPOS.get(
                self.model_size, f"mlx-community/whisper-{self.model_size}-mlx"
            )
            print(f"✅ MLX model configured: {self._mlx_repo} (Apple Silicon)")
            return

        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            print("✅ Model loaded!")
        except ValueError as e:
            if "unsupported device" in str(e).lower():
                print("⚠️  Device not supported, falling back to CPU...")
                from faster_whisper import WhisperModel
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
            beam_size: Beam search size (faster-whisper only; ignored for mlx)
            verbose: Whether to show verbose output

        Returns:
            Tuple of (transcribed_text, info_dict)
        """
        print("📝 Transcribing...")

        if self.device == "mlx":
            return self._transcribe_mlx(audio_file, language=language, verbose=verbose)

        return self._transcribe_faster_whisper(
            audio_file, language=language, beam_size=beam_size, verbose=verbose
        )

    def _transcribe_mlx(self, audio_file: str, language: str = "en", verbose: bool = False) -> Tuple[str, dict]:
        """Transcribe using mlx-whisper (Apple Silicon)."""
        try:
            import mlx_whisper
        except ImportError:
            raise ImportError(
                "mlx-whisper is required for Apple Silicon acceleration.\n"
                "Install it with: pip install mlx-whisper"
            )

        if not verbose:
            stdout_redirect = contextlib.redirect_stdout(io.StringIO())
            stderr_redirect = contextlib.redirect_stderr(io.StringIO())
        else:
            stdout_redirect = contextlib.nullcontext()
            stderr_redirect = contextlib.nullcontext()

        with stdout_redirect, stderr_redirect:
            result = mlx_whisper.transcribe(
                audio_file,
                path_or_hf_repo=self._mlx_repo,
                language=language if language != "auto" else None,
                verbose=verbose,
            )

        transcribed_text = result.get("text", "").strip()
        detected_language = result.get("language", language)

        print("✅ Transcription complete!")
        print(f"   Detected language: {detected_language}")
        print(f"   Transcribed text: {transcribed_text}")
        print("-" * 60)

        return transcribed_text, {
            'language': detected_language,
            'language_probability': 1.0,
        }

    def _transcribe_faster_whisper(
        self, audio_file: str, language: str = "en", beam_size: int = 5, verbose: bool = False
    ) -> Tuple[str, dict]:
        """Transcribe using faster-whisper (CPU/CUDA)."""
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
