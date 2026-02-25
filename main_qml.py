"""
LogiControl — QML Entry Point
==============================
Launches the Qt Quick / QML UI with PySide6.
Replaces the old tkinter-based main.py.
Run with:   python main_qml.py
"""

import sys
import os

# Ensure project root on path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Set Material theme before any Qt imports
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"
os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"] = "Dark"
os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] = "#00d4aa"

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QUrl, QCoreApplication
from PySide6.QtQml import QQmlApplicationEngine

# Ensure PySide6 QML plugins are found
import PySide6
_pyside_dir = os.path.dirname(PySide6.__file__)
os.environ.setdefault("QML2_IMPORT_PATH", os.path.join(_pyside_dir, "qml"))
os.environ.setdefault("QT_PLUGIN_PATH", os.path.join(_pyside_dir, "plugins"))

from core.engine import Engine
from ui.backend import Backend


def _app_icon() -> QIcon:
    """Load the app icon from the pre-cropped .ico file."""
    ico = os.path.join(ROOT, "images", "logo.ico")
    return QIcon(ico)


def main():
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("LogiControl")
    app.setOrganizationName("LogiControl")
    app.setWindowIcon(_app_icon())

    # ── Engine ─────────────────────────────────────────────────
    engine = Engine()
    engine.start()
    print("[LogiControl] Engine started — remapping is active")

    # ── QML Backend ────────────────────────────────────────────
    backend = Backend(engine)

    # ── QML Engine ─────────────────────────────────────────────
    qml_engine = QQmlApplicationEngine()
    qml_engine.rootContext().setContextProperty("backend", backend)
    qml_engine.rootContext().setContextProperty(
        "applicationDirPath", ROOT.replace("\\", "/"))

    qml_path = os.path.join(ROOT, "ui", "qml", "Main.qml")
    qml_engine.load(QUrl.fromLocalFile(qml_path))

    if not qml_engine.rootObjects():
        print("[LogiControl] FATAL: Failed to load QML")
        sys.exit(1)

    root_window = qml_engine.rootObjects()[0]

    # ── System Tray ────────────────────────────────────────────
    tray = QSystemTrayIcon(_app_icon(), app)
    tray.setToolTip("LogiControl — MX Master 3S")

    tray_menu = QMenu()

    open_action = QAction("Open Settings", tray_menu)
    open_action.triggered.connect(lambda: (
        root_window.show(),
        root_window.raise_(),
        root_window.requestActivate(),
    ))
    tray_menu.addAction(open_action)

    toggle_action = QAction("Disable Remapping", tray_menu)

    def toggle_remapping():
        enabled = not engine._enabled
        engine.set_enabled(enabled)
        toggle_action.setText(
            "Disable Remapping" if enabled else "Enable Remapping")

    toggle_action.triggered.connect(toggle_remapping)
    tray_menu.addAction(toggle_action)

    tray_menu.addSeparator()

    quit_action = QAction("Quit LogiControl", tray_menu)

    def quit_app():
        engine.hook.stop()
        engine._app_detector.stop()
        tray.hide()
        app.quit()

    quit_action.triggered.connect(quit_app)
    tray_menu.addAction(quit_action)

    tray.setContextMenu(tray_menu)
    tray.activated.connect(lambda reason: (
        root_window.show(),
        root_window.raise_(),
        root_window.requestActivate(),
    ) if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()

    # ── Run ────────────────────────────────────────────────────
    try:
        sys.exit(app.exec())
    finally:
        engine.hook.stop()
        engine._app_detector.stop()
        print("[LogiControl] Shut down cleanly")


if __name__ == "__main__":
    main()
