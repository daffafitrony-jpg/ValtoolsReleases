#!/usr/bin/env python
"""
ValTools Automation Backend
Handles Steam login via command line parameter
Called from Electron via subprocess
"""

import argparse
import json
import sys
import os
import time
import subprocess

def send_status(text, subtext="", color="white"):
    """Send status update to Electron"""
    print(json.dumps({
        "type": "status",
        "text": text,
        "subtext": subtext,
        "color": color
    }))
    sys.stdout.flush()

def run_injection(username, password, steam_path):
    """Direct Steam login using command line parameter"""
    try:
        # Check Steam path
        if not os.path.exists(steam_path):
            send_status("ERROR", f"Steam not found: {steam_path}", "red")
            return False

        # Kill existing Steam completely
        send_status("MENUTUP STEAM...", "Menghentikan semua proses Steam...", "yellow")
        subprocess.call("taskkill /F /IM steam.exe", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.call("taskkill /F /IM steamwebhelper.exe", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(3)

        # Launch Steam with -login parameter for DIRECT login
        # This bypasses the account picker entirely
        send_status("LOGIN LANGSUNG...", "Membuka Steam dengan kredensial...", "cyan")
        
        # Use -login username password to directly login
        process = subprocess.Popen(
            [steam_path, "-login", username, password],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        send_status("MENUNGGU...", "Steam sedang login...", "cyan")
        time.sleep(8)  # Wait for Steam to process login

        # Check if steam.exe is running (login successful)
        result = subprocess.run(
            'tasklist /FI "IMAGENAME eq steam.exe" /NH',
            shell=True,
            capture_output=True,
            text=True
        )
        
        if "steam.exe" in result.stdout.lower():
            send_status("SUKSES!", "Login berhasil! Steam sudah terbuka.", "lime")
            return True
        else:
            send_status("GAGAL", "Steam tidak merespon. Coba lagi.", "red")
            return False

    except Exception as e:
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
