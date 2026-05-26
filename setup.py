from setuptools import setup
import os
import shutil

APP = ['mac_main.py']

# Setup standard data files
DATA_FILES = [
    ('', ['assets.py', '.env', 'static/AppIcon.icns']),
]

def add_directory(dest_root, source_root):
    for root, dirs, files in os.walk(source_root):
        # Skip pyc and hidden files
        if '__pycache__' in root:
            continue
        dest_dir = os.path.join(dest_root, os.path.relpath(root, source_root))
        if dest_dir.endswith('.'):
            dest_dir = dest_dir[:-1]
        file_list = [os.path.join(root, f) for f in files if not f.startswith('.') and not f.endswith('.pyc')]
        if file_list:
            DATA_FILES.append((dest_dir, file_list))

add_directory('templates', 'templates')
add_directory('static', 'static')

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'static/AppIcon.icns',
    'packages': [
        'flask', 'webview', 'cloudscraper', 'requests', 'bs4',
        'charset_normalizer',
        'discord_webhook', 'gspread', 'discogs_client',
        'requests_oauthlib', 'services', 'services.clients', 'services.logic', 'services.utils', 'services.models', 'server',
        'objc', 'AppKit', 'Foundation', 'WebKit'
    ],
    'includes': ['jinja2.ext'],
    'plist': {
        'CFBundleName': 'Discogs Toolkit',
        'CFBundleDisplayName': 'Discogs Toolkit',
        'CFBundleIdentifier': 'com.discogstoolkit.app',
        'LSMinimumSystemVersion': '14.0', # Target Sequoia compatibility
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

# After build, move to dist/macos
if os.path.exists('dist/Discogs Toolkit.app'):
    os.makedirs('dist/macos', exist_ok=True)
    # Clean old build in target
    if os.path.exists('dist/macos/Discogs Toolkit.app'):
        shutil.rmtree('dist/macos/Discogs Toolkit.app')
    shutil.move('dist/Discogs Toolkit.app', 'dist/macos/Discogs Toolkit.app')
    print("\n--- Build Complete ---")
    print("App is located at: dist/macos/Discogs Toolkit.app")
