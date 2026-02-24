"""
Main configuration window for LogiControl.
Draws a visual representation of the MX Master 3S matching the
Logi Options+ layout (front-left + side-right views) and lets
the user choose an action for every remappable button / scroll.
Includes Point & Scroll settings and per-application Profiles.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

# Add parent to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    BUTTON_NAMES, load_config, save_config,
    get_active_mappings, set_mapping,
    create_profile, delete_profile,
    KNOWN_APPS,
)
from key_simulator import ACTIONS

# ── Colour palette (dark theme matching Logi Options+) ───────────
BG           = "#1a1a2e"
BG_CARD      = "#242438"
BG_HOVER     = "#2e2e46"
ACCENT       = "#00d4aa"   # Logitech teal-green
ACCENT_DIM   = "#1a6b55"
DOT          = "#00d4aa"
DOT_GLOW     = "#00ffc8"
TEXT         = "#e0e0e0"
TEXT_DIM     = "#808098"
TEXT_LABEL   = "#b0b0c8"
SUCCESS      = "#00d4aa"
BORDER       = "#2e2e46"
LINE_COLOR   = "#ff4466"   # Red annotation lines
MOUSE_BODY   = "#3a3a50"
MOUSE_DARK   = "#2a2a3c"
WARN_FG      = "#ffaa44"

# ── Helpers ───────────────────────────────────────────────────────
def action_choices():
    """Return list of (action_id, label) sorted by category then label."""
    items = [(aid, a["label"], a["category"]) for aid, a in ACTIONS.items()]
    items.sort(key=lambda x: (x[2], x[1]))
    return [(aid, label) for aid, label, _ in items]


def get_action_label(action_id):
    a = ACTIONS.get(action_id, {})
    return a.get("label", "Do Nothing")


# ══════════════════════════════════════════════════════════════════
class MainWindow:
    """The main LogiControl configuration window."""

    TAB_MOUSE = 0
    TAB_SCROLL = 1
    TAB_PROFILES = 2

    def __init__(self, root, engine=None):
        self.root = root
        self.engine = engine
        self.cfg = load_config()
        self.combos = {}
        self._active_button = None
        self._active_button2 = None
        self._active_tab = self.TAB_MOUSE
        self._test_active = False

        self._setup_window()
        self._build_ui()

        # Let the engine notify us of auto profile switches
        if self.engine:
            self.engine.set_profile_change_callback(self._on_engine_profile_switch)
            self.engine.set_dpi_read_callback(self._on_device_dpi_read)

    # ── window chrome ─────────────────────────────────────────────
    def _setup_window(self):
        self.root.title("LogiControl  -  MX Master 3S")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        w, h = 960, 740
        sx = self.root.winfo_screenwidth()
        sy = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sx-w)//2}+{(sy-h)//2}")

        # Dark title bar on Windows 10/11
        try:
            import ctypes
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT,
                         font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=BG, foreground=TEXT,
                         font=("Segoe UI Semibold", 20))
        style.configure("Sub.TLabel", background=BG, foreground=TEXT_DIM,
                         font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=BG, foreground=SUCCESS,
                         font=("Segoe UI", 9))

        style.configure("Accent.TButton",
                         background=ACCENT, foreground="#1a1a2e",
                         font=("Segoe UI Semibold", 10), padding=(16, 8))
        style.map("Accent.TButton",
                   background=[("active", DOT_GLOW)])

        style.configure("TCombobox",
                         fieldbackground=BG_CARD, background=BG_CARD,
                         foreground=TEXT, selectbackground=ACCENT,
                         selectforeground="#1a1a2e", arrowcolor=TEXT,
                         font=("Segoe UI", 10))
        self.root.option_add("*TCombobox*Listbox*Background", BG_CARD)
        self.root.option_add("*TCombobox*Listbox*Foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox*selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#1a1a2e")
        self.root.option_add("*TCombobox*Listbox*Font", ("Segoe UI", 10))

    # ══════════════════════════════════════════════════════════════
    # Build UI — master layout
    # ══════════════════════════════════════════════════════════════
    def _build_ui(self):
        pad = 24

        # ── Top bar: tabs ─────────────────────────────────────────
        top_bar = tk.Frame(self.root, bg=BG)
        top_bar.pack(fill="x", padx=pad, pady=(pad, 0))

        tab_frame = tk.Frame(top_bar, bg=BG)
        tab_frame.pack(side="left")

        self._tab_labels = []
        for i, name in enumerate(("Mouse", "Point & Scroll", "Profiles")):
            lbl = tk.Label(tab_frame, text=name, bg=BG,
                           fg=ACCENT if i == 0 else TEXT_DIM,
                           font=("Segoe UI Semibold", 12), cursor="hand2")
            lbl.pack(side="left", padx=(0, 24))
            lbl.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            self._tab_labels.append(lbl)

        # Underline placeholder
        self._ul_frame = tk.Frame(self.root, bg=BG)
        self._ul_frame.pack(fill="x", padx=pad, pady=(2, 0))
        self._ul_bar = tk.Frame(self._ul_frame, bg=ACCENT, height=2, width=52)
        self._ul_bar.pack(anchor="w")

        self.status_label = tk.Label(top_bar, text="   Running", bg=BG,
                                     fg=SUCCESS, font=("Segoe UI", 9))
        self.status_label.pack(side="right")

        # Separator
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x",
                                                        padx=pad, pady=(8, 0))

        # ── Tab content container ─────────────────────────────────
        self._tab_container = tk.Frame(self.root, bg=BG)
        self._tab_container.pack(fill="both", expand=True, padx=0, pady=0)

        self._tab_frames = []
        for _ in range(3):
            f = tk.Frame(self._tab_container, bg=BG)
            self._tab_frames.append(f)

        self._build_mouse_tab(self._tab_frames[0])
        self._build_scroll_tab(self._tab_frames[1])
        self._build_profiles_tab(self._tab_frames[2])

        # Show the mouse tab by default
        self._show_tab(self.TAB_MOUSE)

    # ── tab switching ─────────────────────────────────────────────
    def _switch_tab(self, idx):
        if idx == self._active_tab:
            return
        self._active_tab = idx
        self._show_tab(idx)

    def _show_tab(self, idx):
        for i, f in enumerate(self._tab_frames):
            f.pack_forget()
        self._tab_frames[idx].pack(fill="both", expand=True)

        # Update tab label colours
        for i, lbl in enumerate(self._tab_labels):
            lbl.configure(fg=ACCENT if i == idx else TEXT_DIM)

        # Refresh tab-specific content
        if idx == self.TAB_SCROLL:
            self._refresh_scroll_tab()
        elif idx == self.TAB_PROFILES:
            self._refresh_profiles_tab()

    # ══════════════════════════════════════════════════════════════
    # TAB 1: Mouse (button mapping canvas)
    # ══════════════════════════════════════════════════════════════
    def _build_mouse_tab(self, parent):
        pad = 24

        # Canvas
        self.canvas = tk.Canvas(parent, width=912, height=400, bg=BG,
                                highlightthickness=0)
        self.canvas.pack(padx=pad, pady=(12, 0))
        self._draw_mice()

        # Separator
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x",
                                                     padx=pad, pady=(8, 0))

        # Config panel
        self.config_frame = tk.Frame(parent, bg=BG)
        self.config_frame.pack(fill="x", padx=pad, pady=(12, 0))
        self._build_config_panel()

        # Footer
        footer = tk.Frame(parent, bg=BG)
        footer.pack(fill="x", padx=pad, pady=(8, pad))

        tk.Label(footer,
                 text="Click a green dot on the mouse to configure that button",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side="left")

        btn = ttk.Button(footer, text="Minimize to Tray",
                         style="Accent.TButton", command=self._minimize_to_tray)
        btn.pack(side="right")

        self._test_btn = tk.Label(footer, text="  Test Buttons  ",
                                  bg=BG_CARD, fg=TEXT, cursor="hand2",
                                  font=("Segoe UI Semibold", 9),
                                  padx=10, pady=5)
        self._test_btn.pack(side="right", padx=(0, 12))
        self._test_btn.bind("<Button-1>", lambda e: self._toggle_test_mode())
        self._test_btn.bind("<Enter>",
                            lambda e: self._test_btn.configure(bg=ACCENT, fg="#1a1a2e"))
        self._test_btn.bind("<Leave>",
                            lambda e: self._test_btn.configure(
                                bg=("#553333" if self._test_active else BG_CARD),
                                fg=TEXT))

        # Debug output area (hidden until test mode)
        self._debug_frame = tk.Frame(parent, bg=BG)
        self._debug_text = tk.Text(self._debug_frame, bg="#0e0e1a", fg="#66ff88",
                                   font=("Consolas", 9), height=5, width=100,
                                   state="disabled", wrap="word",
                                   insertbackground="#66ff88",
                                   highlightthickness=1,
                                   highlightbackground=BORDER)
        self._debug_text.pack(fill="x", padx=24, pady=(4, 8))

    # ── draw two mouse views (front-left and side-right) ──────────
    def _draw_mice(self):
        c = self.canvas
        mappings = get_active_mappings(self.cfg)

        # ══ LEFT VIEW (front-left, showing top, middle & gesture) ═
        lx, ly = 200, 200
        body = [
            lx - 55, ly - 130,  lx - 68, ly - 70,  lx - 72, ly - 10,
            lx - 68, ly + 50,   lx - 55, ly + 95,   lx - 35, ly + 125,
            lx,      ly + 138,  lx + 35, ly + 125,  lx + 55, ly + 95,
            lx + 68, ly + 50,   lx + 72, ly - 10,   lx + 68, ly - 70,
            lx + 55, ly - 130,  lx + 20, ly - 142,  lx - 20, ly - 142,
        ]
        c.create_polygon(body, fill=MOUSE_BODY, outline=MOUSE_DARK,
                         width=2, smooth=True)
        c.create_line(lx, ly - 142, lx, ly - 45, fill="#4a4a60", width=1)
        c.create_oval(lx - 8, ly - 125, lx + 8, ly - 95,
                      fill="#222236", outline=ACCENT, width=2)
        gx, gy = lx - 64, ly + 15
        c.create_oval(gx - 14, gy - 14, gx + 14, gy + 14,
                      fill=MOUSE_DARK, outline="#4a4a60", width=1)

        self._draw_dot(c, lx, ly - 110, "middle")
        self._draw_dot(c, gx, gy, "gesture")

        # Annotation: Middle button
        mx_end, my_end = lx + 130, ly - 155
        c.create_line(lx, ly - 110, mx_end, my_end,
                      fill=LINE_COLOR, width=1, dash=(3, 2))
        c.create_oval(mx_end - 3, my_end - 3, mx_end + 3, my_end + 3,
                      fill=LINE_COLOR, outline="")
        c.create_text(mx_end + 10, my_end, text="Middle button",
                      anchor="w", fill=TEXT_LABEL, font=("Segoe UI Semibold", 9))
        mid_action = get_action_label(mappings.get("middle", "none"))
        self._middle_label_id = c.create_text(
            mx_end + 10, my_end + 16,
            text=f"Keystroke assignment : {mid_action}",
            anchor="w", fill=TEXT_DIM, font=("Segoe UI", 8))

        # Annotation: Gesture button
        gx_end, gy_end = lx - 175, ly + 75
        c.create_line(gx, gy, gx_end + 90, gy_end,
                      fill=LINE_COLOR, width=1, dash=(3, 2))
        c.create_oval(gx_end + 87, gy_end - 3, gx_end + 93, gy_end + 3,
                      fill=LINE_COLOR, outline="")
        gest_action = get_action_label(mappings.get("gesture", "none"))
        c.create_text(gx_end - 10, gy_end - 10,
                      text="Gesture button", anchor="w",
                      fill=TEXT_LABEL, font=("Segoe UI Semibold", 9))
        self._gesture_label_id = c.create_text(
            gx_end - 10, gy_end + 8,
            text=f"Keystroke assignment : {gest_action}",
            anchor="w", fill=TEXT_DIM, font=("Segoe UI", 8))

        # ══ RIGHT VIEW (side, showing back/fwd buttons & hscroll) ═
        rx, ry = 580, 200
        side = [
            rx - 75, ry - 100,  rx - 88, ry - 40,  rx - 85, ry + 30,
            rx - 68, ry + 80,   rx - 40, ry + 115,  rx + 10, ry + 125,
            rx + 55, ry + 108,  rx + 85, ry + 60,   rx + 92, ry + 0,
            rx + 82, ry - 55,   rx + 60, ry - 100,  rx + 25, ry - 118,
            rx - 25, ry - 118,  rx - 58, ry - 108,
        ]
        c.create_polygon(side, fill=MOUSE_BODY, outline=MOUSE_DARK,
                         width=2, smooth=True)
        hwx, hwy = rx - 70, ry - 50
        c.create_oval(hwx - 14, hwy - 10, hwx + 14, hwy + 10,
                      fill="#222236", outline=ACCENT, width=2)
        fx, fy = rx - 58, ry + 8
        c.create_rectangle(fx - 18, fy - 12, fx + 18, fy + 2,
                           fill=MOUSE_DARK, outline="#4a4a60", width=1)
        bx, by = rx - 58, ry + 28
        c.create_rectangle(bx - 18, by - 2, bx + 18, by + 12,
                           fill=MOUSE_DARK, outline="#4a4a60", width=1)

        self._draw_dot(c, hwx, hwy, "hscroll")
        self._draw_dot(c, fx, fy - 5, "xbutton2")
        self._draw_dot(c, bx, by + 5, "xbutton1")

        # Annotation: Horizontal scroll
        hx_end, hy_end = rx + 120, ry - 120
        c.create_line(hwx, hwy, hx_end, hy_end,
                      fill=LINE_COLOR, width=1, dash=(3, 2))
        c.create_oval(hx_end - 3, hy_end - 3, hx_end + 3, hy_end + 3,
                      fill=LINE_COLOR, outline="")
        c.create_text(hx_end + 10, hy_end, text="Horizontal scroll",
                      anchor="w", fill=TEXT_LABEL, font=("Segoe UI Semibold", 9))
        hl = get_action_label(mappings.get("hscroll_left", "none"))
        hr = get_action_label(mappings.get("hscroll_right", "none"))
        self._hscroll_label_id = c.create_text(
            hx_end + 10, hy_end + 16,
            text=f"Left: {hl}  |  Right: {hr}",
            anchor="w", fill=TEXT_DIM, font=("Segoe UI", 8))

        # Annotation: Forward button
        fx_end, fy_end = rx + 80, ry + 50
        c.create_line(fx, fy - 5, fx_end, fy_end,
                      fill=LINE_COLOR, width=1, dash=(3, 2))
        c.create_oval(fx_end - 3, fy_end - 3, fx_end + 3, fy_end + 3,
                      fill=LINE_COLOR, outline="")
        fwd_action = get_action_label(mappings.get("xbutton2", "none"))
        c.create_text(fx_end + 10, fy_end, text="Forward button",
                      anchor="w", fill=TEXT_LABEL, font=("Segoe UI Semibold", 9))
        self._fwd_label_id = c.create_text(
            fx_end + 10, fy_end + 16,
            text=f"Keystroke assignment : {fwd_action}",
            anchor="w", fill=TEXT_DIM, font=("Segoe UI", 8))

        # Annotation: Back button
        bx_end, by_end = rx + 80, ry + 100
        c.create_line(bx, by + 5, bx_end, by_end,
                      fill=LINE_COLOR, width=1, dash=(3, 2))
        c.create_oval(bx_end - 3, by_end - 3, bx_end + 3, by_end + 3,
                      fill=LINE_COLOR, outline="")
        back_action = get_action_label(mappings.get("xbutton1", "none"))
        c.create_text(bx_end + 10, by_end, text="Back button",
                      anchor="w", fill=TEXT_LABEL, font=("Segoe UI Semibold", 9))
        self._back_label_id = c.create_text(
            bx_end + 10, by_end + 16,
            text=f"Keystroke assignment : {back_action}",
            anchor="w", fill=TEXT_DIM, font=("Segoe UI", 8))

        # Model label
        c.create_text(400, ry + 170, text="Logitech MX Master 3S",
                      fill=TEXT_DIM, font=("Segoe UI Semibold", 10))

    # ── draw a teal interactive dot ───────────────────────────────
    def _draw_dot(self, canvas, x, y, btn_key, radius=8):
        glow = canvas.create_oval(x - radius - 4, y - radius - 4,
                                  x + radius + 4, y + radius + 4,
                                  fill="", outline=DOT_GLOW, width=1,
                                  stipple="gray25")
        dot = canvas.create_oval(x - radius, y - radius,
                                 x + radius, y + radius,
                                 fill=DOT, outline="", activefill=DOT_GLOW)

        def on_click(event, bk=btn_key):
            self._select_button(bk)

        canvas.tag_bind(dot, "<Button-1>", on_click)
        canvas.tag_bind(glow, "<Button-1>", on_click)

    # ── bottom config panel ───────────────────────────────────────
    def _build_config_panel(self):
        self.panel_title = tk.Label(self.config_frame,
                                    text="Select a button on the mouse above",
                                    bg=BG, fg=TEXT,
                                    font=("Segoe UI Semibold", 12))
        self.panel_title.pack(anchor="w")

        self.panel_desc = tk.Label(self.config_frame,
                                   text="Click any green dot to configure its action",
                                   bg=BG, fg=TEXT_DIM, font=("Segoe UI", 9))
        self.panel_desc.pack(anchor="w", pady=(2, 8))

        # Combo row
        self.combo_row = tk.Frame(self.config_frame, bg=BG)
        self.combo_row.pack(fill="x")

        choices = action_choices()
        self._choice_labels = [label for _, label in choices]
        self._choice_ids = [aid for aid, _ in choices]

        self.combo_lbl = tk.Label(self.combo_row, text="Action:",
                                  bg=BG, fg=TEXT_LABEL,
                                  font=("Segoe UI", 10))
        self.combo_lbl.pack(side="left", padx=(0, 8))

        self.combo_var = tk.StringVar()
        self.combo = ttk.Combobox(self.combo_row, textvariable=self.combo_var,
                                  values=self._choice_labels, state="readonly",
                                  width=42)
        self.combo.pack(side="left", padx=(0, 16))
        self.combo.bind("<<ComboboxSelected>>", self._on_action_selected)

        self.combo2_lbl = tk.Label(self.combo_row, text="Scroll Right:",
                                   bg=BG, fg=TEXT_LABEL,
                                   font=("Segoe UI", 10))
        self.combo2_var = tk.StringVar()
        self.combo2 = ttk.Combobox(self.combo_row, textvariable=self.combo2_var,
                                   values=self._choice_labels, state="readonly",
                                   width=42)
        self.combo2.bind("<<ComboboxSelected>>", self._on_action2_selected)
        self.combo2_lbl.pack_forget()
        self.combo2.pack_forget()

        # Quick picks
        self.quick_frame = tk.Frame(self.config_frame, bg=BG)
        self.quick_frame.pack(fill="x", pady=(10, 0))

    # ── button selection / actions (Mouse tab) ────────────────────
    def _select_button(self, btn_key):
        mappings = get_active_mappings(self.cfg)

        if btn_key == "hscroll":
            self._active_button = "hscroll_left"
            self._active_button2 = "hscroll_right"
            self.panel_title.configure(text="Horizontal scroll (thumb wheel)")
            self.panel_desc.configure(
                text="Configure separate actions for left and right scroll")
            self.combo_lbl.configure(text="Scroll Left:")
            self.combo_var.set(
                get_action_label(mappings.get("hscroll_left", "none")))
            self.combo2_var.set(
                get_action_label(mappings.get("hscroll_right", "none")))
            self.combo2_lbl.pack(side="left", padx=(0, 8))
            self.combo2.pack(side="left")
        else:
            self._active_button = btn_key
            self._active_button2 = None
            name = BUTTON_NAMES.get(btn_key, btn_key)
            self.panel_title.configure(text=name)
            self._set_button_panel_desc(btn_key, mappings)
            self.combo_lbl.configure(text="Action:")
            self.combo_var.set(
                get_action_label(mappings.get(btn_key, "none")))
            self.combo2_lbl.pack_forget()
            self.combo2.pack_forget()

        self._update_quick_picks(btn_key)

    def _set_button_panel_desc(self, btn_key, mappings):
        middle_action = mappings.get("middle", "none")
        gesture_action = mappings.get("gesture", "none")
        conflict = middle_action != "none" and gesture_action != "none"

        if btn_key == "gesture":
            if conflict:
                self.panel_desc.configure(
                    text="Warning: Gesture may not fire while Middle is mapped. "
                         "Set Middle to Pass-through.")
            else:
                self.panel_desc.configure(
                    text="Without Logi Options+, this button sends Middle Click")
            return
        if btn_key == "middle" and conflict:
            self.panel_desc.configure(
                text="Warning: Middle and Gesture are both mapped and can conflict.")
            return
        self.panel_desc.configure(
            text="Choose what happens when you press this button")

    def _on_action_selected(self, event):
        idx = self.combo.current()
        if idx >= 0 and self._active_button:
            action_id = self._choice_ids[idx]
            self.cfg = set_mapping(self.cfg, self._active_button, action_id)
            if self.engine:
                self.engine.reload_mappings()
            if self._active_button in ("middle", "gesture"):
                mappings = get_active_mappings(self.cfg)
                self._set_button_panel_desc(self._active_button, mappings)
            self._flash_status("Saved")
            self._refresh_canvas_labels()

    def _on_action2_selected(self, event):
        idx = self.combo2.current()
        if idx >= 0 and self._active_button2:
            action_id = self._choice_ids[idx]
            self.cfg = set_mapping(self.cfg, self._active_button2, action_id)
            if self.engine:
                self.engine.reload_mappings()
            self._flash_status("Saved")
            self._refresh_canvas_labels()

    def _update_quick_picks(self, btn_key):
        for w in self.quick_frame.winfo_children():
            w.destroy()

        quick_map = {
            "xbutton1": ["alt_tab", "browser_back", "browser_forward",
                         "copy", "paste"],
            "xbutton2": ["alt_tab", "browser_back", "browser_forward",
                         "copy", "paste"],
            "hscroll":  ["volume_up", "volume_down",
                         "browser_back", "browser_forward"],
            "middle":   ["alt_tab", "play_pause", "win_d", "none"],
            "gesture":  ["alt_tab", "task_view", "win_d", "play_pause"],
        }
        quick = quick_map.get(btn_key, ["alt_tab", "browser_back",
                                         "browser_forward"])

        tk.Label(self.quick_frame, text="Quick pick:",
                 bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))

        for aid in quick:
            label = ACTIONS.get(aid, {}).get("label", aid)
            chip = tk.Label(self.quick_frame, text=label,
                            bg=BG_CARD, fg=TEXT, font=("Segoe UI", 9),
                            padx=10, pady=4, cursor="hand2")
            chip.pack(side="left", padx=(0, 6))
            chip.bind("<Enter>",
                      lambda e, w=chip: w.configure(bg=ACCENT, fg="#1a1a2e"))
            chip.bind("<Leave>",
                      lambda e, w=chip: w.configure(bg=BG_CARD, fg=TEXT))
            chip.bind("<Button-1>",
                      lambda e, a=aid: self._quick_set(a))

    def _quick_set(self, action_id):
        if self._active_button:
            self.cfg = set_mapping(self.cfg, self._active_button, action_id)
            self.combo_var.set(get_action_label(action_id))
            if self.engine:
                self.engine.reload_mappings()
            if self._active_button in ("middle", "gesture"):
                mappings = get_active_mappings(self.cfg)
                self._set_button_panel_desc(self._active_button, mappings)
            self._flash_status("Saved")
            self._refresh_canvas_labels()

    # refresh annotation labels on canvas
    def _refresh_canvas_labels(self):
        c = self.canvas
        m = get_active_mappings(self.cfg)
        if hasattr(self, '_middle_label_id'):
            c.itemconfigure(self._middle_label_id,
                            text=f"Keystroke assignment : "
                                 f"{get_action_label(m.get('middle','none'))}")
        if hasattr(self, '_gesture_label_id'):
            c.itemconfigure(self._gesture_label_id,
                            text=f"Keystroke assignment : "
                                 f"{get_action_label(m.get('gesture','none'))}")
        if hasattr(self, '_back_label_id'):
            c.itemconfigure(self._back_label_id,
                            text=f"Keystroke assignment : "
                                 f"{get_action_label(m.get('xbutton1','none'))}")
        if hasattr(self, '_fwd_label_id'):
            c.itemconfigure(self._fwd_label_id,
                            text=f"Keystroke assignment : "
                                 f"{get_action_label(m.get('xbutton2','none'))}")
        if hasattr(self, '_hscroll_label_id'):
            la = get_action_label(m.get("hscroll_left", "none"))
            ra = get_action_label(m.get("hscroll_right", "none"))
            c.itemconfigure(self._hscroll_label_id,
                            text=f"Left: {la}  |  Right: {ra}")

    # ── test / detect mode ────────────────────────────────────────
    def _toggle_test_mode(self):
        if self._test_active:
            self._test_active = False
            self._test_btn.configure(text="  Test Buttons  ", bg=BG_CARD)
            self._debug_frame.pack_forget()
            if self.engine:
                self.engine.hook.debug_mode = False
                self.engine.hook._debug_callback = None
            self.root.geometry("960x740")
        else:
            self._test_active = True
            self._test_btn.configure(text="  Stop Test  ", bg="#553333")
            self._debug_frame.pack(fill="x", after=self.canvas)
            self._debug_text.configure(state="normal")
            self._debug_text.delete("1.0", "end")
            self._debug_text.insert("end",
                ">>> Test mode ON — press any mouse button to see what it sends <<<\n")
            self._debug_text.configure(state="disabled")
            self.root.geometry("960x840")
            if self.engine:
                self.engine.hook.debug_mode = True
                self.engine.hook.set_debug_callback(self._on_debug_event)

    def _on_debug_event(self, info):
        self.root.after(0, self._append_debug, info)

    def _append_debug(self, info):
        self._debug_text.configure(state="normal")
        self._debug_text.insert("end", info + "\n")
        self._debug_text.see("end")
        lines = int(self._debug_text.index("end-1c").split(".")[0])
        if lines > 50:
            self._debug_text.delete("1.0", f"{lines - 50}.0")
        self._debug_text.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════
    # TAB 2: Point & Scroll
    # ══════════════════════════════════════════════════════════════
    def _build_scroll_tab(self, parent):
        pad = 24
        content = tk.Frame(parent, bg=BG)
        content.pack(fill="both", expand=True, padx=pad, pady=pad)

        tk.Label(content, text="Point & Scroll", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(content, text="Adjust pointer speed and scroll behaviour",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 20))

        # ── Pointer speed (DPI) ───────────────────────────────────
        dpi_frame = tk.Frame(content, bg=BG_CARD, padx=16, pady=14)
        dpi_frame.pack(fill="x", pady=(0, 16))

        tk.Label(dpi_frame, text="Pointer Speed (DPI)", bg=BG_CARD, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(dpi_frame,
                 text="Adjust the tracking speed of the sensor. "
                      "Higher values = faster pointer.",
                 bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))

        slider_row = tk.Frame(dpi_frame, bg=BG_CARD)
        slider_row.pack(fill="x")

        tk.Label(slider_row, text="200", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left")

        current_dpi = self.cfg.get("settings", {}).get("dpi", 1000)
        self._dpi_var = tk.IntVar(value=current_dpi)
        self._dpi_scale = tk.Scale(slider_row, from_=200, to=8000,
                                   orient="horizontal", variable=self._dpi_var,
                                   bg=BG_CARD, fg=TEXT, troughcolor=BG,
                                   highlightthickness=0, sliderrelief="flat",
                                   activebackground=DOT_GLOW,
                                   resolution=50, length=500, showvalue=False,
                                   command=self._on_dpi_change)
        self._dpi_scale.pack(side="left", padx=8, fill="x", expand=True)

        tk.Label(slider_row, text="8000", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left")

        self._dpi_value_label = tk.Label(slider_row,
                                         text=f"  {current_dpi} DPI",
                                         bg=BG_CARD, fg=ACCENT,
                                         font=("Segoe UI Semibold", 11),
                                         width=10)
        self._dpi_value_label.pack(side="left", padx=(16, 0))

        # Quick DPI buttons
        dpi_quick = tk.Frame(dpi_frame, bg=BG_CARD)
        dpi_quick.pack(fill="x", pady=(6, 0))
        tk.Label(dpi_quick, text="Presets:", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        for val in (400, 800, 1000, 1600, 2400, 4000, 6000, 8000):
            chip = tk.Label(dpi_quick, text=str(val), bg=BG, fg=TEXT,
                            font=("Segoe UI", 9), padx=10, pady=3,
                            cursor="hand2")
            chip.pack(side="left", padx=(0, 6))
            chip.bind("<Enter>",
                      lambda e, w=chip: w.configure(bg=ACCENT, fg="#1a1a2e"))
            chip.bind("<Leave>",
                      lambda e, w=chip: w.configure(bg=BG, fg=TEXT))
            chip.bind("<Button-1>",
                      lambda e, v=val: self._set_dpi(v))

        # ── Scroll options ────────────────────────────────────────
        scroll_frame = tk.Frame(content, bg=BG_CARD, padx=16, pady=14)
        scroll_frame.pack(fill="x", pady=(0, 16))

        tk.Label(scroll_frame, text="Scroll Direction", bg=BG_CARD, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(scroll_frame,
                 text="Invert the scroll direction (natural scrolling)",
                 bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))

        settings = self.cfg.get("settings", {})

        self._invert_vscroll_var = tk.BooleanVar(
            value=settings.get("invert_vscroll", False))
        cb_v = tk.Checkbutton(scroll_frame, text="Invert vertical scroll",
                              variable=self._invert_vscroll_var,
                              bg=BG_CARD, fg=TEXT, selectcolor=BG,
                              activebackground=BG_CARD, activeforeground=TEXT,
                              font=("Segoe UI", 10),
                              command=self._on_scroll_toggle)
        cb_v.pack(anchor="w", pady=(0, 6))

        self._invert_hscroll_var = tk.BooleanVar(
            value=settings.get("invert_hscroll", False))
        cb_h = tk.Checkbutton(scroll_frame, text="Invert horizontal scroll",
                              variable=self._invert_hscroll_var,
                              bg=BG_CARD, fg=TEXT, selectcolor=BG,
                              activebackground=BG_CARD, activeforeground=TEXT,
                              font=("Segoe UI", 10),
                              command=self._on_scroll_toggle)
        cb_h.pack(anchor="w")

        # ── Note ──────────────────────────────────────────────────
        note_frame = tk.Frame(content, bg=BG_CARD, padx=16, pady=12)
        note_frame.pack(fill="x")
        tk.Label(note_frame,
                 text="Note: DPI changes require HID++ communication with the "
                      "device and will take effect after a short delay.",
                 bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 9),
                 wraplength=800, justify="left").pack(anchor="w")

    def _on_device_dpi_read(self, dpi):
        """Called from engine background thread when DPI is read from device."""
        def _update():
            self._dpi_var.set(dpi)
            self._dpi_value_label.configure(text=f"  {dpi} DPI")
            self.cfg.setdefault("settings", {})["dpi"] = dpi
        self.root.after(0, _update)

    def _on_dpi_change(self, val):
        dpi = self._dpi_var.get()
        self._dpi_value_label.configure(text=f"  {dpi} DPI")
        # Debounce: only send HID++ command when user stops sliding
        if hasattr(self, '_dpi_after_id'):
            self.root.after_cancel(self._dpi_after_id)
        self._dpi_after_id = self.root.after(500, lambda: self._apply_dpi(dpi))

    def _apply_dpi(self, dpi):
        """Actually send DPI to the device via engine."""
        if self.engine:
            self.engine.set_dpi(dpi)
        else:
            self.cfg.setdefault("settings", {})["dpi"] = dpi
            save_config(self.cfg)
        self._flash_status(f"DPI → {dpi}")

    def _set_dpi(self, val):
        self._dpi_var.set(val)
        self._dpi_value_label.configure(text=f"  {val} DPI")
        if self.engine:
            self.engine.set_dpi(val)
        else:
            self.cfg.setdefault("settings", {})["dpi"] = val
            save_config(self.cfg)
        self._flash_status(f"DPI → {val}")

    def _on_scroll_toggle(self):
        self.cfg.setdefault("settings", {})["invert_vscroll"] = self._invert_vscroll_var.get()
        self.cfg["settings"]["invert_hscroll"] = self._invert_hscroll_var.get()
        save_config(self.cfg)
        # Tell engine to re-read settings so the hook picks up the change
        if self.engine:
            self.engine.reload_mappings()
        self._flash_status("Saved")

    def _refresh_scroll_tab(self):
        """Re-read config when switching to this tab."""
        settings = self.cfg.get("settings", {})
        self._dpi_var.set(settings.get("dpi", 1000))
        self._dpi_value_label.configure(
            text=f"  {settings.get('dpi', 1000)} DPI")
        self._invert_vscroll_var.set(settings.get("invert_vscroll", False))
        self._invert_hscroll_var.set(settings.get("invert_hscroll", False))

    # ══════════════════════════════════════════════════════════════
    # TAB 3: Profiles
    # ══════════════════════════════════════════════════════════════
    def _build_profiles_tab(self, parent):
        pad = 24
        self._prof_parent = parent

        content = tk.Frame(parent, bg=BG)
        content.pack(fill="both", expand=True, padx=pad, pady=pad)

        tk.Label(content, text="Application Profiles", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(content,
                 text="Automatically switch button mappings when you use a specific app",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 16))

        # Two-column layout: left = profile list, right = detail
        cols = tk.Frame(content, bg=BG)
        cols.pack(fill="both", expand=True)

        # ── Left column: profile list ─────────────────────────────
        left = tk.Frame(cols, bg=BG_CARD, width=260, padx=10, pady=10)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)

        tk.Label(left, text="Profiles", bg=BG_CARD, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))

        self._profile_listbox_frame = tk.Frame(left, bg=BG_CARD)
        self._profile_listbox_frame.pack(fill="both", expand=True)

        # Add-profile row
        add_row = tk.Frame(left, bg=BG_CARD)
        add_row.pack(fill="x", pady=(8, 0))

        self._new_profile_var = tk.StringVar()
        self._new_profile_combo = ttk.Combobox(
            add_row, textvariable=self._new_profile_var,
            values=[info["label"] for info in KNOWN_APPS.values()],
            state="readonly", width=22)
        self._new_profile_combo.pack(side="left", padx=(0, 6))

        add_btn = tk.Label(add_row, text=" + Add ", bg=ACCENT, fg="#1a1a2e",
                           font=("Segoe UI Semibold", 9), padx=8, pady=3,
                           cursor="hand2")
        add_btn.pack(side="left")
        add_btn.bind("<Button-1>", lambda e: self._add_profile())

        # ── Right column: detail / mapping editor ─────────────────
        self._prof_detail = tk.Frame(cols, bg=BG_CARD, padx=16, pady=14)
        self._prof_detail.pack(side="left", fill="both", expand=True)

        self._prof_detail_title = tk.Label(self._prof_detail,
                                           text="Select a profile",
                                           bg=BG_CARD, fg=TEXT,
                                           font=("Segoe UI Semibold", 13))
        self._prof_detail_title.pack(anchor="w")

        self._prof_detail_apps = tk.Label(self._prof_detail,
                                          text="",
                                          bg=BG_CARD, fg=TEXT_DIM,
                                          font=("Segoe UI", 9))
        self._prof_detail_apps.pack(anchor="w", pady=(2, 12))

        # Mapping combos (one per button)
        self._prof_combos = {}
        choices = action_choices()
        self._pchoice_labels = [label for _, label in choices]
        self._pchoice_ids = [aid for aid, _ in choices]

        self._prof_mapping_frame = tk.Frame(self._prof_detail, bg=BG_CARD)
        self._prof_mapping_frame.pack(fill="x")

        for btn_key, btn_label in BUTTON_NAMES.items():
            row = tk.Frame(self._prof_mapping_frame, bg=BG_CARD)
            row.pack(fill="x", pady=3)

            tk.Label(row, text=btn_label, bg=BG_CARD, fg=TEXT_LABEL,
                     font=("Segoe UI", 10), width=22,
                     anchor="w").pack(side="left")

            var = tk.StringVar()
            cb = ttk.Combobox(row, textvariable=var,
                              values=self._pchoice_labels,
                              state="readonly", width=30)
            cb.pack(side="left", padx=(8, 0))
            cb.bind("<<ComboboxSelected>>",
                    lambda e, bk=btn_key: self._on_profile_mapping_change(bk))
            self._prof_combos[btn_key] = (var, cb)

        # Delete button
        self._prof_delete_btn = tk.Label(self._prof_detail,
                                         text="  Delete Profile  ",
                                         bg="#662222", fg=TEXT,
                                         font=("Segoe UI Semibold", 9),
                                         padx=10, pady=5, cursor="hand2")
        self._prof_delete_btn.pack(anchor="w", pady=(16, 0))
        self._prof_delete_btn.bind("<Button-1>",
                                   lambda e: self._delete_selected_profile())
        self._prof_delete_btn.bind(
            "<Enter>",
            lambda e: self._prof_delete_btn.configure(bg="#aa3333"))
        self._prof_delete_btn.bind(
            "<Leave>",
            lambda e: self._prof_delete_btn.configure(bg="#662222"))

        # Active status
        self._prof_active_label = tk.Label(
            self._prof_detail, text="", bg=BG_CARD, fg=SUCCESS,
            font=("Segoe UI", 9))
        self._prof_active_label.pack(anchor="w", pady=(8, 0))

        self._selected_profile = None
        self._populate_profile_list()

    def _populate_profile_list(self):
        """Rebuild the profile list in the left column."""
        for w in self._profile_listbox_frame.winfo_children():
            w.destroy()

        profiles = self.cfg.get("profiles", {})
        active = self.cfg.get("active_profile", "default")

        for pname, pdata in profiles.items():
            label = pdata.get("label", pname)
            apps = pdata.get("apps", [])
            is_active = pname == active

            row = tk.Frame(self._profile_listbox_frame, bg=BG_CARD,
                           padx=6, pady=6, cursor="hand2")
            row.pack(fill="x", pady=1)

            # Active indicator
            ind_color = ACCENT if is_active else BG_CARD
            ind = tk.Frame(row, bg=ind_color, width=4, height=28)
            ind.pack(side="left", padx=(0, 8))
            ind.pack_propagate(False)

            text_frame = tk.Frame(row, bg=BG_CARD)
            text_frame.pack(side="left", fill="x", expand=True)

            tk.Label(text_frame, text=label, bg=BG_CARD, fg=TEXT,
                     font=("Segoe UI Semibold", 10),
                     anchor="w").pack(anchor="w")

            if apps:
                app_labels = [KNOWN_APPS.get(a, {}).get("label", a)
                              for a in apps]
                tk.Label(text_frame, text=", ".join(app_labels),
                         bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 8),
                         anchor="w").pack(anchor="w")
            else:
                tk.Label(text_frame, text="All applications (fallback)",
                         bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 8),
                         anchor="w").pack(anchor="w")

            # Bind click on the whole row
            for widget in (row, text_frame) + tuple(text_frame.winfo_children()):
                widget.bind("<Button-1>",
                            lambda e, p=pname: self._select_profile(p))

    def _select_profile(self, pname):
        self._selected_profile = pname
        profiles = self.cfg.get("profiles", {})
        pdata = profiles.get(pname, {})

        self._prof_detail_title.configure(text=pdata.get("label", pname))

        apps = pdata.get("apps", [])
        if apps:
            app_labels = [KNOWN_APPS.get(a, {}).get("label", a) for a in apps]
            self._prof_detail_apps.configure(
                text=f"Apps: {', '.join(app_labels)}")
        else:
            self._prof_detail_apps.configure(
                text="Applies to all apps not assigned to a specific profile")

        # Fill mapping combos
        mappings = pdata.get("mappings", {})
        for btn_key in BUTTON_NAMES:
            var, cb = self._prof_combos[btn_key]
            action_id = mappings.get(btn_key, "none")
            var.set(get_action_label(action_id))

        # Show/hide delete button (can't delete default)
        if pname == "default":
            self._prof_delete_btn.pack_forget()
        else:
            self._prof_delete_btn.pack(anchor="w", pady=(16, 0))

        active = self.cfg.get("active_profile", "default")
        if pname == active:
            self._prof_active_label.configure(text="\u25cf Currently active")
        else:
            self._prof_active_label.configure(text="")

    def _on_profile_mapping_change(self, btn_key):
        if not self._selected_profile:
            return
        var, cb = self._prof_combos[btn_key]
        idx = cb.current()
        if idx < 0:
            return
        action_id = self._pchoice_ids[idx]

        self.cfg = set_mapping(self.cfg, btn_key, action_id,
                               profile=self._selected_profile)
        if self.engine:
            self.engine.reload_mappings()
        self._flash_status("Saved")
        # If editing active profile, refresh canvas labels
        if self._selected_profile == self.cfg.get("active_profile", "default"):
            self._refresh_canvas_labels()

    def _add_profile(self):
        selected_label = self._new_profile_var.get()
        if not selected_label:
            return

        # Find the exe that matches this label
        exe = None
        for ex, info in KNOWN_APPS.items():
            if info["label"] == selected_label:
                exe = ex
                break
        if not exe:
            return

        # Check if a profile already handles this app
        for pname, pdata in self.cfg.get("profiles", {}).items():
            if exe.lower() in [a.lower() for a in pdata.get("apps", [])]:
                self._flash_status("Already exists")
                return

        # Create profile keyed by app name
        safe_name = exe.replace(".exe", "").lower()
        self.cfg = create_profile(
            self.cfg, safe_name,
            label=selected_label,
            apps=[exe],
            copy_from="default",
        )

        self._populate_profile_list()
        self._select_profile(safe_name)
        self._new_profile_var.set("")
        self._flash_status("Profile created")

        if self.engine:
            self.engine.cfg = self.cfg
            self.engine.reload_mappings()

    def _delete_selected_profile(self):
        if not self._selected_profile or self._selected_profile == "default":
            return
        self.cfg = delete_profile(self.cfg, self._selected_profile)
        self._selected_profile = None
        self._populate_profile_list()
        self._prof_detail_title.configure(text="Select a profile")
        self._prof_detail_apps.configure(text="")
        for btn_key in BUTTON_NAMES:
            var, cb = self._prof_combos[btn_key]
            var.set("")
        self._prof_delete_btn.pack_forget()
        self._prof_active_label.configure(text="")
        self._flash_status("Deleted")

        if self.engine:
            self.engine.cfg = self.cfg
            self.engine.reload_mappings()

    def _refresh_profiles_tab(self):
        self._populate_profile_list()
        if self._selected_profile:
            self._select_profile(self._selected_profile)

    # ══════════════════════════════════════════════════════════════
    # Engine auto-switch callback
    # ══════════════════════════════════════════════════════════════
    def _on_engine_profile_switch(self, profile_name):
        """Called from the engine thread when the active app changes."""
        self.root.after(0, self._handle_profile_switch, profile_name)

    def _handle_profile_switch(self, profile_name):
        self.cfg["active_profile"] = profile_name
        profiles = self.cfg.get("profiles", {})
        label = profiles.get(profile_name, {}).get("label", profile_name)
        self.status_label.configure(
            text=f"   Profile: {label}", fg=ACCENT)
        # Refresh canvas labels with the new active profile's mappings
        self._refresh_canvas_labels()
        # Refresh profiles tab if visible
        if self._active_tab == self.TAB_PROFILES:
            self._refresh_profiles_tab()

    # ══════════════════════════════════════════════════════════════
    # Shared utilities
    # ══════════════════════════════════════════════════════════════
    def _flash_status(self, msg, ms=2000):
        self.status_label.configure(text=f"   {msg}", fg=SUCCESS)
        self.root.after(ms, lambda: self.status_label.configure(
            text="   Running", fg=SUCCESS))

    def _minimize_to_tray(self):
        self.root.withdraw()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
