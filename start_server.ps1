# 以后台（脱离当前会话）方式启动本地可视化工作台。
#
# 用法（本机是 Windows PowerShell 5.1，命令名是 powershell；装了 PowerShell 7 也可用 pwsh）：
#   powershell -ExecutionPolicy Bypass -File start_server.ps1                    # 默认 8765
#   powershell -ExecutionPolicy Bypass -File start_server.ps1 -Port 8801         # 换端口
#   powershell -ExecutionPolicy Bypass -File start_server.ps1 -Port 8765 -Stop   # 停止
#
# 注意：本文件必须保存为 UTF-8 with BOM。Windows PowerShell 5.1 读无 BOM 的 UTF-8
# 脚本时会按 GBK 解码，中文字符串会把引号"吃掉"，报"字符串缺少终止符"。
#
# 与前台的 python app.py serve 的区别：
#   · 服务进程不挂在当前终端/会话下，关掉终端或结束调用方都不会带走它；
#   · 输出重定向到 logs\server-<时间戳>.log，出问题先看这个文件；
#   · 端口被占用时会报出是谁（PID）占着，而不是默默换端口；
#   · 端口选择交给 app.py（它自己会顺延），脚本按"新出现的监听端口"去认。

param(
    [int]$Port = 8765,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = 'C:\Users\pxj10\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $py) {
    Write-Host '找不到 Python 解释器。' -ForegroundColor Red
    exit 1
}

function Get-Listeners([int]$p) {
    @(netstat -ano | Select-String (":" + $p + "\s+.*LISTENING") |
        ForEach-Object { [int]($_.Line.Trim() -split '\s+')[-1] } | Select-Object -Unique)
}

# ---------- 停止 ----------
if ($Stop) {
    $pids = Get-Listeners $Port
    if (-not $pids) {
        Write-Host "端口 $Port 上没有正在运行的工作台。" -ForegroundColor Yellow
        exit 0
    }
    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "已停止 PID $procId（端口 $Port）" -ForegroundColor Green
        } catch {
            Write-Host "无法停止 PID ${procId}：$($_.Exception.Message)" -ForegroundColor Red
            Write-Host "可尝试：任务管理器 → 详细信息 → 结束 python.exe（PID $procId）" -ForegroundColor Yellow
        }
    }
    exit 0
}

# ---------- 启动 ----------
$existing = Get-Listeners $Port
if ($existing) {
    Write-Host "端口 $Port 已被占用（PID $($existing -join ', ')）。" -ForegroundColor Yellow
    Write-Host "若确认它就是这个工作台：直接打开 http://127.0.0.1:$Port/" -ForegroundColor Yellow
    Write-Host "若是残留进程：pwsh -File start_server.ps1 -Port $Port -Stop" -ForegroundColor Yellow
    exit 1
}

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $logDir "server-$stamp.log"
$errlog = Join-Path $logDir "server-$stamp.err.log"

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Start-Process -FilePath $py `
    -ArgumentList '-u', 'app.py', 'serve', '--port', "$Port" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errlog | Out-Null

# 等它真的开始监听，再报告实际端口
$actual = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 250
    for ($c = $Port; $c -lt ($Port + 20); $c++) {
        if (Get-Listeners $c) { $actual = $c; break }
    }
    if ($actual) { break }
}

if (-not $actual) {
    Write-Host '启动失败，日志：' -ForegroundColor Red
    if (Test-Path $log) { Get-Content $log -Encoding UTF8 }
    if ((Test-Path $errlog) -and (Get-Item $errlog).Length -gt 0) { Get-Content $errlog -Encoding UTF8 }
    exit 1
}

Write-Host "工作台已启动：http://127.0.0.1:$actual/" -ForegroundColor Green
Write-Host "日志：$log" -ForegroundColor Cyan
Write-Host "停止：pwsh -File start_server.ps1 -Port $actual -Stop" -ForegroundColor Cyan
