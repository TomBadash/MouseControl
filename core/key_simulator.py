"""
Keyboard and mouse action simulator using Windows SendInput API.
Supports key combos (e.g. Alt+Tab), single keys, media keys,
and browser navigation keys.
"""

import ctypes
import ctypes.wintypes as wintypes
import time
from ctypes import Structure, Union, c_ulong, c_ushort, c_long, sizeof

# --- Input structures for SendInput ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

# Virtual key codes
VK_MENU = 0x12        # Alt
VK_TAB = 0x09         # Tab
VK_LMENU = 0xA4       # Left Alt
VK_SHIFT = 0x10       # Shift
VK_CONTROL = 0x11     # Ctrl
VK_LWIN = 0x5B        # Left Windows key
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E
VK_BACK = 0x08        # Backspace

# Browser / app keys
VK_BROWSER_BACK = 0xA6
VK_BROWSER_FORWARD = 0xA7
VK_BROWSER_REFRESH = 0xA8
VK_BROWSER_STOP = 0xA9
VK_BROWSER_HOME = 0xAC

# Media keys
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# F keys
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B

# Copy / Paste shortcuts — we simulate Ctrl+C etc. as combos
VK_C = 0x43
VK_V = 0x56
VK_X = 0x58
VK_Z = 0x5A
VK_A = 0x41
VK_S = 0x53
VK_W = 0x57
VK_T = 0x54
VK_N = 0x4E
VK_F = 0x46
VK_D = 0x44

# --- ctypes structures ---
class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", c_ushort),
        ("wScan", c_ushort),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", ctypes.POINTER(c_ulong)),
    ]

class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", c_long),
        ("dy", c_long),
        ("mouseData", c_ulong),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", ctypes.POINTER(c_ulong)),
    ]

class HARDWAREINPUT(Structure):
    _fields_ = [
        ("uMsg", c_ulong),
        ("wParamL", c_ushort),
        ("wParamH", c_ushort),
    ]

