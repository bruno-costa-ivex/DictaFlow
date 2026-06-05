#!/usr/bin/env python3
"""
Keyboard Handler Module
Handles keyboard events for recording trigger
"""

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
            modifier_key: Modifier key name ("alt", "ctrl", "shift", "super", "cmd")
            trigger_key: Trigger key character (e.g., "w")
            on_start: Callback function when recording should start
            on_stop: Callback function when recording should stop
        """
        self.modifier_key = modifier_key.lower()
        self.trigger_key = trigger_key.lower()
        self.on_start = on_start
        self.on_stop = on_stop
        
        # State tracking
        self.modifier_pressed = False
        self.trigger_pressed = False
        self.is_recording = False
        
        # Get modifier key objects
        if self.modifier_key not in self.MODIFIER_KEYS:
            raise ValueError(
                f"Invalid modifier key: {modifier_key}\n"
                f"Valid options: {', '.join(self.MODIFIER_KEYS.keys())}"
            )
        
        self.modifier_keys = self.MODIFIER_KEYS[self.modifier_key]
        self.listener = None
    
    def _on_key_press(self, key):
        """Handle key press events."""
        try:
            # Check for modifier key
            if key in self.modifier_keys:
                self.modifier_pressed = True
            # Check for trigger key
            elif hasattr(key, 'char') and key.char and key.char.lower() == self.trigger_key:
                self.trigger_pressed = True
            
            # Start recording when both keys are pressed
            if self.modifier_pressed and self.trigger_pressed and not self.is_recording:
                self.is_recording = True
                if self.on_start:
                    self.on_start()
        except AttributeError:
            pass
    
    def _on_key_release(self, key):
        """Handle key release events."""
        try:
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
                # If recording, stop and process
                if self.is_recording:
                    self.is_recording = False
                    if self.on_stop:
                        self.on_stop()
        except AttributeError:
            pass
    
    def start(self):
        """Start listening for keyboard events."""
        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.listener.start()
    
    def stop(self):
        """Stop listening for keyboard events."""
        if self.listener:
            self.listener.stop()
    
    def join(self):
        """Wait for the listener thread to finish."""
        if self.listener:
            self.listener.join()

