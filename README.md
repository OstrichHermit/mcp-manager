# MCP Manager

中文 | **[English](README_EN.md)**

一个轻量级的 MCP（Model Context Protocol）服务器，用于动态启用和禁用其他 MCP 服务器，帮助你节省宝贵的上下文窗口空间。

通过修改 `~/.claude.json` 配置文件，与 [Claude Code](https://claude.ai/claude-code) 配合使用。

## 功能

- `enable_mcp` - 启用指定的 MCP 服务器（从禁用列表移除）
- `disable_mcp` - 禁用指定的 MCP 服务器（添加到禁用列表）
- `list_disabled_mcps` - 列出当前所有被禁用的 MCP 服务器

## 安装

```bash
pip install -r requirements.txt
```

## 配置

在你的 `.mcp.json` 或 `~/.claude.json` 中添加：

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

## 使用方法

### 启用 MCP 服务器

```
使用工具：mcp__mcp-manager__enable_mcp
参数：
- server_name: 要启用的 MCP 服务器名称（例如 "12306", "moji-weather", "variflight"）
```

### 禁用 MCP 服务器

```
使用工具：mcp__mcp-manager__disable_mcp
参数：
- server_name: 要禁用的 MCP 服务器名称
```

### 查看禁用列表

```
使用工具：mcp__mcp-manager__list_disabled_mcps
无需参数
```

## 工作原理

这个 MCP 服务器通过读取和修改 `~/.claude.json` 配置文件中当前工作区项目下的 `disabledMcpServers` 列表来管理 MCP 服务器的启用/禁用状态。

## 注意事项

启用或禁用 MCP 服务器后，需要重启 Claude Code 才能使更改生效。

## 典型使用场景

当你需要使用某个不常用的 MCP 服务器时：

1. 使用 `enable_mcp` 启用它
2. 重启 Claude Code
3. 使用该 MCP 服务器的工具完成任务
4. 使用 `disable_mcp` 禁用它
5. 重启 Claude Code

这样可以避免不常用的 MCP 服务器占用宝贵的上下文窗口空间。

## 许可证

[MIT](LICENSE)
