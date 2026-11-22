<#
.SYNOPSIS
    Live-reload Key-Ops-Toolkit in every Blender started from VS Code (Blender Development extension).

.DESCRIPTION
    Finds each running blender.exe with a listening localhost port, checks that the port answers
    GET /ping with "OK", and posts a reload request for this repo. With -Script, also runs a Python
    file inside each Blender afterwards (the script should write its results to a file; it must not
    raise, because the VS Code debugger pauses Blender on any exception).

    Prints one line per Blender and a final summary. Exit code 0 when at least one Blender reloaded,
    1 when none did (usually Blender was started outside VS Code).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/reload.ps1
    powershell -ExecutionPolicy Bypass -File scripts/reload.ps1 -Script C:/temp/check.py
#>
param(
    [string]$Script = ""
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path -replace '\\', '/'
$name = Split-Path $repo -Leaf

$procs = @(Get-Process blender -ErrorAction SilentlyContinue)
if ($procs.Count -eq 0) {
    Write-Output "FAIL no blender.exe running. Start Blender from VS Code (Blender: Start)."
    exit 1
}

$reloaded = 0
foreach ($p in $procs) {
    $ports = @(Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @("127.0.0.1", "::1", "0.0.0.0") } |
        Select-Object -ExpandProperty LocalPort -Unique)
    $port = $null
    foreach ($candidate in $ports) {
        try {
            $pong = Invoke-RestMethod -Uri "http://127.0.0.1:$candidate/ping" -TimeoutSec 2
            if ("$pong".Trim() -eq "OK") { $port = $candidate; break }
        } catch { }
    }
    if (-not $port) {
        Write-Output "SKIP pid $($p.Id): no VS Code server (started outside VS Code)"
        continue
    }

    $body = @{ type = "reload"; names = @($name); dirs = @($repo) } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$port/" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30 | Out-Null
        Write-Output "OK   pid $($p.Id) port ${port}: reloaded"
        $reloaded++
    } catch {
        Write-Output "FAIL pid $($p.Id) port ${port}: reload $($_.Exception.Message)"
        continue
    }

    if ($Script) {
        $path = (Resolve-Path $Script).Path -replace '\\', '/'
        $sbody = @{ type = "script"; path = $path } | ConvertTo-Json -Compress
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:$port/" -Method Post -ContentType "application/json" -Body $sbody -TimeoutSec 60 | Out-Null
            Write-Output "OK   pid $($p.Id): ran $path"
        } catch {
            Write-Output "FAIL pid $($p.Id): script $($_.Exception.Message)"
        }
    }
}

Write-Output "reloaded $reloaded of $($procs.Count) blender.exe"
if ($reloaded -eq 0) { exit 1 }
exit 0
