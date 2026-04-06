@echo off
echo Stopping MCP Manager Web...
setlocal enabledelayedexpansion
for /f "usebackq" %%p in (`python -c "import yaml;print(yaml.safe_load(open('proxy/config.yaml')).get('web',{}).get('port',8090))"`) do set PORT=%%p
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :!PORT! ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)
echo Web server stopped.
pause
