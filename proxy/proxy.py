#!/usr/bin/env python3
"""
MCP Proxy - 通用 MCP 工具过滤器代理

通过代理模式，只暴露上游 MCP 服务器中指定的工具，过滤掉不需要的工具定义。

用法:
    python proxy.py --profile web-reader
    python proxy.py --config /path/to/config.yaml --profile brave-search
"""

import argparse
import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import uuid

import yaml
import httpx
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route, Mount
from mcp.server import Server
from mcp.types import Tool, CallToolResult, TextContent, ImageContent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-proxy")

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30


# ============================================================
# 配置加载
# ============================================================

def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"配置文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config or "profiles" not in config:
        logger.error(f"配置文件格式错误: 缺少 'profiles' 字段")
        sys.exit(1)
    return config


def get_profile(config: dict, profile_name: str) -> dict:
    """获取指定的 profile 配置"""
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        available = ", ".join(profiles.keys())
        logger.error(f"Profile '{profile_name}' 不存在。可用的 profiles: {available}")
        sys.exit(1)
    return profiles[profile_name]


# ============================================================
# 上游客户端抽象基类
# ============================================================

class UpstreamClient(ABC):
    """上游 MCP 客户端抽象基类"""

    @abstractmethod
    async def connect(self) -> None:
        """连接上游并完成 MCP 握手"""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """获取上游所有工具定义（原始字典列表）"""
        ...

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用上游工具，返回 JSON-RPC 结果"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        ...


# ============================================================
# Stdio 上游客户端
# ============================================================

class StdioUpstreamClient(UpstreamClient):
    """通过 stdio 与上游 MCP 服务器通信的客户端"""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None,
                 timeout: int = DEFAULT_TIMEOUT, framing: str = "content-length",
                 shell: str | None = None):
        self.command = command
        self.args = args
        self.env = env or {}
        self.timeout = timeout
        self.framing = framing  # "content-length" 或 "newline"
        self.shell = shell  # shell 模式的完整命令字符串
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._request_id_lock = asyncio.Lock()

    async def connect(self) -> None:
        """启动子进程并完成 MCP 握手"""
        # 构建环境变量：继承当前进程的环境，合并配置中的环境变量
        env = {**dict(__import__("os").environ), **self.env}

        if self.shell:
            # shell 模式：使用完整的命令字符串
            logger.info(f"启动上游进程(shell): {self.shell}")
            self._process = await asyncio.create_subprocess_shell(
                self.shell,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
        else:
            # exec 模式：使用 command + args
            logger.info(f"启动上游进程: {self.command} {' '.join(self.args)}")
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )

        # MCP 握手
        init_result = await self._send_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcp-proxy", "version": "1.0.0"},
        })
        logger.info(f"上游服务器信息: {init_result.get('serverInfo', {})}")

        # 发送 initialized 通知
        await self._send_notification("notifications/initialized", {})
        logger.info("MCP 握手完成")

    async def list_tools(self) -> list[dict]:
        """获取上游所有工具"""
        result = await self._send_request("tools/list", {})
        tools = result.get("tools", [])
        logger.info(f"上游共暴露 {len(tools)} 个工具")
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用上游工具"""
        return await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

    async def close(self) -> None:
        """关闭子进程"""
        if self._process and self._process.returncode is None:
            logger.info("关闭上游进程")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()

    # ---------- 内部方法 ----------

    async def _next_request_id(self) -> int:
        """获取下一个请求 ID（线程安全）"""
        async with self._request_id_lock:
            rid = self._next_id
            self._next_id += 1
            return rid

    async def _send_request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 请求并等待响应"""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("上游进程未启动或已关闭")

        request_id = await self._next_request_id()
        message = json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }, ensure_ascii=False)

        # 根据 framing 配置选择发送格式
        if self.framing == "newline":
            self._process.stdin.write(message.encode("utf-8") + b"\n")
        else:
            self._process.stdin.write(f"Content-Length: {len(message.encode('utf-8'))}\r\n\r\n".encode("utf-8"))
            self._process.stdin.write(message.encode("utf-8"))
        await self._process.stdin.drain()

        # 读取响应（循环直到匹配到对应 ID）
        while True:
            response = await self._read_message()
            if response is None:
                raise RuntimeError("上游进程已关闭，未收到响应")

            # 忽略通知（无 id 字段）
            if "id" not in response:
                continue

            if response.get("id") == request_id:
                if "error" in response:
                    error = response["error"]
                    raise RuntimeError(f"上游返回错误 [{error.get('code')}]: {error.get('message')}")
                return response.get("result", {})

    async def _send_notification(self, method: str, params: dict) -> None:
        """发送 JSON-RPC 通知（无需等待响应）"""
        if not self._process or not self._process.stdin:
            return

        message = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }, ensure_ascii=False)

        if self.framing == "newline":
            self._process.stdin.write(message.encode("utf-8") + b"\n")
        else:
            self._process.stdin.write(f"Content-Length: {len(message.encode('utf-8'))}\r\n\r\n".encode("utf-8"))
            self._process.stdin.write(message.encode("utf-8"))
        await self._process.stdin.drain()

    async def _read_message(self) -> dict | None:
        """读取一条 JSON-RPC 消息（支持 Content-Length 和 newline 两种模式）"""
        if not self._process or not self._process.stdout:
            return None

        try:
            if self.framing == "newline":
                # newline 模式：直接读取一行 JSON
                line_bytes = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=self.timeout
                )
                if not line_bytes:
                    return None
                return json.loads(line_bytes.decode("utf-8").strip())
            else:
                # Content-Length 模式
                content_length = None
                while True:
                    line_bytes = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=self.timeout
                    )
                    if not line_bytes:
                        return None
                    line = line_bytes.decode("utf-8").strip()
                    if line == "":
                        break
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":", 1)[1].strip())

                if content_length is None:
                    logger.warning("未收到 Content-Length 头，尝试按行读取")
                    line_bytes = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=self.timeout
                    )
                    if not line_bytes:
                        return None
                    return json.loads(line_bytes.decode("utf-8").strip())

                body_bytes = await asyncio.wait_for(
                    self._process.stdout.readexactly(content_length), timeout=self.timeout
                )
                return json.loads(body_bytes.decode("utf-8"))

        except asyncio.TimeoutError:
            logger.error("读取上游响应超时")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"解析上游响应 JSON 失败: {e}")
            return None


