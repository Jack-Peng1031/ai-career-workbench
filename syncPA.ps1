# 本地 <-> PythonAnywhere 同步（PowerShell 版；功能与 syncPA.bat 相同）
# 用法：powershell -ExecutionPolicy Bypass -File syncPA.ps1 [-Action push|pull|diff|check|reload|setup]
param([ValidateSet('menu','check','diff','push','push-reload','pull','setup','reload')][string]$Action = 'menu')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    if ($env:WORKBENCH_PY) { return $env:WORKBENCH_PY }
    $bundled = 'C:\Users\pxj10\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    if (Get-Command 'py' -ErrorAction SilentlyContinue) { return 'py -3' }
    if (Get-Command 'python' -ErrorAction SilentlyContinue) { return 'python' }
    throw ' 找不到 Python，请设置环境变量 WORKBENCH_PY'
}

$py = Find-Python
$script = Join-Path $PSScriptRoot 'tools\pa_sync.py'

function Invoke-Sync([string[]]$SyncArgs) {
    Write-Host "[信息] $py $script $($SyncArgs -join ' ')" -ForegroundColor DarkGray
    & ($py -split ' ')[0] @(($py -split ' ')[1..99] | Where-Object { $_ }) $script @SyncArgs
}

switch ($Action) {
    'check'       { Invoke-Sync @('check') }
    'diff'        { Invoke-Sync @('diff') }
    'push'        { Invoke-Sync @('push') }
    'push-reload' { Invoke-Sync @('push', '--reload') }
    'pull'        { Invoke-Sync @('pull') }
    'setup'       { Invoke-Sync @('setup') }
    'reload'      { Invoke-Sync @('reload') }
    default {
        Write-Host '========================================'
        Write-Host '     本地 <-> PythonAnywhere 同步'
        Write-Host '========================================'
        Write-Host ''
        Write-Host '  1. 检查连通性（认证方式 / 远端目录）'
        Write-Host '  2. 预览将要同步的文件（不修改任何东西）'
        Write-Host '  3. 上传：本地 -> PythonAnywhere'
        Write-Host '  4. 上传并重新加载 Web App'
        Write-Host '  5. 拉回：PythonAnywhere -> 本地'
        Write-Host '  6. 显示 SSH 公钥（首次配置用）'
        Write-Host '  7. 通知 PythonAnywhere 重新加载 Web App'
        Write-Host '  0. 退出'
        Write-Host ''
        $sel = Read-Host '请输入序号后回车'
        switch ($sel) {
            '1' { Invoke-Sync @('check') }
            '2' { Invoke-Sync @('diff') }
            '3' { Invoke-Sync @('push') }
            '4' { Invoke-Sync @('push', '--reload') }
            '5' { Invoke-Sync @('pull') }
            '6' { Invoke-Sync @('setup') }
            '7' { Invoke-Sync @('reload') }
            '0' { return }
            default { Write-Host "[错误] 没有这个选项：$sel" -ForegroundColor Red }
        }
    }
}
