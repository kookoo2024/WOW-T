# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['keyboard', 'pynput', 'pynput.keyboard', 'pynput.mouse', 'customtkinter', 'darkdetect', 'cv2', 'numpy', 'PIL', 'PIL._tkinter_finder', 'pyautogui']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt6', 'PySide2', 'PySide6', 'tkinter.test', 'unittest', 'test', 'tests', 'pytest', 'IPython', 'jupyter', 'notebook', 'sphinx', 'docutils', 'pydoc', 'xmlrpc', 'multiprocessing', 'concurrent', 'asyncio', 'sqlite3', 'curses', 'dbm', 'gettext', 'shelve', 'tabnanny', 'turtle', 'venv', 'zoneinfo', 'pydoc_data', 'distutils', 'lib2to3', 'py_compile', 'compileall', 'zipimport', 'importlib.metadata', 'importlib.resources', 'cv2.gapi', 'cv2.utils', 'matplotlib', 'scipy', 'pandas', 'sympy', 'networkx', 'sklearn', 'PIL.SpiderImagePlugin', 'PIL.SgiImagePlugin', 'PIL.FpxImagePlugin', 'PIL.MicImagePlugin', 'PIL.MpoImagePlugin', 'PIL.FitsImagePlugin', 'PIL.DcxImagePlugin', 'PIL.EpsImagePlugin', 'PIL.IcnsImagePlugin', 'PIL.ImImagePlugin', 'PIL.ImtImagePlugin', 'PIL.IptcImagePlugin', 'PIL.Jpeg2KImagePlugin', 'PIL.McIdasImagePlugin', 'PIL.PcdImagePlugin', 'PIL.PcxImagePlugin', 'PIL.PdfImagePlugin', 'PIL.PixarImagePlugin', 'PIL.PsdImagePlugin', 'PIL.SunImagePlugin', 'PIL.TgaImagePlugin', 'PIL.WalImageFile', 'PIL.WebPImagePlugin', 'PIL.WmfImagePlugin', 'PIL.XVThumbImagePlugin', 'PIL.XbmImagePlugin', 'PIL.XpmImagePlugin'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='WOW技能助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