# ============================================================
# HTTP 上游客户端
# ============================================================

class HttpUpstreamClient(UpstreamClient):
    """通过 HTTP 与上游 MCP 服务器通信的客户端"""

    def __init__(self, url: str, headers: dict[str, str] | None = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self._next_id = 1
        self._request_id_lock = asyncio.Lock()

    async def connect(self) -> None:
        """HTTP 模式不需要显式连接，验证上游可用性"""
        try:
            result = await self._send_request("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mcp-proxy", "version": "1.0.0"},
            })
            logger.info(f"上游服务器信息: {result.get('serverInfo', {})}")
            logger.info("MCP 握手完成")
        except Exception as e:
            logger.error(f"连接上游失败: {e}")
            raise

    async def list_tools(self) -> list[dict]:
        """获取上游所有工具"""
        result = await self._send_request("tools/list", {})
        tools = result.get("tools", [])
        logger.info(f"上游共暴露 {len(tools)} 个工具")
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用上游工具"""
        return await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

    async def close(self) -> None:
        """HTTP 模式无需关闭"""
        pass

    # ---------- 内部方法 ----------

    async def _next_request_id(self) -> int:
        """获取下一个请求 ID"""
        async with self._request_id_lock:
            rid = self._next_id
            self._next_id += 1
            return rid

    async def _send_request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC HTTP 请求"""
        request_id = await self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload, headers=headers)

        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            # SSE 流式响应，解析 SSE 提取 JSON-RPC 结果
            return self._parse_sse_response(response.text)
        else:
            # 普通 JSON 响应
            result = response.json()
            if "error" in result:
                error = result["error"]
                raise RuntimeError(f"上游返回错误 [{error.get('code')}]: {error.get('message')}")
            return result.get("result", {})

    @staticmethod
    def _parse_sse_response(text: str) -> dict:
        """解析 SSE 响应，提取 JSON-RPC 结果

        SSE 格式示例:
            event: message
            data: {"jsonrpc":"2.0","id":1,"result":{...}}
        """
        current_data = None
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    current_data = json.loads(data_str)

        if current_data is None:
            raise RuntimeError("SSE 响应中未找到有效数据")

        if "error" in current_data:
            error = current_data["error"]
            raise RuntimeError(f"上游返回错误 [{error.get('code')}]: {error.get('message')}")

        return current_data.get("result", {})


