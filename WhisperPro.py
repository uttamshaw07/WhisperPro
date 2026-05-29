import sys
import subprocess

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
from tkinter import messagebox
import noisereduce as nr

from faster_whisper import WhisperModel

# ======================
# CONFIG
# ======================
SAMPLE_RATE = 16000
CHANNELS = 1
HOTKEY = "F5"

# Initialize model
try:
    print("Loading Whisper model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
except Exception as e:
    print(f"⚠️ Error loading Whisper model: {e}")
    model = None

# ======================
# DATABASE (7-day memory)
# ======================
import os
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

    # Delete entries older than 7 days
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    c.execute("DELETE FROM history WHERE time < ?", (seven_days_ago,))
    conn.commit()


# ======================
# FLOW BAR UI
# ======================
class FlowBar:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("220x40+1000+20")

        self.label = tk.Label(
            self.root,
            text="🎤 WhisperPro Ready",
            bg="black",
            fg="white",
            font=("Arial", 10)
        )
        self.label.pack(fill="both", expand=True)

        threading.Thread(target=self.root.mainloop, daemon=True).start()

    def update(self, text):
        self.label.config(text=text)


flow = FlowBar()


# ======================
# AUDIO RECORDING
# ======================
recording = False
audio_buffer = []


def audio_callback(indata, frames, time, status):
    if recording:
        audio_buffer.append(indata.copy())


def reduce_noise(audio):
    try:
        return nr.reduce_noise(y=audio, sr=SAMPLE_RATE)
    except:
        return audio


# ======================
# SMART FIX
# ======================
def smart_fix(text):
    text = text.strip()

    # Replace spoken punctuation with actual punctuation
    text = text.replace(" comma ", ",")
    text = text.replace(" full stop ", ".")
    text = text.replace(" question mark ", "?")
    text = text.replace(" exclamation mark ", "!")

    # Capitalize sentences
    sentences = text.split(".")
    sentences = [s.strip().capitalize() for s in sentences if s.strip()]
    result = ". ".join(sentences)
    
    return result if result else text


# ======================
# TRANSCRIPTION
# ======================
def transcribe(audio):
    if model is None:
        flow.update("⚠️ Model not loaded")
        return None
    
    audio = reduce_noise(audio)

    try:
        segments, info = model.transcribe(
            audio,
            beam_size=5,
            vad_filter=True
        )

        text = " ".join([s.text for s in segments]).strip()
        return smart_fix(text)
    except Exception as e:
        print(f"Transcription error: {e}")
        flow.update("⚠️ Transcription failed")
        return None


# ======================
# AUTO TYPE
# ======================
def paste_text(text):
    if not text:
        return
    try:
        pyperclip.copy(text)
        keyboard.press_and_release("ctrl+v")
    except Exception as e:
        print(f"Paste error: {e}")


# ======================
# RECORD CONTROL
# ======================
def start_recording():
    global recording, audio_buffer
    recording = True
    audio_buffer = []
    flow.update("🎤 Listening...")


def stop_recording():
    global recording
    recording = False
    flow.update("⏳ Processing...")

    if len(audio_buffer) == 0:
        flow.update("⚠️ No audio detected")
        return None

    audio = np.concatenate(audio_buffer, axis=0)
    audio = np.squeeze(audio)

    return audio


# ======================
# HOTKEY LOOP
# ======================
def main():
    global recording

    def listen():
        global recording

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=audio_callback
            ):

                while True:
                    if keyboard.is_pressed(HOTKEY):
                        if not recording:
                            start_recording()

                    else:
                        if recording:
                            audio = stop_recording()

                            if audio is not None:
                                text = transcribe(audio)

                                if text:
                                    print("📝", text)
                                    save_history(text)
                                    paste_text(text)
                                    flow.update("✅ Done! (Hold F5)")
                                    threading.Timer(2.0, lambda: flow.update("🎤 WhisperPro Ready")).start()

                    sd.sleep(50)
        except Exception as e:
            print(f"Recording error: {e}")
            flow.update(f"⚠️ Error: {str(e)[:20]}")

    threading.Thread(target=listen, daemon=True).start()

    # Keep main thread alive
    try:
        while True:
            sd.sleep(1000)
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
        conn.close()


if __name__ == "__main__":
    print("🚀 WhisperPro Started")
    print("Hold F5 → Speak → Release → Text appears")
    print("Running in background... Press Ctrl+C to exit")
    print("(You can close this window, app stays running)")

    main()
