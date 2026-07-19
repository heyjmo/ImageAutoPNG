# ImageAutoPNG — per-user install (no admin required)
# Installs to %LOCALAPPDATA%\ImageAutoPNG and adds Startup entry.

$ErrorActionPreference = "Stop"

$AppName = "ImageAutoPNG"
$SourceDir = $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$Python = $null

Write-Host "=== $AppName Installer (current user) ===" -ForegroundColor Cyan

# Prefer pythonw / python from PATH
foreach ($cand in @("python", "py")) {
    try {
        $cmd = Get-Command $cand -ErrorAction Stop
        $Python = $cmd.Source
        break
    } catch { }
}

if (-not $Python) {
    Write-Host "Python was not found on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10+ from https://www.python.org/downloads/ (check 'Add to PATH')."
    exit 1
}

Write-Host "Using Python: $Python"

# Create install directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Copy application files
$files = @(
    "app.py",
    "config.py",
    "converter.py",
    "tray_icon.py",
    "requirements.txt",
    "run.vbs",
    "uninstall.ps1"
)
foreach ($f in $files) {
    $src = Join-Path $SourceDir $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $InstallDir $f) -Force
    }
}

Write-Host "Installed files to: $InstallDir"

# Install dependencies for current user
Write-Host "Installing Python packages..."
& $Python -m pip install --user -r (Join-Path $InstallDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed." -ForegroundColor Red
    exit 1
}

# Resolve pythonw for silent launch
$PythonDir = Split-Path -Parent $Python
$Pythonw = Join-Path $PythonDir "pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    # Windows Store / py launcher layout
    $Pythonw = $Python
}

# Create Start Menu shortcut
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$ShortcutPath = Join-Path $StartMenu "$AppName.lnk"
$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Pythonw
$Sc.Arguments = "`"$(Join-Path $InstallDir 'app.py')`""
$Sc.WorkingDirectory = $InstallDir
$Sc.Description = "Convert .webp and .heic images to PNG in the background"
$Sc.Save()
Write-Host "Start Menu shortcut: $ShortcutPath"

# Registry Run key for login startup
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$Cmd = "`"$Pythonw`" `"$(Join-Path $InstallDir 'app.py')`""
Set-ItemProperty -Path $RunKey -Name $AppName -Value $Cmd
Write-Host "Startup entry registered (starts with Windows)."

# Default config if missing (user profile — not LocalAppData, which Store Python virtualizes)
$ConfigDir = Join-Path $env:USERPROFILE (".{0}" -f $AppName.ToLower())
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir "config.json"
if (-not (Test-Path $ConfigPath)) {
    $downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"
    @{
        watch_folder              = $downloads
        delete_originals          = $true
        convert_existing_on_start = $true
        start_with_windows        = $true
        recursive                 = $false
    } | ConvertTo-Json | Set-Content -Path $ConfigPath -Encoding UTF8
    Write-Host "Default config watches: $downloads"
    Write-Host "Config path: $ConfigPath"
}

# Launch now
Write-Host "Starting $AppName..."
Start-Process -FilePath $Pythonw -ArgumentList "`"$(Join-Path $InstallDir 'app.py')`"" -WorkingDirectory $InstallDir

Write-Host ""
Write-Host "Done. $AppName is running in the system tray." -ForegroundColor Green
Write-Host "Right-click the tray icon for options (folder, pause, quit)."
Write-Host "To uninstall later, run: $InstallDir\uninstall.ps1"
