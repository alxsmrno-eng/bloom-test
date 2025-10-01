@echo off
setlocal ENABLEDELAYEDEXPANSION

if not exist .venv\Scripts\activate.bat (
    echo [KayListener] Debes crear el entorno virtual (.venv) antes de compilar.
    exit /b 1
)

call .venv\Scripts\activate.bat
set ICON_PATH=app\assets\icon.ico
set ICON_ARG=
if exist %ICON_PATH% (
    set ICON_ARG=--icon %ICON_PATH%
) else (
    echo [KayListener] Icono no encontrado, compilando sin icono personalizado.
)
pyinstaller --noconfirm --clean --name KayListener %ICON_ARG% kaylistener.spec
if errorlevel 1 (
    echo [KayListener] Error al ejecutar PyInstaller.
    exit /b 1
)

echo [KayListener] Build completado. Ejecutable en dist\KayListener\KayListener.exe
