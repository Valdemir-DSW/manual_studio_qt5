@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo =============================================
echo Manual Studio Qt5 - cx_Freeze + Inno Setup
echo =============================================

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE (
  where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo ERRO: Python nao foi encontrado no PATH.
  pause
  exit /b 1
)

echo [1/4] Instalando dependencias de build...
%PYEXE% -m pip install -r requirements.txt
if errorlevel 1 goto :fail
%PYEXE% -m pip install "cx_Freeze>=7.2,<9"
if errorlevel 1 goto :fail

echo [2/4] Gerando executavel com cx_Freeze...
if exist "build\ManualStudio" rmdir /s /q "build\ManualStudio"
%PYEXE% setup_cxfreeze.py build_exe --build-exe "build\ManualStudio"
if errorlevel 1 goto :fail
if not exist "build\ManualStudio\ManualStudioQt5.exe" (
  echo ERRO: cx_Freeze terminou sem gerar ManualStudioQt5.exe.
  goto :fail
)

echo [3/4] Procurando o compilador do Inno Setup...
set "ISCC="
for %%I in (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  "%ProgramFiles%\Inno Setup 6\ISCC.exe"
  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
  "%LOCALAPPDATA%\Inno Setup 6\ISCC.exe"
) do (
  if not defined ISCC if exist "%%~I" set "ISCC=%%~I"
)

if not defined ISCC (
  for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
)

if not defined ISCC call :registry_inno "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
if not defined ISCC call :registry_inno "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
if not defined ISCC call :registry_inno "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"

if not defined ISCC (
  echo.
  echo Inno Setup 6 nao foi encontrado.
  echo O executavel portatil foi criado em: build\ManualStudio
  echo Instale o Inno Setup 6 e execute este BAT novamente para gerar o instalador.
  pause
  exit /b 2
)

echo Encontrado: %ISCC%
echo [4/4] Compilando instalador...
if not exist dist mkdir dist
"%ISCC%" "installer\manual_studio.iss"
if errorlevel 1 goto :fail

echo.
echo SUCESSO.
echo Aplicacao: build\ManualStudio\ManualStudioQt5.exe
echo Instalador: dist\ManualStudioQt5_Setup.exe
pause
exit /b 0

:registry_inno
set "REGKEY=%~1"
set "INNODIR="
for /f "tokens=2,*" %%A in ('reg query "%REGKEY%" /v InstallLocation 2^>nul ^| find /i "InstallLocation"') do set "INNODIR=%%B"
if defined INNODIR if exist "%INNODIR%\ISCC.exe" set "ISCC=%INNODIR%\ISCC.exe"
exit /b 0

:fail
echo.
echo FALHA na compilacao. Verifique as mensagens acima.
pause
exit /b 1
