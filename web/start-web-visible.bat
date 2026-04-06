@echo off
title MCP Manager Web
cd /d "%~dp0.."
python -m web.web_server
pause
