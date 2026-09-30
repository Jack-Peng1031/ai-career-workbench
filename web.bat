@echo off
chcp 65001 >nul
setlocal
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
python app.py serve --port 8765
echo.
pause
exit /b 0