# 杀掉 windows-mcp streamable-http 服务进程树（uvx 拉起的 uvx.exe + python）
# 匹配串注意：实际命令行是 windows-mcp.exe" serve，中间隔了 .exe"，
# 所以必须用 *windows-mcp*serve* 而不是 *windows-mcp serve*（踩过坑）
# 排除自身和父进程，防止 Where-Object 匹配到自己的命令行自杀（踩过两次坑）
$mypid = $PID
$parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$mypid").ParentProcessId
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like '*windows-mcp*serve*' -and
    $_.ProcessId -ne $mypid -and
    $_.ProcessId -ne $parent
} | ForEach-Object {
    Write-Host ("killing " + $_.ProcessId + " : " + $_.Name)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "done"
