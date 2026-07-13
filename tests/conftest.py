"""
Shared test setup for DictaFlow unit tests.

DictaFlow depends on OS-bound / heavy packages (pynput, pyperclip, mlx-whisper)
that are awkward to install in CI and require accessibility permissions on macOS.
We stub them here *before* the project modules import them, so the unit tests
exercise the real DictaFlow logic without those packages being installed.

The stubs are intentionally faithful to the small surface DictaFlow uses:
distinct sentinel objects for each key, a Controller that records press/release
calls, and a Listener that does nothing.
"""

import sys
import types
from pathlib import Path

# Make the project root importable (tests/ lives one level below it).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _Key:
    """A unique, hashable sentinel standing in for a pynput Key enum member."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<Key.{self.name}>"


class _StubController:
    """Records key presses/releases so tests can assert on them."""

    def __init__(self):
        self.events = []  # list of (action, key) tuples

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))

    def type(self, text):
        self.events.append(("type", text))


class _StubListener:
    def __init__(self, on_press=None, on_release=None):
        self.on_press = on_press
        self.on_release = on_release
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def join(self):
        pass


def _build_keyboard_module():
    """Construct a stand-in for `pynput.keyboard`."""
    keyboard = types.ModuleType("pynput.keyboard")

    class Key:
        # modifiers used by keyboard_handler.MODIFIER_KEYS
        alt_l = _Key("alt_l")
        alt_r = _Key("alt_r")
        ctrl_l = _Key("ctrl_l")
        ctrl_r = _Key("ctrl_r")
        shift_l = _Key("shift_l")
        shift_r = _Key("shift_r")
        cmd_l = _Key("cmd_l")
        cmd_r = _Key("cmd_r")
        # single-key paste modifiers used by text_inserter
        ctrl = _Key("ctrl")
        cmd = _Key("cmd")
        # special keys used by text_inserter direct typing
        enter = _Key("enter")
        tab = _Key("tab")

    keyboard.Key = Key
    keyboard.Controller = _StubController
    keyboard.Listener = _StubListener
    return keyboard


def _stub_pynput():
    pynput = types.ModuleType("pynput")
    keyboard = _build_keyboard_module()
    pynput.keyboard = keyboard
    sys.modules["pynput"] = pynput
    sys.modules["pynput.keyboard"] = keyboard


def _stub_pyperclip():
    pyperclip = types.ModuleType("pyperclip")
    clipboard = {"value": ""}
    pyperclip.copy = lambda text: clipboard.__setitem__("value", text)
    pyperclip.paste = lambda: clipboard["value"]
    pyperclip._clipboard = clipboard  # exposed for assertions
    sys.modules["pyperclip"] = pyperclip


# Only stub the modules that aren't actually installed, so a fully-provisioned
# machine can run the same tests against the real packages if it has them.
def _ensure(name, stub):
    try:
        __import__(name)
    except ImportError:
        stub()


_ensure("pynput", _stub_pynput)
_ensure("pyperclip", _stub_pyperclip)
