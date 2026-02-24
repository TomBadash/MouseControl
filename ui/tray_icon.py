"""
System tray icon using pystray.
Provides quick access to open settings, toggle on/off, and quit.
"""

import threading
import os
import sys

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("[Tray] pystray / Pillow not installed — tray icon disabled")


def _create_icon_image(size=64):
    """Draw a simple tray icon — a stylised mouse pointer."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([4, 4, size - 4, size - 4], fill="#89b4fa")

    # "M" letter for Mouse / MX
    try:
        font = ImageFont.truetype("segoeuib.ttf", size // 2)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "M", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 2), "M",
              fill="#1e1e2e", font=font)
    return img


class TrayIcon:
    """Manages the system-tray icon and its context menu."""

    def __init__(self, on_open_settings=None, on_toggle=None, on_quit=None):
        self.on_open_settings = on_open_settings
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self._icon = None
        self._enabled = True

    def _toggle_label(self):
        return "Disable Remapping" if self._enabled else "Enable Remapping"

    def _handle_toggle(self, icon, item):
        self._enabled = not self._enabled
        if self.on_toggle:
            self.on_toggle(self._enabled)
        # Rebuild menu to update label
        icon.menu = self._build_menu()
        icon.update_menu()

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Open Settings", self._handle_open,
                             default=True),
            pystray.MenuItem(self._toggle_label(),
                             self._handle_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit LogiControl", self._handle_quit),
        )

    def _handle_open(self, icon, item):
        if self.on_open_settings:
            self.on_open_settings()

    def _handle_quit(self, icon, item):
        icon.stop()
        if self.on_quit:
            self.on_quit()

    def start(self):
        if not HAS_TRAY:
            return
        image = _create_icon_image()
        self._icon = pystray.Icon(
            "LogiControl",
            image,
            "LogiControl — MX Master 3S",
            menu=self._build_menu(),
        )
        # Run in its own thread so it doesn't block tkinter
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
