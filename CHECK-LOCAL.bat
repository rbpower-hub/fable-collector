@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%PY%" (
  echo [ERREUR] Environnement local absent.
  echo          Lancer d'abord "%ROOT%\SETUP-LOCAL.bat"
  exit /b 1
)

pushd "%ROOT%" >nul

echo [INFO] Preflight...
"%PY%" -m fable.preflight || goto :fail

echo [INFO] Ruff...
"%PY%" -m ruff check . || goto :fail

echo [INFO] Pytest...
"%PY%" -m pytest -q || goto :fail

popd >nul
echo.
echo [OK] Verification locale terminee.
exit /b 0

:fail
set "RC=%ERRORLEVEL%"
popd >nul
echo.
echo [ERREUR] Verification locale echouee. Code=%RC%
exit /b %RC%
