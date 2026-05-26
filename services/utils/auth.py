import os
import sys
import json
import subprocess

SERVICE_NAME = "com.discogstoolkit.app.auth"
ACCOUNT_NAME = "DiscogsToolkit"

def save_to_keychain(username, access_token, access_secret, avatar_url):
    """Saves auth data to macOS Keychain using the security CLI."""
    if sys.platform != 'darwin':
        return False
    
    try:
        payload = json.dumps({
            'access_token': access_token,
            'access_secret': access_secret,
            'username': username,
            'avatar_url': avatar_url
        })
        
        # -a: account name
        # -s: service name
        # -w: password data (our JSON payload)
        # -U: update if already exists
        subprocess.run([
            'security', 'add-generic-password', 
            '-a', ACCOUNT_NAME, 
            '-s', SERVICE_NAME, 
            '-w', payload, 
            '-U'
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Keychain save error: {e}")
        return False

def get_from_keychain():
    """Retrieves auth data from macOS Keychain."""
    if sys.platform != 'darwin':
        return None
    
    try:
        result = subprocess.run([
            'security', 'find-generic-password', 
            '-a', ACCOUNT_NAME, 
            '-s', SERVICE_NAME, 
            '-w'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout.strip())
    except Exception as e:
        # Silently fail if not found or error
        pass
    return None

def delete_from_keychain():
    """Deletes auth data from macOS Keychain."""
    if sys.platform != 'darwin':
        return False
    
    try:
        subprocess.run([
            'security', 'delete-generic-password', 
            '-a', ACCOUNT_NAME, 
            '-s', SERVICE_NAME
        ], capture_output=True)
        return True
    except Exception:
        pass
    return False

def is_macos_dist():
    """Returns True if running as a frozen macOS app."""
    return sys.platform == 'darwin' and getattr(sys, 'frozen', False)
