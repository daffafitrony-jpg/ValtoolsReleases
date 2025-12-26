#!/usr/bin/env python
"""
ValTools Steam Guard Backend
Handles Firebase sync with Fernet encryption for Steam Guard accounts
Called from Electron via subprocess
"""

import json
import sys
import argparse
import requests
import hashlib
import base64

try:
    from cryptography.fernet import Fernet
except ImportError:
    print(json.dumps({"error": "cryptography library required"}))
    sys.exit(1)

# Configuration
FIREBASE_URL = "https://steamguardvaltools-default-rtdb.asia-southeast1.firebasedatabase.app/"

def generate_key(password):
    """Generate Fernet key from password (same as original)"""
    digest = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt(text, key):
    """Encrypt with Fernet"""
    return Fernet(key).encrypt(text.encode()).decode()

def decrypt(text, key):
    """Decrypt with Fernet"""
    return Fernet(key).decrypt(text.encode()).decode()

def login_admin(password):
    """Login as admin and get accounts"""
    try:
        response = requests.get(f"{FIREBASE_URL}.json")
        data = response.json()
        
        if not data:
            return {"success": False, "error": "Database empty", "new_db": True}
        
        admin_key = generate_key(password)
        try:
            real_key = decrypt(data['admin_blob'], admin_key)
            master_key = real_key.encode()
            accounts = json.loads(decrypt(data['data_blob'], master_key))
            
            return {
                "success": True,
                "accounts": accounts,
                "master_key": real_key,
                "role": "ADMIN"
            }
        except Exception as e:
            return {"success": False, "error": "Wrong password"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def login_guest(code):
    """Login as guest with voucher code"""
    try:
        response = requests.get(f"{FIREBASE_URL}vouchers/{code}.json")
        voucher = response.json()
        
        if not voucher:
            return {"success": False, "error": "Invalid voucher"}
        
        from datetime import datetime
        if datetime.now() > datetime.strptime(voucher['expiry'], "%Y-%m-%d"):
            return {"success": False, "error": "Voucher expired"}
        
        v_key = generate_key(code)
        real_key = decrypt(voucher['key_blob'], v_key)
        master_key = real_key.encode()
        
        # Load accounts with master key
        dr = requests.get(f"{FIREBASE_URL}data_blob.json").json()
        accounts = json.loads(decrypt(dr, master_key))
        
        return {
            "success": True,
            "accounts": accounts,
            "master_key": real_key,
            "role": "GUEST"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def setup_admin(password):
    """Setup new admin"""
    try:
        real_key = Fernet.generate_key().decode()
        admin_key = generate_key(password)
        
        payload = {
            "admin_blob": encrypt(real_key, admin_key),
            "data_blob": encrypt("{}", real_key.encode()),
            "vouchers": {}
        }
        
        requests.put(f"{FIREBASE_URL}.json", json=payload)
        
        return {
            "success": True,
            "master_key": real_key,
            "role": "ADMIN"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_accounts(master_key, accounts):
    """Save accounts to Firebase"""
    try:
        enc = encrypt(json.dumps(accounts), master_key.encode())
        requests.put(f"{FIREBASE_URL}data_blob.json", json=enc)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_voucher(master_key, days):
    """Create a guest voucher"""
    try:
        import random
        import string
        from datetime import datetime, timedelta
        
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        exp = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        v_key = generate_key(code)
        blob = encrypt(master_key, v_key)
        
        requests.put(f"{FIREBASE_URL}vouchers/{code}.json", json={"expiry": exp, "key_blob": blob})
        
        return {"success": True, "code": code, "expiry": exp}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='ValTools Steam Guard Backend')
    parser.add_argument('--action', required=True, 
                        choices=['login-admin', 'login-guest', 'setup-admin', 'save-accounts', 'create-voucher'],
                        help='Action to perform')
    parser.add_argument('--password', type=str, help='Admin password')
    parser.add_argument('--code', type=str, help='Voucher code')
    parser.add_argument('--master-key', type=str, help='Master key for save')
    parser.add_argument('--accounts', type=str, help='Accounts JSON for save')
    parser.add_argument('--days', type=int, default=7, help='Voucher days')
    
    args = parser.parse_args()
    
    if args.action == 'login-admin':
        result = login_admin(args.password)
    elif args.action == 'login-guest':
        result = login_guest(args.code.upper())
    elif args.action == 'setup-admin':
        result = setup_admin(args.password)
    elif args.action == 'save-accounts':
        accounts = json.loads(args.accounts)
        result = save_accounts(args.master_key, accounts)
    elif args.action == 'create-voucher':
        result = create_voucher(args.master_key, args.days)
    else:
        result = {"error": "Invalid action"}
    
    print(json.dumps(result))

if __name__ == '__main__':
    main()
