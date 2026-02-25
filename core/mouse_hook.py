"""
Low-level Windows mouse hook using ctypes.
Intercepts mouse button presses and horizontal scroll events
so we can remap them before they reach applications.
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from ctypes import (CFUNCTYPE, POINTER, Structure, c_int, c_uint, c_ushort,
                    c_ulong, c_void_p, sizeof, byref, create_string_buffer, windll)

try:
    from core.hid_gesture import HidGestureListener
except Exception:              # ImportError or hidapi missing
    HidGestureListener = None

# Windows constants
WH_MOUSE_LL = 14
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEHWHEEL = 0x020E  # Horizontal scroll
WM_MOUSEWHEEL = 0x020A    # Vertical scroll

HC_ACTION = 0

XBUTTON1 = 0x0001  # Back button
XBUTTON2 = 0x0002  # Forward button

# Struct for low-level mouse hook
class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

# Hook procedure type
HOOKPROC = CFUNCTYPE(ctypes.c_long, c_int, wintypes.WPARAM, ctypes.POINTER(MSLLHOOKSTRUCT))

# Win32 API functions
SetWindowsHookExW = windll.user32.SetWindowsHookExW
SetWindowsHookExW.restype = wintypes.HHOOK
SetWindowsHookExW.argtypes = [c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]

CallNextHookEx = windll.user32.CallNextHookEx
CallNextHookEx.restype = ctypes.c_long
CallNextHookEx.argtypes = [wintypes.HHOOK, c_int, wintypes.WPARAM, ctypes.POINTER(MSLLHOOKSTRUCT)]

UnhookWindowsHookEx = windll.user32.UnhookWindowsHookEx
UnhookWindowsHookEx.restype = wintypes.BOOL
UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

GetModuleHandleW = windll.kernel32.GetModuleHandleW
GetModuleHandleW.restype = wintypes.HMODULE
GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

GetMessageW = windll.user32.GetMessageW
PostThreadMessageW = windll.user32.PostThreadMessageW

WM_QUIT = 0x0012

# Injected flag — events we synthesize ourselves carry this
INJECTED_FLAG = 0x00000001

# ── Raw Input constants ───────────────────────────────────────────
WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
RIM_TYPEHID = 2
RIDI_DEVICENAME = 0x20000007
SW_HIDE = 0

# Standard mouse buttons that the LL hook already handles (bits 0-4)
STANDARD_BUTTON_MASK = 0x1F

# ── Raw Input structures ─────────────────────────────────────────

class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", c_ushort),
        ("usUsage", c_ushort),
        ("dwFlags", c_ulong),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType", c_ulong),
        ("dwSize", c_ulong),
        ("hDevice", c_void_p),
        ("wParam", POINTER(c_ulong)),
    ]

class RAWMOUSE(Structure):
    _fields_ = [
        ("usFlags", c_ushort),
        ("usButtonFlags", c_ushort),
        ("usButtonData", c_ushort),
        ("ulRawButtons", c_ulong),
        ("lLastX", c_int),
        ("lLastY", c_int),
        ("ulExtraInformation", c_ulong),
    ]

class RAWHID(Structure):
    _fields_ = [
        ("dwSizeHid", c_ulong),
        ("dwCount", c_ulong),
    ]

WNDPROC_TYPE = CFUNCTYPE(ctypes.c_longlong, wintypes.HWND, c_uint,
                          wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("style", c_uint),
        ("lpfnWndProc", WNDPROC_TYPE),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]

# ── Win32 API — Raw Input ────────────────────────────────────────
RegisterRawInputDevices = windll.user32.RegisterRawInputDevices

GetRawInputData = windll.user32.GetRawInputData
GetRawInputData.argtypes = [c_void_p, c_uint, c_void_p, POINTER(c_uint), c_uint]
GetRawInputData.restype = c_uint

GetRawInputDeviceInfoW = windll.user32.GetRawInputDeviceInfoW
RegisterClassExW = windll.user32.RegisterClassExW

CreateWindowExW = windll.user32.CreateWindowExW
CreateWindowExW.restype = wintypes.HWND
CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    c_int, c_int, c_int, c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]

ShowWindow = windll.user32.ShowWindow

DefWindowProcW = windll.user32.DefWindowProcW
DefWindowProcW.restype = ctypes.c_longlong
DefWindowProcW.argtypes = [wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM]

TranslateMessage = windll.user32.TranslateMessage
DispatchMessageW = windll.user32.DispatchMessageW
DestroyWindow = windll.user32.DestroyWindow


def hiword(dword):
    """Extract the high word from a DWORD (mouse data)."""
    val = (dword >> 16) & 0xFFFF
    if val >= 0x8000:
        val -= 0x10000
    return val


class MouseEvent:
    """Represents a captured mouse event."""
    XBUTTON1_DOWN = "xbutton1_down"
    XBUTTON1_UP = "xbutton1_up"
    XBUTTON2_DOWN = "xbutton2_down"
    XBUTTON2_UP = "xbutton2_up"
    MIDDLE_DOWN = "middle_down"
    MIDDLE_UP = "middle_up"
    GESTURE_DOWN = "gesture_down"      # MX Master 3S gesture button
    GESTURE_UP = "gesture_up"           # (without Logi Options registers as middle-click)
    HSCROLL_LEFT = "hscroll_left"
    HSCROLL_RIGHT = "hscroll_right"

    def __init__(self, event_type, raw_data=None):
        self.event_type = event_type
        self.raw_data = raw_data
        self.timestamp = time.time()


# Custom messages for deferred scroll injection (avoids calling SendInput
# from inside the low-level hook, which causes recursive deadlock / lag).
WM_APP = 0x8000
WM_APP_INJECT_VSCROLL = WM_APP + 1   # wParam = signed delta (as c_long)
WM_APP_INJECT_HSCROLL = WM_APP + 2   # wParam = signed delta (as c_long)

# Scroll injection via key_simulator (which has working SendInput + INPUT structs)
from core.key_simulator import inject_scroll as _inject_scroll_impl
from core.key_simulator import MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL

PostMessageW = windll.user32.PostMessageW
PostMessageW.argtypes = [wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM]
PostMessageW.restype = wintypes.BOOL


class MouseHook:
    """
    Installs a low-level mouse hook on Windows to intercept
    side-button clicks and horizontal scroll events.
    """

    def __init__(self):
        self._hook = None
        self._hook_thread = None
        self._thread_id = None
        self._running = False
        self._callbacks = {}          # event_type -> list of callables
        self._blocked_events = set()  # event types to block (consume)
        self._hook_proc = None        # prevent GC of the callback
        self._debug_callback = None   # callback for debug/detect mode
        self.debug_mode = False       # when True, logs ALL mouse events
        # Scroll inversion settings (set by the engine from config)
        self.invert_vscroll = False
        self.invert_hscroll = False
        # Coalesced scroll injection state (accumulate deltas, inject once)
        self._pending_vscroll = 0     # accumulated inverted vertical delta
        self._pending_hscroll = 0     # accumulated inverted horizontal delta
        self._vscroll_posted = False  # True if a WM_APP_INJECT_VSCROLL is in the queue
        self._hscroll_posted = False  # True if a WM_APP_INJECT_HSCROLL is in the queue
        # Raw Input state for gesture button detection
        self._ri_wndproc_ref = None   # prevent GC of window proc
        self._ri_hwnd = None
        self._device_name_cache = {}
        self._gesture_active = False  # central dedup flag for gesture
        self._prev_raw_buttons = {}   # hDevice -> last ulRawButtons value
        # HID++ gesture listener (hidapi-based)
        self._hid_gesture = None

    def register(self, event_type, callback):
        """Register a callback for a specific mouse event type."""
        self._callbacks.setdefault(event_type, []).append(callback)

    def block(self, event_type):
        """Mark an event type to be blocked (not passed to other apps)."""
        self._blocked_events.add(event_type)

    def unblock(self, event_type):
        """Allow an event type to pass through normally."""
        self._blocked_events.discard(event_type)

    def reset_bindings(self):
        """Clear all callbacks and blocked events without stopping the hook.
        Call this before re-registering bindings for a new profile."""
        self._callbacks.clear()
        self._blocked_events.clear()

    def set_debug_callback(self, callback):
        """Set a callback to receive ALL raw mouse events for detection."""
        self._debug_callback = callback

    def _dispatch(self, event):
        """Fire all registered callbacks for this event type."""
        for cb in self._callbacks.get(event.event_type, []):
            try:
                cb(event)
            except Exception as e:
                print(f"[MouseHook] callback error: {e}")

    # Map of WM_ constants to names for debug
    _WM_NAMES = {
        0x0200: "WM_MOUSEMOVE",
        0x0201: "WM_LBUTTONDOWN", 0x0202: "WM_LBUTTONUP",
        0x0204: "WM_RBUTTONDOWN", 0x0205: "WM_RBUTTONUP",
        0x0207: "WM_MBUTTONDOWN", 0x0208: "WM_MBUTTONUP",
        0x020A: "WM_MOUSEWHEEL",  0x020B: "WM_XBUTTONDOWN",
        0x020C: "WM_XBUTTONUP",   0x020E: "WM_MOUSEHWHEEL",
    }

    def _low_level_handler(self, nCode, wParam, lParam):
        """The actual hook procedure called by Windows."""
        if nCode == HC_ACTION:
            data = lParam.contents
            mouse_data = data.mouseData
            flags = data.flags
            event = None
            should_block = False

            # Debug mode: report every non-move event
            if self.debug_mode and self._debug_callback:
                wm_name = self._WM_NAMES.get(wParam, f"0x{wParam:04X}")
                if wParam != 0x0200:  # skip mouse-move spam
                    extra = data.dwExtraInfo.contents.value if data.dwExtraInfo else 0
                    info = (f"{wm_name}  mouseData=0x{mouse_data:08X}  "
                            f"hiword={hiword(mouse_data)}  flags=0x{flags:04X}  "
                            f"extraInfo=0x{extra:X}")
                    try:
                        self._debug_callback(info)
                    except Exception:
                        pass

            # Skip events we injected ourselves
            if flags & INJECTED_FLAG:
                return CallNextHookEx(self._hook, nCode, wParam, lParam)

            if wParam == WM_XBUTTONDOWN:
                xbutton = hiword(mouse_data)
                if xbutton == XBUTTON1:
                    event = MouseEvent(MouseEvent.XBUTTON1_DOWN)
                    should_block = MouseEvent.XBUTTON1_DOWN in self._blocked_events
                elif xbutton == XBUTTON2:
                    event = MouseEvent(MouseEvent.XBUTTON2_DOWN)
                    should_block = MouseEvent.XBUTTON2_DOWN in self._blocked_events

            elif wParam == WM_XBUTTONUP:
                xbutton = hiword(mouse_data)
                if xbutton == XBUTTON1:
                    event = MouseEvent(MouseEvent.XBUTTON1_UP)
                    should_block = MouseEvent.XBUTTON1_UP in self._blocked_events
                elif xbutton == XBUTTON2:
                    event = MouseEvent(MouseEvent.XBUTTON2_UP)
                    should_block = MouseEvent.XBUTTON2_UP in self._blocked_events

            elif wParam == WM_MBUTTONDOWN:
                event = MouseEvent(MouseEvent.MIDDLE_DOWN)
                should_block = MouseEvent.MIDDLE_DOWN in self._blocked_events

            elif wParam == WM_MBUTTONUP:
                event = MouseEvent(MouseEvent.MIDDLE_UP)
                should_block = MouseEvent.MIDDLE_UP in self._blocked_events

            elif wParam == WM_MOUSEWHEEL:
                # Vertical scroll inversion — coalesced injection
                if self.invert_vscroll:
                    delta = hiword(mouse_data)
                    if delta != 0:
                        self._pending_vscroll += (-delta)
                        if not self._vscroll_posted and self._ri_hwnd:
                            self._vscroll_posted = True
                            PostMessageW(self._ri_hwnd,
                                         WM_APP_INJECT_VSCROLL, 0, 0)
                        return 1  # Block original

            elif wParam == WM_MOUSEHWHEEL:
                delta = hiword(mouse_data)
                # Hardware-level inversion toggle — coalesced injection
                if self.invert_hscroll:
                    if delta != 0:
                        self._pending_hscroll += (-delta)
                        if not self._hscroll_posted and self._ri_hwnd:
                            self._hscroll_posted = True
                            PostMessageW(self._ri_hwnd,
                                         WM_APP_INJECT_HSCROLL, 0, 0)
                        return 1  # Block original
                # Action dispatch for mapped hscroll events
                # MX Master 3S: positive delta = physical scroll right
                if delta > 0:
                    event = MouseEvent(MouseEvent.HSCROLL_LEFT, abs(delta))
                    should_block = MouseEvent.HSCROLL_LEFT in self._blocked_events
                elif delta < 0:
                    event = MouseEvent(MouseEvent.HSCROLL_RIGHT, abs(delta))
                    should_block = MouseEvent.HSCROLL_RIGHT in self._blocked_events

            if event:
                self._dispatch(event)
                if should_block:
                    return 1  # Block the event

        return CallNextHookEx(self._hook, nCode, wParam, lParam)

    # ── Raw Input: device identification ──────────────────────────

    def _get_device_name(self, hDevice):
        """Get the device path for a Raw Input device handle."""
        if hDevice in self._device_name_cache:
            return self._device_name_cache[hDevice]
        try:
            sz = c_uint(0)
            GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, None, byref(sz))
            if sz.value > 0:
                buf = ctypes.create_unicode_buffer(sz.value + 1)
                GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, buf, byref(sz))
                name = buf.value
            else:
                name = ""
        except Exception:
            name = ""
        self._device_name_cache[hDevice] = name
        return name

    def _is_logitech(self, hDevice):
        return "046d" in self._get_device_name(hDevice).lower()

    # ── Raw Input: gesture detection ──────────────────────────────

    def _ri_wndproc(self, hwnd, msg, wParam, lParam):
        """Window procedure that receives Raw Input messages and
        deferred scroll-injection requests."""
        if msg == WM_INPUT:
            try:
                self._process_raw_input(lParam)
            except Exception as e:
                print(f"[MouseHook] Raw Input error: {e}")
            return 0

        if msg == WM_APP_INJECT_VSCROLL:
            delta = self._pending_vscroll
            self._pending_vscroll = 0
            self._vscroll_posted = False
            if delta != 0:
                _inject_scroll_impl(MOUSEEVENTF_WHEEL, delta)
            return 0

        if msg == WM_APP_INJECT_HSCROLL:
            delta = self._pending_hscroll
            self._pending_hscroll = 0
            self._hscroll_posted = False
            if delta != 0:
                _inject_scroll_impl(MOUSEEVENTF_HWHEEL, delta)
            return 0

        return DefWindowProcW(hwnd, msg, wParam, lParam)

    def _process_raw_input(self, lParam):
        """Parse a WM_INPUT message and detect gesture button."""
        sz = c_uint(0)
        GetRawInputData(lParam, RID_INPUT, None, byref(sz),
                        sizeof(RAWINPUTHEADER))
        if sz.value == 0:
            return

        buf = create_string_buffer(sz.value)
        ret = GetRawInputData(lParam, RID_INPUT, buf, byref(sz),
                              sizeof(RAWINPUTHEADER))
        if ret == 0xFFFFFFFF:
            return

        header = RAWINPUTHEADER.from_buffer_copy(buf)

        if not self._is_logitech(header.hDevice):
            return

        if header.dwType == RIM_TYPEMOUSE:
            self._check_raw_mouse_gesture(header.hDevice, buf)

    def _check_raw_mouse_gesture(self, hDevice, buf):
        """Detect gesture button via extra button bits in ulRawButtons."""
        mouse = RAWMOUSE.from_buffer_copy(buf, sizeof(RAWINPUTHEADER))
        raw_btns = mouse.ulRawButtons
        prev_btns = self._prev_raw_buttons.get(hDevice, 0)
        self._prev_raw_buttons[hDevice] = raw_btns

        # Only look at buttons beyond the standard 5 (bits 5+)
        extra_now = raw_btns & ~STANDARD_BUTTON_MASK
        extra_prev = prev_btns & ~STANDARD_BUTTON_MASK

        if extra_now == extra_prev:
            return

        if extra_now and not extra_prev:
            if not self._gesture_active:
                self._gesture_active = True
                print(f"[MouseHook] Gesture DOWN (rawBtns extra: 0x{extra_now:X})")
                self._dispatch(MouseEvent(MouseEvent.GESTURE_DOWN))
        elif not extra_now and extra_prev:
            if self._gesture_active:
                self._gesture_active = False
                print("[MouseHook] Gesture UP")
                self._dispatch(MouseEvent(MouseEvent.GESTURE_UP))

    # ── Raw Input: setup ──────────────────────────────────────────

    def _setup_raw_input(self):
        """Create hidden window and register for Raw Input on the hook thread."""
        hInst = GetModuleHandleW(None)
        cls_name = f"LogiControlRawInput_{id(self)}"

        self._ri_wndproc_ref = WNDPROC_TYPE(self._ri_wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._ri_wndproc_ref
        wc.hInstance = hInst
        wc.lpszClassName = cls_name

        atom = RegisterClassExW(byref(wc))
        if not atom:
            # Class may already exist — try creating the window anyway
            pass

        self._ri_hwnd = CreateWindowExW(
            0, cls_name, "LogiControl RI", 0,
            0, 0, 1, 1,
            None, None, hInst, None,
        )
        if not self._ri_hwnd:
            print("[MouseHook] CreateWindowExW failed — gesture detection unavailable")
            return False

        ShowWindow(self._ri_hwnd, SW_HIDE)

        # Register for Raw Input collections
        rid = (RAWINPUTDEVICE * 4)()

        # 0: All mice — to read ulRawButtons for higher button bits
        rid[0].usUsagePage = 0x01
        rid[0].usUsage = 0x02
        rid[0].dwFlags = RIDEV_INPUTSINK
        rid[0].hwndTarget = self._ri_hwnd

        # 1: Logitech HID++ short reports
        rid[1].usUsagePage = 0xFF43
        rid[1].usUsage = 0x0202
        rid[1].dwFlags = RIDEV_INPUTSINK
        rid[1].hwndTarget = self._ri_hwnd

        # 2: Logitech HID++ long reports
        rid[2].usUsagePage = 0xFF43
        rid[2].usUsage = 0x0204
        rid[2].dwFlags = RIDEV_INPUTSINK
        rid[2].hwndTarget = self._ri_hwnd

        # 3: Consumer Controls (some firmware maps gesture here)
        rid[3].usUsagePage = 0x0C
        rid[3].usUsage = 0x01
        rid[3].dwFlags = RIDEV_INPUTSINK
        rid[3].hwndTarget = self._ri_hwnd

        ok = RegisterRawInputDevices(rid, 4, sizeof(RAWINPUTDEVICE))
        if ok:
            print("[MouseHook] Raw Input: mice + Logitech HID + consumer")
            return True

        # Fallback: mice + one vendor collection
        ok2 = RegisterRawInputDevices(rid, 2, sizeof(RAWINPUTDEVICE))
        if ok2:
            print("[MouseHook] Raw Input: mice + Logitech HID short")
            return True

        # Fallback: mice only
        ok3 = RegisterRawInputDevices(rid, 1, sizeof(RAWINPUTDEVICE))
        if ok3:
            print("[MouseHook] Raw Input: mice only")
            return True

        print("[MouseHook] Raw Input registration failed")
        return False

    def _run_hook(self):
        """Run the message loop on a dedicated thread."""
        self._thread_id = windll.kernel32.GetCurrentThreadId()

        # IMPORTANT: must keep reference alive so GC doesn't collect it
        self._hook_proc = HOOKPROC(self._low_level_handler)

        self._hook = SetWindowsHookExW(
            WH_MOUSE_LL,
            self._hook_proc,
            GetModuleHandleW(None),
            0,
        )
        if not self._hook:
            print("[MouseHook] Failed to install hook!")
            return

        print("[MouseHook] Hook installed successfully")

        # Set up Raw Input for gesture button detection
        self._setup_raw_input()

        self._running = True

        # Message pump — required for low-level hooks AND Raw Input
        msg = wintypes.MSG()
        while self._running:
            result = GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            TranslateMessage(ctypes.byref(msg))
            DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        if self._ri_hwnd:
            DestroyWindow(self._ri_hwnd)
            self._ri_hwnd = None
        if self._hook:
            UnhookWindowsHookEx(self._hook)
            self._hook = None
        print("[MouseHook] Hook removed")

    # ── HID++ gesture helpers ─────────────────────────────────────

    def _on_hid_gesture_down(self):
        """Called from HidGestureListener thread on button press."""
        if not self._gesture_active:
            self._gesture_active = True
            self._dispatch(MouseEvent(MouseEvent.GESTURE_DOWN))

    def _on_hid_gesture_up(self):
        """Called from HidGestureListener thread on button release."""
        if self._gesture_active:
            self._gesture_active = False
            self._dispatch(MouseEvent(MouseEvent.GESTURE_UP))

    def start(self):
        """Start the mouse hook on a background thread."""
        if self._hook_thread and self._hook_thread.is_alive():
            return

        # Start HID++ gesture listener (primary path for BT gesture button)
        if HidGestureListener is not None:
            self._hid_gesture = HidGestureListener(
                on_down=self._on_hid_gesture_down,
                on_up=self._on_hid_gesture_up,
            )
            self._hid_gesture.start()

        self._hook_thread = threading.Thread(target=self._run_hook, daemon=True)
        self._hook_thread.start()
        # Give it a moment to install
        time.sleep(0.1)

    def stop(self):
        """Stop the hook and its message loop."""
        self._running = False
        # Stop HID++ gesture listener
        if self._hid_gesture:
            self._hid_gesture.stop()
            self._hid_gesture = None
        if self._thread_id:
            PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._hook_thread:
            self._hook_thread.join(timeout=2)
        self._hook = None
        self._ri_hwnd = None
        self._thread_id = None
