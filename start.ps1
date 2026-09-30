# AI 职业生涯规划 · 学习实践工作台（PowerShell 入口）
#
# 用法：
#   .\start.ps1                    # 交互菜单
#   .\start.ps1 today              # 直接跑某个命令（等价 python app.py today）
#   .\start.ps1 report --quarter
#
# 注意：本文件必须保存为 UTF-8 with BOM。Windows PowerShell 5.1 按 GBK 读无 BOM 的
# UTF-8 脚本，中文会变成乱码。
#
# 关于第 2 项：服务跑在前台（Ctrl+C 停止）是有意的——窗口关掉服务就停，不留后台
# 残留进程。想再开一个服务时，本脚本会先检测端口，已经在跑就直接打开浏览器。

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

Set-Location $PSScriptRoot

$py = Join-Path $env:LOCALAPPDATA '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

function Get-Listeners([int]$p) {
    @(netstat -ano | Select-String (":" + $p + "\s+.*LISTENING") |
        ForEach-Object { [int]($_.Line.Trim() -split '\s+')[-1] } | Select-Object -Unique)
}

if ($args.Count -gt 0) {
    & $py app.py @args
    exit $LASTEXITCODE
}

Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  AI 职业生涯规划 · 学习实践工作台' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  1  今天的 todo 清单'
Write-Host '  2  打开可视化工作台（浏览器；前台运行，Ctrl+C 停止）'
Write-Host '  3  未来 7 天一览'
Write-Host '  4  学习实践报告（月 / 90天 / 年）'
Write-Host '  5  加了新材料后重算计划'
Write-Host '  6  导出 Markdown 打卡清单'
Write-Host '  7  自定义任务：列表 / 新增 / 删除'
Write-Host '  0  退出'
$c = Read-Host '请输入编号并回车'
switch ($c) {
    '1' { & $py app.py today }
    '2' {
        $port = 8765
        if (Get-Listeners $port) {
            Write-Host "端口 $port 上已有工作台在运行，直接打开浏览器。" -ForegroundColor Yellow
            Start-Process "http://127.0.0.1:$port/"
        } else {
            Write-Host "正在启动：http://127.0.0.1:$port/　（按 Ctrl+C 停止）" -ForegroundColor Green
            Start-Process "http://127.0.0.1:$port/"
            & $py app.py serve --port $port
        }
    }
    '3' { & $py app.py week --days 7 }
    '4' { & $py app.py report --quarter }
    '5' { & $py app.py replan }
    '6' { & $py app.py export --days 30 }
    '7' { & $py app.py tasks }
    default { }
}
