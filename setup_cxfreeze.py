import sys
from pathlib import Path
from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parent

build_exe_options = {
    "packages": ["PyQt5", "PyQt5.QtWebEngineWidgets", "PIL"],
    "include_files": [
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "manual_studio.ajuda"), "manual_studio.ajuda"),
    ],
    "excludes": ["tkinter", "unittest"],
    "include_msvcr": True,
    "optimize": 1,
}

base = "Win32GUI" if sys.platform == "win32" else None

executables = [
    Executable(
        str(ROOT / "main.py"),
        base=base,
        target_name="ManualStudioQt5.exe",
        icon=str(ROOT / "assets" / "manual_studio.ico"),
    )
]

setup(
    name="ManualStudioQt5",
    version="1.0.0",
    description="Editor e publicador de manuais técnicos em PyQt5",
    options={"build_exe": build_exe_options},
    executables=executables,
)
