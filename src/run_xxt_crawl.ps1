# 分离进程长跑：抓小学堂的页面/位图。
#
# 为什么要脱离工具调用：**后台任务有 1 小时上限**，而全量抓取是几十小时的活。
# 分离进程（Start-Process -WindowStyle Hidden）跑在工具调用之外，
# 父 shell 退出也不影响它；输出重定向到日志，随时可查。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File src/run_xxt_crawl.ps1 -Stage pages -Db chuwenzi
#   powershell -NoProfile -ExecutionPolicy Bypass -File src/run_xxt_crawl.ps1 -Stage images -Db chuwenzi
param(
    [ValidateSet('pages', 'images')]
    [string]$Stage = 'pages',
    [string]$Db = 'chuwenzi',
    [int]$Delay = 4,
    [int]$Size = 400,
    [int]$Batch = 200,
    [int]$PerPage = 400,
    [int]$Lanes = 1,
    [string]$ShapeList = '',
    [string]$Out = '',
    [int]$Limit = 0
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Out) { $Out = Join-Path $root ("tmp/xxt/" + $Db) }
$logDir = Join-Path $root 'tmp/xxt/logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outLog = Join-Path $logDir ("{0}-{1}-{2}.log" -f $Db, $Stage, $stamp)
$errLog = Join-Path $logDir ("{0}-{1}-{2}.err" -f $Db, $Stage, $stamp)

$args = @('-X', 'utf8', '-u', (Join-Path $root 'src/fetch_xiaoxuetang_glyphs.py'),
          '--mode', 'glyphs', '--stage', $Stage, '--db', $Db,
          '--delay', "$Delay", '--out', $Out)
if ($Stage -eq 'pages') {
    $args += @('--zi-from', '1', '--zi-to', '0', '--per-page', "$PerPage",
               '--progress-every', '50')
} else {
    $args += @('--size', "$Size", '--batch', "$Batch", '--lanes', "$Lanes")
    if ($ShapeList) { $args += @('--shape-list', "$ShapeList") }
    if ($Limit -gt 0) { $args += @('--limit', "$Limit") }
}

Write-Host "启动：$($args -join ' ')"
Write-Host "日志：$outLog"
$proc = Start-Process -FilePath 'python' -ArgumentList $args -WorkingDirectory $root `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
    -WindowStyle Hidden -PassThru
Write-Host ("PID = {0}" -f $proc.Id)
