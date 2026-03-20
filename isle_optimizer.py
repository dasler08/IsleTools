import tkinter as tk
from tkinter import ttk
import os
import shutil
import subprocess
import datetime

# === CONFIG PATH ===
CONFIG_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "TheIsle", "Saved", "Config", "WindowsClient", "GameUserSettings.ini"
)
BACKUP_PATH = CONFIG_PATH + ".backup"

# === COLORS ===
C = {
    "bg":      "#0a0a0a",
    "panel":   "#111111",
    "panel2":  "#161616",
    "border":  "#222222",
    "border2": "#2e2e2e",
    "text":    "#b0b0b0",
    "muted":   "#484848",
    "accent2": "#606060",
    "low":     "#c0392b",
    "mid":     "#b07d20",
    "high":    "#2e7d52",
    "white":   "#e8e8e8",
    "warn":    "#c0392b",
}

# ── Keys the presets will write (must already exist in the file OR be safely addable) ──
# Grouped by ini section so the writer knows where to inject missing keys.
PRESET_KEYS = {
    # section key -> (ini_section_header, keys...)
    "main": "[/Script/Engine.GameUserSettings]",
    "scal": "[ScalabilityGroups]",
    "rend": "[/Script/Engine.RendererSettings]",
}

PRESETS = {
    "LOW": {
        "label": "LOW", "color": C["low"], "desc": "Max FPS · Low fidelity",
        # [/Script/Engine.GameUserSettings]
        "LumenEnabled":           "False",
        "ShadowSmoothing":        "0",    # range 0-3, keep low
        "bUseDynamicResolution":  "False",
        "CloudSetting":           "2",    # max is 2, always at max
        "ScreenPercentage":       "100",
        # [ScalabilityGroups]
        "sg.ViewDistanceQuality": "1",    # 1 on low
        "sg.ShadowQuality":       "3",    # shadows always high (range 0-3)
        "sg.TextureQuality":      "1",    # textures 1 on low
        "sg.EffectsQuality":      "0",    # effects off on low
        "sg.FoliageQuality":      "1",
        "sg.ShadingQuality":      "0",
        "sg.ResolutionQuality":   "0",    # leave as-is (game manages this)
        "sg.LandscapeQuality":    "1",
        # [/Script/Engine.RendererSettings]
        "MotionBlurQuality":      "0",    # off on low (range 0-4)
        "stats": {
            "Lumen":       ("Off",  0),
            "Shadows":     ("High", 3),
            "Shad.Smooth": ("Off",  0),
            "Textures":    ("Low",  1),
            "Effects":     ("Off",  0),
            "View Dist":   ("Low",  1),
            "Clouds":      ("Max",  3),
            "Motion Blur": ("Off",  0),
        },
    },
    "MID": {
        "label": "MID", "color": C["mid"], "desc": "Balanced · Good visuals",
        "LumenEnabled":           "True",
        "ShadowSmoothing":        "0",    # keep low even on mid
        "bUseDynamicResolution":  "False",
        "CloudSetting":           "2",    # max
        "ScreenPercentage":       "100",
        "sg.ViewDistanceQuality": "2",    # 2 on mid
        "sg.ShadowQuality":       "3",    # always high
        "sg.TextureQuality":      "2",    # textures 2
        "sg.EffectsQuality":      "2",    # effects 2
        "sg.FoliageQuality":      "2",
        "sg.ShadingQuality":      "1",
        "sg.ResolutionQuality":   "0",
        "sg.LandscapeQuality":    "2",
        "MotionBlurQuality":      "3",    # blur 3 on mid+ (range 0-4)
        "stats": {
            "Lumen":       ("On",   3),
            "Shadows":     ("High", 3),
            "Shad.Smooth": ("Off",  0),
            "Textures":    ("Mid",  2),
            "Effects":     ("Mid",  2),
            "View Dist":   ("Mid",  2),
            "Clouds":      ("Max",  3),
            "Motion Blur": ("High", 3),
        },
    },
    "HIGH": {
        "label": "HIGH", "color": C["high"], "desc": "Max quality · High-end GPU",
        "LumenEnabled":           "True",
        "ShadowSmoothing":        "0",    # low even on high — your preference
        "bUseDynamicResolution":  "False",
        "CloudSetting":           "2",    # max
        "ScreenPercentage":       "100",
        "sg.ViewDistanceQuality": "3",    # 3 on high
        "sg.ShadowQuality":       "3",    # always high
        "sg.TextureQuality":      "2",    # capped at 2 per your preference
        "sg.EffectsQuality":      "2",    # 2
        "sg.FoliageQuality":      "3",
        "sg.ShadingQuality":      "3",
        "sg.ResolutionQuality":   "0",
        "sg.LandscapeQuality":    "3",
        "MotionBlurQuality":      "3",    # blur 3
        "stats": {
            "Lumen":       ("On",   3),
            "Shadows":     ("High", 3),
            "Shad.Smooth": ("Off",  0),
            "Textures":    ("Mid",  2),
            "Effects":     ("Mid",  2),
            "View Dist":   ("High", 3),
            "Clouds":      ("Max",  3),
            "Motion Blur": ("High", 3),
        },
    },
}

