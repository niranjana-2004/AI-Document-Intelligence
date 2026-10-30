@echo off
setlocal EnableDelayedExpansion

title Cognidocs System Launcher
cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"

:: Ensure logs directory exists
if not exist "%PROJECT_ROOT%logs" (
    mkdir "%PROJECT_ROOT%logs" >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: Duplicate launcher instance lock
:: -----------------------------------------------------------------------------
set "LOCK_DIR=%PROJECT_ROOT%logs\.launcher.lock"
mkdir "%LOCK_DIR%" 2>nul
if %errorlevel% equ 0 goto :lock_acquired

:: Lock exists - check if stale (> 2 minutes)
powershell.exe -NoProfile -Command "param($p) if (Test-Path $p) { if (((Get-Date) - (Get-Item $p).LastWriteTime).TotalMinutes -gt 2) { Remove-Item $p -Force -Recurse -EA SilentlyContinue; exit 0 } } exit 1" -args "%LOCK_DIR%" >nul 2>&1
if %errorlevel% equ 0 (
    mkdir "%LOCK_DIR%" 2>nul
    goto :lock_acquired
)

echo [INFO] Another instance of Start-Cognidocs.bat is currently running.
echo        Please wait a moment for it to complete.
ping 127.0.0.1 -n 3 >nul
exit /b 0

:lock_acquired

echo ===================================================
echo             Cognidocs System Launcher              
echo ===================================================
echo Project Root : %PROJECT_ROOT%
echo Logs         : %PROJECT_ROOT%logs\
echo.
echo [COGNIDOCS] Initializing system services...
echo.

:: -----------------------------------------------------------------------------
:: Step 0: Check essential system prerequisites
:: -----------------------------------------------------------------------------
where.exe curl.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo ===================================================
    echo   [ERROR] curl.exe was not found in system PATH.
    echo ===================================================
    echo Windows 10/11 includes curl by default in C:\Windows\System32.
    echo Please ensure curl is accessible in your PATH.
    echo.
    goto :handle_exit_error
)

where.exe powershell.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo ===================================================
    echo   [ERROR] powershell.exe was not found in system PATH.
    echo ===================================================
    echo PowerShell is required to run background services.
    echo.
    goto :handle_exit_error
)

if not exist "%PROJECT_ROOT%scripts\run-hidden.ps1" (
    echo ===================================================
    echo   [ERROR] Helper script not found at:
    echo           %PROJECT_ROOT%scripts\run-hidden.ps1
    echo ===================================================
    echo.
    goto :handle_exit_error
)

:: -----------------------------------------------------------------------------
:: Step 1: Check & Start Ollama (http://127.0.0.1:11434) [1/4]
:: -----------------------------------------------------------------------------
echo [1/4] Checking Ollama service (http://127.0.0.1:11434)...
set "OLLAMA_ALREADY_RUNNING=0"
set "OLLAMA_READY=0"

curl.exe -s --connect-timeout 1 http://127.0.0.1:11434/ >nul 2>&1
if %errorlevel% equ 0 (
    set "OLLAMA_ALREADY_RUNNING=1"
    set "OLLAMA_READY=1"
    goto :ollama_check_model
)

where.exe ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARNING] 'ollama' executable was not found in system PATH.
    echo             Ollama cannot be started automatically.
    echo             Cognidocs will use extractive fallback for document summaries.
    echo             To enable full local LLM intelligence, install from https://ollama.com
    goto :ollama_done
)

echo   [STARTING] Launching Ollama service in the background...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command "ollama serve" -WorkingDirectory "%PROJECT_ROOT%." -LogFile "%PROJECT_ROOT%logs\ollama.log"

:: Poll Ollama until responsive
<nul set /p="  Waiting for Ollama to respond"
for /L %%i in (1,1,25) do (
    curl.exe -s --connect-timeout 0.5 http://127.0.0.1:11434/ >nul 2>&1
    if not errorlevel 1 (
        set "OLLAMA_READY=1"
        goto :ollama_poll_success
    )
    <nul set /p=.
    ping 127.0.0.1 -n 1 -w 500 >nul 2>&1
)
echo.
echo   [WARNING] Ollama did not respond within timeout (proceeding with fallback).
goto :ollama_done

