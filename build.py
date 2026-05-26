"""Cross-platform PyInstaller build script.

Uses os.pathsep so --add-data works on both Unix (':') and Windows (';')
without shell-level escaping differences.
"""
import os

import PyInstaller.__main__

SEP = os.pathsep

PyInstaller.__main__.run([
    "--onefile",
    "--name", "fic-guard",
    "--collect-all", "rich",
    "--collect-all", "flask",
    "--collect-all", "flask_wtf",
    "--collect-all", "wtforms",
    "--collect-all", "waitress",
    f"--add-data=src/fic_guard/web/templates{SEP}fic_guard/web/templates",
    "fic_guard_entry.py",
])
