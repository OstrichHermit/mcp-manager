# windows-mcp streamable-http 常驻服务启动脚本
# 为什么不用 stdio：proxy.py 的 asyncio readline 默认 64KB 限制，
# 截图等大 base64 响应会炸掉流导致整个 MCP 挂死（2026-09-14 排查结论）
# PATH 设为注册表 Machine+User 完整值。
# 注：PowerShell 工具裸名启动的 bug 已在源码修复为绝对路径回退
#（2026-09-15，windows_mcp/powershell/service.py 的 _resolve_shell），
# 不再依赖启动环境 PATH，但完整 PATH 仍是好习惯
$env:PATH = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
# 输出重定向到 log_file（manager Web 控制台的日志面板读这个文件）。
# 用 cmd /c 做字节级重定向：PowerShell 原生 2>&1 会把 stderr 包装成 ErrorRecord，不干净
cmd /c "uvx windows-mcp==0.8.6 serve --transport streamable-http --host 127.0.0.1 --port 8340 >> D:\AgentWorkspace\mcp-manager\proxy\logs\windows-mcp-http.log 2>&1"
