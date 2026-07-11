# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs

datas = [
    ('../config', 'config'),
    ('../assets/models/face_landmarker.task', 'assets/models'),
    ('../assets/models/vosk-model-small-cn-0.22', 'assets/models/vosk-model-small-cn-0.22'),
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
    'vosk',
    'sounddevice',
]
binaries += collect_dynamic_libs('mediapipe')
binaries += collect_dynamic_libs('vosk')


import os
import sys

_spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HeadScroll',
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
    name='HeadScroll',
)
