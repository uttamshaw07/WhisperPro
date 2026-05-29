import sys
import subprocess
import threading
import tkinter as tk
import sqlite3
import datetime
import os

# 1. Add new dependencies for the UI and System Tray
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

# ... [Keep your existing dependency checker and imports here] ...
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

# ... [Keep your existing Config, Database, Audio, Transcription, and Auto Type functions] ...

# ======================
# DASHBOARD UI (History & Settings)
# ======================
class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WhisperPro Dashboard")
        self.geometry("600x400")
        self.attributes("-topmost", True)
        
        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar for navigation
        self.sidebar = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="WhisperPro", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_history = ctk.CTkButton(self.sidebar, text="History", command=self.show_history)
        self.btn_history.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_settings = ctk.CTkButton(self.sidebar, text="Settings", command=self.show_settings)
        self.btn_settings.grid(row=2, column=0, padx=20, pady=10)

        # Main Content Area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Default view
        self.show_history()

        # Hide window instead of destroying it when X is clicked
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

    def show_history(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        label = ctk.CTkLabel(self.main_frame, text="Transcription History", font=ctk.CTkFont(size=18, weight="bold"))
        label.pack(pady=10)
        # TODO: Fetch from SQLite and display in a scrollable frame here

    def show_settings(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        label = ctk.CTkLabel(self.main_frame, text="Settings", font=ctk.CTkFont(size=18, weight="bold"))
        label.pack(pady=10)
        # TODO: Add Language Dropdowns and Hotkey settings here

    def hide_window(self):
        self.withdraw() # Hides the window without killing the app

# ======================
# SYSTEM TRAY & APP LIFECYCLE
# ======================
dashboard_app = None

def create_tray_icon():
    # Create a simple generic image for the tray icon (or load your own .ico)
    image = Image.new('RGB', (64, 64), color = (0, 207, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, 48, 48), fill=(26, 26, 46))
    
    def on_open(icon, item):
        # Show the dashboard when "Open Dashboard" is clicked
        if dashboard_app:
            dashboard_app.deiconify()
            dashboard_app.focus()

    def on_exit(icon, item):
        icon.stop()
        os._exit(0) # Force close everything cleanly

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open, default=True),
        pystray.MenuItem("Exit WhisperPro", on_exit)
    )
    
    icon = pystray.Icon("WhisperPro", image, "WhisperPro", menu)
    icon.run()

def main():
    global dashboard_app
    
    # 1. Start the hotkey listener thread
    threading.Thread(target=listen, daemon=True).start()
    
    # 2. Start the System Tray icon thread
    threading.Thread(target=create_tray_icon, daemon=True).start()

    # 3. Initialize the CustomTkinter Dashboard (Hidden by default)
    ctk.set_appearance_mode("Dark")
    dashboard_app = Dashboard()
    dashboard_app.withdraw() # Hide it immediately

    # 4. Start the Tkinter Mainloop (this blocks, keeping the app alive)
    dashboard_app.mainloop()

if __name__ == "__main__":
    print("🚀 WhisperPro Started")
    main()
