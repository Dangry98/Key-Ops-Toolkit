<#
.SYNOPSIS
    Build Key-Ops-Toolkit, install it into a throwaway Blender profile and run the headless tests.

.DESCRIPTION
    Uses a scratch BLENDER_USER_RESOURCES directory, so the user's own Blender config and installed
    add-ons are never touched. Builds the extension zip from the current working tree (so it picks up
    unsaved-to-git edits), installs it into the user_default repository, then runs each test with
    `blender -b --factory-startup --python <test>`.

    Output is filtered to FAIL lines, errors and tracebacks plus one summary line per test, to keep
    logs short. Use -Full to see everything. Full logs are always kept in the scratch directory.

.PARAMETER Version
    Blender version prefix to find under Desktop/Downloads, e.g. "5.4", "4.2.3", "5.2.2".
    Default "5.4". Ignored when -Blender is given.

.PARAMETER Blender
    Full path to a blender.exe.

.PARAMETER Gui
    Also run every tests/gui_*.py in a real Blender window (not -b) with simulated events: every modal
    tool, pie and menu is opened, moved and cancelled, so draw callbacks and status bars really run.
    Fails on any Python traceback in that log. A window opens and closes by itself.

.PARAMETER Tests
    Test files to run, relative to the repo. Default: tests/test_registration.py tests/test_redesign.py.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/test.ps1
    powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Version 4.2.3 -Tests tests/test_registration.py
    powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Version 4.2.3 -Gui
#>
param(
    [string]$Version = "5.4",
    [string]$Blender = "",
    [string[]]$Tests = @("tests/test_registration.py", "tests/test_redesign.py", "tests/test_menu_drawing.py", "tests/test_ui_draw.py", "tests/test_kit_coverage.py", "tests/test_backlog.py", "tests/test_edge_trim.py", "tests/test_cylinder_sides.py", "tests/test_push_pull.py"),
    [switch]$Full,
    [switch]$Gui
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $Blender) {
    $roots = @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\Downloads", "C:\Program Files\Blender Foundation")
    $found = foreach ($r in $roots) {
        Get-ChildItem -Path $r -Directory -Filter "*lender*$Version*" -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName "blender.exe" } |
            Where-Object { Test-Path $_ }
    }
    $Blender = @($found | Sort-Object -Descending)[0]
    if (-not $Blender) {
        Write-Output "FAIL no blender.exe found for version '$Version'. Pass -Blender <path>."
        exit 2
    }
}
Write-Output "blender: $Blender"

$work = Join-Path $env:TEMP ("keyops-test-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$res = Join-Path $work "user"
$out = Join-Path $work "build"
New-Item -ItemType Directory -Force -Path $res, $out | Out-Null
$env:BLENDER_USER_RESOURCES = $res

function Invoke-Blender([string[]]$BlenderArgs, [string]$Log) {
    # Start-Process instead of "&": Windows PowerShell turns native stderr into terminating
    # errors under ErrorActionPreference=Stop. Quote each argument for the command line.
    $quoted = $BlenderArgs | ForEach-Object { '"' + $_ + '"' }
    $errLog = "$Log.err"
    $p = Start-Process -FilePath $Blender -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $Log -RedirectStandardError $errLog
    Get-Content $errLog | Add-Content $Log
    Remove-Item $errLog
    return $p.ExitCode
}

$code = Invoke-Blender @("--command", "extension", "build", "--source-dir", $repo, "--output-dir", $out) (Join-Path $work "build.log")
$zip = Get-ChildItem -Path $out -Filter *.zip | Select-Object -First 1
if ($code -ne 0 -or -not $zip) {
    Write-Output "FAIL build (exit $code)"
    Get-Content (Join-Path $work "build.log") -Tail 20
    exit 1
}

$code = Invoke-Blender @("--command", "extension", "install-file", "-r", "user_default", "-e", $zip.FullName) (Join-Path $work "install.log")
if ($code -ne 0) {
    Write-Output "FAIL install (exit $code)"
    Get-Content (Join-Path $work "install.log") -Tail 20
    exit 1
}
Write-Output "built + installed $($zip.Name)"

$failed = 0
foreach ($t in $Tests) {
    $testPath = Join-Path $repo $t
    $log = Join-Path $work ((Split-Path $t -Leaf) + ".log")
    $code = Invoke-Blender @("-b", "--factory-startup", "--python-exit-code", "1", "--python", $testPath) $log
    $lines = Get-Content $log
    $pass = @($lines | Where-Object { $_ -match '^PASS ' }).Count
    $fail = @($lines | Where-Object { $_ -match '^FAIL ' }).Count
    if ($Full) {
        $lines
    } else {
        $lines | Where-Object { $_ -notmatch '^PASS ' -and $_ -match '^FAIL |Traceback|Error|Exception' } | Select-Object -First 40
    }
    $status = if ($code -eq 0 -and $fail -eq 0) { "OK  " } else { "FAIL" }
    if ($status -eq "FAIL") { $failed++ }
    Write-Output "$status $t  pass=$pass fail=$fail exit=$code"
}

if ($Gui) {
  foreach ($gt in (Get-ChildItem (Join-Path $repo "tests") -Filter "gui_*.py" | Sort-Object Name)) {
    $t = "tests/" + $gt.Name
    $log = Join-Path $work ($gt.Name + ".log")
    $code = Invoke-Blender @("--factory-startup", "--enable-event-simulate", "--python", (Join-Path $repo $t)) $log
    $lines = Get-Content $log
    $pass = @($lines | Where-Object { $_ -match '^PASS ' }).Count
    $fail = @($lines | Where-Object { $_ -match '^FAIL ' }).Count
    $tracebacks = @($lines | Where-Object { $_ -match 'Traceback' }).Count
    $done = @($lines | Where-Object { $_ -match '^ALLDONE' }).Count
    if ($Full) {
        $lines
    } else {
        $lines | Where-Object { $_ -match '^FAIL |^SKIP |Traceback|Error|^  File ' } | Select-Object -First 40
    }
    $ok = ($code -eq 0 -and $fail -eq 0 -and $tracebacks -eq 0 -and $done -eq 1)
    $status = if ($ok) { "OK  " } else { "FAIL" }
    if (-not $ok) { $failed++ }
    Write-Output "$status $t  pass=$pass fail=$fail tracebacks=$tracebacks exit=$code"
  }
}

Write-Output "logs: $work"
if ($failed -gt 0) { exit 1 }
exit 0
