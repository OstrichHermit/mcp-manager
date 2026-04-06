@echo off
echo Stopping MCP Proxy Manager Web...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8090 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)
echo Web server stopped.
pause
