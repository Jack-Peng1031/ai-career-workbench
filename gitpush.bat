@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo           一键 Git 推送脚本
echo ========================================
echo.

REM ============ 检查是否在 Git 仓库中 ============
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前目录不是 Git 仓库，请把脚本放到项目根目录。
    pause
    exit /b 1
)

REM ============ 获取当前分支名 ============
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%i
echo [信息] 当前分支: %BRANCH%
echo.

REM ============ 显示当前状态 ============
git status -s
echo.

REM ============ 检查是否有改动 ============
git diff --quiet && git diff --cached --quiet
if not errorlevel 1 (
    echo [信息] 没有检测到任何改动，无需提交。
    echo.
    goto :PUSH
)

REM ============ 输入提交说明 ============
set /p MSG=请输入本次提交说明（直接回车使用默认）: 
if "%MSG%"=="" set MSG=update: %date% %time%

echo.
echo [信息] 提交说明: %MSG%
echo.

REM ============ 添加、提交 ============
git add .
git commit -m "%MSG%"
if errorlevel 1 (
    echo [错误] 提交失败。
    pause
    exit /b 1
)

:PUSH
echo.
echo [信息] 正在推送到远程 %BRANCH% ...
git push origin %BRANCH%
if errorlevel 1 (
    echo.
    echo [错误] 推送失败，可能是远程有新提交。尝试拉取后再推送...
    git pull --rebase origin %BRANCH%
    if errorlevel 1 (
        echo [错误] 拉取失败，请手动解决冲突。
        pause
        exit /b 1
    )
    git push origin %BRANCH%
    if errorlevel 1 (
        echo [错误] 推送仍然失败，请检查网络或远程配置。
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo           推送成功 ✅
echo ========================================
pause
endlocal