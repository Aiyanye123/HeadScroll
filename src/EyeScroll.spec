# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs
import os
import sys

_spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

datas = [
    (os.path.join(_spec_dir, '..', 'config', 'default_config.json'), 'config'),
    (os.path.join(_spec_dir, '..', 'assets', 'models', 'face_landmarker.task'), 'assets/models'),
    (os.path.join(_spec_dir, '..', 'assets', 'models', 'vosk-model-small-cn-0.22'),
     'assets/models/vosk-model-small-cn-0.22'),
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
        'pandas',
        'scipy',
        'sklearn',
        # Optional notebook, TLS, and Qt modules pulled in by dependency
        # hooks. HeadScroll uses local models and Qt Core/Gui/Widgets only.
        'IPython',
        'jedi',
        'traitlets',
        'cryptography',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtNetwork',
    ],
    noarchive=False,
    optimize=0,
)

# Some third-party hooks add native binaries and package data even when their
# Python modules are excluded above. Remove only trees and Qt libraries that
# HeadScroll never imports; keep camera, MediaPipe, Vosk, and widget runtime data.
unused_prefixes = (
    'cryptography\\',
    'IPython\\',
    'jedi\\',
    'traitlets\\',
    'PySide6\\Qt6Pdf',
    'PySide6\\Qt6Qml',
    'PySide6\\Qt6Quick',
    'PySide6\\Qt6Network',
    'PySide6\\opengl32sw.dll',
    'PySide6\\plugins\\tls\\',
)
a.binaries = [item for item in a.binaries if not item[0].startswith(unused_prefixes)]
a.datas = [item for item in a.datas if not item[0].startswith(unused_prefixes)]
# Qt6Widgets does not need ICU DLLs discovered from another application's PATH.
a.binaries = [
    item for item in a.binaries
    if not os.path.basename(item[0]).casefold().startswith('icu')
]
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
