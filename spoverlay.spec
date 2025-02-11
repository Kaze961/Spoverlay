# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['spoverlay.py'],
    pathex=['C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay'],
    binaries=[],
datas=[
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/config.json', '.'),
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/placeholder.png', '.'),
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/prev_icon.png', '.'),
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/play_icon.png', '.'),
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/pause_icon.png', '.'),
    ('C:/Users/Marcel/Desktop/Spoverlay-main/spoverlay/next_icon.png', '.')
],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'pynput',
        'spotipy',
        'flask'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='spoverlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='spoverlay'
)