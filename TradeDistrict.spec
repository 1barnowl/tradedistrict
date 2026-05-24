# -*- mode: python ; coding: utf-8 -*-
"""
TradeDistrict.spec — drop this into ~/Desktop/tradedistrict/tradedistrict/ and run:
    source venv/bin/activate
    pyinstaller TradeDistrict.spec
The binary will appear at dist/TradeDistrict (Linux) or dist/TradeDistrict.exe (Windows)
"""
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Collect all packages fully ───────────────────────────────────────────────
webview_datas,   webview_binaries,   webview_hidden   = collect_all('webview')
pyqt5_datas,     pyqt5_binaries,     pyqt5_hidden     = collect_all('PyQt5')
pyqtwe_datas,    pyqtwe_binaries,    pyqtwe_hidden    = collect_all('PyQtWebEngine')
flask_datas,     flask_binaries,     flask_hidden     = collect_all('flask')
werkzeug_datas,  werkzeug_binaries,  werkzeug_hidden  = collect_all('werkzeug')
jinja2_datas,    jinja2_binaries,    jinja2_hidden    = collect_all('jinja2')

all_datas = (
    webview_datas
    + pyqt5_datas
    + pyqtwe_datas
    + flask_datas
    + werkzeug_datas
    + jinja2_datas
)

all_binaries = (
    webview_binaries
    + pyqt5_binaries
    + pyqtwe_binaries
    + flask_binaries
    + werkzeug_binaries
    + jinja2_binaries
)

all_hidden = (
    webview_hidden
    + pyqt5_hidden
    + pyqtwe_hidden
    + flask_hidden
    + werkzeug_hidden
    + jinja2_hidden
    + collect_submodules('webview')
    + collect_submodules('PyQt5')
    + collect_submodules('PyQtWebEngine')
    + collect_submodules('flask')
    + collect_submodules('werkzeug')
    + collect_submodules('flask_cors')
    + collect_submodules('apscheduler')
    + collect_submodules('bs4')
    + collect_submodules('lxml')
    + collect_submodules('requests')
    + collect_submodules('dateutil')
    + [
        'webview.platforms.qt',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtNetwork',
        'PyQtWebEngine',
        'flask',
        'flask_cors',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'werkzeug.middleware.shared_data',
        'jinja2',
        'jinja2.ext',
        'click',
        'itsdangerous',
        'blinker',
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.background',
        'apscheduler.executors',
        'apscheduler.executors.pool',
        'apscheduler.jobstores',
        'apscheduler.jobstores.memory',
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml.html',
        'requests',
        'urllib3',
        'urllib3.util',
        'certifi',
        'charset_normalizer',
        'idna',
        'dateutil',
        'dateutil.parser',
        'dateutil.tz',
        'sqlite3',
        'json',
        'threading',
        'logging',
    ]
)

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=[
        ('templates',    'templates'),
        ('static',       'static'),
        ('intelligence', 'intelligence'),
        ('scrapers',     'scrapers'),
    ] + all_datas,
    hiddenimports=all_hidden,
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
    a.binaries,
    a.datas,
    [],
    name='TradeDistrict',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # keep True so you can see errors; set False once working
    onefile=True,
)
