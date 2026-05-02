# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
project = Path.cwd()

a = Analysis(
    ['main.py'],
    pathex=[str(project)],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('data', 'data'),
        ('docs', 'docs'),
        ('README.md', '.'),
        ('LICENSE', '.'),
        ('PRIVACY.md', '.'),
        ('SECURITY.md', '.'),
        ('DISCLAIMER.md', '.'),
    ],
    hiddenimports=['matplotlib.backends.backend_agg', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['demo_evidence', 'tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeoTraceForensicsX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeoTraceForensicsX',
)
