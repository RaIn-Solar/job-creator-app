@echo off
REM ============================================================
REM  Build Solbiz Desktop (run this once on a Windows PC that
REM  has Python installed -- the same Python you use to run the
REM  app with "python app.py").
REM
REM  Just double-click this file. When it finishes, the app is
REM  in the  dist\Solbiz  folder -- zip that folder and send it
REM  to your team.
REM ============================================================
setlocal

REM Move to the repository root (this script lives in \desktop).
cd /d "%~dp0.."

echo.
echo [1/3] Checking Python...
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
%PY% --version || (
  echo.
  echo Could not find Python. Install it from https://www.python.org/downloads/
  echo ^(check "Add Python to PATH" during install^), then run this again.
  pause
  exit /b 1
)

echo.
echo [2/3] Installing the packaging tools ^(one-time, needs internet^)...
%PY% -m pip install --upgrade pip
%PY% -m pip install --upgrade pyinstaller flask
if errorlevel 1 (
  echo.
  echo Something went wrong installing the tools. Check your internet
  echo connection and try again.
  pause
  exit /b 1
)

echo.
echo [3/3] Building Solbiz.exe ^(this takes a few minutes^)...
%PY% -m PyInstaller --noconfirm --clean desktop\solbiz.spec
if errorlevel 1 (
  echo.
  echo The build failed. Copy the red text above and send it to Claude.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  DONE!  Your app is here:   dist\Solbiz\
echo.
echo  Next: right-click the  dist\Solbiz  folder, choose
echo  "Send to -^> Compressed (zipped) folder", and share that
echo  zip with your team. See desktop\README-DESKTOP.md.
echo ============================================================
echo.
pause
