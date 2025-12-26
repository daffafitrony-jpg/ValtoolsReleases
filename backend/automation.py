#!/usr/bin/env python
"""
ValTools Automation Backend
Handles Steam login injection via PyAutoGUI
Called from Electron via subprocess
"""

import argparse
import json
import sys
import os
import time
import subprocess

try:
    import pyautogui
    import pyperclip
    import pygetwindow as gw
    import ctypes
except ImportError as e:
    print(json.dumps({"type": "error", "message": f"Missing library: {e}"}))
    sys.exit(1)

# Disable PyAutoGUI failsafe
pyautogui.FAILSAFE = False

# Constants
TIMEOUT_SECONDS = 60

def send_status(text, subtext="", color="white"):
    """Send status update to Electron"""
    print(json.dumps({
        "type": "status",
        "text": text,
        "subtext": subtext,
        "color": color
    }))
    sys.stdout.flush()

def get_steam_window():
    """Find Steam login window"""
    try:
        windows = gw.getWindowsWithTitle('Steam') + gw.getWindowsWithTitle('Sign in')
        for w in windows:
            if w.visible and "ValTools" not in w.title:
                if 200 < w.width < 1000 and w.height > 200:
                    return w
    except:
        pass
    return None

def is_steam_active():
    """Check if the active window is Steam (not notepad/browser/etc)"""
    try:
        aw = gw.getActiveWindow()
        if aw:
            title = aw.title.lower()
            # Forbidden windows - never paste here
            forbidden = ["notepad", "browser", "chrome", "firefox", "edge", "word", 
                        "excel", "code", "visual studio", "sublime", "atom", "discord"]
            if any(f in title for f in forbidden):
                return False
            # Must contain steam-related words
            if "steam" in title or "sign in" in title:
                return True
    except:
        pass
    return False

def run_injection(username, password, steam_path):
    """Main injection logic with security checks"""
    try:
        # Check Steam path
        if not os.path.exists(steam_path):
            send_status("ERROR", f"Steam not found: {steam_path}", "red")
            return False

        # Kill existing Steam
        send_status("RESTART STEAM...", "Menutup Steam...", "yellow")
        subprocess.call("taskkill /F /IM steam.exe", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(2)

        # Launch Steam
        send_status("MEMBUKA STEAM...", "Menunggu jendela Steam...", "cyan")
        subprocess.Popen(steam_path)

        # Wait for Steam window
        target = None
        start = time.time()
        while time.time() - start < TIMEOUT_SECONDS:
            target = get_steam_window()
            if target:
                send_status("TERDETEKSI!", "Steam window ditemukan", "cyan")
                break
            elapsed = int(time.time() - start)
            send_status("MENCARI...", f"Mencari jendela Steam... ({elapsed}s)", "yellow")
            time.sleep(1)

        if not target:
            send_status("TIMEOUT", "Steam window tidak ditemukan", "red")
            return False

        # Wait for UI to load
        send_status("MENUNGGU UI...", "Steam UI sedang loading...", "cyan")
        time.sleep(5)

        # Get fresh window reference and activate
        send_status("AKTIVASI...", "Mengaktifkan jendela Steam...", "cyan")
        target = get_steam_window()
        if target:
            try:
                if target.isMinimized:
                    target.restore()
                target.activate()
                time.sleep(0.3)
                try:
                    ctypes.windll.user32.SetForegroundWindow(target._hWnd)
                except:
                    pass
            except Exception as e:
                send_status("DEBUG", f"Activate: {str(e)}", "yellow")
        
        time.sleep(0.5)

        # Click on the username field
        target = get_steam_window()
        if target:
            username_x = target.left + (target.width // 3)
            username_y = target.top + int(target.height * 0.28)
            
            send_status("KLIK FIELD...", "Memilih field username...", "cyan")
            pyautogui.click(username_x, username_y)
            time.sleep(0.5)

        # ===== SECURITY CHECK 1: Before typing username =====
        send_status("SECURITY CHECK...", "Verifikasi window aktif...", "yellow")
        if not is_steam_active():
            send_status("SECURITY BLOCK!", "Bukan Steam window - DIBATALKAN", "red")
            pyperclip.copy("")  # Clear clipboard
            return False

        # Clear and type username
        send_status("INJECTING...", "Memasukkan username...", "cyan")
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('backspace')
        time.sleep(0.2)
        
        # Double check before paste
        if not is_steam_active():
            send_status("SECURITY BLOCK!", "Window berubah - DIBATALKAN", "red")
            pyperclip.copy("")
            return False
            
        pyperclip.copy(username)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        # Tab to password field
        send_status("INJECTING...", "Memasukkan password...", "cyan")
        pyautogui.press('tab')
        time.sleep(0.5)
        
        # ===== SECURITY CHECK 2: Before typing password =====
        if not is_steam_active():
            send_status("SECURITY BLOCK!", "Bukan Steam window - DIBATALKAN", "red")
            pyperclip.copy("")  # Clear clipboard
            return False
        
        # Type password
        pyperclip.copy(password)
        pyautogui.hotkey('ctrl', 'v')
        pyperclip.copy("")  # Immediately clear password from clipboard
        time.sleep(0.5)
        
        # Submit
        pyautogui.press('enter')

        send_status("SUKSES!", "Login berhasil!", "lime")
        time.sleep(1)
        
        return True

    except Exception as e:
        pyperclip.copy("")  # Clear clipboard on error
        send_status("ERROR", str(e), "red")
        return False

def main():
    parser = argparse.ArgumentParser(description='ValTools Automation Backend')
    parser.add_argument('--username', required=True, help='Steam username')
    parser.add_argument('--password', required=True, help='Steam password')
    parser.add_argument('--steam-path', required=True, help='Path to Steam executable')
    
    args = parser.parse_args()
    
    success = run_injection(args.username, args.password, args.steam_path)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()


