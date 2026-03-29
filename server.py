#!/usr/bin/env python3
"""
MCP Manager - 动态管理 MCP 服务器的启用/禁用状态

这个 MCP 服务器提供两个工具：
1. enable_mcp - 启用指定的 MCP 服务器（从禁用列表移除）
2. disable_mcp - 禁用指定的 MCP 服务器（添加到禁用列表）
"""

import json
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 MCP 服务器实例
app = Server("mcp-manager")

# 配置文件路径
CLAUDE_JSON_PATH = Path.home() / ".claude.json"

def read_claude_json():
    """读取 claude.json 配置文件"""
    try:
        with open(CLAUDE_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise

def write_claude_json(data):
    """写入 claude.json 配置文件"""
    try:
        with open(CLAUDE_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("配置文件已更新")
    except Exception as e:
        logger.error(f"写入配置文件失败: {e}")
        raise

@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="enable_mcp",
            description="启用指定的 MCP 服务器（从禁用列表中移除）。启用后需要重启 Claude Code 才能生效。",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "要启用的 MCP 服务器名称（例如：12306, moji-weather, variflight 等）"
                    }
                },
                "required": ["server_name"]
            }
        ),
        Tool(
            name="disable_mcp",
            description="禁用指定的 MCP 服务器（添加到禁用列表）。禁用后需要重启 Claude Code 才能生效。",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "要禁用的 MCP 服务器名称（例如：12306, moji-weather, variflight 等）"
                    }
                },
                "required": ["server_name"]
            }
        ),
        Tool(
            name="list_disabled_mcps",
            description="列出当前所有被禁用的 MCP 服务器",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用"""

    if name == "enable_mcp":
        server_name = arguments.get("server_name")
        if not server_name:
            return [TextContent(type="text", text="错误：必须提供 server_name 参数")]

        try:
            # 读取配置
            config = read_claude_json()

            # 获取当前工作区的禁用列表
            # 尝试多种路径格式来匹配配置文件
            current_dir = Path.cwd()

            # 如果在 mcp-manager 目录中运行，需要获取父目录
            if current_dir.name == "mcp-manager":
                current_dir = current_dir.parent

            possible_paths = [
                str(current_dir).replace("\\", "/"),  # D:/AgentWorkspace
                str(current_dir),  # D:\AgentWorkspace
            ]

            workspace_path = None
            if "projects" in config:
                for path in possible_paths:
                    if path in config["projects"]:
                        workspace_path = path
                        break

            if workspace_path:
                disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

                if server_name in disabled_list:
                    # 从禁用列表移除
                    disabled_list.remove(server_name)
                    config["projects"][workspace_path]["disabledMcpServers"] = disabled_list

                    # 写回配置
                    write_claude_json(config)

                    result = f"✅ 成功启用 MCP 服务器: {server_name}\n\n"
                    result += f"已从禁用列表中移除。请重启 Claude Code 使更改生效。"
                    logger.info(f"已启用 MCP 服务器: {server_name}")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' 未在禁用列表中，无需启用"
                    logger.info(f"MCP 服务器 '{server_name}' 未被禁用")

            else:
                result = f"❌ 错误：找不到当前工作区的配置\n当前目录: {Path.cwd()}\n尝试的路径: {possible_paths}"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"❌ 启用 MCP 服务器失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    elif name == "disable_mcp":
        server_name = arguments.get("server_name")
        if not server_name:
            return [TextContent(type="text", text="错误：必须提供 server_name 参数")]

        try:
            # 读取配置
            config = read_claude_json()

            # 获取当前工作区的禁用列表
            # 尝试多种路径格式来匹配配置文件
            current_dir = Path.cwd()

            # 如果在 mcp-manager 目录中运行，需要获取父目录
            if current_dir.name == "mcp-manager":
                current_dir = current_dir.parent

            possible_paths = [
                str(current_dir).replace("\\", "/"),  # D:/AgentWorkspace
                str(current_dir),  # D:\AgentWorkspace
            ]

            workspace_path = None
            if "projects" in config:
                for path in possible_paths:
                    if path in config["projects"]:
                        workspace_path = path
                        break

            if workspace_path:
                disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

                if server_name not in disabled_list:
                    # 添加到禁用列表
                    disabled_list.append(server_name)
                    config["projects"][workspace_path]["disabledMcpServers"] = disabled_list

                    # 写回配置
                    write_claude_json(config)

                    result = f"✅ 成功禁用 MCP 服务器: {server_name}\n\n"
                    result += f"已添加到禁用列表。请重启 Claude Code 使更改生效。"
                    logger.info(f"已禁用 MCP 服务器: {server_name}")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' 已在禁用列表中"
                    logger.info(f"MCP 服务器 '{server_name}' 已被禁用")

            else:
                result = f"❌ 错误：找不到当前工作区的配置\n当前目录: {Path.cwd()}\n尝试的路径: {possible_paths}"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"❌ 禁用 MCP 服务器失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    elif name == "list_disabled_mcps":
        try:
            # 读取配置
            config = read_claude_json()

            # 获取当前工作区的禁用列表
            # 尝试多种路径格式来匹配配置文件
            current_dir = Path.cwd()

            # 如果在 mcp-manager 目录中运行，需要获取父目录
            if current_dir.name == "mcp-manager":
                current_dir = current_dir.parent

            possible_paths = [
                str(current_dir).replace("\\", "/"),  # D:/AgentWorkspace
                str(current_dir),  # D:\AgentWorkspace
            ]

            workspace_path = None
            if "projects" in config:
                for path in possible_paths:
                    if path in config["projects"]:
                        workspace_path = path
                        break

            if workspace_path:
                disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

                if disabled_list:
                    result = f"📋 当前被禁用的 MCP 服务器 ({len(disabled_list)} 个):\n\n"
                    for i, server in enumerate(disabled_list, 1):
                        result += f"{i}. {server}\n"
                else:
                    result = "✅ 当前没有禁用的 MCP 服务器"
            else:
                result = "❌ 错误：找不到当前工作区的配置"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"❌ 查询禁用列表失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    else:
        return [TextContent(type="text", text=f"❌ 未知的工具: {name}")]

async def main():
    """启动 MCP 服务器"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
