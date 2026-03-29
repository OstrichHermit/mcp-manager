# MCP Manager

A lightweight MCP (Model Context Protocol) server for dynamically enabling and disabling other MCP servers, helping you save valuable context window space.

Works with [Claude Code](https://claude.ai/claude-code) by modifying the `~/.claude.json` configuration file.

## Features

- `enable_mcp` - Enable an MCP server by removing it from the disabled list
- `disable_mcp` - Disable an MCP server by adding it to the disabled list
- `list_disabled_mcps` - List all currently disabled MCP servers

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

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

## Usage

### Enable an MCP server

```
Use tool: mcp__mcp-manager__enable_mcp
Arguments:
- server_name: The MCP server name to enable (e.g. "12306", "moji-weather", "variflight")
```

### Disable an MCP server

```
Use tool: mcp__mcp-manager__disable_mcp
Arguments:
- server_name: The MCP server name to disable
```

### List disabled servers

```
Use tool: mcp__mcp-manager__list_disabled_mcps
No arguments needed
```

## How It Works

This MCP server reads and modifies the `disabledMcpServers` list in your `~/.claude.json` configuration file under the current workspace project entry.

## Important Note

After enabling or disabling an MCP server, you need to restart Claude Code for the changes to take effect.

## Typical Workflow

When you need to use an occasionally-used MCP server:

1. Use `enable_mcp` to enable it
2. Restart Claude Code
3. Use the MCP server's tools to complete your task
4. Use `disable_mcp` to disable it
5. Restart Claude Code

This prevents rarely-used MCP servers from consuming valuable context window space.

## License

[MIT](LICENSE)
