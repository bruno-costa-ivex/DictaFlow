#!/usr/bin/env python3
"""
Visual Indicator Module
Displays an animated audio wave overlay while recording
"""

import threading
import math
import random
import time

try:
    import tkinter as tk
    from tkinter import font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False


class WaveIndicator:
    """Animated wave overlay that appears during recording."""

    def __init__(self, position: str = "center", width: int = 340, height: int = 80):
        if not HAS_TK:
            print("Warning: tkinter not available, visual indicator disabled")
            self.enabled = False
            return

        self.enabled = True
        self.width = width
        self.height = height
        self.position = position

        self._root = None
        self._canvas = None
        self._is_visible = False
        self._phase = 0.0
        self._audio_level = 0.0
        self._target_level = 0.0
        self._state = "idle"
        self._running = False
        self._dots_phase = 0

        # Timing
        self._start_time = 0.0
        self._elapsed_time = 0.0

        # Fade animation
        self._opacity = 0.0
        self._target_opacity = 0.0
        self._fade_speed = 0.15

        # Wave parameters
        self._num_bars = 20  # Fewer bars = thicker bars
        self._bar_heights = [0.0] * self._num_bars
        self._target_heights = [0.0] * self._num_bars

        # Spinner for transcribing
        self._spinner_angle = 0.0

        # Modern color palette
        self._colors = {
            "recording": "#ef4444",      # Red
            "recording_glow": "#f87171",
            "recording_dim": "#dc2626",
            "processing": "#8b5cf6",     # Purple
            "processing_glow": "#a78bfa",
            "complete": "#10b981",       # Green
            "bg": "#18181b",             # Zinc 900
            "bg_border": "#3f3f46",      # Zinc 700
            "text": "#fafafa",           # Zinc 50
            "text_dim": "#a1a1aa",       # Zinc 400
        }

        # Start tk thread
        self._tk_ready = threading.Event()
        self._tk_thread = threading.Thread(target=self._tk_main, daemon=True)
        self._tk_thread.start()
        self._tk_ready.wait(timeout=2.0)

    def _tk_main(self):
        """Run tkinter main loop in separate thread."""
        try:
            self._root = tk.Tk()
            self._root.withdraw()

            # Frameless floating window
            self._root.overrideredirect(True)
            self._root.attributes('-topmost', True)
            try:
                self._root.attributes('-alpha', 0.0)
            except:
                pass

            self._root.configure(bg=self._colors["bg"])
            self._root.geometry(f"{self.width}x{self.height}")
            self._position_window()

            # Create canvas
            self._canvas = tk.Canvas(
                self._root,
                width=self.width,
                height=self.height,
                bg=self._colors["bg"],
                highlightthickness=0
            )
            self._canvas.pack()

            # Load font
            try:
                self._font = tkfont.Font(family="Ubuntu", size=11, weight="bold")
                self._font_small = tkfont.Font(family="Ubuntu", size=9)
                self._font_timer = tkfont.Font(family="Ubuntu Mono", size=10, weight="bold")
            except:
                self._font = tkfont.Font(family="Sans", size=11, weight="bold")
                self._font_small = tkfont.Font(family="Sans", size=9)
                self._font_timer = tkfont.Font(family="Monospace", size=10, weight="bold")

            self._running = True
            self._tk_ready.set()
            self._animate()
            self._root.mainloop()

        except Exception as e:
            print(f"Tkinter error: {e}")
            self.enabled = False
            self._tk_ready.set()

    def _position_window(self):
        """Position the window."""
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()

        if "center" in self.position:
            x = (screen_width - self.width) // 2
        elif "right" in self.position:
            x = screen_width - self.width - 40
        else:
            x = 40

        if "top" in self.position:
            y = 50
        elif "bottom" in self.position:
            y = screen_height - self.height - 60
        else:
            y = (screen_height - self.height) // 2

        self._root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, fill, outline=None, width=1, tags=""):
        """Draw a rounded rectangle."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self._canvas.create_polygon(
            points, fill=fill, outline=outline or fill,
            width=width, smooth=True, tags=tags
        )

    def _draw_frame(self):
        """Draw the window frame/background."""
        if not self._canvas:
            return

        self._canvas.delete("frame")

        # Main background with border
        self._draw_rounded_rect(
            1, 1, self.width - 1, self.height - 1,
            radius=16,
            fill=self._colors["bg"],
            outline=self._colors["bg_border"],
            width=1,
            tags="frame"
        )

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    def _draw_recording_ui(self):
        """Draw the recording UI with wave visualization."""
        if not self._canvas:
            return

        self._canvas.delete("content")

        color = self._colors["recording"]

        # Wave bars - centered waveform (full height, no header)
        padding = 20
        bar_area_width = self.width - padding * 2
        bar_width = bar_area_width / self._num_bars
        spacing = 3  # More spacing for thicker bars
        center_y = self.height // 2
        max_height = self.height - 20

        for i, bar_height in enumerate(self._bar_heights):
            x = padding + i * bar_width
            h = max(6, bar_height * max_height)

            x1 = x + spacing / 2
            x2 = x + bar_width - spacing / 2
            y1 = center_y - h / 2
            y2 = center_y + h / 2

            # Color gradient based on height
            intensity = min(1.0, bar_height * 1.5)
            if intensity > 0.5:
                bar_color = self._colors["recording_glow"]
            else:
                bar_color = color

            # Draw rounded bar (thicker)
            bar_radius = min((x2 - x1) / 2, 4)
            self._draw_rounded_rect(
                x1, y1, x2, y2,
                radius=bar_radius,
                fill=bar_color,
                tags="content"
            )

    def _draw_transcribing_ui(self):
        """Draw the transcribing UI with spinner."""
        if not self._canvas:
            return

        self._canvas.delete("content")

        center_x = self.width // 2
        center_y = self.height // 2

        # Draw spinning arc
        spinner_radius = 16
        arc_extent = 90

        self._canvas.create_arc(
            center_x - 50 - spinner_radius,
            center_y - spinner_radius,
            center_x - 50 + spinner_radius,
            center_y + spinner_radius,
            start=self._spinner_angle,
            extent=arc_extent,
            style="arc",
            outline=self._colors["processing"],
            width=3,
            tags="content"
        )

        # Background circle
        self._canvas.create_oval(
            center_x - 50 - spinner_radius + 2,
            center_y - spinner_radius + 2,
            center_x - 50 + spinner_radius - 2,
            center_y + spinner_radius - 2,
            outline=self._colors["bg_border"],
            width=1,
            tags="content"
        )

        # "Transcribing" text with animated dots
        dots = "." * ((self._dots_phase % 4))
        text = f"Transcribing{dots}"

        self._canvas.create_text(
            center_x + 10, center_y,
            text=text,
            font=self._font,
            fill=self._colors["text"],
            anchor="w",
            tags="content"
        )

    def _draw_complete_ui(self):
        """Draw completion feedback."""
        if not self._canvas:
            return

        self._canvas.delete("content")

        center_x = self.width // 2
        center_y = self.height // 2

        # Checkmark circle
        radius = 18
        self._canvas.create_oval(
            center_x - 50 - radius, center_y - radius,
            center_x - 50 + radius, center_y + radius,
            fill=self._colors["complete"],
            outline="",
            tags="content"
        )

        # Checkmark
        cx, cy = center_x - 50, center_y
        self._canvas.create_line(
            cx - 8, cy,
            cx - 2, cy + 6,
            cx + 10, cy - 6,
            fill=self._colors["bg"],
            width=3,
            capstyle="round",
            joinstyle="round",
            tags="content"
        )

        # "Done" text
        self._canvas.create_text(
            center_x + 10, center_y,
            text="Done!",
            font=self._font,
            fill=self._colors["complete"],
            anchor="w",
            tags="content"
        )

    def _update_opacity(self):
        """Update window opacity for fade effect."""
        if not self._root:
            return

        # Smooth opacity interpolation
        diff = self._target_opacity - self._opacity
        if abs(diff) > 0.01:
            self._opacity += diff * self._fade_speed
            try:
                self._root.attributes('-alpha', self._opacity)
            except:
                pass
        else:
            self._opacity = self._target_opacity

    def _animate(self):
        """Animation tick - runs at ~60fps."""
        if not self._running:
            return

        # Update fade
        self._update_opacity()

        if self._is_visible or self._opacity > 0.01:
            self._phase += 0.12
            self._dots_phase = int(self._phase * 1.5) % 4
            self._spinner_angle = (self._spinner_angle + 8) % 360

            self._draw_frame()

            if self._state == "recording":
                # Fast, aggressive audio level response
                self._audio_level += (self._target_level - self._audio_level) * 0.5

                # Wave frequency increases aggressively with audio level
                base_freq = 0.5
                audio_freq_boost = self._audio_level * 3.0
                wave_freq = base_freq + audio_freq_boost

                center = self._num_bars / 2
                for i in range(self._num_bars):
                    # Bell curve - center bars are taller based on audio level
                    dist_from_center = abs(i - center) / center
                    bell_curve = math.exp(-2.5 * dist_from_center * dist_from_center)

                    # Aggressive sine wave modulation
                    wave_offset = math.sin(self._phase * wave_freq + i * 0.4) * 0.25 * self._audio_level

                    # Height based on audio level - more dramatic response
                    base_height = 0.08 + self._audio_level * 0.92 * bell_curve + wave_offset

                    # More variation for dynamic feel
                    noise = random.uniform(-0.04, 0.04) * self._audio_level

                    self._target_heights[i] = max(0.05, min(0.98, base_height + noise))

                # Faster interpolation for snappier response
                for i in range(self._num_bars):
                    self._bar_heights[i] += (self._target_heights[i] - self._bar_heights[i]) * 0.4

                self._draw_recording_ui()

            elif self._state == "processing":
                self._draw_transcribing_ui()

            elif self._state == "complete":
                self._draw_complete_ui()

        # Hide window when fully faded out
        if self._opacity < 0.01 and not self._is_visible:
            if self._root:
                try:
                    self._root.withdraw()
                except:
                    pass
            self._bar_heights = [0.0] * self._num_bars
            self._target_heights = [0.0] * self._num_bars

        if self._root:
            self._root.after(16, self._animate)  # ~60fps

    def set_audio_level(self, level: float):
        """Update audio level (0.0 to 1.0)."""
        self._target_level = max(0.0, min(1.0, level))

    def show(self, state: str = "recording"):
        """Show the indicator with fade-in."""
        if not self.enabled or not self._root:
            return

        self._state = state
        self._target_level = 0.15
        self._is_visible = True
        self._phase = 0.0
        self._target_opacity = 0.95
        self._start_time = time.time()

        def _show():
            if self._root:
                self._root.deiconify()
                self._root.lift()
                self._root.attributes('-topmost', True)

        self._root.after(0, _show)

    def hide(self):
        """Hide the indicator with fade-out."""
        if not self.enabled or not self._root:
            return

        self._is_visible = False
        self._target_opacity = 0.0

    def set_state(self, state: str):
        """Change visual state (recording, processing, complete)."""
        self._state = state

    def destroy(self):
        """Clean up resources."""
        self._running = False
        if self._root:
            try:
                self._root.quit()
            except:
                pass


_indicator = None


def get_indicator(**kwargs) -> WaveIndicator:
    """Get or create the wave indicator singleton."""
    global _indicator
    if _indicator is None:
        _indicator = WaveIndicator(**kwargs)
    return _indicator
