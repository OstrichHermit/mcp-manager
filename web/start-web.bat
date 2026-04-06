@echo off
cd /d "%~dp0.."
start "" /b pythonw web\web_server.py --port 8090 --project mcp-manager
exit
