#!/usr/bin/env python3
"""
MCP Manager Proxy Web 控制界面
基于 FastAPI 的 Web 服务器，提供 MCP 代理服务监控和日志功能
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# 配置路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "proxy" / "config.yaml"
PROXY_DIR = PROJECT_ROOT / "proxy"
PROXY_LOG_DIR = PROXY_DIR / "logs"  # proxy 进程的实际日志目录

# 确保日志目录存在
PROXY_LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 配置加载
# ============================================================================

def load_proxy_config() -> dict:
    """加载 proxy 配置文件"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def get_web_config() -> dict:
    """获取 Web 服务器配置（host, port），默认值兜底"""
    config = load_proxy_config()
    return config.get('web', {})


def get_all_profiles() -> List[dict]:
    """获取所有 profile 配置列表"""
    config = load_proxy_config()
    profiles = []
    for profile_id, profile in config.get('profiles', {}).items():
        # 获取日志文件路径
        log_file = profile.get('log_file')
        if not log_file:
            log_file = str(PROXY_LOG_DIR / f"{profile_id}.log")

        profiles.append({
            'id': profile_id,
            'name': profile.get('name', profile_id),
            'type': profile.get('type', 'proxy'),
            'transport': profile.get('transport', 'stdio'),
            'port': profile.get('port'),
            'url': profile.get('url'),
            'log_file': log_file,
        })
    return profiles


# ============================================================================
# 进程管理
# ============================================================================

_process_cache = {'cache': [], 'cache_time': 0}


def _refresh_process_cache():
    """刷新进程缓存（1秒内不重复刷新），参考 IM Claude Bridge 的实现"""
    now = time.time()
    if _process_cache['cache_time'] and now - _process_cache['cache_time'] < 1:
        return
    try:
        # 和 IM Claude Bridge 完全一致的查询方式：一条 wmic 查出所有 python 进程
        result = subprocess.run(
            ['wmic', 'process', 'where',
             "name='python.exe' or name='pythonw.exe'",
             'get', 'processid,commandline', '/format:csv'],
            capture_output=True, text=True, encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        lines = result.stdout.strip().split('\n')
        _process_cache['cache'] = lines
        _process_cache['cache_time'] = now
    except:
        pass


def find_process_by_pattern(pattern: str) -> Optional[int]:
    """通过命令行模式查找进程 PID，只查找包含 mcp-manager 的进程"""
    _refresh_process_cache()
    try:
        for line in _process_cache['cache']:
            # 先过滤出 mcp-manager 相关的进程行
            if 'mcp-manager' not in line.lower():
                continue
            if pattern.lower() in line.lower():
                parts = line.split(',')
                if len(parts) >= 3:
                    pid_str = parts[2].strip('"')
                    if pid_str.isdigit():
                        return int(pid_str)
    except:
        pass
    return None


def get_service_status(profile_id: str, profile_config: dict) -> dict:
    """获取服务状态"""
    service_type = profile_config.get('type', 'proxy')

    if service_type == 'proxy':
        # proxy 类型：查找包含 proxy.py --profile {profile_id} 的进程
        pattern = f'--profile {profile_id}'
        pid = find_process_by_pattern(pattern)
    else:
        # external 类型：用 profile_id 查找（因为启动命令里没有 name）
        pid = find_process_by_pattern(profile_id)

    return {
        'running': pid is not None,
        'pid': pid,
    }


def get_web_server_status() -> dict:
    """获取 Web Server 自身进程状态"""
    # 匹配 web_server.py（使用更精确的模式，同时匹配 --port 参数）
    pid = find_process_by_pattern('web_server.py --port')
    if pid is None:
        # 兼容旧版本：直接匹配 web_server.py
        pid = find_process_by_pattern('web_server.py')
    return {'running': pid is not None, 'pid': pid}


def start_service(profile_id: str, profile_config: dict) -> bool:
    """启动服务"""
    service_type = profile_config.get('type', 'proxy')

    if service_type == 'proxy':
        # 启动 proxy 服务
        port = profile_config.get('port', 3337)
        command = f'python proxy.py --profile {profile_id} --serve --port {port} --project mcp-manager'

        subprocess.Popen(
            command,
            cwd=str(PROXY_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True
        )
        return True
    else:
        # 启动 external 服务
        start_cmd = profile_config.get('start_command')
        if not start_cmd:
            return False

        # 获取工作目录（从命令中提取）
        work_dir = str(PROJECT_ROOT)
        if ':' in start_cmd:
            # 处理绝对路径，如 D:/AgentWorkspace/MemU/start.bat
            drive_letter = start_cmd[0] + ':'
            # 提取路径部分
            parts = start_cmd.split()
            for part in parts:
                if '/' in part or '\\' in part:
                    # 去掉文件名得到目录
                    work_dir = str(Path(part).parent)
                    break

        subprocess.Popen(
            start_cmd,
            cwd=work_dir,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True
        )
        return True


def stop_service(profile_id: str, profile_config: dict) -> bool:
    """停止服务"""
    service_type = profile_config.get('type', 'proxy')

    if service_type == 'proxy':
        # proxy 类型：查找并终止进程
        pattern = f'--profile {profile_id}'
        pid = find_process_by_pattern(pattern)
        if pid:
            # 和 IM Claude Bridge 一致：subprocess.run 不带 creationflags
            subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True
            )
        return True  # 无论是否在运行都返回成功
    else:
        # external 类型
        stop_cmd = profile_config.get('stop_command')
        if stop_cmd:
            subprocess.Popen(
                stop_cmd,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=True
            )
        else:
            # 默认：按 profile_id 查找命令行并终止
            pid = find_process_by_pattern(profile_id)
            if pid:
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True
                )
        return True


