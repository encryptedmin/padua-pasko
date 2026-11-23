@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PORT=8000"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto :venv_ready

echo Setting up the local Python environment...
where py >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py"
    set "PY_ARGS=-3.14"
) else (
    where python >nul 2>&1
    if errorlevel 1 goto :no_python
    set "PY_CMD=python"
    set "PY_ARGS="
)

%PY_CMD% %PY_ARGS% -m venv "%~dp0.venv"
if errorlevel 1 goto :venv_failed

:venv_ready
set "PYTHON=%VENV_PY%"

"%PYTHON%" -c "import django, cryptography" >nul 2>&1
if errorlevel 1 (
    echo Installing Bunutan Python requirements...
    "%PYTHON%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 goto :install_failed
)

set "DJANGO_DEBUG=True"
set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1"

echo.
echo Preparing the Bunutan database...
"%PYTHON%" manage.py makemigrations --noinput
if errorlevel 1 goto :migration_failed

"%PYTHON%" manage.py migrate --noinput
if errorlevel 1 goto :migration_failed

"%PYTHON%" manage.py check
if errorlevel 1 goto :check_failed

echo.
echo Bunutan is ready for local testing.
echo Main page:       http://127.0.0.1:%PORT%/
echo Organizer login: http://127.0.0.1:%PORT%/manage/login/
echo This is Django's local development server. Do not use this launcher for deployment.
echo Press Ctrl+C in this window to stop the server.
echo.

"%PYTHON%" manage.py runserver 127.0.0.1:%PORT%
if errorlevel 1 (
    echo.
    echo The server stopped with an error. Check whether port %PORT% is already in use.
    pause
    exit /b 1
)
exit /b 0

:no_python
echo Python 3.14 was not found. Install Python 3.14 and make sure the py launcher or python command is available.
pause
exit /b 1

:venv_failed
echo Could not create the .venv environment.
pause
exit /b 1

:install_failed
echo Dependency installation failed. Check your internet connection and requirements.txt, then run this file again.
pause
exit /b 1

:migration_failed
echo Database migration failed. Review the error above before starting Bunutan.
pause
exit /b 1

:check_failed
echo Django reported a configuration error. Review the error above before starting Bunutan.
pause
exit /b 1
