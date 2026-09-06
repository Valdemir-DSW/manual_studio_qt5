@echo off
setlocal
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name ManualStudioQt5 --icon "assets\manual_studio.ico" --add-data "manual_studio.ajuda;." --add-data "assets;assets" --hidden-import PyQt5.QtWebEngineWidgets --hidden-import PyQt5.QtWebEngineCore main.py
if errorlevel 1 (
  echo.
  echo Falha na compilacao.
  pause
  exit /b 1
)
echo.
echo Gerado: dist\ManualStudioQt5.exe
echo Icone integrado ao executavel e a janela do aplicativo.
pause
