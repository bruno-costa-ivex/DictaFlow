#!/usr/bin/env python3
"""
Text Inserter Module
Types transcribed text at the current cursor position
"""

import sys
import time
from pynput.keyboard import Controller, Key

# macOS uses Cmd+V to paste; Linux/Windows use Ctrl+V
_PASTE_KEY = Key.cmd if sys.platform == "darwin" else Key.ctrl


class TextInserter:
    """Types text at the current cursor position using keyboard simulation."""
    
    def __init__(self, typing_delay: float = 0.01, auto_capitalize: bool = True):
        """
        Initialize text inserter.
        
        Args:
            typing_delay: Delay between keystrokes in seconds (for reliability)
            auto_capitalize: Automatically capitalize first letter of sentences
        """
        self.keyboard = Controller()
        self.typing_delay = typing_delay
        self.auto_capitalize = auto_capitalize
    
    def insert_text(self, text: str, add_period: bool = False):
        """
        Insert text at the current cursor position.
        
        Args:
            text: Text to insert
            add_period: Add a period at the end if text doesn't end with punctuation
        """
        if not text or not text.strip():
            return
        
        # Clean and prepare text
        text = text.strip()
        
        # Auto-capitalize first letter if enabled
        if self.auto_capitalize and text:
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        
        # Add period if requested and text doesn't end with punctuation
        if add_period and text and text[-1] not in '.!?':
            text += '.'
        
        # Type the text character by character
        # This ensures it works in any application
        for char in text:
            try:
                if char == '\n':
                    # Handle newline
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
                elif char == '\t':
                    # Handle tab
                    self.keyboard.press(Key.tab)
                    self.keyboard.release(Key.tab)
                else:
                    # Type regular character
                    self.keyboard.type(char)
                
                # Small delay for reliability
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay)
            except Exception as e:
                print(f"⚠️  Error typing character '{char}': {e}")
                # Continue with next character
    
    def insert_with_shortcut(self, text: str, use_ctrl_v: bool = False):
        """
        Insert text using clipboard (Ctrl+V) method.
        This is more reliable in some applications.
        
        Args:
            text: Text to insert
            use_ctrl_v: Use Ctrl+V method instead of direct typing
        """
        if not text or not text.strip():
            return
        
        if use_ctrl_v:
            # Use clipboard method
            try:
                import pyperclip
                # Save current clipboard
                try:
                    old_clipboard = pyperclip.paste()
                except Exception:
                    old_clipboard = None
                
                # Set new text to clipboard
                pyperclip.copy(text.strip())
                
                # Paste using Cmd+V (macOS) or Ctrl+V (Linux/Windows)
                self.keyboard.press(_PASTE_KEY)
                self.keyboard.press('v')
                self.keyboard.release('v')
                self.keyboard.release(_PASTE_KEY)
                
                # Small delay
                time.sleep(0.1)
                
                # Restore old clipboard if possible
                if old_clipboard:
                    try:
                        time.sleep(0.05)
                        pyperclip.copy(old_clipboard)
                    except Exception:
                        pass
            except ImportError:
                print("⚠️  pyperclip not available, falling back to direct typing")
                self.insert_text(text)
            except Exception as e:
                print(f"⚠️  Error using clipboard method: {e}")
                # Fallback to direct typing
                self.insert_text(text)
        else:
            # Use direct typing
            self.insert_text(text)

