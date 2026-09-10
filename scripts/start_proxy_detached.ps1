# 清理可能残留的 3340 占用进程
$conn = Get-NetTCPConnection -LocalPort 3340 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $conn | ForEach-Object {
        Write-Output "杀残留 PID $($_.OwningProcess)"
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

# 以独立隐藏进程启动代理（脱离 CC 会话树）
Start-Process -FilePath "python" `
    -ArgumentList "proxy.py", "--profile", "windows-mcp", "--serve", "--port", "3340", "--project", "mcp-manager" `
    -WorkingDirectory "D:\AgentWorkspace\mcp-manager\proxy" `
    -WindowStyle Hidden

Start-Sleep -Seconds 8

# 验证
$listen = Get-NetTCPConnection -LocalPort 3340 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    $opid = ($listen | Select-Object -First 1).OwningProcess
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$opid"
    $pp = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -ErrorAction SilentlyContinue
    Write-Output "3340 LISTENING, PID=$opid, 父进程=$($pp.Name) (应为独立 powershell/cmd, 非 bash)"
} else {
    Write-Output "3340 未监听, 启动失败"
}