RESOLUTIONS = ["1280x720", "1366x768", "1600x900", "1920x1080", "2560x1440", "3840x2160"]

# Keys to display in the "Current Settings" live strip
LIVE_KEYS = [
    ("Lumen",     "LumenEnabled"),
    ("Shadows",   "sg.ShadowQuality"),
    ("Shd.Smooth","ShadowSmoothing"),
    ("Textures",  "sg.TextureQuality"),
    ("Effects",   "sg.EffectsQuality"),
    ("View Dist", "sg.ViewDistanceQuality"),
    ("Clouds",    "CloudSetting"),
    ("Blur",      "MotionBlurQuality"),
    ("FPS Cap",   "FrameRateLimit"),
]

# ── Friendly display for raw values ──
def friendly(key, raw):
    if raw is None:
        return "?"
    raw = raw.strip()
    if key == "LumenEnabled":
        return "On" if raw.lower() == "true" else "Off"
    if key == "FrameRateLimit":
        try:
            v = float(raw)
            return "Unlim" if v == 0 else str(int(v))
        except Exception:
            return raw
    if key in ("ResolutionSizeX", "ResolutionSizeY"):
        return raw
    return raw


# ── INI read ──
def read_all_values(keys):
    result = {k: None for k in keys}
    if not os.path.exists(CONFIG_PATH):
        return result
    with open(CONFIG_PATH, "r") as f:
        for line in f:
            s = line.strip()
            for k in keys:
                if s.startswith(k + "="):
                    result[k] = s.split("=", 1)[1]
    return result


# Which ini section each key belongs to (for injection when key is missing)
KEY_SECTIONS = {
    "LumenEnabled":          "[/Script/Engine.GameUserSettings]",
    "ShadowSmoothing":       "[/Script/Engine.GameUserSettings]",
    "bUseDynamicResolution": "[/Script/Engine.GameUserSettings]",
    "CloudSetting":          "[/Script/Engine.GameUserSettings]",
    "FrameRateLimit":        "[/Script/Engine.GameUserSettings]",
    "ResolutionSizeX":       "[/Script/Engine.GameUserSettings]",
    "ResolutionSizeY":       "[/Script/Engine.GameUserSettings]",
    "LastUserConfirmedResolutionSizeX": "[/Script/Engine.GameUserSettings]",
    "LastUserConfirmedResolutionSizeY": "[/Script/Engine.GameUserSettings]",
    "sg.ShadowQuality":      "[ScalabilityGroups]",
    "sg.TextureQuality":     "[ScalabilityGroups]",
    "sg.EffectsQuality":     "[ScalabilityGroups]",
    "sg.FoliageQuality":     "[ScalabilityGroups]",
    "sg.ShadingQuality":     "[ScalabilityGroups]",
    "sg.ViewDistanceQuality":"[ScalabilityGroups]",
    "sg.ResolutionQuality":  "[ScalabilityGroups]",
    "sg.LandscapeQuality":   "[ScalabilityGroups]",
    "MotionBlurQuality":     "[/Script/Engine.RendererSettings]",
}