# ============================================================================
# 日志读取
# ============================================================================

def read_service_logs(log_file: Path, lines: int = 100) -> List[str]:
    """读取服务日志"""
    if not Path(log_file).exists():
        return []

    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception as e:
        return [f'Error reading log: {e}']


# ============================================================================
# FastAPI 应用
# ============================================================================

app = FastAPI(title="MCP Manager", description="MCP 服务器管理、代理与监控界面")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: str):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_text(message)
                except:
                    pass


ws_manager = ConnectionManager()


# ============================================================================
# API 端点
# ============================================================================

@app.get("/api/profiles")
async def get_profiles():
    """获取所有 profile 配置列表"""
    profiles = get_all_profiles()
    config = load_proxy_config()

    # 更新每个 profile 的状态
    for profile in profiles:
        profile_id = profile['id']
        if profile_id in config.get('profiles', {}):
            profile['status'] = get_service_status(profile_id, config['profiles'][profile_id])

    # 添加 web_server 状态到列表开头
    profiles.insert(0, {
        'id': 'web_server',
        'name': 'Web',
        'type': 'system',
        'status': get_web_server_status()
    })

    return {'profiles': profiles, 'timestamp': datetime.now().isoformat()}


@app.get("/api/profiles/{profile_id}/status")
async def get_profile_status(profile_id: str):
    """获取单个 profile 状态"""
    config = load_proxy_config()
    profiles = config.get('profiles', {})

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail='Profile not found')

    return {
        'profile_id': profile_id,
        'status': get_service_status(profile_id, profiles[profile_id]),
        'timestamp': datetime.now().isoformat()
    }


