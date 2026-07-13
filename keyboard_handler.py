#!/usr/bin/env python3
"""
Keyboard Handler Module
Handles keyboard events for recording trigger
"""

import sys
from pynput import keyboard
from typing import Callable, Optional


class KeyboardHandler:
    """Keyboard event handler for recording triggers."""
    
    # Key mapping
    MODIFIER_KEYS = {
        "alt": [keyboard.Key.alt_l, keyboard.Key.alt_r],
        "ctrl": [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r],
        "shift": [keyboard.Key.shift_l, keyboard.Key.shift_r],
        "super": [keyboard.Key.cmd_l, keyboard.Key.cmd_r],
        "cmd": [keyboard.Key.cmd_l, keyboard.Key.cmd_r],  # macOS Command key
    }

    # Solo-key triggers: hold this ONE physical key by itself — no separate
    # letter needed, no combo to suppress. Deliberately scoped to a single
    # side rather than "either alt_l or alt_r" like MODIFIER_KEYS above:
    # holding the *left* copy of a modifier alone happens constantly as a
    # side effect of ordinary shortcuts (Cmd+C, Cmd+Tab, Ctrl+click, ...),
    # but holding the *right* copy alone essentially never does. This is the
    # same trick macOS's own built-in dictation trigger relies on.
    SOLO_KEYS = {
        "right_cmd": keyboard.Key.cmd_r,
        "right_alt": keyboard.Key.alt_r,
        "right_ctrl": keyboard.Key.ctrl_r,
        "right_shift": keyboard.Key.shift_r,
        "left_cmd": keyboard.Key.cmd_l,
        "left_alt": keyboard.Key.alt_l,
        "left_ctrl": keyboard.Key.ctrl_l,
        "left_shift": keyboard.Key.shift_l,
    }

    def __init__(
        self,
        modifier_key: str = "alt",
        trigger_key: str = "w",
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None
    ):
        """
        Initialize keyboard handler.

        Args:
            modifier_key: Either a combo modifier ("alt", "ctrl", "shift",
                "super", "cmd" — used together with trigger_key), or, when
                trigger_key is empty, a solo key ("right_cmd", "right_alt",
                "right_ctrl", "right_shift", "left_cmd", "left_alt",
                "left_ctrl", "left_shift") held by itself.
            trigger_key: Trigger key character (e.g., "w") for combo mode.
                Leave empty ("") to use solo-key mode instead.
            on_start: Callback function when recording should start
            on_stop: Callback function when recording should stop
        """
        self.modifier_key = modifier_key.lower()
        self.trigger_key = (trigger_key or "").lower()
        self.on_start = on_start
        self.on_stop = on_stop

        self.solo_mode = not self.trigger_key

        # State tracking
        self.modifier_pressed = False
        self.trigger_pressed = False
        self.is_recording = False

        # macOS only, combo mode only: whether the trigger key currently
        # being held down was recognized as part of our combo (modifier held
        # at press time), and whether the raw keystroke pynput is about to
        # hand back to the OS should be swallowed so it doesn't also fire the
        # frontmost app's own binding for it (e.g. Ctrl+W closing a browser
        # tab). Not needed in solo mode: holding one right-side modifier key
        # alone isn't bound to anything, so there's nothing to suppress.
        self._combo_key_active = False
        self._suppress_current_event = False

        if self.solo_mode:
            if self.modifier_key not in self.SOLO_KEYS:
                raise ValueError(
                    f"Invalid solo key: {modifier_key}\n"
                    f"With trigger_key empty, modifier_key must be one of: "
                    f"{', '.join(self.SOLO_KEYS.keys())}"
                )
            self.solo_key = self.SOLO_KEYS[self.modifier_key]
            self.modifier_keys = [self.solo_key]
        else:
            if self.modifier_key not in self.MODIFIER_KEYS:
                raise ValueError(
                    f"Invalid modifier key: {modifier_key}\n"
                    f"Valid options: {', '.join(self.MODIFIER_KEYS.keys())}"
                )
            self.modifier_keys = self.MODIFIER_KEYS[self.modifier_key]

        self.listener = None
    
    def _on_key_press(self, key):
        """Handle key press events."""
        if self.solo_mode:
            if key == self.solo_key and not self.is_recording:
                self.is_recording = True
                if self.on_start:
                    self.on_start()
            return

        try:
            self._suppress_current_event = False
            # Check for modifier key
            if key in self.modifier_keys:
                self.modifier_pressed = True
            # Check for trigger key
            elif hasattr(key, 'char') and key.char and key.char.lower() == self.trigger_key:
                self.trigger_pressed = True
                if self.modifier_pressed:
                    self._combo_key_active = True
                self._suppress_current_event = self._combo_key_active

            # Start recording when both keys are pressed
            if self.modifier_pressed and self.trigger_pressed and not self.is_recording:
                self.is_recording = True
                if self.on_start:
                    self.on_start()
        except AttributeError:
            pass

    def _on_key_release(self, key):
        """Handle key release events."""
        if self.solo_mode:
            if key == self.solo_key and self.is_recording:
                self.is_recording = False
                if self.on_stop:
                    self.on_stop()
            return

        try:
            self._suppress_current_event = False
            # Check for modifier key
            if key in self.modifier_keys:
                self.modifier_pressed = False
                # If recording, stop and process
                if self.is_recording:
                    self.is_recording = False
                    if self.on_stop:
                        self.on_stop()
            # Check for trigger key
            elif hasattr(key, 'char') and key.char and key.char.lower() == self.trigger_key:
                self.trigger_pressed = False
                self._suppress_current_event = self._combo_key_active
                self._combo_key_active = False
                # If recording, stop and process
                if self.is_recording:
                    self.is_recording = False
                    if self.on_stop:
                        self.on_stop()
        except AttributeError:
            pass

    def _darwin_intercept(self, event_type, event):
        """Swallow our hotkey's raw keystroke system-wide (macOS only).

        Without this, `pynput.keyboard.Listener` only *monitors* key events —
        it still forwards them to the frontmost app, which then also runs its
        own binding for the same combo (e.g. Ctrl+W closing a browser tab or
        Ctrl+Q quitting an app). This runs synchronously right after
        `_on_key_press`/`_on_key_release` for the very same event (pynput
        calls them from the same tap callback, in that order), so the flag
        set there is fresh. Returning anything other than `event` tells
        pynput to suppress it; returning `event` passes it through unchanged,
        which is what happens for every other keystroke on the system.
        """
        if self._suppress_current_event:
            self._suppress_current_event = False
            return None
        return event

    def start(self):
        """Start listening for keyboard events."""
        listener_kwargs = {
            "on_press": self._on_key_press,
            "on_release": self._on_key_release,
        }
        # Solo mode never sets _suppress_current_event, so there's nothing to
        # swallow — skip darwin_intercept and stay in lightweight listen-only
        # mode rather than paying for a blocking event tap for no reason.
        if sys.platform == "darwin" and not self.solo_mode:
            listener_kwargs["darwin_intercept"] = self._darwin_intercept

        self.listener = keyboard.Listener(**listener_kwargs)
        self.listener.start()
    
    def stop(self):
        """Stop listening for keyboard events."""
        if self.listener:
            self.listener.stop()
    
    def join(self):
        """Wait for the listener thread to finish."""
        if self.listener:
            self.listener.join()

