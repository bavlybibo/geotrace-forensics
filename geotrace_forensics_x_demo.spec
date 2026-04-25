# -*- mode: python ; coding: utf-8 -*-
"""Demo PyInstaller spec for GeoTrace Forensics X.

This build includes demo_evidence for classroom walkthroughs and recordings.
Do not use this spec for public production releases.
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules('PIL')
    + collect_submodules('reportlab')
    + collect_submodules('folium')
    + collect_submodules('matplotlib')
    + collect_submodules('pytesseract')
    + collect_submodules('pillow_heif')
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('data', 'data'), ('demo_evidence', 'demo_evidence')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeoTraceForensicsX-Demo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeoTraceForensicsX-Demo',
)
