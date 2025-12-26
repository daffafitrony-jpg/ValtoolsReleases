import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import json
import os
import time
import threading
import requests
import pyautogui
import pyperclip
import pygetwindow as gw
from cryptography.fernet import Fernet
import hashlib
import ctypes
import sys
import math
import traceback

# ==================================================================
# BAGIAN 1: LIBRARY TAMBAHAN (STEAM GUARD)
# ==================================================================
try:
    import customtkinter as ctk
    import imaplib
    import email
    from email.header import decode_header
    import base64
    from datetime import datetime, timedelta
    import random
    import string
    import re
except ImportError:
    messagebox.showerror("Missing Library", "Harap install library tambahan:\npip install customtkinter")
    sys.exit()

# ==================================================================
# BAGIAN 2: KODE STEAM GUARD (ORIGINAL)
# ==================================================================
FIREBASE_URL = "https://steamguardvaltools-default-rtdb.asia-southeast1.firebasedatabase.app/" 

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SteamPrivacyFinal(ctk.CTkToplevel): # Diubah ke Toplevel agar tidak bentrok dengan Main Window
    def __init__(self):
        super().__init__()
        self.title("Steam Guard ValTools")
        self.geometry("950x600")
        
        self.master_key = None
        self.user_role = None
        self.accounts = {}
        
        if "ISI_URL" in FIREBASE_URL:
            messagebox.showerror("Error", "URL Firebase belum diisi!")
            self.destroy()
            return

        self.show_login_screen()

    def generate_key(self, pwd):
        digest = hashlib.sha256(pwd.encode()).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, txt, key):
        return Fernet(key).encrypt(txt.encode()).decode()

    def decrypt(self, txt, key):
        return Fernet(key).decrypt(txt.encode()).decode()

    def setup_new_admin(self, pwd):
        real_key = Fernet.generate_key().decode()
        adm_key = self.generate_key(pwd)
        payload = {
            "admin_blob": self.encrypt(real_key, adm_key),
            "data_blob": self.encrypt("{}", real_key.encode()),
            "vouchers": {}
        }
        requests.put(f"{FIREBASE_URL}/.json", json=payload)
        self.master_key = real_key.encode()
        self.accounts = {}
        return True

    def login_admin(self, pwd):
        try:
            r = requests.get(f"{FIREBASE_URL}/.json").json()
            if not r: return "NEW_DB"
            adm_key = self.generate_key(pwd)
            real_key = self.decrypt(r['admin_blob'], adm_key)
            self.master_key = real_key.encode()
            self.accounts = json.loads(self.decrypt(r['data_blob'], self.master_key))
            return "SUCCESS"
        except: return "FAIL"

    def login_guest(self, code):
        try:
            r = requests.get(f"{FIREBASE_URL}/vouchers/{code}.json").json()
            if not r: return "INVALID"
            if datetime.now() > datetime.strptime(r['expiry'], "%Y-%m-%d"): return "EXPIRED"
            v_key = self.generate_key(code)
            real_key = self.decrypt(r['key_blob'], v_key)
            self.master_key = real_key.encode()
            dr = requests.get(f"{FIREBASE_URL}/data_blob.json").json()
            self.accounts = json.loads(self.decrypt(dr, self.master_key))
            return "SUCCESS"
        except: return "ERROR"

    def save_cloud(self):
        enc = self.encrypt(json.dumps(self.accounts), self.master_key)
        requests.put(f"{FIREBASE_URL}/data_blob.json", json=enc)

    def create_voucher_cloud(self, days):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        exp = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        v_key = self.generate_key(code)
        blob = self.encrypt(self.master_key.decode(), v_key)
        requests.put(f"{FIREBASE_URL}/vouchers/{code}.json", json={"expiry": exp, "key_blob": blob})
        return code, exp

    def check_steam_code(self, name, acc_data):
        self.console_log(f"🔍 CONNECTING TO {name}...", "white", clear=True)
        self.update()
        try:
            mail = imaplib.IMAP4_SSL(acc_data['server'])
            mail.login(acc_data['email'], acc_data['pass'])
            mail.select("inbox")
            _, msgs = mail.search(None, '(FROM "noreply@steampowered.com")')
            ids = msgs[0].split()
            if not ids:
                self.console_log("❌ Tidak ada email Steam.", "red")
                mail.logout(); return
            _, data = mail.fetch(ids[-1], "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj, enc = decode_header(msg["Subject"])[0]
            if isinstance(subj, bytes): subj = subj.decode(enc if enc else "utf-8")
            
            safe_keywords = ["access from new computer", "akses dari komputer baru", "mobile authenticator", "New sign in to Steam"]
            if not any(k in subj.lower() for k in safe_keywords):
                self.console_log("\n⛔ BLOCKED: SECURITY ALERT ⛔", "red")
                mail.logout(); return

            self.console_log(f"📧 Subject: {subj}", "white")
            body = msg.get_payload(decode=True).decode(errors="ignore") if not msg.is_multipart() else \
                   next((p.get_payload(decode=True).decode(errors="ignore") for p in msg.walk() if p.get_content_type()=="text/plain"), "")
            
            codes = re.findall(r'\b[A-Z0-9]{5}\b', body)
            ignored = ["STEAM", "LOGIN", "GMAIL", "YAHOO", "EMAIL", "VALVE", "HTTPS", "CLASS", "STYLE", "WIDTH", "COLOR", "BLOCK"]
            real_code = next((c for c in codes if c not in ignored), None)
            if real_code: self.console_log(f"\n✅ KODE:  >>> {real_code} <<<\n", "#00FF00")
            else: self.console_log("⚠️ Kode tidak terdeteksi otomatis.", "yellow")
            mail.logout()
        except Exception as e: self.console_log(f"❌ Error: {e}", "red")

    def clear_ui(self):
        for w in self.winfo_children(): w.destroy()
    def clear_main_frame(self):
        for w in self.main_frame.winfo_children(): w.destroy()
    def console_log(self, text, color="white", clear=False):
        self.console.configure(state="normal")
        if clear: self.console.delete("1.0", "end")
        if text:
            self.console.insert("end", text + "\n", color)
            self.console.tag_config(color, foreground=color)
            self.console.see("end")
        self.console.configure(state="disabled")

    def show_login_screen(self):
        self.clear_ui()
        self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=0)
        frame = ctk.CTkFrame(self); frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(frame, text="STEAM GUARD LOGIN", font=("Arial", 20, "bold")).pack(pady=20, padx=40)
        tabs = ctk.CTkTabview(frame, width=300); tabs.pack(pady=10)
        tabs.add("GUEST"); tabs.add("ADMIN")
        self.e_guest = ctk.CTkEntry(tabs.tab("GUEST"), placeholder_text="VOUCHER CODE", justify="center"); self.e_guest.pack(pady=20)
        ctk.CTkButton(tabs.tab("GUEST"), text="MASUK", command=self.act_guest).pack()
        self.e_admin = ctk.CTkEntry(tabs.tab("ADMIN"), placeholder_text="ADMIN PASSWORD", show="*", justify="center"); self.e_admin.pack(pady=20)
        ctk.CTkButton(tabs.tab("ADMIN"), text="LOGIN", fg_color="red", command=self.act_admin).pack()

    def act_admin(self):
        p = self.e_admin.get()
        s = self.login_admin(p)
        if s=="SUCCESS": self.setup_dashboard("ADMIN")
        elif s=="NEW_DB": 
            if messagebox.askyesno("Setup", "Buat Database Baru?"): self.setup_new_admin(p); self.setup_dashboard("ADMIN")
        else: messagebox.showerror("Fail", "Wrong Password")

    def act_guest(self):
        c = self.e_guest.get().upper()
        s = self.login_guest(c)
        if s=="SUCCESS": self.setup_dashboard("GUEST")
        elif s=="EXPIRED": messagebox.showerror("Fail", "Expired")
        else: messagebox.showerror("Fail", "Invalid Code")

    def setup_dashboard(self, role):
        self.user_role = role
        self.clear_ui()
        self.grid_columnconfigure(0, weight=0); self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1); self.grid_rowconfigure(1, weight=0)
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="MENU", font=("Arial", 20, "bold")).pack(pady=30)
        ctk.CTkButton(self.sidebar, text="🏠 Daftar Akun", command=self.show_account_list, fg_color="transparent", border_width=1).pack(pady=5, padx=20, fill="x")
        if role == "ADMIN":
            ctk.CTkButton(self.sidebar, text="+ Tambah Akun", command=self.show_add_form, fg_color="#2b2b2b").pack(pady=5, padx=20, fill="x")
            ctk.CTkButton(self.sidebar, text="🎟️ Buat Voucher", command=self.show_voucher_form, fg_color="orange", text_color="black").pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="Logout", fg_color="darkred", command=self.show_login_screen).pack(side="bottom", pady=20, padx=20, fill="x")
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.show_account_list()
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.console.configure(state="disabled")
        self.console_log(f"Login sebagai {role}.", "white")

    def show_account_list(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="DAFTAR AKUN STEAM", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0,20))
        scroll_area = ctk.CTkScrollableFrame(self.main_frame)
        scroll_area.pack(fill="both", expand=True)
        if not self.accounts: ctk.CTkLabel(scroll_area, text="Belum ada akun tersimpan.").pack(pady=50); return
        for name, data in self.accounts.items():
            row = ctk.CTkFrame(scroll_area)
            row.pack(fill="x", pady=5, padx=5)
            if self.user_role == "ADMIN":
                info = ctk.CTkFrame(row, fg_color="transparent"); info.pack(side="left", padx=10)
                ctk.CTkLabel(info, text=name, font=("Arial", 14, "bold"), anchor="w").pack(anchor="w")
                ctk.CTkLabel(info, text=data['email'], text_color="gray", font=("Arial", 10)).pack(anchor="w")
            else: ctk.CTkLabel(row, text=name, font=("Arial", 16, "bold"), width=150, anchor="w").pack(side="left", padx=15, pady=10)
            btn_box = ctk.CTkFrame(row, fg_color="transparent"); btn_box.pack(side="right", padx=10, pady=5)
            ctk.CTkButton(btn_box, text="LIHAT KODE", width=100, command=lambda n=name, d=data: self.check_steam_code(n, d)).pack(side="left", padx=5)
            if self.user_role == "ADMIN": ctk.CTkButton(btn_box, text="X", width=30, fg_color="darkred", command=lambda n=name: self.delete_acc(n)).pack(side="left", padx=5)

    def show_add_form(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="TAMBAH AKUN BARU", font=("Arial", 18, "bold")).pack(pady=20)
        f = ctk.CTkFrame(self.main_frame); f.pack(pady=10)
        ctk.CTkLabel(f, text="Nama:").pack(pady=5); self.entry_add_name = ctk.CTkEntry(f, width=300); self.entry_add_name.pack(pady=5)
        ctk.CTkLabel(f, text="Email:").pack(pady=5); self.entry_add_email = ctk.CTkEntry(f, width=300); self.entry_add_email.pack(pady=5)
        ctk.CTkLabel(f, text="Pass:").pack(pady=5); self.entry_add_pass = ctk.CTkEntry(f, width=300, show="*"); self.entry_add_pass.pack(pady=5)
        b = ctk.CTkFrame(self.main_frame, fg_color="transparent"); b.pack(pady=20)
        ctk.CTkButton(b, text="Simpan", fg_color="green", command=self.save_new_account).pack(side="left", padx=10)
        ctk.CTkButton(b, text="Batal", fg_color="gray", command=self.show_account_list).pack(side="left", padx=10)

    def save_new_account(self):
        n = self.entry_add_name.get(); e = self.entry_add_email.get(); p = self.entry_add_pass.get()
        if n and e and p:
            s = "imap.mail.yahoo.com" if "yahoo" in e else "imap.gmail.com"
            self.accounts[n] = {"email": e, "pass": p, "server": s}
            self.save_cloud(); self.console_log(f"✅ Disimpan: {n}", "green", clear=True); self.show_account_list()
        else: self.console_log("❌ Data kurang!", "red", clear=True)

    def show_voucher_form(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="VOUCHER TAMU", font=("Arial", 18, "bold")).pack(pady=20)
        f = ctk.CTkFrame(self.main_frame); f.pack(pady=10)
        ctk.CTkLabel(f, text="Hari:").pack(pady=5); self.entry_days = ctk.CTkEntry(f, width=100, justify="center"); self.entry_days.pack(pady=5)
        ctk.CTkButton(f, text="Generate", command=self.generate_voucher_action).pack(pady=10)
        self.lbl_result_title = ctk.CTkLabel(self.main_frame, text="KODE:", font=("Arial", 12))
        self.entry_result_code = ctk.CTkEntry(self.main_frame, font=("Arial", 24, "bold"), justify="center", width=250)
        self.lbl_result_exp = ctk.CTkLabel(self.main_frame, text="", text_color="orange")
        ctk.CTkButton(self.main_frame, text="Kembali", fg_color="gray", command=self.show_account_list).pack(side="bottom", pady=20)

    def generate_voucher_action(self):
        try:
            d = int(self.entry_days.get())
            c, e = self.create_voucher_cloud(d)
            self.lbl_result_title.pack(pady=(20, 5)); self.entry_result_code.delete(0, "end"); self.entry_result_code.insert(0, c); self.entry_result_code.pack(pady=5)
            self.lbl_result_exp.configure(text=f"Exp: {e}"); self.lbl_result_exp.pack(pady=5)
        except: self.console_log("❌ Input salah", "red", clear=True)

    def delete_acc(self, name):
        if messagebox.askyesno("Hapus", f"Hapus {name}?"): del self.accounts[name]; self.save_cloud(); self.show_account_list()