# ============================================================
# 工具过滤逻辑
# ============================================================

def filter_tools(upstream_tools: list[dict], allowed_names: list[str]) -> list[dict]:
    """根据配置的工具名列表过滤上游工具

    Args:
        upstream_tools: 上游返回的原始工具定义列表
        allowed_names: 配置中允许暴露的工具名列表

    Returns:
        过滤后的工具定义列表
    """
    # 如果允许列表为空，透传所有工具
    if not allowed_names:
        logger.info("未指定 tools 过滤列表，将透传所有工具")
        return list(upstream_tools)

    allowed_set = set(allowed_names)
    filtered = []
    found_names = set()

    for tool in upstream_tools:
        tool_name = tool.get("name", "")
        found_names.add(tool_name)
        if tool_name in allowed_set:
            filtered.append(tool)

    # 检查配置中是否有工具名在上游不存在
    missing = allowed_set - found_names
    for name in missing:
        logger.warning(f"配置的工具 '{name}' 在上游服务器中不存在，已跳过")

    return filtered


# ============================================================
# MCP 服务器构建
# ============================================================

def build_server(profile_name: str, upstream_client: UpstreamClient,
                 filtered_tools: list[dict]) -> Server:
    """构建对外暴露的 MCP 服务器

    Args:
        profile_name: profile 名称，用于服务器标识
        upstream_client: 已连接的上游客户端
        filtered_tools: 过滤后的工具定义列表

    Returns:
        配置好的 MCP Server 实例
    """
    server_name = f"mcp-proxy-{profile_name}"
    app = Server(server_name)

    # 预构建 Tool 对象
    tool_objects: list[Tool] = []
    for tool_def in filtered_tools:
        tool_objects.append(Tool(
            name=tool_def.get("name", "unknown"),
            description=tool_def.get("description"),
            inputSchema=tool_def.get("inputSchema", {"type": "object", "properties": {}}),
        ))

    logger.info(f"将暴露 {len(tool_objects)} 个工具: "
                f"{', '.join(t.name for t in tool_objects)}")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """返回过滤后的工具列表"""
        return tool_objects

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        """转发工具调用到上游"""
        logger.info(f"调用工具: {name}")
        try:
            result = await upstream_client.call_tool(name, arguments)
            # 上游返回的 result 结构:
            # {"content": [{"type": "text", "text": "..."}, ...], "isError": false}
            return _build_call_result(result)
        except asyncio.TimeoutError:
            error_msg = f"上游调用超时 ({upstream_client.timeout}s)"
            logger.error(error_msg)
            return CallToolResult(
                content=[TextContent(type="text", text=f"错误: {error_msg}")],
                isError=True,
            )
        except Exception as e:
            error_msg = f"上游调用失败: {e}"
            logger.error(error_msg)
            return CallToolResult(
                content=[TextContent(type="text", text=f"错误: {error_msg}")],
                isError=True,
            )

    return app


