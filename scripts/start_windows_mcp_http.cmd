@echo off
rem windows-mcp streamable-http 常驻服务启动脚本
rem 为什么不用 stdio：proxy.py 的 asyncio readline 默认 64KB 限制，
rem 截图等大 base64 响应会炸掉流导致整个 MCP 挂死（2026-09-14 排查结论）
rem PATH 必须用注册表里的完整 Machine+User 值：
rem windows-mcp 内部 shutil.which("pwsh")/Popen("powershell") 依赖完整 PATH，
rem 精简 PATH 会导致 PowerShell 工具报 WinError 2
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%b"
set "PATH=%SYS_PATH%;%USR_PATH%"
uvx windows-mcp serve --transport streamable-http --host 127.0.0.1 --port 8340
