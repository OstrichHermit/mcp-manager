#!/usr/bin/env python3
"""
MCP Manager - 动态管理 MCP 服务器的启用/禁用状态

这个 MCP 服务器提供以下工具：
1. list_mcps - 列出所有 MCP 服务器（本地 + 全局），显示名称、来源、状态、类型
2. enable_mcp - 启用指定的 MCP 服务器（从禁用列表移除），支持项目/全局范围
3. disable_mcp - 禁用指定的 MCP 服务器（添加到禁用列表），支持项目/全局范围
4. list_disabled_mcps - 列出当前被禁用的 MCP 服务器，显示来源信息
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


def get_workspace_path(config: dict) -> str | None:
    """
    从 .claude.json 配置中提取当前工作区的路径。

    处理当前目录在 mcp-manager 子目录中的情况（需要跳到父目录），
    尝试正斜杠和反斜杠两种路径格式来匹配。

    Args:
        config: .claude.json 的完整配置字典

    Returns:
        匹配到的 workspace_path 字符串，找不到则返回 None
    """
    current_dir = Path.cwd()

    # 如果在 mcp-manager 目录中运行，需要获取父目录
    if current_dir.name == "mcp-manager":
        current_dir = current_dir.parent

    # 尝试正斜杠和反斜杠两种路径格式
    possible_paths = [
        str(current_dir).replace("\\", "/"),  # D:/AgentWorkspace
        str(current_dir),  # D:\AgentWorkspace
    ]

    if "projects" in config:
        for path in possible_paths:
            if path in config["projects"]:
                return path

    return None


def get_all_servers(config: dict, workspace_path: str | None) -> dict:
    """
    收集所有 MCP 服务器信息（全局 + 本地）。

    从 .claude.json 的 mcpServers 读取全局服务器，
    从 {workspace_path}/.mcp.json 的 mcpServers 读取本地服务器。
    本地服务器优先（同名覆盖全局）。

    Args:
        config: .claude.json 的完整配置字典
        workspace_path: 当前工作区路径（用于读取 .mcp.json）

    Returns:
        字典，格式: {"server_name": {"source": "local"/"global", "config": {...}}, ...}
    """
    servers: dict[str, dict] = {}

    # 1. 读取全局服务器（.claude.json 的 mcpServers）
    global_servers = config.get("mcpServers", {})
    for name, srv_config in global_servers.items():
        servers[name] = {"source": "global", "config": srv_config}

    # 2. 读取本地服务器（.mcp.json 的 mcpServers），覆盖全局同名服务器
    if workspace_path:
        mcp_json_path = Path(workspace_path) / ".mcp.json"
        try:
            with open(mcp_json_path, 'r', encoding='utf-8') as f:
                mcp_data = json.load(f)
            local_servers = mcp_data.get("mcpServers", {})
            for name, srv_config in local_servers.items():
                servers[name] = {"source": "local", "config": srv_config}
        except FileNotFoundError:
            logger.debug(f"未找到本地 .mcp.json: {mcp_json_path}")
        except Exception as e:
            logger.warning(f"读取 .mcp.json 失败: {e}")

    return servers


def get_server_type(srv_config: dict) -> str:
    """
    从服务器配置推断传输类型。

    Args:
        srv_config: 服务器配置字典

    Returns:
        "http" 或 "stdio"
    """
    if srv_config.get("type") == "http" or "url" in srv_config:
        return "http"
    return "stdio"


def get_disabled_set(config: dict, workspace_path: str) -> set[str]:
    """获取当前工作区的被禁用服务器集合"""
    return set(config["projects"][workspace_path].get("disabledMcpServers", []))


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="list_mcps",
            description="列出所有 MCP 服务器（本地 + 全局），显示名称、来源（本地/全局）、状态（启用/禁用）和传输类型（stdio/http）。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="enable_mcp",
            description="启用指定的 MCP 服务器（从禁用列表中移除）。启用后需要重启 Claude Code 才能生效。",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "要启用的 MCP 服务器名称（例如：12306, moji-weather, variflight 等）"
                    },
                    "scope": {
                        "type": "string",
                        "description": "作用范围：\"project\" 只在当前项目中启用（默认），\"global\" 在所有项目中启用",
                        "enum": ["project", "global"]
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
                    },
                    "scope": {
                        "type": "string",
                        "description": "作用范围：\"project\" 只在当前项目中禁用（默认），\"global\" 在所有项目中禁用",
                        "enum": ["project", "global"]
                    }
                },
                "required": ["server_name"]
            }
        ),
        Tool(
            name="list_disabled_mcps",
            description="列出当前所有被禁用的 MCP 服务器，显示每个服务器的来源（本地/全局）。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "list_mcps":
        try:
            config = read_claude_json()
            workspace_path = get_workspace_path(config)
            all_servers = get_all_servers(config, workspace_path)

            # 获取当前项目的禁用列表
            disabled_set: set[str] = set()
            if workspace_path:
                disabled_set = get_disabled_set(config, workspace_path)

            # 按来源排序：本地在前，全局在后；同来源按名称排序
            sorted_servers = sorted(
                all_servers.items(),
                key=lambda x: (0 if x[1]["source"] == "local" else 1, x[0])
            )

            total = len(sorted_servers)
            enabled_count = sum(
                1 for s_name, _ in sorted_servers if s_name not in disabled_set
            )
            disabled_count = total - enabled_count

            result = f"所有 MCP 服务器 ({total} 个):\n\n"
            result += f"  本地: {sum(1 for _, v in sorted_servers if v['source'] == 'local')} 个 | "
            result += f"全局: {sum(1 for _, v in sorted_servers if v['source'] == 'global')} 个 | "
            result += f"启用: {enabled_count} 个 | 禁用: {disabled_count} 个\n"
            result += f"{'─' * 50}\n\n"

            for i, (srv_name, srv_info) in enumerate(sorted_servers, 1):
                source_label = "本地" if srv_info["source"] == "local" else "全局"
                srv_type = get_server_type(srv_info["config"])
                status = "禁用" if srv_name in disabled_set else "启用"

                result += f"  {i}. {srv_name} [{source_label}] ({srv_type}) — {status}\n"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"查询 MCP 服务器列表失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    elif name == "enable_mcp":
        server_name = arguments.get("server_name")
        if not server_name:
            return [TextContent(type="text", text="错误：必须提供 server_name 参数")]

        scope = arguments.get("scope", "project")

        try:
            config = read_claude_json()
            workspace_path = get_workspace_path(config)
            all_servers = get_all_servers(config, workspace_path)

            # 获取服务器来源信息
            source_info = ""
            if server_name in all_servers:
                source_label = "本地" if all_servers[server_name]["source"] == "local" else "全局"
                source_info = f"（来源：{source_label}）"
            else:
                source_info = "（来源：未知，该服务器名不在任何已知的本地或全局服务器列表中）"

            if scope == "global":
                # 全局范围：从所有项目的禁用列表中移除
                affected_projects = []
                if "projects" in config:
                    for proj_path, proj_config in config["projects"].items():
                        disabled_list = proj_config.get("disabledMcpServers", [])
                        if server_name in disabled_list:
                            disabled_list.remove(server_name)
                            proj_config["disabledMcpServers"] = disabled_list
                            affected_projects.append(proj_path)

                if affected_projects:
                    write_claude_json(config)
                    result = f"✅ 成功全局启用 MCP 服务器: {server_name} {source_info}\n\n"
                    result += f"已从 {len(affected_projects)} 个项目的禁用列表中移除：\n"
                    for proj in affected_projects:
                        result += f"  - {proj}\n"
                    result += "\n请重启 Claude Code 使更改生效。"
                    logger.info(f"已全局启用 MCP 服务器: {server_name}，影响 {len(affected_projects)} 个项目")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' {source_info}\n\n"
                    result += "该服务器未在任何项目的禁用列表中，无需启用。"
                    logger.info(f"MCP 服务器 '{server_name}' 未在任何项目中被禁用")

            else:
                # 项目范围（默认）
                if not workspace_path:
                    result = f"❌ 错误：找不到当前工作区的配置\n当前目录: {Path.cwd()}"
                    return [TextContent(type="text", text=result)]

                disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

                if server_name in disabled_list:
                    disabled_list.remove(server_name)
                    config["projects"][workspace_path]["disabledMcpServers"] = disabled_list
                    write_claude_json(config)

                    result = f"✅ 成功启用 MCP 服务器: {server_name} {source_info}\n\n"
                    result += f"已从当前项目的禁用列表中移除。请重启 Claude Code 使更改生效。"
                    logger.info(f"已启用 MCP 服务器: {server_name}（项目范围）")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' {source_info}\n\n"
                    result += "该服务器未在当前项目的禁用列表中，无需启用。"
                    logger.info(f"MCP 服务器 '{server_name}' 未在当前项目中被禁用")

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"❌ 启用 MCP 服务器失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    elif name == "disable_mcp":
        server_name = arguments.get("server_name")
        if not server_name:
            return [TextContent(type="text", text="错误：必须提供 server_name 参数")]

        scope = arguments.get("scope", "project")

        try:
            config = read_claude_json()
            workspace_path = get_workspace_path(config)
            all_servers = get_all_servers(config, workspace_path)

            # 获取服务器来源信息
            source_info = ""
            if server_name in all_servers:
                source_label = "本地" if all_servers[server_name]["source"] == "local" else "全局"
                source_info = f"（来源：{source_label}）"
            else:
                source_info = "（来源：未知，该服务器名不在任何已知的本地或全局服务器列表中）"

            if scope == "global":
                # 全局范围：添加到所有项目的禁用列表
                affected_projects = []
                if "projects" in config:
                    for proj_path, proj_config in config["projects"].items():
                        disabled_list = proj_config.get("disabledMcpServers", [])
                        if server_name not in disabled_list:
                            disabled_list.append(server_name)
                            proj_config["disabledMcpServers"] = disabled_list
                            affected_projects.append(proj_path)

                if affected_projects:
                    write_claude_json(config)
                    result = f"✅ 成功全局禁用 MCP 服务器: {server_name} {source_info}\n\n"
                    result += f"已添加到 {len(affected_projects)} 个项目的禁用列表：\n"
                    for proj in affected_projects:
                        result += f"  - {proj}\n"
                    result += "\n请重启 Claude Code 使更改生效。"
                    logger.info(f"已全局禁用 MCP 服务器: {server_name}，影响 {len(affected_projects)} 个项目")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' {source_info}\n\n"
                    result += "该服务器已在所有项目的禁用列表中。"
                    logger.info(f"MCP 服务器 '{server_name}' 已在所有项目中被禁用")

            else:
                # 项目范围（默认）
                if not workspace_path:
                    result = f"❌ 错误：找不到当前工作区的配置\n当前目录: {Path.cwd()}"
                    return [TextContent(type="text", text=result)]

                disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

                if server_name not in disabled_list:
                    disabled_list.append(server_name)
                    config["projects"][workspace_path]["disabledMcpServers"] = disabled_list
                    write_claude_json(config)

                    result = f"✅ 成功禁用 MCP 服务器: {server_name} {source_info}\n\n"
                    result += f"已添加到当前项目的禁用列表。请重启 Claude Code 使更改生效。"
                    logger.info(f"已禁用 MCP 服务器: {server_name}（项目范围）")
                else:
                    result = f"ℹ️ MCP 服务器 '{server_name}' {source_info}\n\n"
                    result += "该服务器已在当前项目的禁用列表中。"
                    logger.info(f"MCP 服务器 '{server_name}' 已在当前项目中被禁用")

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"❌ 禁用 MCP 服务器失败: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    elif name == "list_disabled_mcps":
        try:
            config = read_claude_json()
            workspace_path = get_workspace_path(config)
            all_servers = get_all_servers(config, workspace_path)

            if not workspace_path:
                return [TextContent(type="text", text="❌ 错误：找不到当前工作区的配置")]

            disabled_list = config["projects"][workspace_path].get("disabledMcpServers", [])

            if disabled_list:
                result = f"📋 当前被禁用的 MCP 服务器 ({len(disabled_list)} 个):\n\n"

                for i, server in enumerate(disabled_list, 1):
                    # 查找服务器来源
                    if server in all_servers:
                        source_label = "本地" if all_servers[server]["source"] == "local" else "全局"
                        srv_type = get_server_type(all_servers[server]["config"])
                        result += f"  {i}. {server} [{source_label}] ({srv_type})\n"
                    else:
                        result += f"  {i}. {server} [未知]\n"

                result += f"\n使用 enable_mcp 工具可重新启用。"
            else:
                result = "✅ 当前没有禁用的 MCP 服务器"

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
