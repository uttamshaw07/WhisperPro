import sys
import subprocess
import os

REQUIRED = {
    'sounddevice':   'sounddevice',
    'numpy':         'numpy',
    'keyboard':      'keyboard',
    'pyperclip':     'pyperclip',
    'noisereduce':   'noisereduce',
    'faster_whisper':'faster-whisper',
}
for mod, pkg in REQUIRED.items():
    try:
        __import__(mod)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import datetime
import sqlite3
import sounddevice as sd
import numpy as np
import keyboard
import pyperclip
import noisereduce as nr
from faster_whisper import WhisperModel

APP_DIR     = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'WhisperPro')
os.makedirs(APP_DIR, exist_ok=True)
DB_PATH     = os.path.join(APP_DIR, 'history.db')
CONFIG_PATH = os.path.join(APP_DIR, 'config.txt')

BG=('#0b0f1a'); BG2=('#111827'); BG3=('#1e2738')
ACCENT=('#3b82f6'); ACCENT2=('#60a5fa')
RED=('#ef4444'); GREEN=('#22c55e'); YELLOW=('#f59e0b')
TEXT=('#e2e8f0'); MUTED=('#64748b'); WHITE=('#ffffff')

def load_config():
    cfg = {'HOTKEY':'F5','LANGUAGE':'auto','HISTORY_DAYS':'7'}
    if os.path.exists(CONFIG_PATH):
        for line in open(CONFIG_PATH):
            if '=' in line:
                k,v = line.strip().split('=',1); cfg[k]=v
    return cfg

def save_config(cfg):
    with open(CONFIG_PATH,'w') as f:
        [f.write(f'{k}={v}\n') for k,v in cfg.items()]

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur  = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, time TEXT)')
conn.commit()

def db_save(text):
    cur.execute('INSERT INTO history (text,time) VALUES (?,?)',(text,datetime.datetime.now().isoformat()))
    conn.commit()
    days=int(load_config().get('HISTORY_DAYS',7))
    cut=(datetime.datetime.now()-datetime.timedelta(days=days)).isoformat()
    cur.execute('DELETE FROM history WHERE time<?',(cut,)); conn.commit()

def db_fetch():
    cur.execute('SELECT text,time FROM history ORDER BY time DESC LIMIT 300')
    return cur.fetchall()

def db_clear():
    cur.execute('DELETE FROM history'); conn.commit()

RATE=16000; recording=False; buf=[]; mic_stream=None

def _cb(indata,frames,t,status):
    if recording: buf.append(indata.copy())

def mic_start():
    global recording,buf,mic_stream
    recording=True; buf=[]
    mic_stream=sd.InputStream(samplerate=RATE,channels=1,callback=_cb)
    mic_stream.start()

def mic_stop():
    global recording,mic_stream
    recording=False
    if mic_stream: mic_stream.stop(); mic_stream.close(); mic_stream=None
    if not buf: return None
    return np.squeeze(np.concatenate(buf,axis=0))

whisper_model=None; model_ready=False

def _load_model():
    global whisper_model,model_ready
    try:
        whisper_model=WhisperModel('base',device='cpu',compute_type='int8')
        model_ready=True
    except Exception as e: print('Model error:',e)

threading.Thread(target=_load_model,daemon=True).start()

def transcribe(audio):
    if not whisper_model: return None
    lang=load_config().get('LANGUAGE','auto')
    try:
        segs,_=whisper_model.transcribe(audio,beam_size=5,vad_filter=True,language=None if lang=='auto' else lang)
        text=' '.join(s.text for s in segs).strip()
        for w,p in [(' comma ',','),(' full stop ','.'),(' question mark ','?'),(' exclamation mark ','!')]:
            text=text.replace(w,p)
        parts=[s.strip().capitalize() for s in text.split('.') if s.strip()]
        return '. '.join(parts) or text
    except: return None

def do_paste(text):
    try: pyperclip.copy(text); keyboard.press_and_release('ctrl+v')
    except: pass