def _build_call_result(upstream_result: dict) -> CallToolResult:
    """将上游的 tools/call 结果转换为 CallToolResult

    上游 result 格式:
    {
        "content": [
            {"type": "text", "text": "..."},
            {"type": "image", "data": "...", "mimeType": "image/png"},
            ...
        ],
        "isError": false
    }
    """
    content_list = upstream_result.get("content", [])
    is_error = upstream_result.get("isError", False)

    parsed_content = []
    for item in content_list:
        item_type = item.get("type", "text")
        if item_type == "text":
            parsed_content.append(TextContent(
                type="text",
                text=item.get("text", ""),
            ))
        elif item_type == "image":
            parsed_content.append(ImageContent(
                type="image",
                data=item.get("data", ""),
                mimeType=item.get("mimeType", "image/png"),
            ))
        else:
            # 其他类型（如 resource、embedded resource 等），转为文本
            parsed_content.append(TextContent(
                type="text",
                text=json.dumps(item, ensure_ascii=False),
            ))

    return CallToolResult(content=parsed_content, isError=is_error)


# ============================================================
# Dummy OAuth 路由（用于 Claude Code OAuth 发现流程）
# ============================================================

def build_oauth_routes(port: int) -> list:
    """构建 dummy OAuth 路由（仅用于满足 Claude Code 的 OAuth 发现流程）"""

    base_url = f"http://127.0.0.1:{port}"
    # 内存存储：code -> {redirect_uri, client_id, code_challenge}
    _oauth_codes: dict[str, dict] = {}

    async def protected_resource_metadata(request):
        """RFC 9728 - Protected Resource Metadata"""
        return JSONResponse({
            "authorization_servers": [base_url],
            "resource": f"{base_url}/mcp",
        })

    async def authorization_server_metadata(request):
        """RFC 8414 - Authorization Server Metadata"""
        return JSONResponse({
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oauth/authorize",
            "token_endpoint": f"{base_url}/oauth/token",
            "registration_endpoint": f"{base_url}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "scopes_supported": ["mcp"],
        })

    async def _parse_body(request):
        """解析请求体，支持 JSON 和 form-urlencoded"""
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            return await request.json()
        form = await request.form()
        return dict(form)

    async def register(request):
        """RFC 7591 - Dynamic Client Registration"""
        body = await _parse_body(request)
        client_id = f"mcp-proxy-{uuid.uuid4().hex[:8]}"
        return JSONResponse({
            "client_id": client_id,
            "client_secret": f"secret-{uuid.uuid4().hex[:16]}",
            "client_name": body.get("client_name", "MCP Proxy Client"),
            "redirect_uris": body.get("redirect_uris", []),
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    async def authorize(request):
        """OAuth Authorization Endpoint - 自动批准并重定向"""
        redirect_uri = request.query_params.get("redirect_uri", "")
        state = request.query_params.get("state", "")
        code = uuid.uuid4().hex[:16]
        _oauth_codes[code] = {
            "redirect_uri": redirect_uri,
            "client_id": request.query_params.get("client_id", ""),
            "code_challenge": request.query_params.get("code_challenge", ""),
        }
        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(
            url=f"{redirect_uri}{separator}code={code}&state={state}",
            status_code=302,
        )

    async def token(request):
        """OAuth Token Endpoint - 签发 dummy token"""
        body = await _parse_body(request)
        code = body.get("code", "")
        # 验证 code 存在（简化验证，不校验 code_verifier）
        if code and code in _oauth_codes:
            del _oauth_codes[code]
        access_token = f"dummy-{uuid.uuid4().hex[:32]}"
        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
            "scope": body.get("scope", "mcp"),
        })

    return [
        Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
        Route("/.well-known/oauth-authorization-server", authorization_server_metadata),
        Route("/oauth/register", register, methods=["POST"]),
        Route("/oauth/authorize", authorize),
        Route("/oauth/token", token, methods=["POST"]),
    ]


# ============================================================
# 主入口
# ============================================================

