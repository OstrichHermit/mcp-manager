# MCP Manager

A comprehensive tool for MCP server management, proxying, and monitoring — save context window space and manage your MCP ecosystem in one place.

MCP 服务器管理、代理与监控工具 —— 节省上下文窗口，统一管理你的 MCP 生态。

[English](README_EN.md) | [简体中文](README.md)

---

## ✨ Features

**🔌 MCP Server Management**
- Dynamically enable/disable MCP servers to save valuable context window space
- Support project-level (`project`) and global-level (`global`) disable scope
- List all MCP servers with their status (source, transport type, enabled/disabled)

**🔄 MCP Proxy**
- Connect to upstream MCP servers, filter tools by whitelist, and re-expose them to Claude Code
- Support both stdio (subprocess) and HTTP upstream transport modes
- Built-in OAuth mock endpoints for seamless HTTP proxy connections with Claude Code
- Support both stdio and HTTP proxy running modes

**🖥️ Web Dashboard**
- Real-time monitoring of all services' running status and PID
- Real-time log viewing (independent log panel per service)
- Dark/Light theme toggle
- One-click start/stop/restart all services
- WebSocket real-time push for status updates and log streaming

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/claude-code) CLI (for MCP server management features)

### 2. Installation

```bash
git clone https://github.com/OstrichHermit/mcp-manager.git
cd mcp-manager

pip install -r requirements.txt
```

### 3. Configure MCP Server Management

Add this to your `.mcp.json` or `~/.claude.json`:

```json
{
  "mcpServers": {
    "mcp-manager": {
      "command": "python",
      "args": ["path/to/mcp-manager/server.py"]
    }
  }
}
```

### 4. Configure Proxy

Copy the example configuration file and fill in your actual settings:

```bash
cp proxy/config.yaml.example proxy/config.yaml
```

**Minimal configuration example**:

```yaml
profiles:
  jina-mcp-server:
    name: "Jina"
    type: proxy
    transport: http
    url: https://mcp.jina.ai/v1
    headers:
      Authorization: "Bearer YOUR_API_KEY"
    tools:
      - read_url
    port: 3337
```

