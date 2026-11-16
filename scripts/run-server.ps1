<#
.SYNOPSIS
  Starts the Kid Builder builder server on Windows (PowerShell).

.DESCRIPTION
  Checks Python + Rust + the wasm32 target + trunk are installed, then
  runs kidbuilder-server.py on port 8081. Put this machine's LAN IP in
  the Kid Builder iPhone app Settings as the builder URL, e.g.
  http://192.168.1.10:8081 - or its Tailscale IP when away from home.

  This server runs ALONGSIDE the YewBuilder server, on its own port
  (8081 vs YewBuilder's 8080), from its own folder. It does NOT replace
  the YewBuilder server and does NOT touch it: do not stop the
  "YewBuilder server" scheduled task, do not change it, and do not
  point anything YewBuilder at this port. YewBuilder keeps working
  exactly as it does today, on 8080, whether this server is running
  or not - and Kid Builder works whether the YewBuilder server is
  running or not. The two servers share nothing: different folders,
  different ports, different apps. Stopping one cannot affect the
  other.

  First-time setup (one-off, PowerShell):
    winget install Rustlang.Rustup
    # close and reopen PowerShell, then:
    rustup default stable
    rustup target add wasm32-unknown-unknown
    cargo install trunk

  NOTE: this file must stay pure ASCII. Windows PowerShell 5.1 reads
  .ps1 files as ANSI, so a UTF-8 em dash or curly quote gets mangled
  and breaks parsing (this exact bug killed v1.0.0 of the YewBuilder
  run-server script).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run-server.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run-server.ps1 -Port 8081
#>
param(
    [int]$Port = 8081
)

$ErrorActionPreference = 'Stop'

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command 'python')) { throw "Python not found. Install it from python.org or the Microsoft Store, then re-run this script." }
if (-not (Test-Command 'cargo')) { throw "cargo not found. Run: winget install Rustlang.Rustup - then close and reopen PowerShell and run: rustup default stable" }
if (-not (Test-Command 'trunk')) { throw "trunk not found. Run: cargo install trunk (after: rustup target add wasm32-unknown-unknown)" }

$trunkVersion = trunk --version
$cargoVersion = cargo --version
Write-Host "Kid Builder server - $cargoVersion / $trunkVersion" -ForegroundColor Green
Write-Host "Listening on http://0.0.0.0:$Port - iPhone Settings > Builder server: http://<this-PC-LAN-IP>:$Port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

# This script lives in scripts\, but kidbuilder-server.py lives one level
# up, in the kidbuilder\ folder. Run from there - NOT from $PSScriptRoot
# (the scripts\ folder), or Python looks for the server file in scripts\
# and fails with "can't open file '...\scripts\kidbuilder-server.py'".
# (That exact bug shipped in v1.0.1 and v1.0.2: the YewBuilder script
# this was copied from sits BESIDE server.py, so $PSScriptRoot was
# right for it and wrong here.)
$ServerDir = Split-Path $PSScriptRoot -Parent
$ServerFile = Join-Path $ServerDir 'kidbuilder-server.py'
if (-not (Test-Path $ServerFile)) {
    throw "kidbuilder-server.py not found at $ServerFile`nRun this script from the extracted kidbuilder folder (E:\Downloads\kidbuilder-vX.Y.Z\kidbuilder)."
}
Set-Location $ServerDir
python kidbuilder-server.py $Port
