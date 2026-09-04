# Agent2Agents One-Line Installer for Windows PowerShell

$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:USERPROFILE ".agent2agents"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"

Write-Host "Installing Agent2Agents for Windows..." -ForegroundColor Cyan

# 1. Check Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Error "Python is required but not installed or not in PATH."
    exit 1
}

# 2. Setup directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

$ScriptDir = $PSScriptRoot
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "agent2agents")) -and ($ScriptDir -ne $InstallDir)) {
    Copy-Item -Path (Join-Path $ScriptDir "agent2agents") -Destination $InstallDir -Recurse -Force
    if (Test-Path (Join-Path $ScriptDir "tests")) {
        Copy-Item -Path (Join-Path $ScriptDir "tests") -Destination $InstallDir -Recurse -Force
    }
    foreach ($File in @("setup.py", "run.sh", "install.sh", "install.ps1", "README.md")) {
        $FilePath = Join-Path $ScriptDir $File
        if (Test-Path $FilePath) {
            Copy-Item -Path $FilePath -Destination $InstallDir -Force
        }
    }
} else {
    Write-Host "Downloading source code..."
    $ZipUrl = "https://github.com/SonNX24042005/agent2agents/archive/refs/heads/main.zip"
    $ZipPath = Join-Path $env:TEMP "agent2agents.zip"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $env:TEMP -Force
    Copy-Item -Path (Join-Path $env:TEMP "agent2agents-main\*") -Destination $InstallDir -Recurse -Force
    Remove-Item $ZipPath -Force
    Remove-Item (Join-Path $env:TEMP "agent2agents-main") -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Create Bin Directory
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir | Out-Null
}

# 4. Create CMD wrappers
$Agent2AgentsCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli %*
"@

Set-Content -Path (Join-Path $BinDir "a2a.cmd") -Value $Agent2AgentsCmd
Set-Content -Path (Join-Path $BinDir "agent2agents.cmd") -Value $Agent2AgentsCmd

$Claude2AgyCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --antigravity %*
"@

$Claude2CodexCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --codex %*
"@

$Agy2ClaudeCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --reverse %*
"@

$Agy2CodexCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --antigravity-to-codex %*
"@

$Codex2ClaudeCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --codex-to-claude %*
"@

$Codex2AgyCmd = @"
@echo off
set PYTHONPATH=%USERPROFILE%\.agent2agents
python -m agent2agents.cli --codex-to-antigravity %*
"@

Set-Content -Path (Join-Path $BinDir "claude2agy.cmd") -Value $Claude2AgyCmd
Set-Content -Path (Join-Path $BinDir "claude2codex.cmd") -Value $Claude2CodexCmd
Set-Content -Path (Join-Path $BinDir "agy2claude.cmd") -Value $Agy2ClaudeCmd
Set-Content -Path (Join-Path $BinDir "agy2codex.cmd") -Value $Agy2CodexCmd
Set-Content -Path (Join-Path $BinDir "codex2claude.cmd") -Value $Codex2ClaudeCmd
Set-Content -Path (Join-Path $BinDir "codex2agy.cmd") -Value $Codex2AgyCmd

# 5. Add BinDir to User PATH if missing
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "Added $BinDir to User PATH." -ForegroundColor Yellow
}

Write-Host "`nInstallation completed successfully!" -ForegroundColor Green
Write-Host "Commands installed:"
Write-Host "  - a2a (primary command)"
Write-Host "  - agent2agents (compatibility alias)"
Write-Host "  - claude2agy (direct Claude Code -> Antigravity)"
Write-Host "  - claude2codex (direct Claude Code -> Codex)"
Write-Host "  - agy2claude (direct Antigravity -> Claude Code)"
Write-Host "  - agy2codex (direct Antigravity -> Codex)"
Write-Host "  - codex2claude (direct Codex -> Claude Code)"
Write-Host "  - codex2agy (direct Codex -> Antigravity)"
Write-Host "`nNote: Please restart your PowerShell terminal for PATH changes to take effect." -ForegroundColor Yellow