For more configuration examples (stdio upstream, external services, etc.), see `proxy/config.yaml.example`. For detailed field descriptions, see the [Configuration](#-configuration) section.

### 5. Start Services

**Recommended: Use the Web Dashboard**

The Web Dashboard is the preferred way to start and manage proxy services. All services can be started, stopped, and monitored from the dashboard with one click.

```bash
# Start Web Dashboard (run in background, no console window, for daily use)
web/start-web.bat

# Or visible console window (recommended for debugging)
web/start-web-visible.bat
```

After starting, visit the **Web Dashboard** at: http://localhost:8090 (host and port are configurable in the `web` section of `proxy/config.yaml`)

In the Web Dashboard you can:
- Start/stop/restart all services with one click
- Monitor running status and PID of all services in real time
- View real-time log output (independent panel per service)
- Toggle dark/light theme

> 💡 **Tip**: The Web Dashboard launches proxy services directly via command line (no need to write bat scripts manually). For `proxy` type services, it automatically runs `python proxy.py --profile {id} --serve --port {port} --project mcp-manager`. For `external` type services, it runs the configured `start_command`.

**Stop Web Dashboard**:

```bash
web/stop-web.bat
```

## 🔌 MCP Server Management

Dynamically manage the enable/disable state of MCP servers in Claude Code by modifying the `~/.claude.json` configuration file.

### MCP Tools

1. **list_mcps** — List all MCP servers (local + global), showing name, source, transport type, and status
2. **enable_mcp** — Enable a specified MCP server (remove from disabled list)
3. **disable_mcp** — Disable a specified MCP server (add to disabled list)
4. **list_disabled_mcps** — List all currently disabled MCP servers

### Usage Examples

```
# List all MCP servers and their status
list_mcps()

# Disable a server (project-level by default)
disable_mcp(server_name="moji-weather")

# Enable a server
enable_mcp(server_name="moji-weather")

# Disable globally (affects all projects)
disable_mcp(server_name="moji-weather", scope="global")

# List all disabled servers
list_disabled_mcps()
```

### How It Works

MCP Manager reads and modifies the `disabledMcpServers` list under the current workspace project entry in `~/.claude.json`. Local `.mcp.json` server definitions take priority over global configuration.

> 💡 **Tip**: After enabling or disabling an MCP server, you need to restart Claude Code for changes to take effect.

### Typical Workflow

When you need to use an occasionally-used MCP server:

1. Use `enable_mcp` to enable it
2. Restart Claude Code
3. Use the MCP server's tools to complete your task
4. Use `disable_mcp` to disable it
5. Restart Claude Code

This prevents rarely-used MCP servers from consuming valuable context window space.

## 🔄 MCP Proxy

MCP Proxy is a tool-filtering proxy that sits between Claude Code and upstream MCP servers. Its core value: **only expose the tools you need, not the entire upstream toolset**.

### Workflow

```
Claude Code → MCP Proxy (filter tools) → Upstream MCP Server
```

1. The proxy connects to an upstream MCP server (stdio subprocess or HTTP)
2. It retrieves the full list of upstream tools
3. It filters tools according to the configured whitelist
4. It re-exposes only the filtered tools to the downstream client (Claude Code)
5. Tool invocations are automatically forwarded to the upstream and results are returned

### Supported Upstream Types

**stdio upstream**: Launches the upstream MCP server as a subprocess, communicating via stdin/stdout. Supports two framing modes:
- `content-length` (default): Standard MCP framing format
- `newline`: Newline-delimited JSON messages

**HTTP upstream**: Connects to the upstream MCP server via HTTP POST, with SSE (Server-Sent Events) streaming response support.

### Tool Filtering

Specify a `tools` list in the configuration — only listed tools will be exposed to Claude Code:

```yaml
tools:
  - read_url          # Only expose read_url tool
  - brave_web_search  # Only expose brave_web_search tool
```

If `tools` is not specified, all upstream tools are exposed.

> 💡 **Tip**: For MCP servers with many tools where you only need a few, tool filtering can significantly save context window space.

### OAuth Mock

In HTTP mode, the proxy includes built-in OAuth mock endpoints that automatically satisfy Claude Code's OAuth discovery flow, requiring no real OAuth authentication:

- `/.well-known/oauth-protected-resource` (RFC 9728)
- `/.well-known/oauth-authorization-server` (RFC 8414)
- `/oauth/register` — Dynamic client registration (RFC 7591)
- `/oauth/authorize` — Auto-approve and redirect
- `/oauth/token` — Issue Bearer tokens

## 🖥️ Web Dashboard

A real-time monitoring dashboard built with FastAPI + vanilla JavaScript, for unified lifecycle management of all services.

**Core Features**:
- Real-time monitoring of all services' running status and PID
- Independent log panels (one panel per service with real-time log streaming)
- WebSocket real-time push (status updates every 2 seconds, log polling at 100ms)
- Dark/Light theme toggle (persisted to localStorage)
- One-click start/stop/restart all services
- Responsive layout (5 columns → 2 columns → single column)

**Layout**:
- Left sidebar: App title, WebSocket connection status, service list, system control buttons
- Right main area: Log panel grid (one panel per service with scroll, clear, and scroll-to-bottom controls)

### Service Launch Mechanism

The Web Dashboard launches service processes directly via `subprocess.Popen`, no need to write startup scripts manually:

- **proxy type**: Automatically runs `python proxy.py --profile {id} --serve --port {port} --project mcp-manager`
- **external type**: Runs the `start_command` specified in the configuration

## 🔗 Connecting External HTTP Servers

In addition to proxying existing MCP servers, you can connect external local HTTP servers to the MCP Manager ecosystem and manage them from the Web Dashboard. There are two connection methods:

### Method 1: Via Proxy (Recommended)

For servers that already have an MCP protocol interface (HTTP or stdio) and you want to filter tools before exposing them to Claude Code.

The proxy connects to the upstream server, retrieves the tool list, filters by whitelist, and re-exposes the filtered tools.

**Configuration example (HTTP upstream)**:

```yaml
profiles:
  my-http-server:
    name: "My HTTP Server"
    type: proxy
    transport: http
    port: 3340
    url: "http://127.0.0.1:3000/mcp"
    tools:
      - tool1
      - tool2
```

**Configuration example (stdio upstream)**:

```yaml
profiles:
  my-stdio-server:
    name: "My Stdio Server"
    type: proxy
    transport: stdio
    port: 3341
    command: "python"
    args: ["path/to/server.py"]
    framing: "content-length"    # or "newline"
    tools:
      - my_tool
```

After starting, register the proxy address in Claude Code's `.mcp.json`:

```json
{
  "mcpServers": {
    "proxy-my-server": {
      "type": "http",
      "url": "http://127.0.0.1:3340/mcp"
    }
  }
}
```

### Method 2: External Service (Web Dashboard Managed)

For services that need unified start/stop management in the Web Dashboard but don't go through the proxy layer (e.g., your own MCP server).

In this mode, the external service runs independently — the Web Dashboard only handles lifecycle management and log viewing, without proxying tool calls.

**Requirements**:

For an external service to be correctly managed by the MCP Manager Web Dashboard, the following conditions must be met:

1. **Process identification**: The `start_command` must include `--project mcp-manager` parameter. The Web Dashboard discovers service processes by matching the `mcp-manager` keyword in the command line.
2. **Service identification**: The `start_command` must include `--name {profile_id}` parameter. The Web Dashboard identifies the service by searching for this string in the process command line.
3. **Log file**: Specify the log file path via the `log_file` field. The Web Dashboard reads this file for real-time log display. The recommended log format is `[YYYY-MM-DD HH:MM:SS] message` for consistency.

**All of the above requirements must be implemented by yourself for external MCP servers that don't go through the proxy layer.**

**Configuration example**:

```yaml
profiles:
  my-service:
    name: "My Service"
    type: external
    start_command: "python path/to/server.py --transport http --host 127.0.0.1 --port 3000 --project mcp-manager --name my-service"
    log_file: "path/to/logs/my-service.log"
```

### Connection Workflow Summary

```
1. Add a profile in proxy/config.yaml
2. (external type) Adapt the external service's startup parameters, add --project mcp-manager, etc.
3. Start the service from the Web Dashboard
4. (proxy type) Register the proxy address in Claude Code's .mcp.json
5. Restart Claude Code and start using it
```

> 💡 **Tip**: Beyond tool filtering to save context window space, the proxy also provides logging, making it easier to troubleshoot issues.

## ⚙️ Configuration

### proxy/config.yaml

The configuration file is located at `proxy/config.yaml`, containing two top-level sections: `web` (Web Dashboard configuration) and `profiles` (service configuration).

```yaml
# Web Dashboard configuration
web:
  host: "0.0.0.0"   # Listen address (default: 0.0.0.0, listen on all interfaces)
  port: 8090          # Listen port

profiles:
  jina-mcp-server: ...
```

**Web configuration fields**:

| Field | Description | Default |
|-------|-------------|---------|
| `host` | Web Dashboard listen address | `0.0.0.0` |
| `port` | Web Dashboard listen port | `8090` |

> 💡 **Tip**: Restart the Web service (`web/stop-web.bat` → `web/start-web.bat`) after changing `web` configuration.

**profiles section** uses YAML dictionary format with profile ID as the key:

```yaml
profiles:
  # HTTP upstream proxy
  jina-mcp-server:                    # Profile ID (unique identifier)
    name: "Jina"                      # Display name in Web Dashboard
    type: proxy                       # proxy or external
    transport: http                   # http or stdio
    port: 3337                        # Proxy HTTP service port
    url: "https://mcp.jina.ai/v1"     # HTTP upstream URL
    headers:                          # Custom request headers (optional)
      Authorization: "Bearer YOUR_API_KEY"
    tools:                            # Tool whitelist (optional, omit to expose all)
      - read_url

  # stdio upstream proxy (shell mode)
  brave-search:
    name: "Brave"
    type: proxy
    transport: stdio
    port: 3338
    shell: "npx -y @modelcontextprotocol/server-brave-search"  # Full command string
    env:                              # Environment variables (optional)
      BRAVE_API_KEY: "YOUR_API_KEY"
    framing: "newline"                # Framing: content-length (default) or newline
    tools:
      - brave_web_search

  # stdio upstream proxy (exec mode)
  my-stdio-server:
    name: "My Stdio Server"
    type: proxy
    transport: stdio
    port: 3341
    command: "python"                 # Launch command
    args: ["path/to/server.py"]       # Command arguments
    framing: "content-length"         # Framing format
    tools:
      - my_tool

  # No tools specified = expose all tools
  chrome-devtools:
    name: "Chrome"
    type: proxy
    transport: stdio
    port: 3339
    shell: "npx -y chrome-devtools-mcp@latest"
    framing: "newline"

  # External service (no proxy layer, managed by Web Dashboard)
  memu:
    name: "MemU"
    type: external                    # External service type
    start_command: "python path/to/server.py --port 3000 --project mcp-manager --name memu/"
    stop_command: "..."               # Optional, custom stop command
    log_file: "path/to/logs/memu.log" # Log file path
```

### Configuration Reference

**Common fields**:

| Field | Description | Applies to |
|-------|-------------|------------|
| `name` | Display name in Web Dashboard | All |
| `type` | Service type | All (`proxy` / `external`) |
| `log_file` | Log file path (default: `proxy/logs/{id}.log`) | All |

**proxy type fields**:

| Field | Description | Values |
|-------|-------------|--------|
| `transport` | Upstream transport mode | `http`, `stdio` |
| `port` | Proxy HTTP service port | Any available port |
| `tools` | Tool whitelist | Array of tool names; omit to expose all |
| `timeout` | Upstream request timeout (seconds) | Positive integer (default 30) |

**proxy + http transport fields**:

| Field | Description |
|-------|-------------|
| `url` | HTTP upstream URL |
| `headers` | Custom request headers (key-value pairs) |

**proxy + stdio transport fields**:

| Field | Description |
|-------|-------------|
| `shell` | Full command string (shell mode) |
| `command` + `args` | Launch command and arguments (exec mode, alternative to `shell`) |
| `env` | Environment variables (key-value pairs) |
| `framing` | Framing format: `content-length` (default) or `newline` |

**external type fields**:

| Field | Description |
|-------|-------------|
| `start_command` | Startup command (must contain `mcp-manager` and profile ID) |
| `stop_command` | Stop command (optional, default: `taskkill`) |
| `log_file` | Log file path (must be readable) |

## 🔧 Troubleshooting

### Proxy Service Fails to Start

1. Check `proxy/config.yaml` for correct configuration (field names, indentation, etc.)
2. Verify the upstream MCP server is accessible (test connection manually)
3. Check if the port is already in use: `netstat -ano | findstr <port>`
4. View logs in the Web Dashboard for specific error messages

### Web Dashboard Inaccessible

1. Confirm the Web service is running: `web/start-web.bat`
2. Check if the port configured in `web.port` of `proxy/config.yaml` is already in use
3. Visit `http://localhost:{web.port}` in your browser

### External Service Shows as Stopped (Actually Running)

1. Confirm `start_command` contains the string `mcp-manager` (the Web Dashboard matches processes by this keyword)
2. Confirm `start_command` contains the profile ID (used for precise identification)
3. Check logs in the Web Dashboard for errors

### OAuth Authentication Failure

1. Confirm you're using the proxy's HTTP endpoint (`http://127.0.0.1:<port>/mcp`)
2. The proxy includes built-in OAuth mock — no additional authentication configuration needed
3. If issues persist, check the proxy logs for OAuth request records

### Tool Invocation Failure

1. Confirm the proxy service is running (check status in Web Dashboard)
2. Confirm the tool name is in the whitelist (`tools` configuration)
3. Confirm the tool exists on the upstream server (check proxy startup logs)
4. View proxy logs in the Web Dashboard for detailed error messages

## 📄 License

[MIT](LICENSE)

## 🤝 Contributing

Issues and Pull Requests are welcome!
