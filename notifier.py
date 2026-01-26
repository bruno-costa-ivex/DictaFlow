#!/usr/bin/env python3
"""
Notifier Module
Handles desktop notifications for DictaFlow events
"""

import subprocess
import shutil

# Try to import desktop-notifier, fall back to notify-send
try:
    from desktop_notifier import DesktopNotifier, Urgency
    HAS_DESKTOP_NOTIFIER = True
except ImportError:
    HAS_DESKTOP_NOTIFIER = False


class Notifier:
    """Desktop notification manager for DictaFlow."""

    APP_NAME = "DictaFlow"

    def __init__(self, enabled: bool = True):
        """
        Initialize notifier.

        Args:
            enabled: Whether notifications are enabled
        """
        self.enabled = enabled
        self._notifier = None
        self._has_notify_send = False

        if self.enabled:
            self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the notification backend."""
        if HAS_DESKTOP_NOTIFIER:
            try:
                self._notifier = DesktopNotifier(app_name=self.APP_NAME)
            except Exception as e:
                print(f"Warning: Could not initialize desktop-notifier: {e}")
                self._notifier = None

        # Check for notify-send fallback
        self._has_notify_send = shutil.which("notify-send") is not None

    def _send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal"
    ) -> bool:
        """
        Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body
            urgency: Urgency level ("low", "normal", "critical")

        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            return False

        # Try desktop-notifier first
        if self._notifier is not None:
            try:
                import asyncio

                # Map urgency to desktop-notifier Urgency
                urgency_map = {
                    "low": Urgency.Low,
                    "normal": Urgency.Normal,
                    "critical": Urgency.Critical,
                }

                # Run async notification synchronously
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None:
                    # If there's already a running loop, schedule the coroutine
                    asyncio.ensure_future(
                        self._notifier.send(
                            title=title,
                            message=message,
                            urgency=urgency_map.get(urgency, Urgency.Normal)
                        )
                    )
                else:
                    # No running loop, create one
                    asyncio.run(
                        self._notifier.send(
                            title=title,
                            message=message,
                            urgency=urgency_map.get(urgency, Urgency.Normal)
                        )
                    )
                return True
            except Exception:
                # Fall through to notify-send
                pass

        # Fallback to notify-send
        if self._has_notify_send:
            try:
                subprocess.run(
                    [
                        "notify-send",
                        "--app-name", self.APP_NAME,
                        "--urgency", urgency,
                        title,
                        message
                    ],
                    check=False,
                    capture_output=True,
                    timeout=5
                )
                return True
            except Exception:
                pass

        return False

    def notify_recording_started(self):
        """Show notification when recording starts."""
        self._send_notification(
            title="Recording Started",
            message="Listening for speech...",
            urgency="low"
        )

    def notify_recording_stopped(self):
        """Show notification when recording stops."""
        self._send_notification(
            title="Recording Stopped",
            message="Processing audio...",
            urgency="low"
        )

    def notify_transcription_complete(self, text: str, max_preview_length: int = 100):
        """
        Show notification when transcription completes.

        Args:
            text: The transcribed text
            max_preview_length: Maximum length of text preview in notification
        """
        if not text or not text.strip():
            preview = "(No text transcribed)"
        else:
            preview = text.strip()
            if len(preview) > max_preview_length:
                preview = preview[:max_preview_length - 3] + "..."

        self._send_notification(
            title="Transcription Complete",
            message=preview,
            urgency="normal"
        )