class _INPUTunion(Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(Structure):
    _fields_ = [
        ("type", c_ulong),
        ("union", _INPUTunion),
    ]

SendInput = ctypes.windll.user32.SendInput
SendInput.argtypes = [c_ulong, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = c_ulong

# Scroll event flags
MOUSEEVENTF_WHEEL  = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000


def inject_scroll(flags, delta):
    """Inject a mouse scroll event via SendInput.

    flags: MOUSEEVENTF_WHEEL or MOUSEEVENTF_HWHEEL
    delta: signed scroll amount (positive = up/right, negative = down/left)
    """
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.mouseData = delta & 0xFFFFFFFF
    inp.union.mi.dwFlags = flags
    arr = (INPUT * 1)(inp)
    SendInput(1, arr, sizeof(INPUT))


def _make_key_input(vk, flags=0):
    """Create a keyboard INPUT structure."""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = flags
    inp.union.ki.dwExtraInfo = ctypes.pointer(c_ulong(0))
    return inp


def send_key_combo(keys, hold_ms=50):
    """
    Press and release a combination of keys.
    `keys` is a list of VK codes, e.g. [VK_MENU, VK_TAB].
    All keys are pressed in order, then released in reverse order.
    """
    inputs = []
    # Press all keys
    for vk in keys:
        flags = KEYEVENTF_EXTENDEDKEY if _is_extended(vk) else 0
        inputs.append(_make_key_input(vk, flags))
    # Release all keys in reverse
    for vk in reversed(keys):
        flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if _is_extended(vk) else 0)
        inputs.append(_make_key_input(vk, flags))

    arr = (INPUT * len(inputs))(*inputs)
    SendInput(len(inputs), arr, sizeof(INPUT))


def send_key_press(vk):
    """Press and release a single key."""
    send_key_combo([vk])


def _is_extended(vk):
    """Check if a VK code is an extended key."""
    extended = {
        VK_BROWSER_BACK, VK_BROWSER_FORWARD, VK_BROWSER_REFRESH,
        VK_BROWSER_STOP, VK_BROWSER_HOME,
        VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP,
        VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK,
        VK_MEDIA_STOP, VK_MEDIA_PLAY_PAUSE,
        VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN,
        VK_DELETE, VK_RETURN, VK_TAB,
    }
    return vk in extended


# ----------------------------------------------------------------
# Pre-defined actions that can be assigned to mouse buttons
# ----------------------------------------------------------------

ACTIONS = {
    "alt_tab": {
        "label": "Alt + Tab (Switch Windows)",
        "keys": [VK_MENU, VK_TAB],
        "category": "Navigation",
    },
    "alt_shift_tab": {
        "label": "Alt + Shift + Tab (Switch Windows Reverse)",
        "keys": [VK_MENU, VK_SHIFT, VK_TAB],
        "category": "Navigation",
    },
    "browser_back": {
        "label": "Browser Back",
        "keys": [VK_BROWSER_BACK],
        "category": "Browser",
    },
    "browser_forward": {
        "label": "Browser Forward",
        "keys": [VK_BROWSER_FORWARD],
        "category": "Browser",
    },
    "copy": {
        "label": "Copy (Ctrl+C)",
        "keys": [VK_CONTROL, VK_C],
        "category": "Editing",
    },
    "paste": {
        "label": "Paste (Ctrl+V)",
        "keys": [VK_CONTROL, VK_V],
        "category": "Editing",
    },
    "cut": {
        "label": "Cut (Ctrl+X)",
        "keys": [VK_CONTROL, VK_X],
        "category": "Editing",
    },
    "undo": {
        "label": "Undo (Ctrl+Z)",
        "keys": [VK_CONTROL, VK_Z],
        "category": "Editing",
    },
    "select_all": {
        "label": "Select All (Ctrl+A)",
        "keys": [VK_CONTROL, VK_A],
        "category": "Editing",
    },
    "save": {
        "label": "Save (Ctrl+S)",
        "keys": [VK_CONTROL, VK_S],
        "category": "Editing",
    },
    "close_tab": {
        "label": "Close Tab (Ctrl+W)",
        "keys": [VK_CONTROL, VK_W],
        "category": "Browser",
    },
    "new_tab": {
        "label": "New Tab (Ctrl+T)",
        "keys": [VK_CONTROL, VK_T],
        "category": "Browser",
    },
    "find": {
        "label": "Find (Ctrl+F)",
        "keys": [VK_CONTROL, VK_F],
        "category": "Editing",
    },
    "win_d": {
        "label": "Show Desktop (Win+D)",
        "keys": [VK_LWIN, VK_D],
        "category": "Navigation",
    },
    "task_view": {
        "label": "Task View (Win+Tab)",
        "keys": [VK_LWIN, VK_TAB],
        "category": "Navigation",
    },
    "volume_up": {
        "label": "Volume Up",
        "keys": [VK_VOLUME_UP],
        "category": "Media",
    },
    "volume_down": {
        "label": "Volume Down",
        "keys": [VK_VOLUME_DOWN],
        "category": "Media",
    },
    "volume_mute": {
        "label": "Volume Mute",
        "keys": [VK_VOLUME_MUTE],
        "category": "Media",
    },
    "play_pause": {
        "label": "Play / Pause",
        "keys": [VK_MEDIA_PLAY_PAUSE],
        "category": "Media",
    },
    "next_track": {
        "label": "Next Track",
        "keys": [VK_MEDIA_NEXT_TRACK],
        "category": "Media",
    },
    "prev_track": {
        "label": "Previous Track",
        "keys": [VK_MEDIA_PREV_TRACK],
        "category": "Media",
    },
    "none": {
        "label": "Do Nothing (Pass-through)",
        "keys": [],
        "category": "Other",
    },
}


def execute_action(action_id):
    """Execute a named action by sending the associated key combo."""
    action = ACTIONS.get(action_id)
    if not action or not action["keys"]:
        return
    send_key_combo(action["keys"])
