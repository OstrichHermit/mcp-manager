# MCP Manager

MCP 服务器管理、代理与监控工具 —— 节省上下文窗口，统一管理你的 MCP 生态。

A comprehensive tool for MCP server management, proxying, and monitoring — save context window space and manage your MCP ecosystem in one place.

[English](README_EN.md) | [简体中文](README.md)

---

## ✨ 功能特性

**🔌 MCP 服务器管理**
- 动态启用/禁用 MCP 服务器，节省宝贵的上下文窗口空间
- 支持项目级（`project`）和全局级（`global`）禁用范围
- 列出所有 MCP 服务器及其状态（来源、传输类型、启用/禁用）

**🔄 MCP 代理**
- 连接上游 MCP 服务器，按白名单过滤工具后重新暴露给 Claude Code
- 支持 stdio（子进程）和 HTTP 两种上游传输方式
- 内置 OAuth 模拟端点，让 Claude Code 无缝连接 HTTP 代理
- 同时支持 stdio 和 HTTP 两种代理运行模式

**🖥️ Web 管理面板**
- 实时监控所有服务的运行状态和 PID
- 实时查看日志输出（每个服务独立日志面板）
- 深色/浅色主题切换
- 一键启动/停止/重启所有服务
- WebSocket 实时推送状态更新和日志流

## 🚀 快速开始

### 1. 前置要求

