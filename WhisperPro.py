import sys
import subprocess
import os

# ======================
# 1. DEPENDENCY CHECKER
# ======================
required_modules = {
    'sounddevice': 'sounddevice',
    'numpy': 'numpy',
    'keyboard': 'keyboard',
    'pyperclip': 'pyperclip',
    'noisereduce': 'noisereduce',
    'faster_whisper': 'faster-whisper',
    'pystray': 'pystray',
    'PIL': 'pillow',
    'customtkinter': 'customtkinter'
}

print("Checking dependencies...")
for module_name, pip_name in required_modules.items():
    try:
        if module_name == 'PIL':
            __import__('PIL.Image')
        else:
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
import noisereduce as nr
from faster_whisper import WhisperModel
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

# ======================
# 2. CONFIG & DB
# ======================
SAMPLE_RATE = 16000
CHANNELS = 1
HOTKEY = "F5"

print("Loading Whisper model...")
try:
    model = WhisperModel("base", device="cpu", compute_type="int8")
except Exception as e:
    print(f"⚠️ Error loading Whisper model: {e}")
    model = None

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WhisperPro")
os.makedirs(APP_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DIR, "history.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS history (
    text TEXT,
    time TEXT
)
""")
conn.commit()

def save_history(text):
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO history VALUES (?, ?)", (text, now))
    conn.commit()
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    c.execute("DELETE FROM history WHERE time < ?", (seven_days_ago,))
    conn.commit()

# ======================
# 3. UI COMPONENTS
# ======================
class FlowBar(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1a1a2e")
        
        screen_w = self.winfo_screenwidth()
        bar_w = 360
        bar_h = 52
        x = (screen_w - bar_w) // 2
        y = 18
        self.geometry(f"{bar_w}x{bar_h}+{x}+{y}")
        
        self.label = ctk.CTkLabel(
            self,
            text="🎤  WhisperPro  —  Hold F5 to speak",
            text_color="#00cfff",
            font=("Segoe UI", 14, "bold")
        )
        self.label.pack(fill="both", expand=True, padx=12, pady=8)

    def update_status(self, text):
        if "Listening" in text or "Recording" in text:
            color = "#ff4444"
        elif "Processing" in text:
            color = "#ffaa00"
        elif "Done" in text:
            color = "#00ff88"
        elif "Error" in text or "No audio" in text:
            color = "#ff6600"
        else:
            color = "#00cfff"
        # Thread-safe UI update
        self.after(0, lambda: self.label.configure(text=text, text_color=color))

class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WhisperPro Dashboard")
        self.geometry("700x500")
        ctk.set_appearance_mode("Dark")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=150, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo = ctk.CTkLabel(self.sidebar, text="WhisperPro", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=20)
        
        self.btn_history = ctk.CTkButton(self.sidebar, text="History", command=self.show_history)
        self.btn_history.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_settings = ctk.CTkButton(self.sidebar, text="Settings", command=self.show_settings)
        self.btn_settings.grid(row=2, column=0, padx=20, pady=10)
        
        # Main Frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Initialize floating bar attached to this app
        self.flow = FlowBar(self)
        self.show_history()

    def show_history(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        label = ctk.CTkLabel(self.main_frame, text="Transcription History", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=(10, 20))
        
        scrollable_frame = ctk.CTkScrollableFrame(self.main_frame)
        scrollable_frame.pack(fill="both", expand=True)
        
        c.execute("SELECT time, text FROM history ORDER BY time DESC LIMIT 50")
        rows = c.fetchall()
        
        if not rows:
            ctk.CTkLabel(scrollable_frame, text="No history found.", text_color="gray").pack(pady=20)
            
        for row in rows:
            time_str = datetime.datetime.fromisoformat(row[0]).strftime("%b %d, %H:%M")
            text_val = row[1]
            
            entry_frame = ctk.CTkFrame(scrollable_frame)
            entry_frame.pack(fill="x", pady=5, padx=5)
            
            time_label = ctk.CTkLabel(entry_frame, text=time_str, font=ctk.CTkFont(size=11), text_color="gray")
            time_label.pack(anchor="w", padx=10, pady=(5, 0))
            
            text_label = ctk.CTkLabel(entry_frame, text=text_val, wraplength=450, justify="left")
            text_label.pack(anchor="w", padx=10, pady=(0, 5))

    def show_settings(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        label = ctk.CTkLabel(self.main_frame, text="Settings", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=10)
        
        info = ctk.CTkLabel(self.main_frame, text="Model: Base (Int8 CPU)\nHotkey: F5\nMemory: 7 Days", font=ctk.CTkFont(size=14))
        info.pack(pady=20)

    def hide_window(self):
        self.withdraw()

# ======================
# 4. AUDIO & TRANSCRIPTION
# ======================
recording = False
audio_buffer = []
stream = None
app = None # Global app reference

def audio_callback(indata, frames, time, status):
    if recording:
        audio_buffer.append(indata.copy())

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
        app.flow.update_status("⚠️ Model not loaded")
        return None
    try:
        audio = nr.reduce_noise(y=audio, sr=SAMPLE_RATE)
        segments, info = model.transcribe(audio, beam_size=5, vad_filter=True)
        text = " ".join([s.text for s in segments]).strip()
        return smart_fix(text)
    except Exception as e:
        app.flow.update_status("⚠️ Transcription failed")
        return None

def paste_text(text):
    if not text:
        return
    try:
        pyperclip.copy(text)
        keyboard.press_and_release("ctrl+v")
    except Exception as e:
        print(f"Paste error: {e}")

def start_recording():
    global recording, audio_buffer, stream
    recording = True
    audio_buffer = []
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback)
    stream.start()
    app.flow.update_status("🔴  Recording...  (release F5 to stop)")

def stop_recording():
    global recording, stream
    recording = False
    if stream:
        stream.stop()
        stream.close()
        stream = None
    app.flow.update_status("⏳  Processing...")

    if len(audio_buffer) == 0:
        app.flow.update_status("⚠️  No audio detected")
        threading.Timer(2.0, lambda: app.flow.update_status("🎤  WhisperPro  —  Hold F5 to speak")).start()
        return None

    audio = np.concatenate(audio_buffer, axis=0)
    return np.squeeze(audio)

def listen_hotkey():
    global recording
    def on_f5_press(e):
        if not recording: start_recording()

    def on_f5_release(e):
        if recording:
            audio = stop_recording()
            if audio is not None:
                text = transcribe(audio)
                if text:
                    save_history(text)
                    paste_text(text)
                    app.flow.update_status("✅  Done!")
                    # Refresh history if dashboard is open
                    app.after(0, app.show_history)
                    threading.Timer(2.0, lambda: app.flow.update_status("🎤  WhisperPro  —  Hold F5 to speak")).start()
                else:
                    app.flow.update_status("🎤  WhisperPro  —  Hold F5 to speak")

    keyboard.on_press_key(HOTKEY, on_f5_press)
    keyboard.on_release_key(HOTKEY, on_f5_release)
    keyboard.wait()

# ======================
# 5. TRAY & MAIN LOOP
# ======================
def create_tray_icon():
    image = Image.new('RGB', (64, 64), color = (0, 207, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, 48, 48), fill=(26, 26, 46))
    
    def on_open(icon, item):
        app.after(0, app.deiconify)
        app.after(0, app.focus)

    def on_exit(icon, item):
        icon.stop()
        conn.close()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open, default=True),
        pystray.MenuItem("Exit WhisperPro", on_exit)
    )
    icon = pystray.Icon("WhisperPro", image, "WhisperPro", menu)
    icon.run()

if __name__ == "__main__":
    app = Dashboard()
    app.withdraw() # Hide main window at startup (tray handles opening it)

    # Start Background Threads
    threading.Thread(target=listen_hotkey, daemon=True).start()
    threading.Thread(target=create_tray_icon, daemon=True).start()

    print("🚀 WhisperPro Started (Check System Tray!)")
    
    # Start the Tkinter UI Loop
    app.mainloop()
