"""
Test using Windows Raw Input API to capture HID reports from the
Logitech MX Master 3S — including the gesture button.
Raw Input works alongside the normal input pipeline (shared access).
"""
import ctypes
import ctypes.wintypes as wintypes
import time
import sys
import struct
from ctypes import (
    Structure, Union, POINTER, WINFUNCTYPE, sizeof, byref, c_uint,
    c_ubyte, c_ushort, c_ulong, c_int, windll, create_string_buffer
)

# ── Constants ─────────────────────────────────────────────────────
WM_INPUT = 0x00FF
WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_QUIT = 0x0012

RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000

RID_INPUT = 0x10000003
RID_HEADER = 0x10000005

RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
RIM_TYPEHID = 2

# HID usage pages
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_PAGE_VENDOR = 0xFF43  # Logitech proprietary

HWND_MESSAGE = ctypes.c_void_p(-3)

# ── Structures ────────────────────────────────────────────────────
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
        ("hDevice", ctypes.c_void_p),
        ("wParam", ctypes.POINTER(c_ulong)),
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
        # bRawData follows — variable length
    ]

class RAWINPUT_MOUSE(Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]

# ── Win32 functions ───────────────────────────────────────────────
user32 = windll.user32
kernel32 = windll.kernel32

RegisterRawInputDevices = user32.RegisterRawInputDevices
GetRawInputData = user32.GetRawInputData
GetRawInputData.argtypes = [
    ctypes.c_void_p,  # hRawInput
    c_uint,           # uiCommand
    ctypes.c_void_p,  # pData
    POINTER(c_uint),  # pcbSize
    c_uint,           # cbSizeHeader
]
GetRawInputData.restype = c_uint

DefWindowProcW = user32.DefWindowProcW
DefWindowProcW.restype = ctypes.c_longlong
DefWindowProcW.argtypes = [wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM]
CreateWindowExW = user32.CreateWindowExW
RegisterClassExW = user32.RegisterClassExW
GetMessageW = user32.GetMessageW
TranslateMessage = user32.TranslateMessage
DispatchMessageW = user32.DispatchMessageW
DestroyWindow = user32.DestroyWindow
PostQuitMessage = user32.PostQuitMessage

# GetRawInputDeviceInfoW
GetRawInputDeviceInfoW = user32.GetRawInputDeviceInfoW
RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000b

WNDPROC = WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, c_uint,
                       wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("style", c_uint),
        ("lpfnWndProc", WNDPROC),
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

# ── Globals ───────────────────────────────────────────────────────
event_count = 0
start_time = None
MAX_EVENTS = 100
TIMEOUT = 20

# Track devices we've seen
known_devices = {}

def get_device_name(hDevice):
    """Get the device path string for a RAWINPUT device handle."""
    if hDevice in known_devices:
        return known_devices[hDevice]
    
    size = c_uint(0)
    GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, None, byref(size))
    if size.value > 0:
        buf = ctypes.create_unicode_buffer(size.value + 1)
        GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, buf, byref(size))
        name = buf.value
        known_devices[hDevice] = name
        return name
    known_devices[hDevice] = "unknown"
    return "unknown"


