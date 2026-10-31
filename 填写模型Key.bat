@echo off
cd /d "%~dp0"
title 填写模型 Key
echo.
echo  正在用记事本打开 Key 配置文件……
echo.
echo  把火山方舟 Key 填到 VOLC_ARK_API_KEY= 这一行等号后面，
echo  保存(Ctrl+S)后关掉记事本，再双击「启动工作台.bat」。
echo.
if not exist "%~dp0home\.env" (
  echo  [警告] 没找到 home\.env，请确认整包已完整解压到同一个文件夹。
  pause
  exit /b 1
)
start "" notepad.exe "%~dp0home\.env"
timeout /t 8 >nul
