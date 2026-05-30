"""Cross-platform PyInstaller build script.

Uses os.pathsep so --add-data works on both Unix (':') and Windows (';')
without shell-level escaping differences.
"""
import argparse
import os
import sys

import PyInstaller.__main__

parser = argparse.ArgumentParser()
parser.add_argument('--arch', default=None)
parser.add_argument('--universal', action='store_true')
args, _ = parser.parse_known_args()

SEP = os.pathsep

pyinstaller_args = [
    "--onefile",
    "--name", "fic-guard",
    "--collect-all", "rich",
    "--collect-all", "flask",
    "--collect-all", "flask_wtf",
    "--collect-all", "wtforms",
    "--collect-all", "waitress",
    f"--add-data=src/fic_guard/web/templates{SEP}fic_guard/web/templates",
    f"--add-data=src/fic_guard/data{SEP}fic_guard/data",
    "fic_guard_entry.py",
]

if sys.platform == "win32":
    pyinstaller_args.append("--windowed")
elif sys.platform == "darwin" and args.universal:
    pyinstaller_args.append("--windowed")

if args.arch:
    pyinstaller_args.append(f'--target-arch={args.arch}')
if args.universal:
    pyinstaller_args.append('--target-arch=universal2')

PyInstaller.__main__.run(pyinstaller_args)