# ==================================================================
# BAGIAN 3: VALTOOLS UTAMA (UI & LOGIC)
# ==================================================================
try:
    pyautogui.FAILSAFE = False 
    API_KEY = "$2a$10$rogV/OBNjQ8GYVjQbuRiRu02pxTYppJ2QF4PxFEUJzGo8il9XRyYG"
    BIN_ID = "69208b43d0ea881f40f70c06"
    STATIC_KEY = b'LDfE_w9DvToSg8P1QOk50_h-DqrtDKjJBbm2zmOl42Y=' 
    SETTINGS_FILE = "settings.json"
    TIMEOUT_SECONDS = 60

    # WARNA
    COLOR_BG_MAIN    = "#0b1218"
    COLOR_SIDEBAR    = "#060d13"
    COLOR_ACCENT     = "#f7b500"
    COLOR_CARD       = "#0e1b2a"
    COLOR_BTN_GREEN  = "#2ecc71"
    COLOR_BTN_DARK   = "#1c2a38"
    COLOR_TEXT_WHITE = "#ffffff"
    COLOR_TEXT_GREY  = "#6b7b8c"
    COLOR_HOVER      = "#0e1b2a"

    class OverlayWindow:
        def __init__(self, master):
            self.win = tk.Toplevel(master)
            self.win.attributes('-fullscreen', True)
            self.win.attributes('-topmost', True)
            self.win.configure(bg='black')
            self.win.attributes('-alpha', 0.95)
            self.win.overrideredirect(True)
            self.lbl_status = tk.Label(self.win, text="SYSTEM LOCKED", font=("Segoe UI", 24, "bold"), fg="red", bg="black")
            self.lbl_status.pack(expand=True)
            self.lbl_sub = tk.Label(self.win, text="Memproses...", font=("Segoe UI", 12), fg="yellow", bg="black")
            self.lbl_sub.pack(pady=(0, 50))
            self.win.update()
        def update_text(self, text, color="white"):
            try: self.lbl_status.config(text=text, fg=color); self.win.update()
            except: pass
        def update_sub(self, text):
            try: self.lbl_sub.config(text=text); self.win.update()
            except: pass
        def hide(self): self.win.withdraw()
        def show(self): self.win.deiconify(); self.win.lift()
        def destroy(self): self.win.destroy()

    class ValAdminApp:
        def __init__(self, root):
            self.root = root
            self.root.title("ValTools - V13 Modern")
            self.root.geometry("1000x650")
            
            # Set customtkinter theme
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            if not ctypes.windll.shell32.IsUserAnAdmin():
                messagebox.showwarning("Admin Warning", "Butuh Run as Administrator.")

            try: self.cipher = Fernet(STATIC_KEY)
            except: self.cipher = Fernet(Fernet.generate_key())

            self.settings = self.load_settings()
            self.accounts = {}
            self.admin_hash = ""
            self.is_admin_logged_in = False 
            self.locking_active = False 

            self.setup_ui()
            self.account_list.insert(0, "🔄 Connecting to cloud...")
            threading.Thread(target=self.load_cloud_data, daemon=True).start()

        def setup_ui(self):
            # Main container
            self.root.configure(bg="#0a0e14")
            
            # SIDEBAR - Modern with glassmorphism
            self.sidebar = ctk.CTkFrame(self.root, width=250, corner_radius=0, fg_color="#0d1117", border_width=0)
            self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
            self.sidebar.pack_propagate(False)
            
            # App Logo/Title with gradient effect
            title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            title_frame.pack(pady=(30, 40), padx=20)
            ctk.CTkLabel(title_frame, text="⚡", font=("Segoe UI", 40, "bold"), text_color=COLOR_ACCENT).pack()
            ctk.CTkLabel(title_frame, text="ValTools", font=("Segoe UI", 24, "bold"), text_color="white").pack()
            ctk.CTkLabel(title_frame, text="V13 Modern Edition", font=("Segoe UI", 9), text_color="#6b7b8c").pack()
            
            # Menu buttons dengan icon
            self.menu_buttons = []
            self.create_menu_button("🏠  Dashboard", True, None)
            self.create_menu_button("⚙️  Settings", False, self.change_path)
            self.create_menu_button("🔄  Refresh", False, self.manual_refresh)
            self.create_menu_button("🔐  Admin Login", False, self.trigger_admin_action)
            
            # Spacer
            ctk.CTkFrame(self.sidebar, height=1, fg_color="#1a1f26").pack(fill="x", padx=20, pady=20)
            
            # Steam Guard Button - Modern
            self.btn_sg = ctk.CTkButton(
                self.sidebar, 
                text="🛡️  Steam Guard",
                font=("Segoe UI", 13, "bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                corner_radius=10,
                height=45,
                command=self.open_steam_guard
            )
            self.btn_sg.pack(side="bottom", padx=20, pady=(0, 20), fill="x")
            
            # Role indicator - Modern badge
            self.role_frame = ctk.CTkFrame(self.sidebar, fg_color="#161b22", corner_radius=10, height=70)
            self.role_frame.pack(side="bottom", fill="x", padx=20, pady=10)
            self.lbl_role = ctk.CTkLabel(
                self.role_frame, 
                text="👤  Guest Mode", 
                font=("Segoe UI", 11, "bold"),
                text_color="#6b7b8c"
            )
            self.lbl_role.pack(pady=20)

            # MAIN CONTENT AREA
            self.main = ctk.CTkFrame(self.root, fg_color="#0a0e14", corner_radius=0)
            self.main.pack(side="right", fill="both", expand=True)
            
            # Main Card - Premium glassmorphism style
            self.card = ctk.CTkFrame(
                self.main, 
                width=550,
                height=500,
                fg_color="#161b22",
                corner_radius=20,
                border_width=1,
                border_color="#21262d"
            )
            self.card.place(relx=0.5, rely=0.5, anchor="center")
            
            # Card Header
            header_frame = ctk.CTkFrame(self.card, fg_color="transparent")
            header_frame.pack(pady=(25, 10), padx=30, fill="x")
            
            ctk.CTkLabel(
                header_frame, 
                text="⚡", 
                font=("Arial", 50),
                text_color=COLOR_ACCENT
            ).pack()
            
            ctk.CTkLabel(
                header_frame, 
                text="Account Manager", 
                font=("Segoe UI", 20, "bold"),
                text_color="white"
            ).pack(pady=(5, 0))
            
            ctk.CTkLabel(
                header_frame, 
                text="Select an account to inject credentials", 
                font=("Segoe UI", 11),
                text_color="#6b7b8c"
            ).pack(pady=(5, 0))

            # Account List Container - Modern scrollable
            list_container = ctk.CTkFrame(self.card, fg_color="#0d1117", corner_radius=12)
            list_container.pack(fill="both", expand=True, padx=30, pady=15)
            
            # Custom scrollable frame for accounts
            self.account_scroll = ctk.CTkScrollableFrame(
                list_container,
                fg_color="transparent",
                scrollbar_button_color="#21262d",
                scrollbar_button_hover_color="#30363d"
            )
            self.account_scroll.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Account listbox replacement with modern list
            self.listbox = tk.Listbox(
                list_container,
                font=("Segoe UI", 12),
                bg="#0d1117",
                fg="white",
                selectbackground=COLOR_ACCENT,
                selectforeground="#000",
                bd=0,
                highlightthickness=0,
                relief="flat",
                activestyle="none"
            )
            self.listbox.pack(fill="both", expand=True, padx=12, pady=12)
            
            # Save reference for custom list
            self.account_list = self.listbox

            # Action Buttons - Modern with hover
            btn_container = ctk.CTkFrame(self.card, fg_color="transparent")
            btn_container.pack(fill="x", padx=30, pady=(10, 25))
            
            # Main action button
            self.btn_run = ctk.CTkButton(
                btn_container,
                text="🚀  LOCK & INJECT",
                font=("Segoe UI", 13, "bold"),
                fg_color="#10b981",
                hover_color="#059669",
                corner_radius=10,
                height=48,
                command=self.start_thread
            )
            self.btn_run.pack(side="left", fill="x", expand=True, padx=(0, 8))
            
            # Admin buttons container
            admin_btns = ctk.CTkFrame(btn_container, fg_color="transparent")
            admin_btns.pack(side="right")
            
            self.btn_add = ctk.CTkButton(
                admin_btns,
                text="➕",
                font=("Segoe UI", 16, "bold"),
                width=50,
                height=48,
                fg_color="#374151",
                hover_color="#4b5563",
                corner_radius=10,
                state="disabled",
                command=self.add_account
            )
            self.btn_add.pack(side="left", padx=(0, 8))
            
            self.btn_del = ctk.CTkButton(
                admin_btns,
                text="🗑️",
                font=("Segoe UI", 14, "bold"),
                width=50,
                height=48,
                fg_color="#374151",
                hover_color="#dc2626",
                corner_radius=10,
                state="disabled",
                command=self.delete_account
            )
            self.btn_del.pack(side="left")
            
            # Status bar - Modern
            status_frame = ctk.CTkFrame(self.main, fg_color="#0d1117", corner_radius=0, height=35)
            status_frame.pack(side="bottom", fill="x", padx=0, pady=0)
            
            try: target = os.path.basename(self.settings['steam_path'])
            except: target = "Unknown"
            
            self.lbl_status = ctk.CTkLabel(
                status_frame,
                text=f"🎯 Target: {target}",
                font=("Consolas", 10),
                text_color="#6b7b8c"
            )
            self.lbl_status.pack(side="left", padx=20, pady=5)
            
            self.lbl_connection = ctk.CTkLabel(
                status_frame,
                text="⚪ Connecting...",
                font=("Consolas", 10),
                text_color="#6b7b8c"
            )
            self.lbl_connection.pack(side="right", padx=20, pady=5)

        def create_menu_button(self, text, active, cmd=None):
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                font=("Segoe UI", 12, "bold"),
                fg_color="#1a1f26" if active else "transparent",
                hover_color="#1a1f26",
                corner_radius=10,
                height=42,
                anchor="w",
                command=cmd,
                text_color="white" if active else "#6b7b8c"
            )
            btn.pack(fill="x", padx=15, pady=3)
            self.menu_buttons.append(btn)

        def open_steam_guard(self):
            app = SteamPrivacyFinal()
            app.mainloop()

        def show_custom_input(self, title, prompt, is_password=False):
            # Modern modal dialog
            dialog_window = ctk.CTkToplevel(self.root)
            dialog_window.title(title)
            dialog_window.geometry("400x280")
            dialog_window.resizable(False, False)
            dialog_window.configure(fg_color="#0d1117")
            
            # Center the dialog
            dialog_window.transient(self.root)
            dialog_window.grab_set()
            
            # Content frame
            content = ctk.CTkFrame(dialog_window, fg_color="#161b22", corner_radius=15)
            content.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Icon based on type
            icon = "🔐" if is_password else "✏️"
            ctk.CTkLabel(content, text=icon, font=("Arial", 40)).pack(pady=(20, 10))
            
            # Title
            ctk.CTkLabel(
                content,
                text=title,
                font=("Segoe UI", 18, "bold"),
                text_color="white"
            ).pack(pady=(0, 5))
            
            # Prompt
            ctk.CTkLabel(
                content,
                text=prompt,
                font=("Segoe UI", 11),
                text_color="#6b7b8c"
            ).pack(pady=(0, 15))
            
            # Entry
            entry_var = tk.StringVar()
            entry = ctk.CTkEntry(
                content,
                textvariable=entry_var,
                font=("Segoe UI", 13),
                height=40,
                corner_radius=8,
                fg_color="#0d1117",
                border_color="#21262d",
                text_color="white",
                show="●" if is_password else ""
            )
            entry.pack(pady=10, padx=30, fill="x")
            entry.focus_force()
            
            result = {"value": None}
            
            def on_ok(e=None):
                val = entry_var.get()
                if val:
                    result["value"] = val
                    dialog_window.destroy()
                else:
                    entry.configure(border_color="#dc2626")
                    
            def on_cancel():
                dialog_window.destroy()
            
            # Buttons
            btn_frame = ctk.CTkFrame(content, fg_color="transparent")
            btn_frame.pack(pady=15)
            
            ctk.CTkButton(
                btn_frame,
                text="✓ OK",
                font=("Segoe UI", 12, "bold"),
                fg_color="#10b981",
                hover_color="#059669",
                width=100,
                height=35,
                corner_radius=8,
                command=on_ok
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                btn_frame,
                text="✕ CANCEL",
                font=("Segoe UI", 12, "bold"),
                fg_color="#374151",
                hover_color="#4b5563",
                width=100,
                height=35,
                corner_radius=8,
                command=on_cancel
            ).pack(side="left", padx=5)
            
            entry.bind("<Return>", on_ok)
            entry.bind("<Escape>", lambda e: on_cancel())
            
            # Wait for dialog
            dialog_window.wait_window()
            return result["value"]

        def update_role_ui(self):
            self.lbl_role.configure(text="👑  Admin Mode", text_color="#10b981")
            self.btn_add.configure(state="normal", fg_color="#1d4ed8", hover_color="#1e40af")
            self.btn_del.configure(state="normal", fg_color="#dc2626", hover_color="#b91c1c")

        def force_create_admin(self):
            p = self.show_custom_input("Setup Admin", "Cloud Kosong. Buat Pass:", True)
            if p: self.admin_hash=self.hash_password(p); self.save_cloud_data(); self.is_admin_logged_in=True; self.update_role_ui()

        def check_admin_access(self):
            if self.is_admin_logged_in: return True
            p = self.show_custom_input("Admin Login", "Masukkan Password:", True)
            if p and self.hash_password(p) == self.admin_hash: self.is_admin_logged_in = True; self.update_role_ui(); return True
            else: 
                if p: messagebox.showerror("Error", "Salah!")
                return False

        def trigger_admin_action(self):
            if self.is_admin_logged_in: messagebox.showinfo("Info", "Sudah Admin."); return
            self.check_admin_access()

        def add_account(self):
            a = self.show_custom_input("Add", "Nama Alias:"); 
            if not a: return
            u = self.show_custom_input("Add", "Username:"); 
            if not u: return
            p = self.show_custom_input("Add", "Password:", True)
            if not p: return
            self.accounts[a] = {"u": u, "p": p}; self.refresh_list(); self.save_cloud_data()

        def delete_account(self):
            if self.account_list.curselection():
                raw = self.account_list.get(self.account_list.curselection())
                # Remove icon prefix "🎮 "
                a = raw.replace("🎮 ", "").strip()
                if a in self.accounts:
                    if messagebox.askyesno("Delete Account", f"Delete {a}?"): 
                        del self.accounts[a]
                        self.refresh_list()
                        self.save_cloud_data()

        def manual_refresh(self): 
            self.account_list.delete(0,tk.END)
            self.account_list.insert(0,"🔄 Loading...")
            threading.Thread(target=self.load_cloud_data, daemon=True).start()
            
        def refresh_list(self): 
            self.account_list.delete(0,tk.END)
            if not self.accounts:
                self.account_list.insert(tk.END, "📭 No accounts yet")
            else:
                for idx, name in enumerate(self.accounts, 1):
                    self.account_list.insert(tk.END, f"🎮 {name}")
        def load_settings(self): 
            try: return json.load(open(SETTINGS_FILE)) 
            except: return {"steam_path": r"C:\Program Files (x86)\Steam\steam.exe"}
        
        def change_path(self):
            f = filedialog.askopenfilename(title="Select Steam Executable", filetypes=[("Exe", "*.exe")])
            if f: 
                self.settings['steam_path'] = f
                with open(SETTINGS_FILE, "w") as file: json.dump(self.settings, file)
                self.lbl_status.configure(text=f"🎯 Target: {os.path.basename(f)}")
                messagebox.showinfo("Success", "Steam path updated!")

        def mouse_jail_loop(self):
            anchor_x, anchor_y = pyautogui.position(); PANIC_DISTANCE = 400; time.sleep(0.5)
            while self.locking_active:
                if self.abort_flag: break
                cur_x, cur_y = pyautogui.position()
                if math.hypot(cur_x - anchor_x, cur_y - anchor_y) > PANIC_DISTANCE: self.abort_flag = True; break
                if math.hypot(cur_x - anchor_x, cur_y - anchor_y) > 20: pyautogui.moveTo(anchor_x, anchor_y)
                time.sleep(0.01)

        def start_thread(self): 
            self.btn_run.configure(state="disabled", text="⏳ RUNNING...")
            threading.Thread(target=self.run_login, daemon=True).start()

        def get_steam_window(self):
            try:
                windows = gw.getWindowsWithTitle('Steam') + gw.getWindowsWithTitle('Sign in')
                for w in windows:
                    if w.visible and "ValTools" not in w.title:
                        if 200 < w.width < 1000 and w.height > 200: return w
            except: pass
            return None

        def run_login(self):
            try:
                sel = self.account_list.curselection()
                if not sel: 
                    messagebox.showwarning("Info", "Please select an account first!")
                    return
                    
                raw = self.account_list.get(sel)
                # Remove icon prefix "🎮 "
                alias = raw.replace("🎮 ", "").strip()
                
                if alias not in self.accounts:
                    messagebox.showerror("Error", "Account not found!")
                    return
                    
                acc = self.accounts[alias]
                if not os.path.exists(self.settings['steam_path']): 
                    messagebox.showerror("Error", "Steam path is invalid!")
                    return
                
                self.abort_flag = False; self.locking_active = True
                threading.Thread(target=self.mouse_jail_loop, daemon=True).start()
                self.overlay = OverlayWindow(self.root); self.overlay.update_text("MENGUNCI...", "red")

                self.overlay.update_text("RESTART STEAM...", "yellow")
                subprocess.call("taskkill /F /IM steam.exe", shell=True, stderr=subprocess.DEVNULL)
                time.sleep(2)
                if self.abort_flag: raise Exception("Dibatalkan User")

                self.overlay.update_text("MEMBUKA STEAM...", "cyan")
                subprocess.Popen(self.settings['steam_path'])

                target = None; start = time.time()
                while time.time() - start < TIMEOUT_SECONDS:
                    if self.abort_flag: raise Exception("Dibatalkan User")
                    target = self.get_steam_window()
                    if target: self.overlay.update_sub("Terdeteksi!"); break
                    self.overlay.update_sub(f"Mencari... ({int(time.time()-start)}s)"); time.sleep(1)

                if not target: raise Exception("Timeout")

                self.overlay.update_text("MENUNGGU UI...", "cyan")
                time.sleep(4)
                if self.abort_flag: raise Exception("Dibatalkan User")

                self.locking_active = False; time.sleep(0.5); self.overlay.hide()
                
                target = self.get_steam_window()
                if target:
                    try:
                        if target.isMinimized: target.restore()
                        target.activate(); ctypes.windll.user32.SetForegroundWindow(target._hWnd); pyautogui.click(target.left + 100, target.top + 20)
                    except: pass
                time.sleep(0.5)

                is_safe = False
                forbidden = ["visual studio", "code", "sublime", "notepad", "browser", "chrome"]
                for _ in range(3):
                    try:
                        aw = gw.getActiveWindow(); 
                        if aw: 
                            t = aw.title.lower()
                            if ("steam" in t or "sign" in t) and not any(x in t for x in forbidden): is_safe = True; break
                    except: pass
                    time.sleep(0.2)

                if not is_safe: self.overlay.show(); raise Exception("SAFETY BLOCK: Salah Jendela")

                pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1); pyautogui.press('backspace')
                pyperclip.copy(acc['u']); pyautogui.hotkey('ctrl', 'v'); time.sleep(0.5); pyautogui.press('tab'); time.sleep(0.5)
                pyperclip.copy(acc['p']); pyautogui.hotkey('ctrl', 'v'); time.sleep(0.5); pyautogui.press('enter')

                self.overlay.show(); self.overlay.update_text("SUKSES!", "lime"); self.overlay.update_sub("Login Berhasil."); time.sleep(2)

            except Exception as e:
                self.locking_active = False; 
                try: self.overlay.show()
                except: pass
                if "BLOCK" in str(e): self.overlay.update_text("SAFETY BLOCK!", "red")
                elif "Dibatalkan" in str(e): self.overlay.update_text("DIBATALKAN", "red")
                else: self.overlay.update_text("ERROR", "red"); print(e)
                self.overlay.update_sub(str(e)); time.sleep(4)

            finally:
                self.locking_active = False
                self.btn_run.configure(state="normal", text="🚀  LOCK & INJECT")
                try: self.overlay.destroy()
                except: pass

        def hash_password(self, p): return hashlib.sha256(p.encode()).hexdigest()
        def load_cloud_data(self):
            self.accounts={}
            try:
                h={"X-Master-Key":API_KEY}
                r=requests.get(f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest",headers=h)
                if r.status_code==200:
                    d=r.json().get("record",{})
                    if "payload" in d and d["payload"]:
                        full=json.loads(self.cipher.decrypt(d["payload"].encode()).decode())
                        self.accounts=full.get("accounts",{}); self.admin_hash=full.get("admin_hash","")
                self.root.after(0, self.refresh_list)
                self.root.after(0, lambda: self.lbl_connection.configure(text="🟢 Connected", text_color="#10b981"))
                if not self.admin_hash: 
                    self.root.after(0, self.force_create_admin)
            except:
                self.root.after(0, lambda: self.lbl_connection.configure(text="🔴 Offline", text_color="#dc2626"))
        def save_cloud_data(self):
            try:
                pay={"payload":self.cipher.encrypt(json.dumps({"admin_hash":self.admin_hash,"accounts":self.accounts}).encode()).decode()}
                h={"Content-Type":"application/json","X-Master-Key":API_KEY}
                threading.Thread(target=lambda:requests.put(f"https://api.jsonbin.io/v3/b/{BIN_ID}",json=pay,headers=h),daemon=True).start()
            except: pass

    if __name__ == "__main__":
        root = ctk.CTk()
        root.iconify()  # Minimize initially
        root.update()
        root.deiconify()  # Show after setup
        app = ValAdminApp(root)
        root.mainloop()

except Exception as e:
    error_msg = traceback.format_exc()
    print(error_msg)
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("CRITICAL ERROR", f"Aplikasi Gagal:\n{error_msg}")