async def run(profile_name: str, config_path: str, serve: bool = False, port: int = 3337) -> None:
    """启动 MCP 过滤代理"""
    # 加载配置
    config = load_config(config_path)
    profile = get_profile(config, profile_name)

    transport = profile.get("transport", "stdio")
    allowed_tools = profile.get("tools", [])

    logger.info(f"启动 MCP Proxy - profile: {profile_name}, transport: {transport}")
    if allowed_tools:
        logger.info(f"允许暴露的工具: {', '.join(allowed_tools)}")
    else:
        logger.info("未指定工具过滤列表，将透传所有工具")

    # 创建上游客户端
    timeout = profile.get("timeout", DEFAULT_TIMEOUT)

    if transport == "stdio":
        command = profile.get("command")
        args = profile.get("args", [])
        env = profile.get("env")
        framing = profile.get("framing", "content-length")
        shell = profile.get("shell")
        if not command and not shell:
            logger.error("stdio 模式需要配置 'command' 或 'shell' 字段")
            sys.exit(1)
        upstream: UpstreamClient = StdioUpstreamClient(
            command=command or "",
            args=args,
            env=env,
            timeout=timeout,
            framing=framing,
            shell=shell,
        )
    elif transport == "http":
        url = profile.get("url")
        headers = profile.get("headers")
        if not url:
            logger.error("http 模式需要配置 'url' 字段")
            sys.exit(1)
        upstream = HttpUpstreamClient(
            url=url,
            headers=headers,
            timeout=timeout,
        )
    else:
        logger.error(f"不支持的 transport 类型: {transport}（支持: stdio, http）")
        sys.exit(1)

    # 连接上游并获取工具列表
    try:
        await upstream.connect()
    except Exception as e:
        logger.error(f"连接上游服务器失败: {e}")
        sys.exit(1)

    try:
        all_tools = await upstream.list_tools()
    except Exception as e:
        logger.error(f"获取上游工具列表失败: {e}")
        await upstream.close()
        sys.exit(1)

    # 过滤工具
    filtered = filter_tools(all_tools, allowed_tools)

    if not filtered:
        logger.error("过滤后没有可用的工具，请检查配置")
        await upstream.close()
        sys.exit(1)

    # 构建并启动 MCP 服务器
    app = build_server(profile_name, upstream, filtered)

    if serve:
        # HTTP 服务端模式 - 使用 StreamableHTTPServerTransport
        logger.info(f"MCP Proxy 服务器已就绪 (HTTP 模式, 端口: {port})，等待连接...")

        from mcp.server.streamable_http import StreamableHTTPServerTransport
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Mount

        transport = StreamableHTTPServerTransport(mcp_session_id=None)
        oauth_routes = build_oauth_routes(port)
        starlette_app = Starlette(routes=[
            *oauth_routes,
            Mount("/mcp", app=transport.handle_request),
        ])
        config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port, log_level="info")
        uvicorn_server = uvicorn.Server(config)

        async def run_server():
            try:
                async with transport.connect() as (read_stream, write_stream):
                    await app.run(
                        read_stream,
                        write_stream,
                        app.create_initialization_options(),
                    )
            except asyncio.CancelledError:
                pass

        server_task = asyncio.create_task(run_server())

        try:
            logger.info(f"HTTP MCP 服务运行中 - http://0.0.0.0:{port}/mcp")
            await uvicorn_server.serve()
        except KeyboardInterrupt:
            pass
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            transport.terminate()
            logger.info("HTTP 服务已关闭")
    else:
        # stdio 模式（默认）
        logger.info("MCP Proxy 服务器已就绪 (stdio 模式)，等待连接...")

        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="MCP Proxy - 通用 MCP 工具过滤器代理"
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="使用哪个配置 profile",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径，默认为同目录下的 config.yaml",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        default=False,
        help="启用 HTTP 服务端模式（常驻进程），默认使用 stdio 模式",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3337,
        help="HTTP 服务端模式监听端口（默认: 3337）",
    )

    args = parser.parse_args()

    # 默认配置文件路径：脚本所在目录下的 config.yaml
    if args.config:
        config_path = args.config
    else:
        config_path = str(Path(__file__).parent / "config.yaml")

    asyncio.run(run(args.profile, config_path, serve=args.serve, port=args.port))


if __name__ == "__main__":
    main()
