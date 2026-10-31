@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Td.Meng dsh Workbench
"node\node.exe" start.js
echo.
echo Workbench stopped. Press any key to close this window.
pause >nul