class WhisperProApp:
    def __init__(self):
        cfg=load_config(); self.hotkey=cfg.get('HOTKEY','F5')
        self.root=tk.Tk()
        self.root.title('WhisperPro')
        self.root.geometry('800x560')
        self.root.minsize(680,480)
        self.root.configure(bg=BG)
        self.root.lift()
        self.root.attributes('-topmost',True)
        self.root.after(1000,lambda:self.root.attributes('-topmost',False))
        self.root.protocol('WM_DELETE_WINDOW',self._minimize)
        self._build_ui()
        self._register_hotkey()
        self._tick()

    def _minimize(self):
        self.root.withdraw()
        self.mini.deiconify()

    def show_main(self,*a):
        self.mini.withdraw()
        self.root.deiconify(); self.root.lift()
        self.root.attributes('-topmost',True)
        self.root.after(400,lambda:self.root.attributes('-topmost',False))
        self._refresh_history()

    def _build_ui(self):
        # sidebar
        sb=tk.Frame(self.root,bg=BG2,width=190); sb.pack(side='left',fill='y'); sb.pack_propagate(False)
        lf=tk.Frame(sb,bg=BG2,pady=22); lf.pack(fill='x')
        tk.Label(lf,text='🎤',font=('Segoe UI',30),bg=BG2,fg=ACCENT2).pack()
        tk.Label(lf,text='WhisperPro',font=('Segoe UI',12,'bold'),bg=BG2,fg=WHITE).pack()
        tk.Label(lf,text='AI Voice Typing',font=('Segoe UI',8),bg=BG2,fg=MUTED).pack()
        tk.Frame(sb,bg=BG3,height=1).pack(fill='x',padx=14,pady=6)
        self.nav_btns={}
        for label,key in [('🏠  Home','home'),('📋  History','history'),('⚙️  Settings','settings'),('ℹ️  About','about')]:
            b=tk.Button(sb,text=label,font=('Segoe UI',10),bg=BG2,fg=TEXT,
                        activebackground=BG3,activeforeground=WHITE,relief='flat',
                        anchor='w',padx=18,pady=10,cursor='hand2',
                        command=lambda k=key:self._nav(k))
            b.pack(fill='x',pady=1); self.nav_btns[key]=b
        tk.Frame(sb,bg=BG3,height=1).pack(fill='x',padx=14,pady=8)
        self.hk_lbl=tk.Label(sb,text=f'Hold {self.hotkey} to record',font=('Segoe UI',9,'bold'),bg=BG2,fg=ACCENT2)
        self.hk_lbl.pack(pady=3)
        self.dot=tk.Label(sb,text='● Ready',font=('Segoe UI',9),bg=BG2,fg=GREEN)
        self.dot.pack()

        self.content=tk.Frame(self.root,bg=BG); self.content.pack(side='left',fill='both',expand=True)
        self.pages={'home':self._pg_home(),'history':self._pg_history(),'settings':self._pg_settings(),'about':self._pg_about()}
        self._nav('home')
        self._build_mini()

    def _nav(self,key):
        for p in self.pages.values(): p.pack_forget()
        self.pages[key].pack(fill='both',expand=True)
        for k,b in self.nav_btns.items():
            b.config(bg=BG3 if k==key else BG2, fg=WHITE if k==key else TEXT)
        if key=='history': self._refresh_history()

    # HOME
    def _pg_home(self):
        f=tk.Frame(self.content,bg=BG)
        tk.Frame(f,bg=BG2,pady=1).pack(fill='x')
        hdr=tk.Frame(f,bg=BG2,pady=18,padx=24); hdr.pack(fill='x')
        tk.Label(hdr,text='Welcome to WhisperPro',font=('Segoe UI',17,'bold'),bg=BG2,fg=WHITE).pack(anchor='w')
        tk.Label(hdr,text='Speak anywhere on your PC — text appears instantly',font=('Segoe UI',10),bg=BG2,fg=MUTED).pack(anchor='w',pady=3)

        rec_f=tk.Frame(f,bg=BG,pady=24); rec_f.pack()
        self.rec_btn=tk.Button(rec_f,text=f'🎤\n\nHold  {self.hotkey}  to Record',
                                font=('Segoe UI',13,'bold'),bg=ACCENT,fg=WHITE,
                                activebackground='#2563eb',relief='flat',cursor='hand2',
                                width=22,height=5)
        self.rec_btn.pack()
        tk.Label(rec_f,text='Works in any app — Word, Gmail, Discord, WhatsApp, anything!',
                 font=('Segoe UI',9),bg=BG,fg=MUTED).pack(pady=8)

        stat_f=tk.Frame(f,bg=BG2,padx=22,pady=14); stat_f.pack(fill='x',padx=24,pady=6)
        tk.Label(stat_f,text='LIVE STATUS',font=('Segoe UI',8,'bold'),bg=BG2,fg=MUTED).pack(anchor='w')
        self.live=tk.Label(stat_f,text=f'🟢  Ready — press and hold {self.hotkey} to start',
                            font=('Segoe UI',11),bg=BG2,fg=GREEN); self.live.pack(anchor='w',pady=4)

        last_f=tk.Frame(f,bg=BG2,padx=22,pady=14); last_f.pack(fill='x',padx=24,pady=4)
        tk.Label(last_f,text='LAST TRANSCRIPTION',font=('Segoe UI',8,'bold'),bg=BG2,fg=MUTED).pack(anchor='w')
        self.last_lbl=tk.Label(last_f,text='Nothing yet — start speaking!',
                                font=('Segoe UI',11),bg=BG2,fg=TEXT,wraplength=500,justify='left')
        self.last_lbl.pack(anchor='w',pady=4)

        cards=tk.Frame(f,bg=BG); cards.pack(fill='x',padx=24,pady=8)
        self.c_count=self._card(cards,'0','Today')
        self.c_model=self._card(cards,'Loading…','AI Model')
        self.c_hk=self._card(cards,self.hotkey,'Hotkey')
        return f

    def _card(self,parent,val,label):
        c=tk.Frame(parent,bg=BG2,padx=18,pady=12); c.pack(side='left',expand=True,fill='x',padx=5)
        v=tk.Label(c,text=val,font=('Segoe UI',17,'bold'),bg=BG2,fg=ACCENT2); v.pack()
        tk.Label(c,text=label,font=('Segoe UI',8),bg=BG2,fg=MUTED).pack()
        return v

    # HISTORY
    def _pg_history(self):
        f=tk.Frame(self.content,bg=BG)
        hdr=tk.Frame(f,bg=BG2,pady=16,padx=20); hdr.pack(fill='x')
        tk.Label(hdr,text='📋  Transcription History',font=('Segoe UI',14,'bold'),bg=BG2,fg=WHITE).pack(side='left')
        tk.Button(hdr,text='🗑  Clear All',font=('Segoe UI',9),bg='#3b1515',fg='#f87171',
                  relief='flat',cursor='hand2',padx=10,pady=4,command=self._clear_hist).pack(side='right',padx=4)
        tk.Button(hdr,text='🔄  Refresh',font=('Segoe UI',9),bg=BG3,fg=ACCENT2,
                  relief='flat',cursor='hand2',padx=10,pady=4,command=self._refresh_history).pack(side='right',padx=2)
        lf=tk.Frame(f,bg=BG); lf.pack(fill='both',expand=True,padx=14,pady=10)
        sb=tk.Scrollbar(lf,bg=BG2); sb.pack(side='right',fill='y')
        self.hbox=tk.Text(lf,bg='#080d14',fg=TEXT,font=('Segoe UI',10),relief='flat',
                           wrap='word',yscrollcommand=sb.set,state='disabled',
                           padx=14,pady=10,spacing1=3,spacing3=7)
        self.hbox.pack(fill='both',expand=True); sb.config(command=self.hbox.yview)
        self.hbox.tag_config('stamp',foreground=MUTED,font=('Segoe UI',8))
        self.hbox.tag_config('entry',foreground=TEXT,font=('Segoe UI',10))
        self.hbox.tag_config('div',foreground=BG3)
        return f

    def _refresh_history(self):
        rows=db_fetch()
        self.hbox.config(state='normal'); self.hbox.delete('1.0','end')
        if not rows:
            self.hbox.insert('end','\n\n  No history yet.\n  Hold F5, speak, and your text will appear here.')
        else:
            for text,ts in rows:
                try: stamp=datetime.datetime.fromisoformat(ts).strftime('%d %b %Y  %I:%M %p')
                except: stamp=ts
                self.hbox.insert('end',f'  🕐  {stamp}\n','stamp')
                self.hbox.insert('end',f'  {text}\n','entry')
                self.hbox.insert('end',f'  {"─"*58}\n','div')
        self.hbox.config(state='disabled')

    def _clear_hist(self):
        if messagebox.askyesno('Clear History','Delete all history? Cannot be undone.',parent=self.root):
            db_clear(); self._refresh_history()

    # SETTINGS
    def _pg_settings(self):
        f=tk.Frame(self.content,bg=BG)
        hdr=tk.Frame(f,bg=BG2,pady=16,padx=20); hdr.pack(fill='x')
        tk.Label(hdr,text='⚙️  Settings',font=('Segoe UI',14,'bold'),bg=BG2,fg=WHITE).pack(side='left')
        c=tk.Frame(f,bg=BG); c.pack(fill='both',expand=True,padx=34,pady=18)
        cfg=load_config()

        def sec(t):
            tk.Label(c,text=t,font=('Segoe UI',11,'bold'),bg=BG,fg=ACCENT2).pack(anchor='w',pady=(16,2))
            tk.Frame(c,bg=BG3,height=1).pack(fill='x',pady=(0,8))

        def row(label,widget_fn):
            r=tk.Frame(c,bg=BG); r.pack(fill='x',pady=5)
            tk.Label(r,text=label,font=('Segoe UI',10),bg=BG,fg=TEXT,width=22,anchor='w').pack(side='left')
            widget_fn(r)

        sec('⌨️  Hotkey')
        self.sv_hk=tk.StringVar(value=cfg.get('HOTKEY','F5'))
        row('Record key:',lambda p: ttk.Combobox(p,textvariable=self.sv_hk,values=['F5','F6','F7','F8','F9','F10'],width=10,state='readonly').pack(side='left'))

        sec('🌐  Language')
        self.sv_lang=tk.StringVar(value=cfg.get('LANGUAGE','auto'))
        def _lw(p):
            ttk.Combobox(p,textvariable=self.sv_lang,
                          values=['auto','en','hi','es','fr','de','zh','ar','pt','ru','ja','ko','it'],
                          width=16,state='readonly').pack(side='left')
            tk.Label(p,text='  auto = detect language automatically',font=('Segoe UI',8),bg=BG,fg=MUTED).pack(side='left')
        row('Language:',_lw)

        sec('📋  History')
        self.sv_days=tk.StringVar(value=cfg.get('HISTORY_DAYS','7'))
        def _dw(p):
            ttk.Combobox(p,textvariable=self.sv_days,values=['1','3','7','14','30','90'],width=10,state='readonly').pack(side='left')
            tk.Label(p,text='  days',font=('Segoe UI',10),bg=BG,fg=TEXT).pack(side='left')
        row('Keep history for:',_dw)

        self.save_msg=tk.Label(c,text='',bg=BG,fg=GREEN,font=('Segoe UI',9))
        tk.Button(c,text='  💾   Save Settings  ',font=('Segoe UI',11,'bold'),
                  bg=ACCENT,fg=WHITE,activebackground='#2563eb',
                  relief='flat',cursor='hand2',padx=20,pady=10,
                  command=self._save_sett).pack(anchor='w',pady=14)
        self.save_msg.pack(anchor='w')
        return f

    def _save_sett(self):
        cfg={'HOTKEY':self.sv_hk.get(),'LANGUAGE':self.sv_lang.get(),'HISTORY_DAYS':self.sv_days.get()}
        save_config(cfg)
        self.hotkey=cfg['HOTKEY']
        self.hk_lbl.config(text=f'Hold {self.hotkey} to record')
        self.c_hk.config(text=self.hotkey)
        self.rec_btn.config(text=f'🎤\n\nHold  {self.hotkey}  to Record')
        self._register_hotkey()
        self.save_msg.config(text=f'✅  Saved! Hotkey is now {self.hotkey}')

    # ABOUT
    def _pg_about(self):
        f=tk.Frame(self.content,bg=BG)
        c=tk.Frame(f,bg=BG); c.place(relx=0.5,rely=0.5,anchor='center')
        tk.Label(c,text='🎤',font=('Segoe UI',54),bg=BG,fg=ACCENT2).pack()
        tk.Label(c,text='WhisperPro',font=('Segoe UI',22,'bold'),bg=BG,fg=WHITE).pack(pady=4)
        tk.Label(c,text='AI-Powered Voice Typing — Always Ready',font=('Segoe UI',11),bg=BG,fg=MUTED).pack()
        tk.Frame(c,bg=BG3,height=1,width=310).pack(pady=16)
        for label,val in [('Version','v5.0 Final'),('Engine','OpenAI Whisper'),('Platform','Windows 10/11'),('Data',APP_DIR)]:
            r=tk.Frame(c,bg=BG); r.pack(pady=3)
            tk.Label(r,text=f'{label}:',font=('Segoe UI',9),bg=BG,fg=MUTED,width=12,anchor='e').pack(side='left')
            tk.Label(r,text=val,font=('Segoe UI',9),bg=BG,fg=TEXT).pack(side='left',padx=8)
        return f

    # MINI BAR
    def _build_mini(self):
        self.mini=tk.Toplevel(self.root)
        self.mini.overrideredirect(True)
        self.mini.attributes('-topmost',True)
        self.mini.withdraw()
        sw=self.root.winfo_screenwidth()
        self.mini.geometry(f'300x38+{(sw-300)//2}+14')
        self.mini.configure(bg='#0b0f1a')
        self.mini_lbl=tk.Label(self.mini,text=f'🎤  WhisperPro — Hold {self.hotkey}',
                                font=('Segoe UI',10,'bold'),bg='#0b0f1a',fg=ACCENT2,cursor='hand2')
        self.mini_lbl.pack(fill='both',expand=True,padx=8)
        self.mini_lbl.bind('<Button-1>',self.show_main)
        self.mini.bind('<ButtonPress-1>',lambda e: setattr(self,'_dx',e.x) or setattr(self,'_dy',e.y))
        self.mini.bind('<B1-Motion>',lambda e: self.mini.geometry(f'+{self.mini.winfo_x()+e.x-self._dx}+{self.mini.winfo_y()+e.y-self._dy}'))

    def set_status(self,text,color=None,mini=None):
        color=color or GREEN
        self.live.config(text=text,fg=color)
        self.dot.config(text=text[:30],fg=color)
        if mini: self.mini_lbl.config(text=mini,fg=color)

    def _tick(self):
        self.c_model.config(text='Whisper Base' if model_ready else 'Loading…',fg=GREEN if model_ready else YELLOW)
        today=datetime.date.today().isoformat()
        cur.execute("SELECT COUNT(*) FROM history WHERE time LIKE ?",(f'{today}%',))
        self.c_count.config(text=str(cur.fetchone()[0]))
        self.root.after(2000,self._tick)

    def _register_hotkey(self):
        try: keyboard.unhook_all()
        except: pass
        def on_press(e):
            if not recording:
                mic_start()
                self.root.after(0,lambda: self.set_status('🔴  Recording... release to stop',RED,'🔴  Recording...'))
        def on_release(e):
            if recording:
                audio=mic_stop()
                self.root.after(0,lambda: self.set_status('⏳  Transcribing your speech...',YELLOW,'⏳  Processing...'))
                if audio is not None:
                    def work():
                        text=transcribe(audio)
                        if text:
                            db_save(text); do_paste(text)
                            self.root.after(0,lambda: self.last_lbl.config(text=text))
                            self.root.after(0,lambda: self.set_status(f'✅  "{text[:50]}"',GREEN,'✅  Done!'))
                            self.root.after(3500,lambda: self.set_status(f'🟢  Ready — hold {self.hotkey} to speak',GREEN,f'🎤  WhisperPro — Hold {self.hotkey}'))
                        else:
                            self.root.after(0,lambda: self.set_status('⚠️  Could not understand. Try again.',YELLOW))
                            self.root.after(2500,lambda: self.set_status(f'🟢  Ready — hold {self.hotkey} to speak',GREEN))
                    threading.Thread(target=work,daemon=True).start()
                else:
                    self.root.after(0,lambda: self.set_status('⚠️  No audio captured',YELLOW))
                    self.root.after(2000,lambda: self.set_status(f'🟢  Ready — hold {self.hotkey} to speak',GREEN))
        keyboard.on_press_key(self.hotkey,on_press)
        keyboard.on_release_key(self.hotkey,on_release)

    def run(self):
        self.root.mainloop()

if __name__=='__main__':
    app=WhisperProApp()
    app.run()