def wnd_proc(hwnd, msg, wParam, lParam):
    global event_count, start_time

    if msg == WM_INPUT:
        # Get required buffer size
        size = c_uint(0)
        GetRawInputData(lParam, RID_INPUT, None, byref(size),
                       sizeof(RAWINPUTHEADER))

        if size.value > 0:
            buf = create_string_buffer(size.value)
            GetRawInputData(lParam, RID_INPUT, buf, byref(size),
                           sizeof(RAWINPUTHEADER))

            # Parse header
            header = RAWINPUTHEADER.from_buffer_copy(buf)
            dev_name = get_device_name(header.hDevice)
            is_logitech = "046d" in dev_name.lower()
            
            timestr = time.strftime("%H:%M:%S")

            if header.dwType == RIM_TYPEMOUSE:
                mouse = RAWMOUSE.from_buffer_copy(buf, sizeof(RAWINPUTHEADER))
                flags = mouse.usButtonFlags
                # Only print non-move events
                if flags != 0:
                    tag = "LOGI" if is_logitech else "other"
                    line = (f"[{timestr}] MOUSE ({tag}) "
                            f"btnFlags=0x{flags:04X} "
                            f"btnData=0x{mouse.usButtonData:04X} "
                            f"rawBtns=0x{mouse.ulRawButtons:08X}")
                    print(line)
                    sys.stdout.flush()
                    event_count += 1

            elif header.dwType == RIM_TYPEHID:
                # Parse RAWHID header
                rawhid_offset = sizeof(RAWINPUTHEADER)
                rawhid = RAWHID.from_buffer_copy(buf, rawhid_offset)
                data_offset = rawhid_offset + sizeof(RAWHID)
                data_size = rawhid.dwSizeHid * rawhid.dwCount
                raw_bytes = buf.raw[data_offset:data_offset + data_size]
                
                if raw_bytes:
                    hex_str = " ".join(f"{b:02X}" for b in raw_bytes)
                    tag = "LOGI" if is_logitech else "other"
                    line = (f"[{timestr}] HID ({tag}) "
                            f"size={rawhid.dwSizeHid} "
                            f"count={rawhid.dwCount} "
                            f"data: {hex_str}")
                    print(line)
                    sys.stdout.flush()
                    event_count += 1

            elif header.dwType == RIM_TYPEKEYBOARD:
                # Ignore keyboard for now unless it's from Logitech
                if is_logitech:
                    print(f"[{timestr}] KEYBOARD (LOGI) from gesture button?")
                    sys.stdout.flush()
                    event_count += 1

        return 0

    if msg == WM_DESTROY:
        PostQuitMessage(0)
        return 0

    return DefWindowProcW(hwnd, msg, wParam, lParam)


def main():
    global start_time
    start_time = time.time()

    # Register window class
    wc = WNDCLASSEXW()
    wc.cbSize = sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = WNDPROC(wnd_proc)
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = "LogiTestRawInput"

    if not RegisterClassExW(byref(wc)):
        print("Failed to register window class!")
        return

    # Create message-only window
    hwnd = CreateWindowExW(
        0, "LogiTestRawInput", "RawInput Test",
        0, 0, 0, 0, 0,
        HWND_MESSAGE, None, wc.hInstance, None
    )
    if not hwnd:
        print("Failed to create window!")
        return

    # Register for raw input from ALL mice and ALL HID devices
    rid = (RAWINPUTDEVICE * 3)()

    # All mice
    rid[0].usUsagePage = 0x01  # Generic Desktop
    rid[0].usUsage = 0x02     # Mouse
    rid[0].dwFlags = RIDEV_INPUTSINK
    rid[0].hwndTarget = hwnd

    # All HID (vendor-specific Logitech page)
    rid[1].usUsagePage = 0xFF43  # Logitech vendor page
    rid[1].usUsage = 0x0202
    rid[1].dwFlags = RIDEV_INPUTSINK
    rid[1].hwndTarget = hwnd

    # Also try generic consumer controls
    rid[2].usUsagePage = 0x0C  # Consumer
    rid[2].usUsage = 0x01     # Consumer Control
    rid[2].dwFlags = RIDEV_INPUTSINK
    rid[2].hwndTarget = hwnd

    ok = RegisterRawInputDevices(rid, 3, sizeof(RAWINPUTDEVICE))
    if not ok:
        err = kernel32.GetLastError()
        print(f"RegisterRawInputDevices failed! Error: {err}")
        # Try just mice
        ok2 = RegisterRawInputDevices(rid, 1, sizeof(RAWINPUTDEVICE))
        if ok2:
            print("Registered for mice only (vendor HID registration failed)")
        else:
            print("Failed entirely!")
            return
    else:
        print("Registered for: mice, Logitech HID, consumer controls")

    print(f"\n>>> Press ALL buttons on your MX Master 3S ({TIMEOUT}s timeout) <<<")
    print(">>> Include: gesture, side buttons, middle click, scroll <<<\n")
    sys.stdout.flush()

    # Message pump with timeout
    msg = wintypes.MSG()
    while True:
        if time.time() - start_time > TIMEOUT:
            break
        if event_count >= MAX_EVENTS:
            break

        result = user32.PeekMessageW(byref(msg), None, 0, 0, 1)  # PM_REMOVE=1
        if result:
            if msg.message == WM_QUIT:
                break
            TranslateMessage(byref(msg))
            DispatchMessageW(byref(msg))
        else:
            time.sleep(0.005)

    DestroyWindow(hwnd)
    print(f"\n{'='*60}")
    print(f"Total events: {event_count}")
    if event_count == 0:
        print("No events captured!")
    else:
        print("Check above for gesture button data.")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