@app.post("/api/profiles/{profile_id}/start")
async def start_profile(profile_id: str):
    """启动指定服务"""
    config = load_proxy_config()
    profiles = config.get('profiles', {})

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail='Profile not found')

    try:
        start_service(profile_id, profiles[profile_id])
        return {'success': True, 'message': f'Starting {profile_id}...'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profiles/{profile_id}/stop")
async def stop_profile(profile_id: str):
    """停止指定服务"""
    # web_server 不能通过 API 停止
    if profile_id == 'web_server':
        return {'success': False, 'message': 'Web 服务不能通过此方式停止，请关闭窗口或使用任务管理器'}

    config = load_proxy_config()
    profiles = config.get('profiles', {})

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail='Profile not found')

    try:
        stop_service(profile_id, profiles[profile_id])
        return {'success': True, 'message': f'Stopping {profile_id}...'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/shutdown")
async def shutdown_server():
    """关闭 Web Server 本身"""
    # 先停止所有 MCP 服务
    config = load_proxy_config()
    for profile_id in config.get('profiles', {}):
        try:
            stop_service(profile_id, config['profiles'][profile_id])
        except:
            pass

    # 通过外部脚本关闭 Web Server（避免自己杀自己的不可靠性）
    kill_script = PROJECT_ROOT / 'scripts' / 'kill_web.py'
    if kill_script.exists():
        subprocess.Popen(
            ['cmd', '/c', f'ping 127.0.0.1 -n 2 >nul & python "{kill_script}"'],
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True
        )
    return {'success': True, 'message': 'Web Server 即将关闭...'}


@app.get("/api/profiles/{profile_id}/logs")
async def get_profile_logs(profile_id: str, lines: int = 100):
    """获取服务日志"""
    config = load_proxy_config()
    profiles = config.get('profiles', {})

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail='Profile not found')

    log_file = Path(profiles[profile_id].get('log_file', PROXY_LOG_DIR / f'{profile_id}.log'))
    log_lines = read_service_logs(log_file, lines)

    return {
        'profile_id': profile_id,
        'lines': log_lines,
        'count': len(log_lines),
        'timestamp': datetime.now().isoformat()
    }


# ============================================================================
# WebSocket 端点
# ============================================================================

@app.websocket("/ws/profiles")
async def websocket_profiles(websocket: WebSocket):
    """WebSocket 实时推送所有服务状态"""
    await ws_manager.connect(websocket, "profiles")
    try:
        await websocket.send_json({'type': 'connected', 'channel': 'profiles'})

        while True:
            config = load_proxy_config()
            all_status = {}

            for profile_id, profile_config in config.get('profiles', {}).items():
                all_status[profile_id] = get_service_status(profile_id, profile_config)

            # 添加 web_server 状态
            all_status['web_server'] = get_web_server_status()

            await websocket.send_json({
                'type': 'status_update',
                'data': all_status,
                'timestamp': datetime.now().isoformat()
            })

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f'WebSocket error: {e}')
    finally:
        ws_manager.disconnect(websocket, "profiles")


@app.websocket("/ws/logs/{profile_id}")
async def websocket_logs(websocket: WebSocket, profile_id: str):
    """WebSocket 日志流"""
    config = load_proxy_config()
    profiles = config.get('profiles', {})

    if profile_id not in profiles:
        await websocket.close(code=4004)
        return

    await ws_manager.connect(websocket, f"logs_{profile_id}")

    log_file = Path(profiles[profile_id].get('log_file', PROXY_LOG_DIR / f'{profile_id}.log'))

    try:
        await websocket.send_json({'type': 'connected', 'profile_id': profile_id})

        # 发送初始日志
        if log_file.exists():
            for line in read_service_logs(log_file, 50):
                await websocket.send_json({'type': 'log', 'data': line})

        # 持续监控新内容
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        await websocket.send_json({'type': 'log', 'data': line.strip()})
                    else:
                        await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f'Log WebSocket error: {e}')
    finally:
        ws_manager.disconnect(websocket, f"logs_{profile_id}")


# ============================================================================
# HTML 页面
# ============================================================================

@app.get("/")
async def get_dashboard():
    """主页仪表盘"""
    html_path = Path(__file__).parent / "templates" / "dashboard.html"
    return FileResponse(str(html_path))


# 静态文件服务
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


# ============================================================================
# 启动服务器
# ============================================================================

def run_server(host: str = '0.0.0.0', port: int = 8090):
    """启动 Web 服务器"""
    print(f'MCP Manager Web Server starting on http://{host}:{port}')
    print(f'Config: {CONFIG_PATH}')
    print(f'Logs: {PROXY_LOG_DIR}')

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        use_colors=False
    )


if __name__ == "__main__":
    import argparse

    # 从配置文件读取默认值
    web_config = get_web_config()
    default_host = web_config.get('host', '0.0.0.0')
    default_port = web_config.get('port', 8090)

    parser = argparse.ArgumentParser(description='MCP Manager Web Server')
    parser.add_argument('--host', default=default_host, help=f'监听地址（默认: {default_host}）')
    parser.add_argument('--port', type=int, default=default_port, help=f'监听端口（默认: {default_port}）')
    parser.add_argument('--project', default=None, help='项目标识，用于进程管理')

    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
