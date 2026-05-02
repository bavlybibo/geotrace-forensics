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
        ('demo_evidence', 'demo_evidence'),
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
    excludes=['tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GeoTraceForensicsXDemo', debug=False, console=False)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name='GeoTraceForensicsXDemo')
