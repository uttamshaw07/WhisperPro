import sys
import subprocess
import os

# Auto-install missing modules
required_modules = {
    'sounddevice': 'sounddevice',
    'numpy': 'numpy',
    'keyboard': 'keyboard',
    'pyperclip': 'pyperclip',
    'noisereduce': 'noisereduce',
    'faster_whisper': 'faster-whisper'
}

print("Checking dependencies...")
for module_name, pip_name in required_modules.items():
    try:
        __import__(module_name)
        print(f"✓ {module_name} found")
    except ImportError:
        print(f"Installing {pip_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, "-q"])
        print(f"✓ {pip_name} installed")

import sounddevice as sd
import numpy as np
import keyboard
import pyperclip
import sqlite3
import datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox, font
import noisereduce as nr
from faster_whisper import WhisperModel

# ======================
# CONFIG (editable)
# ======================
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WhisperPro")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, "config.txt")
DB_PATH     = os.path.join(APP_DIR, "history.db")

SAMPLE_RATE = 16000
CHANNELS    = 1

# Load saved hotkey (default F5)
def load_hotkey():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                if line.startswith("HOTKEY="):
                    return line.strip().split("=")[1]
    return "F5"

def save_config(hotkey, language, history_days):
    with open(CONFIG_FILE, "w") as f:
        f.write(f"HOTKEY={hotkey}\n")
        f.write(f"LANGUAGE={language}\n")
        f.write(f"HISTORY_DAYS={history_days}\n")

def load_config():
    cfg = {"HOTKEY": "F5", "LANGUAGE": "auto", "HISTORY_DAYS": "7"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    cfg[k] = v
    return cfg

HOTKEY = load_hotkey()

# ======================
# DATABASE
# ======================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    time TEXT
)
""")
conn.commit()

def save_history(text):
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO history (text, time) VALUES (?, ?)", (text, now))
    conn.commit()
    cfg = load_config()
    days = int(cfg.get("HISTORY_DAYS", 7))
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    c.execute("DELETE FROM history WHERE time < ?", (cutoff,))
    conn.commit()

def get_history(limit=100):
    c.execute("SELECT text, time FROM history ORDER BY time DESC LIMIT ?", (limit,))
    return c.fetchall()

def clear_history():
    c.execute("DELETE FROM history")
    conn.commit()

# ======================
# WHISPER MODEL
# ======================
model = None
def load_model():
    global model
    try:
        print("Loading Whisper model...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✓ Model loaded")
    except Exception as e:
        print(f"⚠️ Model error: {e}")

threading.Thread(target=load_model, daemon=True).start()

# ======================
# AUDIO
# ======================
recording    = False
audio_buffer = []
stream       = None

def audio_callback(indata, frames, time, status):
    if recording:
        audio_buffer.append(indata.copy())

def reduce_noise(audio):
    try:
        return nr.reduce_noise(y=audio, sr=SAMPLE_RATE)
    except:
        return audio

def smart_fix(text):
    text = text.strip()
    text = text.replace(" comma ", ",")
    text = text.replace(" full stop ", ".")
    text = text.replace(" question mark ", "?")
    text = text.replace(" exclamation mark ", "!")
    sentences = text.split(".")
    sentences = [s.strip().capitalize() for s in sentences if s.strip()]
    result = ". ".join(sentences)
    return result if result else text

def transcribe(audio):
    if model is None:
        return None
    cfg = load_config()
    lang = cfg.get("LANGUAGE", "auto")
    lang_arg = None if lang == "auto" else lang
    audio = reduce_noise(audio)
    try:
        segments, _ = model.transcribe(
            audio,
            beam_size=5,
            vad_filter=True,
            language=lang_arg
        )
        text = " ".join([s.text for s in segments]).strip()
        return smart_fix(text)
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

def paste_text(text):
    if not text:
        return
    try:
        pyperclip.copy(text)
        keyboard.press_and_release("ctrl+v")
    except Exception as e:
        print(f"Paste error: {e}")

# ======================
# FLOATING BAR
# ======================
class FlowBar:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WhisperPro")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        sw = self.root.winfo_screenwidth()
        bw, bh = 380, 44
        self.root.geometry(f"{bw}x{bh}+{(sw-bw)//2}+16")
        self.root.configure(bg="#0d0d1a")

        # Make bar draggable
        self.drag_x = 0
        self.drag_y = 0

        self.label = tk.Label(
            self.root,
            text="🎤  WhisperPro  —  Hold F5 to speak",
            bg="#0d0d1a",
            fg="#00cfff",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        self.label.pack(fill="both", expand=True, padx=10)

        # Click bar to open dashboard
        self.label.bind("<Button-1>", self._on_click)
        self.label.bind("<ButtonPress-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag_motion)

        self._dashboard = None
        threading.Thread(target=self.root.mainloop, daemon=True).start()

    def _drag_start(self, e):
        self.drag_x = e.x
        self.drag_y = e.y

    def _drag_motion(self, e):
        x = self.root.winfo_x() + (e.x - self.drag_x)
        y = self.root.winfo_y() + (e.y - self.drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _on_click(self, e):
        # Only open dashboard if not dragging
        if abs(e.x - self.drag_x) < 5 and abs(e.y - self.drag_y) < 5:
            self.open_dashboard()

    def open_dashboard(self):
        if self._dashboard and tk.Toplevel.winfo_exists(self._dashboard.win):
            self._dashboard.win.lift()
        else:
            self._dashboard = Dashboard(self.root)

    def update(self, text, state="idle"):
        colors = {
            "idle":       "#00cfff",
            "recording":  "#ff4444",
            "processing": "#ffaa00",
            "done":       "#00ff88",
            "error":      "#ff6600",
        }
        self.label.config(text=text, fg=colors.get(state, "#00cfff"))

# ======================
# DASHBOARD WINDOW
# ======================
class Dashboard:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("WhisperPro")
        self.win.geometry("680x520")
        self.win.configure(bg="#0d0d1a")
        self.win.resizable(True, True)
        self.win.attributes("-topmost", False)

        # Header
        hdr = tk.Frame(self.win, bg="#111133", height=60)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="🎤  WhisperPro",
            bg="#111133",
            fg="#00cfff",
            font=("Segoe UI", 18, "bold")
        ).pack(side="left", padx=20, pady=12)
        tk.Label(
            hdr,
            text="Voice to Text — Always Listening",
            bg="#111133",
            fg="#445566",
            font=("Segoe UI", 9)
        ).pack(side="left", pady=18)

        # Tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",           background="#0d0d1a", borderwidth=0)
        style.configure("TNotebook.Tab",       background="#111133", foreground="#7799bb",
                         font=("Segoe UI", 10), padding=[16, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", "#1a1a3e")],
                  foreground=[("selected", "#00cfff")])

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        # --- TAB 1: HISTORY ---
        hist_frame = tk.Frame(nb, bg="#0d0d1a")
        nb.add(hist_frame, text="  📋  History  ")
        self._build_history_tab(hist_frame)

        # --- TAB 2: SETTINGS ---
        sett_frame = tk.Frame(nb, bg="#0d0d1a")
        nb.add(sett_frame, text="  ⚙️  Settings  ")
        self._build_settings_tab(sett_frame)

        # --- TAB 3: ABOUT ---
        about_frame = tk.Frame(nb, bg="#0d0d1a")
        nb.add(about_frame, text="  ℹ️  About  ")
        self._build_about_tab(about_frame)

    # ── HISTORY TAB ──────────────────────────────
    def _build_history_tab(self, frame):
        # Toolbar
        toolbar = tk.Frame(frame, bg="#111133", pady=6)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Your transcription history",
                 bg="#111133", fg="#7799bb",
                 font=("Segoe UI", 9)).pack(side="left", padx=14)

        tk.Button(toolbar, text="🔄 Refresh", command=self._refresh_history,
                  bg="#1a3355", fg="#00cfff", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=6, pady=2)

        tk.Button(toolbar, text="🗑️ Clear All", command=self._clear_history,
                  bg="#331a1a", fg="#ff6666", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=2, pady=2)

        # List with scrollbar
        list_frame = tk.Frame(frame, bg="#0d0d1a")
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.history_box = tk.Text(
            list_frame,
            bg="#0a0a18",
            fg="#cce8ff",
            font=("Segoe UI", 10),
            relief="flat",
            wrap="word",
            yscrollcommand=scrollbar.set,
            state="disabled",
            padx=10,
            pady=8,
            spacing1=4,
            spacing3=6
        )
        self.history_box.pack(fill="both", expand=True)
        scrollbar.config(command=self.history_box.yview)

        self._refresh_history()

    def _refresh_history(self):
        rows = get_history(200)
        self.history_box.config(state="normal")
        self.history_box.delete("1.0", "end")
        if not rows:
            self.history_box.insert("end", "No history yet.\nHold F5, speak, and your text will appear here.")
        else:
            for text, time_str in rows:
                try:
                    dt = datetime.datetime.fromisoformat(time_str)
                    stamp = dt.strftime("%d %b %Y  %I:%M %p")
                except:
                    stamp = time_str
                self.history_box.insert("end", f"🕐  {stamp}\n", "time")
                self.history_box.insert("end", f"   {text}\n\n", "text")
        self.history_box.tag_config("time", foreground="#445577", font=("Segoe UI", 8))
        self.history_box.tag_config("text", foreground="#aaddff", font=("Segoe UI", 10))
        self.history_box.config(state="disabled")

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Delete all history? This cannot be undone."):
            clear_history()
            self._refresh_history()

    # ── SETTINGS TAB ─────────────────────────────
    def _build_settings_tab(self, frame):
        cfg = load_config()

        container = tk.Frame(frame, bg="#0d0d1a")
        container.pack(fill="both", expand=True, padx=30, pady=20)

        def section(text):
            tk.Label(container, text=text, bg="#0d0d1a", fg="#00cfff",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(18, 4))
            tk.Frame(container, bg="#1a3355", height=1).pack(fill="x", pady=(0, 10))

        # — Hotkey —
        section("⌨️  Hotkey")
        hk_row = tk.Frame(container, bg="#0d0d1a")
        hk_row.pack(fill="x")
        tk.Label(hk_row, text="Record key:", bg="#0d0d1a", fg="#aabbcc",
                 font=("Segoe UI", 10), width=16, anchor="w").pack(side="left")
        self.hotkey_var = tk.StringVar(value=cfg.get("HOTKEY", "F5"))
        hk_options = ["F5", "F6", "F7", "F8", "F9", "F10"]
        hk_menu = ttk.Combobox(hk_row, textvariable=self.hotkey_var,
                                values=hk_options, width=10, state="readonly")
        hk_menu.pack(side="left", padx=8)

        # — Language —
        section("🌐  Language")
        lang_row = tk.Frame(container, bg="#0d0d1a")
        lang_row.pack(fill="x")
        tk.Label(lang_row, text="Transcribe in:", bg="#0d0d1a", fg="#aabbcc",
                 font=("Segoe UI", 10), width=16, anchor="w").pack(side="left")
        self.lang_var = tk.StringVar(value=cfg.get("LANGUAGE", "auto"))
        lang_options = [
            "auto", "en", "hi", "es", "fr", "de",
            "zh", "ar", "pt", "ru", "ja", "ko", "it"
        ]
        lang_labels = {
            "auto": "Auto Detect", "en": "English", "hi": "Hindi",
            "es": "Spanish",  "fr": "French",  "de": "German",
            "zh": "Chinese",  "ar": "Arabic",  "pt": "Portuguese",
            "ru": "Russian",  "ja": "Japanese","ko": "Korean", "it": "Italian"
        }
        lang_menu = ttk.Combobox(lang_row, textvariable=self.lang_var,
                                  values=lang_options, width=18, state="readonly")
        lang_menu.pack(side="left", padx=8)
        tk.Label(lang_row,
                 text="(Auto Detect works for most languages)",
                 bg="#0d0d1a", fg="#445566",
                 font=("Segoe UI", 8)).pack(side="left", padx=6)

        # — History —
        section("📋  History")
        hist_row = tk.Frame(container, bg="#0d0d1a")
        hist_row.pack(fill="x")
        tk.Label(hist_row, text="Keep history for:", bg="#0d0d1a", fg="#aabbcc",
                 font=("Segoe UI", 10), width=16, anchor="w").pack(side="left")
        self.days_var = tk.StringVar(value=cfg.get("HISTORY_DAYS", "7"))
        days_menu = ttk.Combobox(hist_row, textvariable=self.days_var,
                                  values=["1", "3", "7", "14", "30", "90"], width=10,
                                  state="readonly")
        days_menu.pack(side="left", padx=8)
        tk.Label(hist_row, text="days", bg="#0d0d1a", fg="#aabbcc",
                 font=("Segoe UI", 10)).pack(side="left")

        # Save button
        tk.Button(
            container,
            text="  💾  Save Settings  ",
            command=self._save_settings,
            bg="#003366",
            fg="#00cfff",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=8
        ).pack(pady=24, anchor="w")

        self.save_status = tk.Label(container, text="", bg="#0d0d1a",
                                     fg="#00ff88", font=("Segoe UI", 9))
        self.save_status.pack(anchor="w")

    def _save_settings(self):
        global HOTKEY
        hk   = self.hotkey_var.get()
        lang = self.lang_var.get()
        days = self.days_var.get()
        save_config(hk, lang, days)
        HOTKEY = hk
        self.save_status.config(text="✅  Settings saved! Restart app to apply new hotkey.")

    # ── ABOUT TAB ────────────────────────────────
    def _build_about_tab(self, frame):
        container = tk.Frame(frame, bg="#0d0d1a")
        container.pack(expand=True)

        tk.Label(container, text="🎤", bg="#0d0d1a", fg="#00cfff",
                 font=("Segoe UI", 48)).pack(pady=(40, 10))

        tk.Label(container, text="WhisperPro", bg="#0d0d1a", fg="#00cfff",
                 font=("Segoe UI", 22, "bold")).pack()

        tk.Label(container, text="AI-powered Push-to-Talk Voice Typing",
                 bg="#0d0d1a", fg="#7799bb",
                 font=("Segoe UI", 11)).pack(pady=4)

        tk.Frame(container, bg="#1a3355", height=1, width=300).pack(pady=16)

        info = [
            ("Engine",   "OpenAI Whisper (faster-whisper)"),
            ("Version",  "v5.0"),
            ("Hotkey",   f"Hold {HOTKEY} to record"),
            ("Storage",  APP_DIR),
        ]
        for label, val in info:
            row = tk.Frame(container, bg="#0d0d1a")
            row.pack(pady=3)
            tk.Label(row, text=f"{label}:", bg="#0d0d1a", fg="#445577",
                     font=("Segoe UI", 9), width=12, anchor="e").pack(side="left")
            tk.Label(row, text=val, bg="#0d0d1a", fg="#aaccee",
                     font=("Segoe UI", 9), anchor="w").pack(side="left", padx=8)

# ======================
# INIT UI
# ======================
flow = FlowBar()

# Open dashboard when app icon is double-clicked from taskbar
# (handled via the floating bar click)

# ======================
# RECORD CONTROL
# ======================
def start_recording():
    global recording, audio_buffer, stream
    recording    = True
    audio_buffer = []
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            callback=audio_callback)
    stream.start()
    flow.update("🔴  Recording...  release F5 to stop", "recording")

def stop_recording():
    global recording, stream
    recording = False
    if stream:
        stream.stop()
        stream.close()
        stream = None
    flow.update("⏳  Processing...", "processing")
    if len(audio_buffer) == 0:
        flow.update("⚠️  No audio detected", "error")
        threading.Timer(2.0, lambda: flow.update(
            "🎤  WhisperPro  —  Hold F5 to speak", "idle")).start()
        return None
    audio = np.concatenate(audio_buffer, axis=0)
    return np.squeeze(audio)

# ======================
# HOTKEY LOOP
# ======================
def main():
    def listen():
        def on_press(e):
            if not recording:
                start_recording()

        def on_release(e):
            if recording:
                audio = stop_recording()
                if audio is not None:
                    text = transcribe(audio)
                    if text:
                        print("📝", text)
                        save_history(text)
                        paste_text(text)
                        flow.update("✅  Done!", "done")
                        threading.Timer(2.0, lambda: flow.update(
                            "🎤  WhisperPro  —  Hold F5 to speak", "idle")).start()
                    else:
                        flow.update("🎤  WhisperPro  —  Hold F5 to speak", "idle")

        keyboard.on_press_key(HOTKEY, on_press)
        keyboard.on_release_key(HOTKEY, on_release)
        keyboard.wait()

    threading.Thread(target=listen, daemon=True).start()

    try:
        while True:
            sd.sleep(1000)
    except KeyboardInterrupt:
        print("🛑 WhisperPro shutting down...")
        if stream:
            stream.stop()
            stream.close()
        conn.close()

if __name__ == "__main__":
    print("🚀 WhisperPro v5 Started")
    print(f"Hold {HOTKEY} → Speak → Release → Text appears")
    print("Click the floating bar to open Dashboard")
    main()