:ollama_poll_success
echo.

:ollama_check_model
:: Verify required llama3.2 model
curl.exe -s --connect-timeout 2 http://127.0.0.1:11434/api/tags | findstr /i llama3.2 >nul 2>&1
if %errorlevel% neq 0 goto :ollama_missing_model

if %OLLAMA_ALREADY_RUNNING% equ 1 (
    echo   [OK] Ollama is already running on http://127.0.0.1:11434 [Model: llama3.2 verified].
) else (
    echo   [OK] Ollama is ready on http://127.0.0.1:11434 [Model: llama3.2 verified].
)
goto :ollama_done

:ollama_missing_model
echo   [WARNING] Ollama is active, but required model 'llama3.2' was not found.
echo             To download the model once, open a command prompt and run:
echo                 ollama pull llama3.2
echo             Until then, Ask AI will operate in fallback mode.

:ollama_done
echo.

:: -----------------------------------------------------------------------------
:: Step 2: Check & Start FastAPI Backend (http://127.0.0.1:8000) [2/4]
:: -----------------------------------------------------------------------------
echo [2/4] Checking FastAPI backend (http://127.0.0.1:8000)...
set "BACKEND_ALREADY_RUNNING=0"
set "BACKEND_READY=0"

curl.exe -s --connect-timeout 1 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] FastAPI backend is already running on http://127.0.0.1:8000.
    set "BACKEND_ALREADY_RUNNING=1"
    set "BACKEND_READY=1"
    goto :backend_done
)

if not exist "%PROJECT_ROOT%backend\.venv\Scripts\uvicorn.exe" (
    echo ===================================================
    echo   [ERROR] Python virtual environment was not found at:
    echo           %PROJECT_ROOT%backend\.venv\Scripts\uvicorn.exe
    echo ===================================================
    echo Please create and configure your virtual environment:
    echo   cd backend
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    goto :handle_exit_error
)

:: Check for foreign port conflict on port 8000
powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 10 } else { exit 0 }" >nul 2>&1
if %errorlevel% equ 10 (
    echo ===================================================
    echo   [ERROR] Port 8000 is occupied by an unresponsive process.
    echo ===================================================
    echo A process is already listening on port 8000 but does not respond to /health.
    echo Please close the application occupying port 8000 and try again.
    echo.
    goto :handle_exit_error
)

echo   [STARTING] Launching FastAPI backend in the background...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command ".venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory "%PROJECT_ROOT%backend" -LogFile "%PROJECT_ROOT%logs\backend.log"

:: Poll backend /health endpoint until responsive
<nul set /p="  Waiting for FastAPI backend to become ready"
for /L %%i in (1,1,35) do (
    curl.exe -s --connect-timeout 0.5 http://127.0.0.1:8000/health >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto :backend_poll_success
    )
    <nul set /p=.
    ping 127.0.0.1 -n 1 -w 500 >nul 2>&1
)
echo.
echo ===================================================
echo   [ERROR] FastAPI backend did not become ready.
echo ===================================================
if exist "%PROJECT_ROOT%logs\backend.log" (
    echo.
    echo --- Recent output from logs\backend.log ---
    powershell.exe -NoProfile -Command "Get-Content -Path '%PROJECT_ROOT%logs\backend.log' -Tail 15 -ErrorAction SilentlyContinue"
    echo --------------------------------------------
)
echo.
echo Please review logs\backend.log for error details.
echo.
goto :handle_exit_error

:backend_poll_success
echo.
echo   [OK] FastAPI backend is ready on http://127.0.0.1:8000.

:backend_done
echo.

