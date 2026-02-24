"""
Raw Input test v2 — uses a real (hidden) window instead of HWND_MESSAGE,
and also tries direct HID device file reads via CreateFile + ReadFile.
"""
import ctypes
import ctypes.wintypes as wintypes
import time, sys, struct, threading
from ctypes import (
    Structure, POINTER, WINFUNCTYPE, sizeof, byref,
    c_uint, c_ubyte, c_ushort, c_ulong, c_int, c_void_p,
    windll, create_string_buffer,
)

# ── Constants ─────────────────────────────────────────────────────
WM_INPUT        = 0x00FF
WM_DESTROY      = 0x0002
WS_OVERLAPPED   = 0x00000000
SW_HIDE         = 0

RIDEV_INPUTSINK = 0x00000100
RID_INPUT       = 0x10000003
RIM_TYPEMOUSE   = 0
RIM_TYPEKEYBOARD= 1
RIM_TYPEHID     = 2

RIDI_DEVICENAME = 0x20000007

# ── Structures ────────────────────────────────────────────────────
class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", c_ushort),
        ("usUsage",     c_ushort),
        ("dwFlags",     c_ulong),
        ("hwndTarget",  wintypes.HWND),
    ]

class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType",   c_ulong),
        ("dwSize",   c_ulong),
        ("hDevice",  c_void_p),
        ("wParam",   ctypes.POINTER(c_ulong)),
    ]

class RAWMOUSE(Structure):
    _fields_ = [
        ("usFlags",          c_ushort),
        ("usButtonFlags",    c_ushort),
        ("usButtonData",     c_ushort),
        ("ulRawButtons",     c_ulong),
        ("lLastX",           c_int),
        ("lLastY",           c_int),
        ("ulExtraInformation", c_ulong),
    ]

class RAWHID(Structure):
    _fields_ = [
        ("dwSizeHid", c_ulong),
        ("dwCount",   c_ulong),
    ]

# ── Win32 setup ───────────────────────────────────────────────────
user32   = windll.user32
kernel32 = windll.kernel32

DefWindowProcW = user32.DefWindowProcW
DefWindowProcW.argtypes = [wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM]
DefWindowProcW.restype  = ctypes.c_longlong

GetRawInputData = user32.GetRawInputData
GetRawInputData.argtypes = [c_void_p, c_uint, c_void_p, POINTER(c_uint), c_uint]
GetRawInputData.restype  = c_uint

GetRawInputDeviceInfoW = user32.GetRawInputDeviceInfoW
RegisterRawInputDevices = user32.RegisterRawInputDevices
RegisterClassExW = user32.RegisterClassExW
CreateWindowExW  = user32.CreateWindowExW
ShowWindow       = user32.ShowWindow
PostQuitMessage  = user32.PostQuitMessage

WNDPROC = WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, c_uint,
                       wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize",        c_uint),
        ("style",         c_uint),
        ("lpfnWndProc",   WNDPROC),
        ("cbClsExtra",    c_int),
        ("cbWndExtra",    c_int),
        ("hInstance",     wintypes.HINSTANCE),
        ("hIcon",         wintypes.HICON),
        ("hCursor",       wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName",  wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HICON),
    ]

# ── Globals ───────────────────────────────────────────────────────
event_count = 0
device_cache = {}

def dev_tag(hDevice):
    if hDevice in device_cache:
        return device_cache[hDevice]
    size = c_uint(0)
    GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, None, byref(size))
    if size.value:
        buf = ctypes.create_unicode_buffer(size.value + 1)
        GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, buf, byref(size))
        name = buf.value
    else:
        name = "unknown"
    tag = "LOGI" if "046d" in name.lower() else "other"
    device_cache[hDevice] = (tag, name)
    return (tag, name)


