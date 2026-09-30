@echo off
chcp 65001 >nul
setlocal
rem AI 职业生涯规划 · 学习实践工作台 —— 双击即可用的命令行入口
rem 用法：双击运行＝交互菜单；start.bat today / start.bat report --quarter ＝直接执行
set "PY=%LOCALAPPDATA%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
rem 带参数调用（脚本/自动化）时不暂停，交互双击时才等按键
set "WAIT=pause"
if not "%~1"=="" set "WAIT=rem"

if not "%~1"=="" goto :run
goto :menu

:run
"%PY%" app.py %*
echo.
%WAIT%
exit /b %errorlevel%

:menu
echo ============================================================
echo   AI 职业生涯规划 · 学习实践工作台
echo ============================================================
echo   1  今天的 todo 清单
echo   2  打开可视化工作台（浏览器；前台运行，Ctrl+C 停止）
echo   3  未来 7 天一览
echo   4  学习实践报告（月 / 90天 / 年）
echo   5  加了新材料后重算计划
echo   6  导出 Markdown 打卡清单
echo   7  自定义任务列表（增删见 README 或网页端）
echo   0  退出
echo ============================================================
set "choice="
set /p "choice=请输入编号并回车："

if "%choice%"=="1" "%PY%" app.py today
if "%choice%"=="2" goto :serve
if "%choice%"=="3" "%PY%" app.py week --days 7
if "%choice%"=="4" "%PY%" app.py report --quarter
if "%choice%"=="5" "%PY%" app.py replan
if "%choice%"=="6" "%PY%" app.py export --days 30
if "%choice%"=="7" "%PY%" app.py tasks
if "%choice%"=="0" exit /b 0
echo.
pause
exit /b 0

:serve
rem 端口已被占用就不再起第二个，直接开浏览器
netstat -ano | findstr /r /c:"127.0.0.1:8765 .*LISTENING" >nul
if not errorlevel 1 (
    echo 端口 8765 上已有工作台在运行，直接打开浏览器。
    start "" http://127.0.0.1:8765/
    echo.
    pause
    exit /b 0
)
echo 正在启动：http://127.0.0.1:8765/   （按 Ctrl+C 停止）
start "" http://127.0.0.1:8765/
"%PY%" app.py serve --port 8765
echo.
pause
exit /b 0