:: -----------------------------------------------------------------------------
:: Step 3: Check & Start React Frontend (http://localhost:5173) [3/4]
:: -----------------------------------------------------------------------------
echo [3/4] Checking React frontend (http://localhost:5173)...
set "FRONTEND_ALREADY_RUNNING=0"
set "FRONTEND_READY=0"

curl.exe -s --connect-timeout 1 http://localhost:5173/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] React frontend is already running on http://localhost:5173.
    set "FRONTEND_ALREADY_RUNNING=1"
    set "FRONTEND_READY=1"
    goto :frontend_done
)

where.exe npm >nul 2>&1
if %errorlevel% neq 0 (
    echo ===================================================
    echo   [ERROR] 'npm' command was not found in system PATH.
    echo ===================================================
    echo Node.js is required to run the frontend.
    echo Please install Node.js from https://nodejs.org
    echo.
    goto :handle_exit_error
)

if not exist "%PROJECT_ROOT%frontend\node_modules" (
    echo ===================================================
    echo   [ERROR] frontend\node_modules was not found.
    echo ===================================================
    echo Please install frontend dependencies first:
    echo   cd frontend
    echo   npm install
    echo.
    goto :handle_exit_error
)

:: Check for foreign port conflict on port 5173
powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { exit 10 } else { exit 0 }" >nul 2>&1
if %errorlevel% equ 10 (
    echo ===================================================
    echo   [ERROR] Port 5173 is occupied by an unresponsive process.
    echo ===================================================
    echo A process is already listening on port 5173 but does not respond to HTTP.
    echo Please close the application occupying port 5173 and try again.
    echo.
    goto :handle_exit_error
)

echo   [STARTING] Launching React frontend in the background...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command "npm run dev" -WorkingDirectory "%PROJECT_ROOT%frontend" -LogFile "%PROJECT_ROOT%logs\frontend.log"

:: Poll frontend until responsive
<nul set /p="  Waiting for React frontend to become ready"
for /L %%i in (1,1,30) do (
    curl.exe -s --connect-timeout 0.5 http://localhost:5173/ >nul 2>&1
    if not errorlevel 1 (
        set "FRONTEND_READY=1"
        goto :frontend_poll_success
    )
    <nul set /p=.
    ping 127.0.0.1 -n 1 -w 500 >nul 2>&1
)
echo.
echo ===================================================
echo   [ERROR] React frontend did not become ready.
echo ===================================================
if exist "%PROJECT_ROOT%logs\frontend.log" (
    echo.
    echo --- Recent output from logs\frontend.log ---
    powershell.exe -NoProfile -Command "Get-Content -Path '%PROJECT_ROOT%logs\frontend.log' -Tail 15 -ErrorAction SilentlyContinue"
    echo ---------------------------------------------
)
echo.
echo Please review logs\frontend.log for error details.
echo.
goto :handle_exit_error

:frontend_poll_success
echo.
echo   [OK] React frontend is ready on http://localhost:5173.

:frontend_done
echo.

:: -----------------------------------------------------------------------------
:: Step 4: Open Application in Default Browser [4/4]
:: -----------------------------------------------------------------------------
echo [4/4] Opening Cognidocs...
start "" "http://localhost:5173"
echo   [OK] Application launched successfully in your default browser!
echo.

:: -----------------------------------------------------------------------------
:: Final Summary Banner
:: -----------------------------------------------------------------------------
echo ===================================================
echo   Cognidocs is active and running!
echo   - Frontend : http://localhost:5173
echo   - Backend  : http://127.0.0.1:8000
echo   - API Docs : http://127.0.0.1:8000/docs
curl.exe -s --connect-timeout 0.2 http://127.0.0.1:11434/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   - Ollama   : http://127.0.0.1:11434 [Ready]
) else (
    echo   - Ollama   : http://127.0.0.1:11434 [Fallback mode]
)
echo   - Logs     : logs\
echo ===================================================

:: Remove lock on success
rmdir "%LOCK_DIR%" 2>nul
ping 127.0.0.1 -n 3 >nul
exit /b 0

:: -----------------------------------------------------------------------------
:: Error Exit Handler
:: -----------------------------------------------------------------------------
:handle_exit_error
rmdir "%LOCK_DIR%" 2>nul
echo.
echo Startup aborted due to errors.
echo Press any key to exit...
pause >nul
exit /b 1