def wnd_proc(hwnd, msg, wParam, lParam):
    global event_count

    if msg == WM_INPUT:
        size = c_uint(0)
        GetRawInputData(lParam, RID_INPUT, None, byref(size), sizeof(RAWINPUTHEADER))
        if size.value == 0:
            return DefWindowProcW(hwnd, msg, wParam, lParam)

        buf = create_string_buffer(size.value)
        ret = GetRawInputData(lParam, RID_INPUT, buf, byref(size), sizeof(RAWINPUTHEADER))
        if ret == 0xFFFFFFFF:
            return DefWindowProcW(hwnd, msg, wParam, lParam)

        header = RAWINPUTHEADER.from_buffer_copy(buf)
        tag, devpath = dev_tag(header.hDevice)
        ts = time.strftime("%H:%M:%S")

        if header.dwType == RIM_TYPEMOUSE:
            m = RAWMOUSE.from_buffer_copy(buf, sizeof(RAWINPUTHEADER))
            if m.usButtonFlags != 0:
                print(f"[{ts}] MOUSE ({tag})  flags=0x{m.usButtonFlags:04X}  "
                      f"data=0x{m.usButtonData:04X}  rawBtns=0x{m.ulRawButtons:08X}")
                sys.stdout.flush()
                event_count += 1

        elif header.dwType == RIM_TYPEHID:
            off = sizeof(RAWINPUTHEADER)
            rh  = RAWHID.from_buffer_copy(buf, off)
            data_off = off + sizeof(RAWHID)
            raw = buf.raw[data_off : data_off + rh.dwSizeHid * rh.dwCount]
            if raw:
                hexs = " ".join(f"{b:02X}" for b in raw)
                print(f"[{ts}] HID   ({tag})  size={rh.dwSizeHid} cnt={rh.dwCount}  "
                      f"data: {hexs}")
                if tag == "LOGI":
                    print(f"         path: {devpath}")
                sys.stdout.flush()
                event_count += 1

        elif header.dwType == RIM_TYPEKEYBOARD:
            if tag == "LOGI":
                print(f"[{ts}] KEYBD (LOGI)  — possible gesture button!")
                sys.stdout.flush()
                event_count += 1

        return 0

    if msg == WM_DESTROY:
        PostQuitMessage(0)
        return 0

    return DefWindowProcW(hwnd, msg, wParam, lParam)


# keep the callback alive
_wndproc_ref = WNDPROC(wnd_proc)


def main():
    TIMEOUT = 30

    hInst = kernel32.GetModuleHandleW(None)
    cls_name = "LogiRawInput2"

    wc = WNDCLASSEXW()
    wc.cbSize       = sizeof(WNDCLASSEXW)
    wc.lpfnWndProc  = _wndproc_ref
    wc.hInstance     = hInst
    wc.lpszClassName = cls_name

    atom = RegisterClassExW(byref(wc))
    if not atom:
        print(f"RegisterClassExW failed ({kernel32.GetLastError()})")
        return

    # Create a real window, then hide it (NOT HWND_MESSAGE)
    hwnd = CreateWindowExW(
        0, cls_name, "RawInput2", WS_OVERLAPPED,
        0, 0, 1, 1,
        None,           # parent = desktop  (not HWND_MESSAGE!)
        None, hInst, None,
    )
    if not hwnd:
        print(f"CreateWindowExW failed ({kernel32.GetLastError()})")
        return
    ShowWindow(hwnd, SW_HIDE)

    # ── Register for raw input ────────────────────────────────────
    rid = (RAWINPUTDEVICE * 4)()

    # 0  All mice
    rid[0].usUsagePage = 0x01;  rid[0].usUsage = 0x02
    rid[0].dwFlags = RIDEV_INPUTSINK;  rid[0].hwndTarget = hwnd

    # 1  Logitech vendor-specific
    rid[1].usUsagePage = 0xFF43; rid[1].usUsage = 0x0202
    rid[1].dwFlags = RIDEV_INPUTSINK;  rid[1].hwndTarget = hwnd

    # 2  Consumer controls (media keys etc.)
    rid[2].usUsagePage = 0x0C;  rid[2].usUsage = 0x01
    rid[2].dwFlags = RIDEV_INPUTSINK;  rid[2].hwndTarget = hwnd

    # 3  Keyboard (gesture might map to a key)
    rid[3].usUsagePage = 0x01;  rid[3].usUsage = 0x06
    rid[3].dwFlags = RIDEV_INPUTSINK;  rid[3].hwndTarget = hwnd

    ok = RegisterRawInputDevices(rid, 4, sizeof(RAWINPUTDEVICE))
    if not ok:
        err = kernel32.GetLastError()
        print(f"RegisterRawInputDevices (4) failed – err {err}")
        # fall back to mice-only
        ok2 = RegisterRawInputDevices(rid, 1, sizeof(RAWINPUTDEVICE))
        if not ok2:
            print("Cannot register for raw input at all."); return
        print("Registered for mice only (vendor HID failed)")
    else:
        print("Registered for: mice · Logitech HID · consumer · keyboard")

    print(f"\n>>> Press EVERY button on the MX Master 3S ({TIMEOUT}s) <<<")
    print(">>> Left, Right, Middle, Gesture, Forward, Back, Scroll, HScroll <<<\n")
    sys.stdout.flush()

    # ── Message loop ──────────────────────────────────────────────
    msg = wintypes.MSG()
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        while user32.PeekMessageW(byref(msg), None, 0, 0, 1):
            if msg.message == 0x0012:  # WM_QUIT
                return
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))
        time.sleep(0.005)

    user32.DestroyWindow(hwnd)
    print(f"\n{'='*60}")
    print(f"Captured {event_count} button/HID events.")
    if event_count == 0:
        print("No events at all!")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
