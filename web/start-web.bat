@echo off
cd /d "%~dp0.."
start "" /b pythonw web\web_server.py --project mcp-manager
exit
