@echo off
cd /d "%~dp0"
title 首次安装 dsh 运行依赖（仅轻量版需要，联网一次）
echo.
echo  正在用内置 Node 安装 dsh 运行时，约需几分钟，请耐心等待……
echo.
"node\node.exe" "node\node_modules\npm\bin\npm-cli.js" install "@deepseek-ai/dsh@0.2.1-rc.2" --no-audit --no-fund
echo.
if exist "node_modules\@deepseek-ai\dsh\lib\bin.js" (
  echo  依赖安装完成。以后直接双击「启动工作台.bat」即可。
) else (
  echo  安装似乎未成功，请检查网络后重跑本脚本。
)
echo.
pause
