let profiles = [];
let wsProfiles = null;
let wsLogs = {};
const maxLogLines = 200;

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    await loadAndRenderDashboard();
    connectProfilesWS();
});

// ==================== 配置加载与渲染 ====================

async function loadAndRenderDashboard() {
    try {
        const res = await fetch('/api/profiles');
        const data = await res.json();
        profiles = data.profiles || [];

        renderSidebar();
        renderLogGrid();

        profiles.forEach(profile => {
            connectLogWS(profile.id);
        });
    } catch (e) {
        console.error('Failed to load profiles:', e);
    }
}

function renderSidebar() {
    const list = document.getElementById('componentList');
    list.innerHTML = '';

    profiles.forEach(profile => {
        const item = document.createElement('div');
        item.className = 'component-item';
        item.id = `sidebar-${profile.id}`;

        item.innerHTML = `
            <div>
                <div class="component-name">${escapeHtml(profile.name)}</div>
                <div class="component-pid" id="pid-${profile.id}"></div>
            </div>
            <div class="status-badge">
                <div class="status-dot" id="dot-${profile.id}"></div>
                <span class="status-text" id="status-${profile.id}">--</span>
            </div>
        `;

        list.appendChild(item);
    });
}

function renderLogGrid() {
    const grid = document.getElementById('logGrid');
    grid.innerHTML = '';

    // 过滤掉 web_server，只保留真正的服务
    const services = profiles.filter(p => p.id !== 'web_server');

    // 所有服务横向排列成一行，每个服务一列
    const count = services.length;
    grid.style.gridTemplateColumns = `repeat(${count}, 1fr)`;

    services.forEach(profile => {
        const panel = document.createElement('div');
        panel.className = 'log-panel';
        panel.id = `panel-${profile.id}`;

        panel.innerHTML = `
            <div class="log-header">
                <span class="log-title">
                    <span class="log-status-dot" id="log-dot-${profile.id}"></span>
                    ${escapeHtml(profile.name)}
                </span>
                <div class="log-actions">
                    <button class="btn-action btn-start" id="btn-start-${profile.id}" onclick="startService('${profile.id}')" title="启动">&#9654;</button>
                    <button class="btn-action btn-stop" id="btn-stop-${profile.id}" onclick="stopService('${profile.id}')" title="停止">&#9632;</button>
                    <button class="log-btn" onclick="clearLog('${profile.id}')">清空</button>
                    <button class="log-btn" onclick="scrollToBottom('${profile.id}')">底部</button>
                </div>
            </div>
            <div class="log-content" id="log-${profile.id}"></div>
        `;

        grid.appendChild(panel);
    });
}

// ==================== WebSocket 连接 ====================

function connectProfilesWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsProfiles = new WebSocket(`${protocol}//${location.host}/ws/profiles`);

    wsProfiles.onopen = () => {
        updateConnectionStatus(true);
    };

    wsProfiles.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'status_update') {
            updateAllStatuses(data.data);
        }
    };

    wsProfiles.onclose = () => {
        updateConnectionStatus(false);
        setTimeout(connectProfilesWS, 2000);
    };

    wsProfiles.onerror = () => {
        updateConnectionStatus(false);
    };
}