# ── INI write — replaces existing lines; injects missing keys into correct section ──
def write_config_keys(updates: dict):
    if not os.path.exists(CONFIG_PATH):
        return False
    shutil.copy(CONFIG_PATH, BACKUP_PATH)
    with open(CONFIG_PATH, "r") as f:
        lines = f.readlines()

    written = set()
    new_lines = []
    current_section = ""

    for line in lines:
        stripped = line.strip()

        # track which section we're in
        if stripped.startswith("["):
            current_section = stripped.split("]")[0] + "]"

        replaced = False
        for key, value in updates.items():
            if stripped.startswith(key + "="):
                new_lines.append(f"{key}={value}\n")
                written.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

        # after writing a section header, inject any missing keys that belong here
        if stripped.startswith("["):
            for key, value in updates.items():
                if key not in written and KEY_SECTIONS.get(key) == current_section:
                    new_lines.append(f"{key}={value}\n")
                    written.add(key)

    with open(CONFIG_PATH, "w") as f:
        f.writelines(new_lines)
    return True


def restore_backup():
    if os.path.exists(BACKUP_PATH):
        shutil.copy(BACKUP_PATH, CONFIG_PATH)
        return True
    return False


def apply_preset(preset_name, fps_limit, resolution):
    skip = {"label", "color", "desc", "stats"}
    updates = {k: v for k, v in PRESETS[preset_name].items() if k not in skip}
    updates["FrameRateLimit"] = f"{fps_limit}.000000"
    try:
        w, h = resolution.split("x")
        updates["ResolutionSizeX"] = w
        updates["ResolutionSizeY"] = h
        updates["LastUserConfirmedResolutionSizeX"] = w
        updates["LastUserConfirmedResolutionSizeY"] = h
    except Exception:
        pass
    return write_config_keys(updates)


