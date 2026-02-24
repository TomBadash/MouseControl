"""
LogiControl — Local MX Master 3S Button Remapper
=================================================
Entry point.  Starts the mouse-hook engine and the configuration UI.
Run with:   python main.py
"""

import sys
import os
import tkinter as tk

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import Engine
from ui.main_window import MainWindow
from ui.tray_icon import TrayIcon


def main():
    # ── Start engine (low-level mouse hook) ───────────────────────
    engine = Engine()
    engine.start()
    print("[LogiControl] Engine started — remapping is active")

    # ── Tkinter root ──────────────────────────────────────────────
    root = tk.Tk()

    # ── Build main window ─────────────────────────────────────────
    window = MainWindow(root, engine=engine)

    # ── System tray icon ──────────────────────────────────────────
    def open_settings():
        root.after(0, window.show)

    def toggle_engine(enabled):
        engine.set_enabled(enabled)
        status = "● Running" if enabled else "● Paused"
        root.after(0, lambda: window.status_label.configure(text=status))

    def quit_app():
        engine.stop()
        root.after(0, root.destroy)

    tray = TrayIcon(
        on_open_settings=open_settings,
        on_toggle=toggle_engine,
        on_quit=quit_app,
    )
    tray.start()

    # ── Handle window close → minimize to tray instead of quitting
    def on_close():
        root.withdraw()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # ── Run ───────────────────────────────────────────────────────
    try:
        root.mainloop()
    finally:
        engine.stop()
        tray.stop()
        print("[LogiControl] Shut down cleanly")


if __name__ == "__main__":
    main()
