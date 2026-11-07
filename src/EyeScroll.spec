# -*- mode: python ; coding: utf-8 -*-
import os
import sys

_spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

datas = [
    (os.path.join(_spec_dir, "..", "config", "default_config.json"), "config"),
    (os.path.join(_spec_dir, "..", "assets", "models", "face_landmarker.task"), "assets/models"),
]
binaries = []
hiddenimports = [
    'mediapipe',
    'mediapipe.tasks',
    'mediapipe.tasks.python',
    'mediapipe.tasks.python.core',
    'mediapipe.tasks.python.vision',
    'mediapipe.tasks.python.vision.core',
    'mediapipe.tasks.python.vision.face_landmarker',
]
binaries += collect_dynamic_libs('mediapipe')
hiddenimports += collect_submodules('mediapipe.tasks')

a = Analysis(
    [os.path.join(_spec_dir, 'main.py')],
    pathex=[_spec_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchaudio',
        'torchvision',
        'matplotlib',
        'pandas',
        'scipy',
        'sklearn',
    ],
    noarchive=False,
    optimize=0,
)
# Do not bundle unrelated ICU DLLs resolved from another application's PATH.
a.binaries = [
    binary for binary in a.binaries
    if not os.path.basename(binary[0]).casefold().startswith("icu")
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EyeScroll',
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
    icon=['..\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EyeScroll',
)
