param (
    [Parameter(Mandatory=$true)][string]$Command,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory,
    [Parameter(Mandatory=$true)][string]$LogFile
)

# 1. Ensure target log directory exists
$logDir = Split-Path -Path $LogFile -Parent
if ($logDir -and !(Test-Path -Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# 2. Append timestamped execution banner to the log file
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$banner = @"

======================================================
[Startup: $timestamp]
Command: $Command
Working Directory: $WorkingDirectory
======================================================
"@
Add-Content -Path $LogFile -Value $banner -ErrorAction SilentlyContinue

# 3. Launch process in background with hidden window and output redirection
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "cmd.exe"
$psi.Arguments = "/c $Command >> `"$LogFile`" 2>&1"
$psi.WorkingDirectory = $WorkingDirectory
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.CreateNoWindow = $true
$psi.UseShellExecute = $true

[System.Diagnostics.Process]::Start($psi) | Out-Null
