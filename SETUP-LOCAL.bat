@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "VENV=%ROOT%\.venv"

if not exist "%VENV%\Scripts\python.exe" (
  echo [INFO] Creation de l'environnement virtuel local...
  py -3 -m venv "%VENV%" || exit /b 1
)

echo [INFO] Mise a jour de pip...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip || exit /b 1

echo [INFO] Installation des dependances runtime...
"%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%\requirements.txt" || exit /b 1

echo [INFO] Installation des dependances dev...
"%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%\requirements-dev.txt" || exit /b 1

echo.
echo [OK] Environnement local pret.
echo      Python : "%VENV%\Scripts\python.exe"
echo      Pour verifier le repo : "%ROOT%\CHECK-LOCAL.bat"
echo.