function connectLogWS(profileId) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/logs/${profileId}`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'log') {
            appendLog(profileId, data.data);
        }
    };

    ws.onopen = () => {
        updateLogStatusDot(profileId, true);
    };

    ws.onclose = () => {
        updateLogStatusDot(profileId, false);
        setTimeout(() => connectLogWS(profileId), 2000);
    };

    wsLogs[profileId] = ws;
}

// ==================== 状态更新 ====================

function updateConnectionStatus(connected) {
    const dot = document.getElementById('connectionDot');
    const text = document.getElementById('connectionText');
    dot.className = `connection-dot ${connected ? '' : 'disconnected'}`;
    text.textContent = connected ? '已连接' : '重连中...';
}

function updateAllStatuses(statusMap) {
    document.getElementById('lastUpdate').textContent =
        `最后更新: ${new Date().toLocaleTimeString()}`;

    profiles.forEach(profile => {
        const status = statusMap[profile.id] || { running: false, pid: null };

        const dot = document.getElementById(`dot-${profile.id}`);
        const statusEl = document.getElementById(`status-${profile.id}`);
        const pidEl = document.getElementById(`pid-${profile.id}`);

        if (dot) {
            dot.className = `status-dot${status.running ? ' running' : ''}`;
        }
        if (statusEl) {
            statusEl.textContent = status.running ? '运行中' : '已停止';
        }
        if (pidEl) {
            pidEl.textContent = status.pid ? `PID: ${status.pid}` : '';
        }

        updateLogStatusDot(profile.id, status.running);
        updateButtonState(profile.id, status.running);
    });
}

function updateLogStatusDot(profileId, running) {
    const dot = document.getElementById(`log-dot-${profileId}`);
    if (dot) {
        dot.className = `log-status-dot${running ? ' running' : ''}`;
    }
}

function updateButtonState(profileId, running) {
    const startBtn = document.getElementById(`btn-start-${profileId}`);
    const stopBtn = document.getElementById(`btn-stop-${profileId}`);

    if (startBtn) startBtn.disabled = running;
    if (stopBtn) stopBtn.disabled = !running;
}

// ==================== 日志操作 ====================

function appendLog(profileId, line) {
    const viewer = document.getElementById(`log-${profileId}`);
    if (!viewer) return;

    const lineEl = document.createElement('div');
    lineEl.className = 'log-line';
    lineEl.innerHTML = formatLogLine(line);
    viewer.appendChild(lineEl);

    viewer.scrollTop = viewer.scrollHeight;

    while (viewer.children.length > maxLogLines) {
        viewer.removeChild(viewer.firstChild);
    }
}

function formatLogLine(line) {
    const timestampMatch = line.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]/);
    if (timestampMatch) {
        return `<span class="log-timestamp">[${timestampMatch[1]}]</span>${escapeHtml(line.substring(timestampMatch[0].length))}`;
    }
    return escapeHtml(line);
}

function clearLog(profileId) {
    const viewer = document.getElementById(`log-${profileId}`);
    if (viewer) viewer.innerHTML = '';
}

function scrollToBottom(profileId) {
    const viewer = document.getElementById(`log-${profileId}`);
    if (viewer) viewer.scrollTop = viewer.scrollHeight;
}

// ==================== 服务控制 ====================

async function startService(profileId) {
    const btn = document.getElementById(`btn-start-${profileId}`);
    if (btn) btn.disabled = true;

    try {
        const res = await fetch(`/api/profiles/${profileId}/start`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            alert(`启动失败: ${data.detail || data.message || '未知错误'}`);
        } else if (!data.success) {
            alert(`启动失败: ${data.message || '未知错误'}`);
        }
    } catch (e) {
        alert(`启动失败: ${e}`);
    }
}

async function stopService(profileId) {
    const btn = document.getElementById(`btn-stop-${profileId}`);
    if (btn) btn.disabled = true;

    try {
        const res = await fetch(`/api/profiles/${profileId}/stop`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            alert(`停止失败: ${data.detail || data.message || '未知错误'}`);
        } else if (!data.success) {
            alert(`停止失败: ${data.message || '未知错误'}`);
        }
    } catch (e) {
        alert(`停止失败: ${e}`);
    }
}

async function startAllServices() {
    if (!confirm('确定要启动所有服务吗？')) return;

    for (const profile of profiles) {
        await startService(profile.id);
        await new Promise(r => setTimeout(r, 500));
    }
}

async function stopAllServices() {
    if (!confirm('确定要停止所有服务吗？')) return;

    // 只停止非 web_server 的服务
    const services = profiles.filter(p => p.id !== 'web_server');
    for (const profile of services) {
        await stopService(profile.id);
        await new Promise(r => setTimeout(r, 200));
    }
}

async function restartAllServices() {
    if (!confirm('确定要重启所有服务吗？')) return;

    // 只停止非 web_server 的服务
    const services = profiles.filter(p => p.id !== 'web_server');
    for (const profile of services) {
        await stopService(profile.id);
        await new Promise(r => setTimeout(r, 200));
    }

    // 等待一下确保进程已关闭
    await new Promise(r => setTimeout(r, 1000));

    // 再启动所有服务
    for (const profile of services) {
        await startService(profile.id);
        await new Promise(r => setTimeout(r, 500));
    }
}

async function stopAllAndQuit() {
    if (!confirm('确定要停止所有服务并关闭 Web 吗？')) return;

    // /api/shutdown 会停止所有服务并关闭 Web Server
    try {
        await fetch('/api/shutdown', { method: 'POST' });
    } catch (e) {
        // 响应失败是正常的（服务端被杀了）
    }

    // 延迟关闭窗口
    setTimeout(() => window.close(), 1500);
}

// ==================== 主题切换 ====================

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (theme === 'dark') {
        icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    } else {
        icon.innerHTML = '<circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>';
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

// ==================== 工具函数 ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
