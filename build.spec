# PyInstaller spec for the Vocal Remover app.
# Build with: ./venv/Scripts/pyinstaller.exe build.spec --noconfirm
#
# Onedir build (a folder, not a single exe): a onefile build re-extracts its entire
# payload to a fresh %TEMP% dir on every launch, which was taking ~30-60s+ with
# TensorFlow bundled. Onedir runs directly from an already-unpacked folder instead --
# see CLAUDE.md. Distribute it via installer.iss, not the raw folder.
#
# Pretrained models are NOT bundled here -- spleeter downloads each one automatically
# the first time its mode is used (see common.default_model_path() /
# worker_main._model_is_cached()), which keeps this build small. ffmpeg/ffprobe stay
# bundled since spleeter can't fetch those itself.
#
# The same exe is re-invoked as a one-shot worker subprocess (--worker-job <path>,
# see app/core/separation_controller.py) because spleeter's Separator can only be
# constructed once per OS process -- see CLAUDE.md.

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

app_dir = os.path.join(os.getcwd(), "app")

datas = []
datas += collect_data_files("spleeter")

# Bundled ffmpeg/ffprobe binaries (spleeter shells out to both).
for exe_name in ("ffmpeg.exe", "ffprobe.exe"):
    datas.append((os.path.join(app_dir, "ffmpeg", exe_name), "ffmpeg"))

a = Analysis(
    [os.path.join(app_dir, "main.py")],
    pathex=[app_dir],
    binaries=[],
    datas=datas,
    # spleeter picks its model-function module (unet, blstm, ...) via a dynamic
    # string-based import keyed off each model's JSON config -- PyInstaller's
    # static analysis can't see that, so the submodules must be listed explicitly.
    hiddenimports=collect_submodules("spleeter.model.functions"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="VocalRemover",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VocalRemover",
)
