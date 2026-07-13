# Changelog

All notable changes to DictaFlow are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Poetry-based dependency management (`pyproject.toml` / `poetry.lock`), replacing manual `venv` + `requirements.txt`.
- Solo-key trigger mode (hold one modifier key alone, e.g. `right_cmd`) as the new macOS default, avoiding the reliability problems of suppressing a modifier+letter combo's keystroke from leaking to other apps.
- Native macOS visual indicator (`FloatingPanelIndicator`, a non-activating `NSPanel` built directly on AppKit/PyObjC) replacing the Tkinter overlay on macOS, which could steal focus and trigger a Space switch away from full-screen apps. Tkinter's `WaveIndicator` remains the backend on Linux.
- RAM usage readout in the visual indicator.
- Configurable audio input device pinning (`audio.input_device`), so recording doesn't silently follow whichever device macOS currently considers the default.
- Transcription requests are now serialized via a lock, preventing concurrent `mlx_whisper` calls from crashing when the trigger is pressed again before a previous transcription finishes.
- Desktop notifications (`notifier.py`) are now actually wired up to recording-start/stop/transcription-complete events, respecting `config.yaml`'s toggles.
- `ruff` lint step in CI, plus a local `poetry run ruff check .` command.
- Expanded test coverage: config validation, audio device resolution, and `TranscriptionApp` orchestration (including the new transcription lock).

### Changed
- `main.py`'s recording-start/stop callbacks and the transcription pipeline now catch and report failures (e.g. a disconnected microphone, a failed model download) instead of silently killing the keyboard listener or leaving the visual indicator stuck.
- CI workflow now also runs on pushes to `main`, not only on pull requests.

### Fixed
- Various stale documentation and comments left over from earlier iterations (Alt+W-only keybinding docs, Tkinter-only assumptions, a nonexistent `./setup_cuda_libs.sh` reference).