# ─────────────────────────────────────────────────────────────────────────────
class IsleOptimizer:
    W, H = 880, 560

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.W}x{self.H}+200+140")
        self.root.configure(bg=C["bg"])
        self.root.attributes("-alpha", 0.0)

        self._drag_x = 0
        self._drag_y = 0
        self.fps_var    = tk.IntVar(value=0)
        self.res_var    = tk.StringVar(value="1920x1080")
        self.status_var = tk.StringVar(value="Ready — select a preset to apply")
        self.logo_img   = None

        # live-strip label vars: label -> StringVar
        self._live_vars: dict[str, tk.StringVar] = {}

        self._load_logo()
        self._build_chrome()
        self._show_performance()
        self._fade_in()

    # ── logo ─────────────────────────────────────────────────────────────────
    def _load_logo(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(p):
            try:
                self.logo_img = tk.PhotoImage(file=p)
            except Exception:
                pass

    def _fade_in(self, a=0.0):
        if a < 1.0:
            self.root.attributes("-alpha", min(a, 1.0))
            self.root.after(16, lambda: self._fade_in(a + 0.07))
        else:
            self.root.attributes("-alpha", 1.0)

    # ── chrome ───────────────────────────────────────────────────────────────
    def _build_chrome(self):
        # title bar
        tb = tk.Frame(self.root, bg=C["bg"], height=40)
        tb.place(x=0, y=0, width=self.W)
        for ev, cb in (("<Button-1>", self._drag_start), ("<B1-Motion>", self._drag_move)):
            tb.bind(ev, cb)

        tk.Frame(self.root, bg=C["border2"], height=1).place(x=0, y=0, width=self.W)

        cx = 14
        if self.logo_img:
            ll = tk.Label(tb, image=self.logo_img, bg=C["bg"])
            ll.place(x=cx, y=8)
            for ev, cb in (("<Button-1>", self._drag_start), ("<B1-Motion>", self._drag_move)):
                ll.bind(ev, cb)
            cx += 30

        tk.Label(tb, text="THE ISLE", fg=C["white"],  bg=C["bg"],
                 font=("Courier New", 12, "bold")).place(x=cx, y=10)
        tk.Label(tb, text="OPTIMIZER",  fg=C["muted"], bg=C["bg"],
                 font=("Courier New", 12)).place(x=cx+82, y=10)
        tk.Label(tb, text="v1.13",      fg=C["muted"], bg=C["bg"],
                 font=("Courier New", 8)).place(x=cx+170, y=14)

        for sym, cmd, hov, xo in [("×", self._quit, "#c0392b", 18),
                                   ("−", self._minimize, C["muted"], 46)]:
            b = tk.Label(tb, text=sym, fg=C["muted"], bg=C["bg"],
                         cursor="hand2", font=("Courier New", 14, "bold"), width=2)
            b.place(x=self.W - xo, y=8)
            b.bind("<Enter>", lambda e, w=b, c=hov: w.config(fg=c))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["muted"]))
            b.bind("<Button-1>", lambda e, c=cmd: c())

        tk.Frame(self.root, bg=C["border"], height=1).place(x=0, y=40, width=self.W)

        # sidebar
        sb = tk.Frame(self.root, bg=C["panel"])
        sb.place(x=0, y=41, width=64, height=self.H - 41)
        tk.Frame(self.root, bg=C["border"], width=1).place(x=64, y=41, height=self.H - 41)

        for icon, tip, cmd in [("⚡","Perf",self._show_performance),
                                ("▶","Play",self._show_play),
                                ("↺","Restore",self._show_restore)]:
            f  = tk.Frame(sb, bg=C["panel"], cursor="hand2")
            f.pack(fill="x")
            il = tk.Label(f, text=icon, fg=C["muted"], bg=C["panel"],
                          font=("Courier New", 16), pady=6)
            il.pack()
            tl = tk.Label(f, text=tip, fg=C["muted"], bg=C["panel"],
                          font=("Courier New", 7), pady=2)
            tl.pack()
            tk.Frame(f, bg=C["border"], height=1).pack(fill="x")
            ws = [f, il, tl]
            f.bind("<Enter>",    lambda e, w=ws: [x.config(bg=C["panel2"]) for x in w])
            f.bind("<Leave>",    lambda e, w=ws: [x.config(bg=C["panel"])  for x in w])
            f.bind("<Button-1>", lambda e, c=cmd: c())
            for w in [il, tl]:
                w.bind("<Enter>",    lambda e, ww=ws: [x.config(bg=C["panel2"]) for x in ww])
                w.bind("<Leave>",    lambda e, ww=ws: [x.config(bg=C["panel"])  for x in ww])
                w.bind("<Button-1>", lambda e, c=cmd: c())

        # content area (leaves room for status bar at bottom)
        self.content = tk.Frame(self.root, bg=C["bg"])
        self.content.place(x=65, y=41, width=self.W-65, height=self.H-65)

        # status bar
        tk.Frame(self.root, bg=C["border"], height=1).place(x=65, y=self.H-24, width=self.W-65)
        tk.Label(self.root, textvariable=self.status_var,
                 fg=C["muted"], bg=C["bg"], font=("Courier New", 8)).place(x=75, y=self.H-18)

    def _drag_start(self, e): self._drag_x, self._drag_y = e.x, e.y
    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root-self._drag_x}+{e.y_root-self._drag_y}")
    def _quit(self):     self.root.destroy()
    def _minimize(self): self.root.iconify()
    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    # ── live config strip ─────────────────────────────────────────────────────
    def _build_live_strip(self, parent):
        """Reads the current .ini and shows a compact key=value strip."""
        strip = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border2"], highlightthickness=1)
        strip.pack(fill="x", padx=20, pady=(0, 10))

        header = tk.Frame(strip, bg=C["panel"])
        header.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(header, text="CURRENT CONFIG", fg=C["accent2"], bg=C["panel"],
                 font=("Courier New", 8, "bold")).pack(side="left")

        # refresh button
        refresh_lbl = tk.Label(header, text="↻ refresh", fg=C["muted"], bg=C["panel"],
                               font=("Courier New", 7), cursor="hand2")
        refresh_lbl.pack(side="right")
        refresh_lbl.bind("<Enter>", lambda e: refresh_lbl.config(fg=C["white"]))
        refresh_lbl.bind("<Leave>", lambda e: refresh_lbl.config(fg=C["muted"]))
        refresh_lbl.bind("<Button-1>", lambda e: self._refresh_live_strip())

        cells = tk.Frame(strip, bg=C["panel"])
        cells.pack(fill="x", padx=10, pady=(0, 8))

        self._live_vars.clear()
        raw_keys = [rk for _, rk in LIVE_KEYS]
        values   = read_all_values(raw_keys)

        for i, (label, raw_key) in enumerate(LIVE_KEYS):
            val = friendly(raw_key, values[raw_key])
            var = tk.StringVar(value=val)
            self._live_vars[raw_key] = var

            cell = tk.Frame(cells, bg=C["panel2"],
                            highlightbackground=C["border"], highlightthickness=1)
            cell.grid(row=0, column=i, padx=3, pady=2, sticky="nsew")
            cells.columnconfigure(i, weight=1)

            tk.Label(cell, text=label, fg=C["muted"], bg=C["panel2"],
                     font=("Courier New", 6), pady=2).pack()
            tk.Label(cell, textvariable=var, fg=C["white"], bg=C["panel2"],
                     font=("Courier New", 8, "bold"), pady=2).pack()

    def _refresh_live_strip(self):
        raw_keys = [rk for _, rk in LIVE_KEYS]
        values   = read_all_values(raw_keys)
        for raw_key, var in self._live_vars.items():
            var.set(friendly(raw_key, values.get(raw_key)))
        self.status_var.set("↻  Config refreshed")

    # ══════════════════════════════════════════════════════════════════════════
    # PERFORMANCE PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _show_performance(self):
        self._clear()
        c = self.content

        # page header
        hdr = tk.Frame(c, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="GRAPHICS PRESETS", fg=C["white"],
                 bg=C["bg"], font=("Courier New", 12, "bold")).pack(side="left")
        tk.Label(hdr, text="  · tap a preset to apply",
                 fg=C["muted"], bg=C["bg"], font=("Courier New", 8)).pack(side="left", pady=2)
        tk.Frame(c, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 8))

        # ── live strip ──
        self._build_live_strip(c)

        # ── preset cards ──
        cards = tk.Frame(c, bg=C["bg"])
        cards.pack(fill="x", padx=20)
        for name, data in PRESETS.items():
            self._preset_card(cards, name, data)

        tk.Frame(c, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(12, 8))

        # ── FPS + resolution ──
        tune = tk.Frame(c, bg=C["bg"])
        tune.pack(fill="x", padx=20)

        fps_col = tk.Frame(tune, bg=C["bg"])
        fps_col.pack(side="left", padx=(0, 30))
        fps_top = tk.Frame(fps_col, bg=C["bg"])
        fps_top.pack(fill="x")
        tk.Label(fps_top, text="FPS LIMIT", fg=C["accent2"],
                 bg=C["bg"], font=("Courier New", 8, "bold")).pack(side="left")
        self.fps_label = tk.Label(fps_top, text="Unlimited", fg=C["white"],
                                  bg=C["bg"], font=("Courier New", 8, "bold"))
        self.fps_label.pack(side="right", padx=(12, 0))

        def fps_ch(v):
            val = int(float(v))
            self.fps_label.config(text="Unlimited" if val == 0 else str(val))

        tk.Scale(fps_col, from_=0, to=360, orient="horizontal",
                 variable=self.fps_var, bg=C["bg"], fg=C["text"],
                 troughcolor=C["border2"], activebackground=C["accent2"],
                 highlightthickness=0, bd=0, sliderrelief="flat",
                 showvalue=False, length=200, command=fps_ch).pack()
        tk.Label(fps_col, text="0 = unlimited", fg=C["muted"],
                 bg=C["bg"], font=("Courier New", 7)).pack(anchor="w")

        res_col = tk.Frame(tune, bg=C["bg"])
        res_col.pack(side="left")
        tk.Label(res_col, text="RESOLUTION", fg=C["accent2"],
                 bg=C["bg"], font=("Courier New", 8, "bold")).pack(anchor="w")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Isle.TCombobox",
                        fieldbackground=C["panel2"], background=C["panel2"],
                        foreground=C["white"], arrowcolor=C["accent2"],
                        bordercolor=C["border2"], selectbackground=C["panel2"],
                        selectforeground=C["white"])
        style.map("Isle.TCombobox",
                  fieldbackground=[("readonly", C["panel2"])],
                  background=[("readonly", C["panel2"])],
                  foreground=[("readonly", C["white"])])
        ttk.Combobox(res_col, textvariable=self.res_var, values=RESOLUTIONS,
                     state="readonly", style="Isle.TCombobox", width=13).pack(anchor="w", pady=4)

    # ── preset card ───────────────────────────────────────────────────────────
    def _preset_card(self, parent, name, pdata):
        color = pdata["color"]
        stats = pdata["stats"]

        card = tk.Frame(parent, bg=C["panel"],
                        highlightbackground=C["border2"], highlightthickness=1)
        card.pack(side="left", expand=True, fill="both", padx=5, ipady=8, ipadx=8)

        tk.Frame(card, bg=color, height=2).pack(fill="x")
        tk.Label(card, text=name, fg=color, bg=C["panel"],
                 font=("Courier New", 14, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        tk.Label(card, text=pdata["desc"], fg=C["muted"], bg=C["panel"],
                 font=("Courier New", 7)).pack(anchor="w", padx=10)
        tk.Frame(card, bg=C["border"], height=1).pack(fill="x", padx=10, pady=5)

        stat_items = list(stats.items())
        rows = (len(stat_items) + 1) // 2
        grid = tk.Frame(card, bg=C["panel"])
        grid.pack(fill="x", padx=10, pady=(0, 5))

        for ci in range(2):
            col = tk.Frame(grid, bg=C["panel"])
            col.pack(side="left", fill="both", expand=True, padx=(0, 3 if ci == 0 else 0))
            for ri in range(rows):
                idx = ci * rows + ri
                if idx >= len(stat_items): break
                sname, (sval, level) = stat_items[idx]
                row = tk.Frame(col, bg=C["panel"])
                row.pack(fill="x", pady=1)
                tk.Label(row, text=sname, fg=C["muted"], bg=C["panel"],
                         font=("Courier New", 7), width=9, anchor="w").pack(side="left")
                bb = tk.Frame(row, bg=C["border"], height=3, width=38)
                bb.pack(side="left", padx=3)
                bb.pack_propagate(False)
                fw = int((level / 3) * 38)
                if fw > 0:
                    tk.Frame(bb, bg=color, height=3, width=fw).place(x=0, y=0)
                tk.Label(row, text=sval, fg=C["text"], bg=C["panel"],
                         font=("Courier New", 7)).pack(side="left")

        bf = tk.Frame(card, bg=color, cursor="hand2")
        bf.pack(fill="x", padx=10, pady=(3, 0))
        bl = tk.Label(bf, text=f"APPLY {name}", fg=C["bg"], bg=color,
                      font=("Courier New", 9, "bold"), cursor="hand2", pady=3)
        bl.pack()

        def do_apply(n=name, b=bl):
            ok = apply_preset(n, self.fps_var.get(), self.res_var.get())
            fps_txt = "Unlimited" if self.fps_var.get() == 0 else str(self.fps_var.get())
            if ok:
                self.status_var.set(
                    f"✔  {n} applied  ·  FPS: {fps_txt}  ·  Res: {self.res_var.get()}")
                b.config(text="✔ APPLIED")
                self.root.after(2200, lambda: b.config(text=f"APPLY {n}"))
                self._refresh_live_strip()   # update strip immediately after apply
            else:
                self.status_var.set("✖  Config not found — is The Isle installed?")
                self._toast("Config file not found!", C["warn"])

        hover = self._lighten(color, 25)
        for w in [bf, bl]:
            w.bind("<Button-1>", lambda e, f=do_apply: f())
            w.bind("<Enter>", lambda e, b=bf, lb=bl, h=hover:
                   (b.config(bg=h), lb.config(bg=h)))
            w.bind("<Leave>", lambda e, b=bf, lb=bl, oc=color:
                   (b.config(bg=oc), lb.config(bg=oc)))

    # ══════════════════════════════════════════════════════════════════════════
    # PLAY PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _show_play(self):
        self._clear()
        c = self.content
        tk.Frame(c, bg=C["bg"]).pack(expand=True)
        if self.logo_img:
            tk.Label(c, image=self.logo_img, bg=C["bg"]).pack(pady=(0, 10))
        tk.Label(c, text="LAUNCH THE ISLE", fg=C["white"],
                 bg=C["bg"], font=("Courier New", 14, "bold")).pack()
        tk.Label(c, text="Start the game directly or through Steam",
                 fg=C["muted"], bg=C["bg"], font=("Courier New", 8)).pack(pady=(2, 20))

        pr = tk.Frame(c, bg=C["bg"])
        pr.pack()
        self._big_btn(pr, "▶  PLAY NOW", C["panel2"], self._launch_game,
                      fg=C["white"], border=C["border2"]).pack(side="left")
        wc = tk.Frame(pr, bg=C["bg"])
        wc.pack(side="left", padx=(14, 0))
        tk.Label(wc, text="⚠  MAY NOT WORK", fg=C["warn"],
                 bg=C["bg"], font=("Courier New", 9, "bold")).pack(anchor="w")
        tk.Label(wc, text="Direct exe path may differ\non your system.",
                 fg=C["muted"], bg=C["bg"], font=("Courier New", 7),
                 justify="left").pack(anchor="w")

        tk.Frame(c, bg=C["border"], height=1).pack(fill="x", padx=60, pady=16)
        self._big_btn(c, "LAUNCH VIA STEAM", C["panel"], self._launch_steam,
                      fg=C["text"], border=C["border2"]).pack(pady=4)
        tk.Frame(c, bg=C["bg"]).pack(expand=True)

    def _launch_game(self):
        for p in [r"C:\Program Files (x86)\Steam\steamapps\common\The Isle\TheIsle.exe",
                  r"C:\Program Files\Steam\steamapps\common\The Isle\TheIsle.exe"]:
            if os.path.exists(p):
                subprocess.Popen(p)
                self.status_var.set("▶  Launching The Isle...")
                return
        self._toast("Executable not found.\nTry Launch via Steam.", C["warn"])
        self.status_var.set("✖  Game exe not found — try Steam launch")

    def _launch_steam(self):
        try:
            os.startfile("steam://rungameid/466240")
            self.status_var.set("▶  Opening via Steam...")
        except Exception:
            self._toast("Could not open Steam", C["warn"])

    # ══════════════════════════════════════════════════════════════════════════
    # RESTORE PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _show_restore(self):
        self._clear()
        c = self.content
        tk.Frame(c, bg=C["bg"]).pack(expand=True)
        tk.Label(c, text="BACKUP & RESTORE", fg=C["white"],
                 bg=C["bg"], font=("Courier New", 14, "bold")).pack()

        if os.path.exists(BACKUP_PATH):
            ts   = os.path.getmtime(BACKUP_PATH)
            when = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d  %H:%M:%S")
            tk.Label(c, text=f"Last backup:  {when}", fg=C["text"],
                     bg=C["bg"], font=("Courier New", 9)).pack(pady=(4, 16))
            self._big_btn(c, "↺  RESTORE FROM BACKUP", C["panel2"],
                          self._do_restore, fg=C["white"], border=C["border2"]).pack(pady=4)
        else:
            tk.Label(c,
                     text="No backup found yet.\nOne is created automatically when you apply a preset.",
                     fg=C["muted"], bg=C["bg"], font=("Courier New", 9),
                     justify="center").pack(pady=(4, 16))

        tk.Frame(c, bg=C["border"], height=1).pack(fill="x", padx=60, pady=16)
        tk.Label(c, text="CONFIG FILE", fg=C["accent2"], bg=C["bg"],
                 font=("Courier New", 8, "bold")).pack()
        tk.Label(c, text=CONFIG_PATH, fg=C["muted"], bg=C["bg"],
                 font=("Courier New", 7), wraplength=500, justify="center").pack(pady=4)
        ol = tk.Label(c, text="open folder  ↗", fg=C["muted"], bg=C["bg"],
                      cursor="hand2", font=("Courier New", 8))
        ol.pack()
        ol.bind("<Enter>",    lambda e: ol.config(fg=C["white"]))
        ol.bind("<Leave>",    lambda e: ol.config(fg=C["muted"]))
        ol.bind("<Button-1>", lambda e: subprocess.Popen(
            f'explorer "{os.path.dirname(CONFIG_PATH)}"'))
        tk.Frame(c, bg=C["bg"]).pack(expand=True)

    def _do_restore(self):
        if restore_backup():
            self.status_var.set("↺  Config restored from backup")
            self._toast("Config restored!", C["high"])
            self._show_restore()
        else:
            self._toast("No backup found", C["warn"])

    # ── helpers ───────────────────────────────────────────────────────────────
    def _big_btn(self, parent, text, bg, cmd, fg=None, border=None):
        fg = fg or C["white"]; border = border or C["border2"]
        f   = tk.Frame(parent, bg=bg, cursor="hand2",
                       highlightbackground=border, highlightthickness=1)
        lbl = tk.Label(f, text=text, fg=fg, bg=bg,
                       font=("Courier New", 10, "bold"), cursor="hand2", padx=24, pady=10)
        lbl.pack()
        h = self._lighten(bg, 20)
        for w in [f, lbl]:
            w.bind("<Button-1>", lambda e, c=cmd: c())
            w.bind("<Enter>", lambda e, b=f, bl=lbl, hh=h: (b.config(bg=hh), bl.config(bg=hh)))
            w.bind("<Leave>", lambda e, b=f, bl=lbl, ob=bg: (b.config(bg=ob), bl.config(bg=ob)))
        return f

    def _toast(self, text, color=None):
        color = color or C["accent2"]
        p = tk.Toplevel(self.root)
        p.overrideredirect(True)
        p.configure(bg=C["panel"])
        pw, ph = 260, 70
        p.geometry(f"{pw}x{ph}+{self.root.winfo_x()+(self.W-pw)//2}+"
                   f"{self.root.winfo_y()+self.H-ph-30}")
        p.attributes("-alpha", 0.0)
        tk.Frame(p, bg=color, height=2).pack(fill="x")
        tk.Label(p, text=text, fg=C["white"], bg=C["panel"],
                 font=("Courier New", 9, "bold"), justify="center", wraplength=240).pack(expand=True)

        def fade(a=0.0, out=False):
            if not out:
                if a < 1.0:
                    p.attributes("-alpha", a); p.after(16, lambda: fade(a+0.1))
                else:
                    p.after(1800, lambda: fade(1.0, True))
            else:
                if a > 0.0:
                    p.attributes("-alpha", a); p.after(16, lambda: fade(a-0.07, True))
                else:
                    p.destroy()
        fade()

    @staticmethod
    def _lighten(h, amt=20):
        r = min(255, int(h[1:3], 16)+amt)
        g = min(255, int(h[3:5], 16)+amt)
        b = min(255, int(h[5:7], 16)+amt)
        return f"#{r:02x}{g:02x}{b:02x}"

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    IsleOptimizer().run()
