# ImageAutoPNG — per-user uninstall
param(
    [switch]$Full
)

$ErrorActionPreference = "Continue"
$AppName = "ImageAutoPNG"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName

Write-Host "=== $AppName Uninstaller ===" -ForegroundColor Cyan

# Stop running instances
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*ImageAutoPNG*app.py*" } |
    ForEach-Object {
        Write-Host "Stopping PID $($_.ProcessId)..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# Also match when run from source folder
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*webp-heic-converter*app.py*" } |
    ForEach-Object {
        Write-Host "Stopping PID $($_.ProcessId)..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# Remove startup registry value
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $RunKey -Name $AppName -ErrorAction SilentlyContinue
Write-Host "Removed startup entry."

# Remove Start Menu shortcut
$ShortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName.lnk"
if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "Removed Start Menu shortcut."
}

$ConfigDir = Join-Path $env:USERPROFILE (".{0}" -f $AppName.ToLower())

if (Test-Path $InstallDir) {
    if ($Full) {
        Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Removed install directory: $InstallDir"
    } else {
        $toRemove = @(
            "app.py", "config.py", "converter.py", "tray_icon.py",
            "requirements.txt", "run.vbs", "uninstall.ps1", "install.ps1"
        )
        foreach ($f in $toRemove) {
            $p = Join-Path $InstallDir $f
            if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
        }
        Write-Host "Removed application files from: $InstallDir"
        Write-Host "Config/log kept at $ConfigDir. Use uninstall.ps1 -Full to remove those too."
    }
}

if ($Full -and (Test-Path $ConfigDir)) {
    Remove-Item $ConfigDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Removed config directory: $ConfigDir"
}

# Clean legacy Store-Python virtualized config if present
$Legacy = Join-Path $env:LOCALAPPDATA $AppName
if ($Full -and (Test-Path $Legacy)) {
    Remove-Item $Legacy -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Uninstall complete." -ForegroundColor Green