- Python 3.10+
- [Claude Code](https://claude.ai/claude-code) CLI（用于 MCP 服务器管理功能）

### 2. 安装

```bash
git clone https://github.com/OstrichHermit/mcp-manager.git
cd mcp-manager

pip install -r requirements.txt
```

### 3. 配置 MCP 服务器管理

在 `.mcp.json` 或 `~/.claude.json` 中添加：

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

### 4. 配置代理

复制示例配置文件并填入实际配置：

```bash
cp proxy/config.yaml.example proxy/config.yaml
```

**最小配置示例**：

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

更多配置示例（stdio 上游、外部服务等），请参见 `proxy/config.yaml.example`。详细字段说明请参见 [配置](#-配置) 章节。

### 5. 启动服务

**推荐方式：使用 Web 管理面板**

Web 管理面板是启动和管理代理服务的首选方式。所有服务都可以在面板中一键启动、停止和监控。

```bash
# 启动 Web 管理面板（后台运行，无控制台窗口，日常使用）
web/start-web.bat

# 或可见控制台窗口（推荐调试时使用）
web/start-web-visible.bat
```

启动后访问 **Web 管理面板**：http://localhost:8090（地址和端口可在 `proxy/config.yaml` 的 `web` 段配置）

在 Web 管理面板中你可以：
- 一键启动/停止/重启所有服务
- 实时监控所有服务的运行状态和 PID
- 查看实时日志输出（每个服务独立面板）
- 切换深色/浅色主题

> 💡 **提示**：Web 管理面板通过命令行直接启动代理服务（无需手动编写 bat 脚本）。对于 `proxy` 类型服务，自动运行 `python proxy.py --profile {id} --serve --port {port} --project mcp-manager`。对于 `external` 类型服务，运行配置的 `start_command`。

**停止 Web 管理面板**：

```bash
web/stop-web.bat
```

## 🔌 MCP 服务器管理

通过修改 `~/.claude.json` 配置文件，动态管理 Claude Code 中 MCP 服务器的启用/禁用状态。

### MCP 工具

1. **list_mcps** — 列出所有 MCP 服务器（本地 + 全局），显示名称、来源、传输类型和状态
2. **enable_mcp** — 启用指定的 MCP 服务器（从禁用列表移除）
3. **disable_mcp** — 禁用指定的 MCP 服务器（添加到禁用列表）
4. **list_disabled_mcps** — 列出当前所有被禁用的 MCP 服务器

### 使用示例

```
# 列出所有 MCP 服务器及其状态
list_mcps()

# 禁用某个服务器（默认项目级生效）
disable_mcp(server_name="moji-weather")

# 启用某个服务器
enable_mcp(server_name="moji-weather")

# 全局禁用（所有项目生效）
disable_mcp(server_name="moji-weather", scope="global")

# 列出所有被禁用的服务器
list_disabled_mcps()
```

### 工作原理

MCP Manager 读取并修改 `~/.claude.json` 中当前工作区项目下的 `disabledMcpServers` 列表。本地 `.mcp.json` 中的服务器定义优先于全局配置。

> 💡 **提示**：启用或禁用 MCP 服务器后，需要重启 Claude Code 才能使更改生效。

### 典型工作流程

当你需要使用某个不常用的 MCP 服务器时：

1. 使用 `enable_mcp` 启用它
2. 重启 Claude Code
3. 使用该 MCP 服务器的工具完成任务
4. 使用 `disable_mcp` 禁用它
5. 重启 Claude Code

这样可以避免不常用的 MCP 服务器占用宝贵的上下文窗口空间。

## 🔄 MCP Proxy 代理

MCP Proxy 是一个工具过滤代理，位于 Claude Code 和上游 MCP 服务器之间。它的核心价值：**只暴露你需要的工具，而不是上游服务器的全部工具**。

### 工作流程

```
Claude Code → MCP Proxy（过滤工具）→ 上游 MCP 服务器
```

1. 代理连接上游 MCP 服务器（stdio 子进程或 HTTP）
2. 获取上游的全部工具列表
3. 按配置的白名单过滤工具
4. 将过滤后的工具重新暴露给下游客户端（Claude Code）
5. 工具调用时自动转发到上游并返回结果

### 支持的上游类型

**stdio 上游**：通过子进程启动上游 MCP 服务器，通过标准输入/输出通信。支持两种帧格式：
- `content-length`（默认）：标准 MCP 帧格式
- `newline`：换行符分隔的 JSON 消息

**HTTP 上游**：通过 HTTP POST 连接上游 MCP 服务器，支持 SSE（Server-Sent Events）流式响应。

### 工具过滤

在配置中指定 `tools` 列表，只有列表中的工具会被暴露给 Claude Code：

```yaml
tools:
  - read_url          # 只暴露 read_url 工具
  - brave_web_search  # 只暴露 brave_web_search 工具
```

如果不指定 `tools`，则暴露上游的全部工具。

> 💡 **提示**：对于工具繁多但只需使用其中几个的 MCP 服务器，工具过滤可以显著节省上下文窗口空间。

### OAuth 模拟

HTTP 模式下，代理内置了 OAuth 模拟端点，自动满足 Claude Code 的 OAuth 发现流程，无需真实 OAuth 认证：

- `/.well-known/oauth-protected-resource`（RFC 9728）
- `/.well-known/oauth-authorization-server`（RFC 8414）
- `/oauth/register` — 动态客户端注册（RFC 7591）
- `/oauth/authorize` — 自动批准并重定向
- `/oauth/token` — 签发 Bearer Token

## 🖥️ Web 管理面板

基于 FastAPI + 原生 JavaScript 构建的实时监控仪表板，用于统一管理所有服务的生命周期。

**核心功能**：
- 实时监控所有服务的运行状态和 PID
- 独立日志面板（每个服务一个面板，实时日志流）
- WebSocket 实时推送（每 2 秒更新状态，日志 100ms 轮询）
- 深色/浅色主题切换（持久化到 localStorage）
- 一键启动/停止/重启所有服务
- 响应式布局（5 列 → 2 列 → 单列）

**布局**：
- 左侧边栏：应用标题、WebSocket 连接状态、服务列表、系统控制按钮
- 右侧主区域：日志面板网格（每个服务一个面板，支持滚动、清空、回到底部）

### 服务启动机制

Web 管理面板通过 `subprocess.Popen` 直接启动服务进程，无需手动编写启动脚本：

- **proxy 类型**：自动运行 `python proxy.py --profile {id} --serve --port {port} --project mcp-manager`
- **external 类型**：运行配置中指定的 `start_command`

## 🔗 接入外部 HTTP 服务器

除了代理已有的 MCP 服务器外，你还可以将外部的本地 HTTP 服务器接入 MCP Manager 体系，并通过 Web 管理面板统一管理。有两种接入方式：

### 方式一：通过代理（推荐）

适用于已有 MCP 协议接口（HTTP 或 stdio）的服务器，并希望在暴露给 Claude Code 之前过滤工具。

代理连接上游服务器，获取工具列表，按白名单过滤后重新暴露。

**配置示例（HTTP 上游）**：

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

**配置示例（stdio 上游）**：

```yaml
profiles:
  my-stdio-server:
    name: "My Stdio Server"
    type: proxy
    transport: stdio
    port: 3341
    command: "python"
    args: ["path/to/server.py"]
    framing: "content-length"    # 或 "newline"
    tools:
      - my_tool
```

启动后，在 Claude Code 的 `.mcp.json` 中注册代理地址：

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

### 方式二：外部服务（Web 管理面板管理）

适用于需要在 Web 管理面板中统一管理启动/停止，但不需要经过代理层的已有 MCP 服务器（例如你自己的 MCP 服务器）。

在此模式下，外部服务独立运行，Web 管理面板仅负责生命周期管理和日志查看，不代理工具调用。

要让外部服务被 MCP Manager 的 Web 管理面板正确管理，需满足以下条件：

1. **进程识别**：`start_command` 必须包含 `--project mcp-manager` 参数。Web 管理面板通过匹配命令行中的 `mcp-manager` 关键词来发现服务进程。
2. **服务识别**：`start_command` 必须包含 `--name {profile_id}` 参数。Web 管理面板通过在进程命令行中搜索该字符串来识别服务。
3. **日志文件**：通过 `log_file` 字段指定日志文件路径，Web 管理面板通过读取该文件来进行实时日志显示。推荐的日志格式为 `[YYYY-MM-DD HH:MM:SS] message` 以保持一致性。

**以上所有要求均需要自行为不经过代理层的已有 MCP 服务器实现。**

**配置示例**：

```yaml
profiles:
  my-service:
    name: "My Service"
    type: external
    start_command: "python path/to/server.py --transport http --host 127.0.0.1 --port 3000 --project mcp-manager --name my-service"
    log_file: "path/to/logs/my-service.log"
```

### 接入流程总结

```
1. 在 proxy/config.yaml 中添加 profile 配置
2. external 类型需要适配外部服务的启动参数和日志输出
3. proxy 类型需要在 Claude Code 的 .mcp.json 中注册代理地址
4. 从 Web 管理面板启动服务
5. 重启 Claude Code，开始使用
```

> 💡 **提示**：除了通过工具过滤节省上下文窗口空间外，代理还提供了日志记录功能，方便排查问题。

## ⚙️ 配置

### proxy/config.yaml

配置文件位于 `proxy/config.yaml`，包含两个顶级段：`web`（Web 管理面板配置）和 `profiles`（服务配置）。

```yaml
# Web 管理面板配置
web:
  host: "0.0.0.0"   # 监听地址（默认 0.0.0.0，监听所有网卡）
  port: 8090          # 监听端口

profiles:
  jina-mcp-server: ...
```

**Web 配置字段**：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `host` | Web 管理面板监听地址 | `0.0.0.0` |
| `port` | Web 管理面板监听端口 | `8090` |

> 💡 **提示**：修改 `web` 配置后需重启 Web 服务（`web/stop-web.bat` → `web/start-web.bat`）。

**profiles 段**使用 YAML 字典格式，以 profile ID 为键：

```yaml
profiles:
  # HTTP 上游代理
  jina-mcp-server:                    # Profile ID（唯一标识符）
    name: "Jina"                      # Web 管理面板中的显示名称
    type: proxy                       # proxy 或 external
    transport: http                   # http 或 stdio
    port: 3337                        # 代理 HTTP 服务端口
    url: "https://mcp.jina.ai/v1"     # HTTP 上游地址
    headers:                          # 自定义请求头（可选）
      Authorization: "Bearer YOUR_API_KEY"
    tools:                            # 工具白名单（可选，不填则暴露全部）
      - read_url

  # stdio 上游代理（shell 模式）
  brave-search:
    name: "Brave"
    type: proxy
    transport: stdio
    port: 3338
    shell: "npx -y @modelcontextprotocol/server-brave-search"  # 完整命令字符串
    env:                              # 环境变量（可选）
      BRAVE_API_KEY: "YOUR_API_KEY"
    framing: "newline"                # 帧格式：content-length（默认）或 newline
    tools:
      - brave_web_search

  # stdio 上游代理（exec 模式）
  my-stdio-server:
    name: "My Stdio Server"
    type: proxy
    transport: stdio
    port: 3341
    command: "python"                 # 启动命令
    args: ["path/to/server.py"]       # 命令参数
    framing: "content-length"         # 帧格式
    tools:
      - my_tool

  # 不指定 tools 则暴露全部工具
  chrome-devtools:
    name: "Chrome"
    type: proxy
    transport: stdio
    port: 3339
    shell: "npx -y chrome-devtools-mcp@latest"
    framing: "newline"

  # 外部服务（不经过代理层，由 Web 管理面板管理）
  memu:
    name: "MemU"
    type: external                    # 外部服务类型
    start_command: "python path/to/server.py --port 3000 --project mcp-manager --name memu/"
    stop_command: "..."               # 可选，自定义停止命令
    log_file: "path/to/logs/memu.log" # 日志文件路径
```

### 配置参考

**通用字段**：

| 字段 | 说明 | 适用范围 |
|------|------|----------|
| `name` | Web 管理面板中的显示名称 | 所有类型 |
| `type` | 服务类型 | 所有类型（`proxy` / `external`） |
| `log_file` | 日志文件路径（默认：`proxy/logs/{id}.log`） | 所有类型 |

**proxy 类型字段**：

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `transport` | 上游传输方式 | `http`、`stdio` |
| `port` | 代理 HTTP 服务端口 | 任意可用端口 |
| `tools` | 工具白名单 | 工具名称数组；不填则暴露全部 |
| `timeout` | 上游请求超时时间（秒） | 正整数（默认 30） |

**proxy + http 传输字段**：

| 字段 | 说明 |
|------|------|
| `url` | HTTP 上游地址 |
| `headers` | 自定义请求头（键值对） |

**proxy + stdio 传输字段**：

| 字段 | 说明 |
|------|------|
| `shell` | 完整命令字符串（shell 模式） |
| `command` + `args` | 启动命令及参数（exec 模式，`shell` 的替代方案） |
| `env` | 环境变量（键值对） |
| `framing` | 帧格式：`content-length`（默认）或 `newline` |

**external 类型字段**：

| 字段 | 说明 |
|------|------|
| `start_command` | 启动命令（必须包含 `mcp-manager` 和 profile ID） |
| `stop_command` | 停止命令（可选，默认：`taskkill`） |
| `log_file` | 日志文件路径（必须可读） |

## 🔧 故障排查

### 代理服务启动失败

1. 检查 `proxy/config.yaml` 配置是否正确（字段名、缩进等）
2. 确认上游 MCP 服务器是否可用（手动测试连接）
3. 检查端口是否被占用：`netstat -ano | findstr <port>`
4. 在 Web 管理面板中查看日志获取具体错误信息

### Web 管理面板无法访问

1. 确认 Web 服务已启动：`web/start-web.bat`
2. 检查 `proxy/config.yaml` 中 `web.port` 配置的端口是否被占用
3. 在浏览器访问 `http://localhost:{web.port}`

### 外部服务显示已停止（实际在运行）

1. 确认 `start_command` 包含字符串 `mcp-manager`（Web 管理面板通过此关键词匹配进程）
2. 确认 `start_command` 包含 profile ID（用于精确识别）
3. 在 Web 管理面板中查看日志排查错误

### OAuth 认证失败

1. 确认使用的是代理的 HTTP 端点（`http://127.0.0.1:<port>/mcp`）
2. 代理内置 OAuth 模拟，无需额外配置认证信息
3. 如果仍有问题，检查代理日志中的 OAuth 请求记录

### 工具调用失败

1. 确认代理服务正在运行（在 Web 管理面板查看状态）
2. 确认工具名称在白名单中（`tools` 配置）
3. 确认上游服务器中确实存在该工具（查看代理启动日志）
4. 在 Web 管理面板中查看代理日志获取详细错误信息

## 📄 许可证

[MIT](LICENSE)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
