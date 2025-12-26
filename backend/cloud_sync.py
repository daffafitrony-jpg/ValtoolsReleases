#!/usr/bin/env python
"""
ValTools Cloud Sync Backend
Handles Fernet decryption for cloud data sync
Called from Electron via subprocess
"""

import json
import sys
import argparse
import requests

try:
    from cryptography.fernet import Fernet
except ImportError:
    print(json.dumps({"error": "cryptography library required"}))
    sys.exit(1)

# Configuration (same as original)
API_KEY = "$2a$10$rogV/OBNjQ8GYVjQbuRiRu02pxTYppJ2QF4PxFEUJzGo8il9XRyYG"
BIN_ID = "69208b43d0ea881f40f70c06"
STATIC_KEY = b'LDfE_w9DvToSg8P1QOk50_h-DqrtDKjJBbm2zmOl42Y='

def load_cloud_data():
    """Load and decrypt cloud data"""
    try:
        cipher = Fernet(STATIC_KEY)
        headers = {"X-Master-Key": API_KEY}
        
        response = requests.get(f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest", headers=headers)
        
        if response.status_code == 200:
            data = response.json().get("record", {})
            
            if "payload" in data and data["payload"]:
                decrypted = cipher.decrypt(data["payload"].encode()).decode()
                full = json.loads(decrypted)
                
                result = {
                    "success": True,
                    "accounts": full.get("accounts", {}),
                    "admin_hash": full.get("admin_hash", "")
                }
                print(json.dumps(result))
                return
        
        print(json.dumps({"success": False, "error": "Failed to load data"}))
        
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

def save_cloud_data(admin_hash, accounts):
    """Encrypt and save cloud data"""
    try:
        cipher = Fernet(STATIC_KEY)
        payload = cipher.encrypt(json.dumps({
            "admin_hash": admin_hash,
            "accounts": accounts
        }).encode()).decode()
        
        headers = {
            "Content-Type": "application/json",
            "X-Master-Key": API_KEY
        }
        
        response = requests.put(
            f"https://api.jsonbin.io/v3/b/{BIN_ID}",
            json={"payload": payload},
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            print(json.dumps({"success": True}))
        else:
            print(json.dumps({"success": False, "error": f"HTTP {response.status_code}"}))
            
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

def main():
    parser = argparse.ArgumentParser(description='ValTools Cloud Sync Backend')
    parser.add_argument('--load', action='store_true', help='Load cloud data')
    parser.add_argument('--save', action='store_true', help='Save cloud data')
    parser.add_argument('--save-file', type=str, help='Path to JSON file with data to save')
    parser.add_argument('--admin-hash', type=str, help='Admin hash for save')
    parser.add_argument('--accounts', type=str, help='Accounts JSON for save')
    
    args = parser.parse_args()
    
    if args.load:
        load_cloud_data()
    elif args.save_file:
        # Read from file (recommended for large data)
        try:
            with open(args.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            save_cloud_data(data.get('admin_hash', ''), data.get('accounts', {}))
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Failed to read file: {str(e)}"}))
            sys.exit(1)
    elif args.save and args.admin_hash and args.accounts:
        accounts = json.loads(args.accounts)
        save_cloud_data(args.admin_hash, accounts)
    else:
        print(json.dumps({"error": "Invalid arguments"}))
        sys.exit(1)

if __name__ == '__main__':
    main()
