@echo off
setlocal EnableDelayedExpansion

title Cognidocs Launcher
cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"

echo ===================================================
echo             Cognidocs System Launcher              
echo ===================================================
echo Project Root : %PROJECT_ROOT%
echo Logs         : %PROJECT_ROOT%logs
echo.

:: -----------------------------------------------------------------------------
:: Step 0: Check essential system prerequisites
:: -----------------------------------------------------------------------------
where curl.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] curl.exe was not found in PATH.
    echo Windows 10/11 includes curl by default in C:\Windows\System32.
    echo Please ensure curl is accessible in your PATH.
    echo.
    pause
    exit /b 1
)

where powershell.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] powershell.exe was not found in PATH.
    echo PowerShell is required to run background services.
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%scripts\run-hidden.ps1" (
    echo [ERROR] Helper script not found at:
    echo         %PROJECT_ROOT%scripts\run-hidden.ps1
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%logs" (
    mkdir "%PROJECT_ROOT%logs" >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: Step 1: Check & Start Ollama
:: -----------------------------------------------------------------------------
echo [1/3] Checking Ollama API status...
curl.exe -s --connect-timeout 2 http://127.0.0.1:11434/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Ollama is already running on http://127.0.0.1:11434.
    goto :ollama_done
)

where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARNING] 'ollama' command was not found in PATH.
    echo             Ollama was not started automatically.
    echo             AI synthesis will use extractive fallback until Ollama is running.
    goto :ollama_done
)

echo   [STARTING] Launching Ollama in the background (hidden)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command "ollama serve" -WorkingDirectory "%PROJECT_ROOT%." -LogFile "%PROJECT_ROOT%logs\ollama.log"

echo   Waiting for Ollama API to become ready (up to 30s)...
set "OLLAMA_READY=0"
for /L %%i in (1,1,30) do (
    curl.exe -s --connect-timeout 1 http://127.0.0.1:11434/ >nul 2>&1
    if not errorlevel 1 (
        set "OLLAMA_READY=1"
        goto :ollama_poll_done
    )
    <nul set /p=.
    ping 127.0.0.1 -n 2 >nul
)

:ollama_poll_done
echo.
if !OLLAMA_READY! equ 1 (
    echo   [OK] Ollama is ready on http://127.0.0.1:11434.
) else (
    echo   [WARNING] Ollama did not respond within 30 seconds.
    echo             Check log file: logs\ollama.log
    echo             Continuing startup (backend will use deterministic search fallback)...
)

:ollama_done
echo.

:: -----------------------------------------------------------------------------
:: Step 2: Check & Start FastAPI Backend
:: -----------------------------------------------------------------------------
echo [2/3] Checking FastAPI backend status...
curl.exe -s --connect-timeout 2 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] FastAPI backend is already running on http://127.0.0.1:8000.
    goto :backend_done
)

if not exist "%PROJECT_ROOT%backend\.venv\Scripts\uvicorn.exe" (
    echo   [ERROR] Python virtual environment not found at:
    echo           backend\.venv\Scripts\uvicorn.exe
    echo           Please create the virtual environment in backend\.venv first.
    echo.
    pause
    exit /b 1
)

echo   [STARTING] Launching FastAPI backend in the background (hidden)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command ".venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory "%PROJECT_ROOT%backend" -LogFile "%PROJECT_ROOT%logs\backend.log"

echo   Waiting for FastAPI backend to become ready (up to 15s)...
set "BACKEND_READY=0"
for /L %%i in (1,1,15) do (
    curl.exe -s --connect-timeout 1 http://127.0.0.1:8000/health >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto :backend_poll_done
    )
    <nul set /p=.
    ping 127.0.0.1 -n 2 >nul
)

:backend_poll_done
echo.
if !BACKEND_READY! equ 1 (
    echo   [OK] FastAPI backend is ready on http://127.0.0.1:8000.
) else (
    echo   [WARNING] FastAPI backend did not respond within 15 seconds.
    echo             Check log file: logs\backend.log
    echo             Proceeding with frontend startup...
)

:backend_done
echo.

:: -----------------------------------------------------------------------------
:: Step 3: Check & Start Vite Frontend
:: -----------------------------------------------------------------------------
echo [3/3] Checking Vite frontend status...
set "FRONTEND_ALREADY_RUNNING=0"
curl.exe -s --connect-timeout 2 http://localhost:5173/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Vite frontend is already running on http://localhost:5173.
    set "FRONTEND_ALREADY_RUNNING=1"
    goto :frontend_start_done
)

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] 'npm' command was not found in PATH.
    echo           Node.js is required to run the frontend.
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%frontend\node_modules" (
    echo   [ERROR] frontend\node_modules not found.
    echo           Please run 'npm install' in the frontend directory first.
    echo.
    pause
    exit /b 1
)

echo   [STARTING] Launching Vite frontend in the background (hidden)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\run-hidden.ps1" -Command "npm run dev" -WorkingDirectory "%PROJECT_ROOT%frontend" -LogFile "%PROJECT_ROOT%logs\frontend.log"

:frontend_start_done
echo.

:: -----------------------------------------------------------------------------
:: Step 4: Wait for Frontend Readiness & Open Browser
:: -----------------------------------------------------------------------------
set "FRONTEND_READY=0"

if %FRONTEND_ALREADY_RUNNING% equ 1 (
    set "FRONTEND_READY=1"
    goto :frontend_poll_done
)

echo Waiting for Vite frontend to become ready (up to 20s)...
for /L %%i in (1,1,20) do (
    curl.exe -s --connect-timeout 1 http://localhost:5173/ >nul 2>&1
    if not errorlevel 1 (
        set "FRONTEND_READY=1"
        goto :frontend_poll_done
    )
    <nul set /p=.
    ping 127.0.0.1 -n 2 >nul
)

:frontend_poll_done
echo.
echo.

if !FRONTEND_READY! equ 1 (
    echo ===================================================
    echo   Cognidocs is ready!
    echo   Frontend : http://localhost:5173
    echo   Backend  : http://127.0.0.1:8000
    echo   API Docs : http://127.0.0.1:8000/docs
    echo   Ollama   : http://127.0.0.1:11434
    echo   Logs     : logs\
    echo ===================================================
    echo Opening application in default browser...
    start "" "http://localhost:5173"
    ping 127.0.0.1 -n 3 >nul
    exit /b 0
) else (
    echo ===================================================
    echo   [WARNING] Frontend did not become ready within 20 seconds.
    echo   The browser was not opened automatically.
    echo   Please check the log files for troubleshooting:
    echo     Frontend log : logs\frontend.log
    echo     Backend log  : logs\backend.log
    echo     Ollama log   : logs\ollama.log
    echo ===================================================
    echo.
    pause
    exit /b 1
)
