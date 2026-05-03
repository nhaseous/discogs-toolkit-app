import os
import sys
import threading
import time
import webview

# Set the callback URL for Discogs OAuth to match our local port
os.environ['DISCOGS_CALLBACK_URL'] = 'http://127.0.0.1:8888/callback'

from main import app

def start_flask():
    # Use a less common port to avoid collisions
    app.run(host='127.0.0.1', port=8888, debug=False, threaded=True)

if __name__ == '__main__':
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()
    
    # Wait for Flask to start
    time.sleep(1.5)
    
    webview.create_window(
        'Discogs Toolkit', 
        'http://127.0.0.1:8888', 
        width=1280, 
        height=850,
        min_size=(1000, 700)
    )
    webview.start()
