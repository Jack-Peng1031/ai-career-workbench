@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo      本地 ^<-^> PythonAnywhere 同步
echo ========================================
echo.

REM ============ 找 python ============
set "PYEXE="
set "BUNDLED=C:\Users\pxj10\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if defined WORKBENCH_PY set "PYEXE=%WORKBENCH_PY%"
if not defined PYEXE if exist "%BUNDLED%" set "PYEXE=%BUNDLED%"
if not defined PYEXE (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -3"
)
if not defined PYEXE (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
    echo [错误] 找不到 Python。请设置环境变量 WORKBENCH_PY 指向 python.exe
    echo        例如：set WORKBENCH_PY=C:\Python313\python.exe
    echo.
    pause
    exit /b 1
)
echo [信息] 使用解释器：%PYEXE%
echo.

if "%~1"=="" goto MENU
set "SEL=%~1"
set "WAIT=pause"
goto RUN

:MENU
echo   1. 检查连通性（认证方式 / 远端目录）
echo   2. 预览将要同步的文件（不修改任何东西）
echo   3. 上传：本地 -^> PythonAnywhere
echo   4. 上传并重新加载 Web App
echo   5. 拉回：PythonAnywhere -^> 本地
echo   6. 显示 SSH 公钥（首次配置用）
echo   7. 通知 PythonAnywhere 重新加载 Web App
echo   0. 退出
echo.
set /p SEL=请输入序号后回车:
set "WAIT=pause"

:RUN
if "%SEL%"=="1" ( %PYEXE% tools\pa_sync.py check & goto DONE )
if "%SEL%"=="2" ( %PYEXE% tools\pa_sync.py diff & goto DONE )
if "%SEL%"=="3" ( %PYEXE% tools\pa_sync.py push & goto DONE )
if "%SEL%"=="4" ( %PYEXE% tools\pa_sync.py push --reload & goto DONE )
if "%SEL%"=="5" ( %PYEXE% tools\pa_sync.py pull & goto DONE )
if "%SEL%"=="6" ( %PYEXE% tools\pa_sync.py setup & goto DONE )
if "%SEL%"=="7" ( %PYEXE% tools\pa_sync.py reload & goto DONE )
if "%SEL%"=="0" ( exit /b 0 )
echo [错误] 没有这个选项：%SEL%

:DONE
echo.
echo ========================================
if defined WAIT pause
endlocal
exit /b 0
