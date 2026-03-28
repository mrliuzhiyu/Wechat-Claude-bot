/**
 * 渲染进程 — GUI 逻辑（Web 版，使用 WebSocket）
 */

// ── WebSocket 连接 ──────────────────────────────────────────────────────────

let ws = null;
let reconnectTimer = null;

function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    addLog('info', '已连接到 Bot 服务');
    if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
  };

  ws.onmessage = (event) => {
    try {
      const { channel, data } = JSON.parse(event.data);
      handleEvent(channel, data);
    } catch {}
  };

  ws.onclose = () => {
    addLog('warn', '连接断开，重连中...');
    if (!reconnectTimer) {
      reconnectTimer = setInterval(() => {
        if (!ws || ws.readyState === WebSocket.CLOSED) connectWS();
      }, 3000);
    }
  };

  ws.onerror = () => {};
}

function wsSend(action, payload) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action, payload }));
  }
}

// ── 兼容层：统一 API 接口 ──────────────────────────────────────────────────

const api = {
  startBot: () => wsSend('start'),
  stopBot: () => wsSend('stop'),
};

function handleEvent(channel, data) {
  switch (channel) {
    case 'bot:log': onLog(data); break;
    case 'bot:status': onStatus(data); break;
    case 'bot:qr': onQR(data); break;
    case 'bot:message': onMessage(data); break;
  }
}

// ── 元素引用 ────────────────────────────────────────────────────────────────

const $ = (s) => document.querySelector(s);
const views = {
  checking: $('#view-checking'),
  envError: $('#view-env-error'),
  qr: $('#view-qr'),
  running: $('#view-running'),
};

const statusDot = $('#status-dot');
const statusText = $('#status-text');
const logContent = $('#log-content');
const logPanel = $('#log-panel');
const logToggle = $('#log-toggle');
const logArrow = $('#log-arrow');
const btnStop = $('#btn-stop');
const btnStart = $('#btn-start');
const btnRetry = $('#btn-retry');

let currentView = 'checking';
let statsTimer = null;
let startTime = null;

// ── 视图切换 ────────────────────────────────────────────────────────────────

function showView(name) {
  if (currentView === name) return;
  Object.values(views).forEach(v => v.classList.remove('active'));
  const target = views[name];
  if (target) { target.classList.add('active'); currentView = name; }
}

function setStatus(dotClass, text) {
  statusDot.className = `dot ${dotClass}`;
  statusText.textContent = text;
}

// ── 日志 ────────────────────────────────────────────────────────────────────

const MAX_LOG_LINES = 200;
let logCount = 0;

function addLog(level, message, time) {
  const line = document.createElement('div');
  line.className = `log-line ${level}`;
  line.textContent = `[${time || now()}] ${message}`;
  logContent.appendChild(line);
  logCount++;
  while (logCount > MAX_LOG_LINES) { logContent.removeChild(logContent.firstChild); logCount--; }
  logContent.scrollTop = logContent.scrollHeight;
}

function now() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }

// ── 消息列表 ────────────────────────────────────────────────────────────────

const MAX_MESSAGES = 20;
const recentMessages = $('#recent-messages');
let messageCount = 0;

function addMessage(data) {
  const emptyHint = recentMessages.querySelector('.empty-hint');
  if (emptyHint) emptyHint.remove();

  const item = document.createElement('div');
  item.className = 'msg-item';
  const dir = data.direction === 'in' ? '收' : '发';
  const dirClass = data.direction === 'in' ? 'msg-dir-in' : 'msg-dir-out';
  item.innerHTML = `
    <span class="msg-dir ${dirClass}">${dir}</span>
    <span class="msg-user">${escapeHtml(data.userId)}</span>
    <span class="msg-text">${escapeHtml(data.text)}</span>
  `;
  recentMessages.insertBefore(item, recentMessages.firstChild);
  messageCount++;
  while (messageCount > MAX_MESSAGES) { recentMessages.removeChild(recentMessages.lastChild); messageCount--; }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── 运行时间 ────────────────────────────────────────────────────────────────

function startStatsTimer() {
  startTime = Date.now();
  if (statsTimer) clearInterval(statsTimer);
  statsTimer = setInterval(updateUptime, 10000);
  updateUptime();
}

function stopStatsTimer() {
  if (statsTimer) { clearInterval(statsTimer); statsTimer = null; }
}

function updateUptime() {
  if (!startTime) return;
  const s = Math.floor((Date.now() - startTime) / 1000);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  $('#stat-uptime').textContent = h > 0 ? `${h}h${m}m` : `${m}m`;
}

// ── 事件处理 ────────────────────────────────────────────────────────────────

function onLog(data) { addLog(data.level, data.message, data.time); }

function onStatus(data) {
  const { state } = data;
  switch (state) {
    case 'init':
    case 'checking-env':
      showView('checking');
      setStatus('dot-warn', '检测中...');
      break;
    case 'env-ready':
      setStatus('dot-warn', '等待连接');
      addLog('info', `Claude Code ${data.version || ''} 就绪`);
      break;
    case 'env-error':
      showView('envError');
      setStatus('dot-err', '环境异常');
      if (data.missing === 'claude-code') {
        $('#env-error-msg').textContent = '未检测到 Claude Code CLI';
      }
      btnStart.style.display = 'none';
      btnStop.style.display = 'none';
      break;
    case 'need-login':
      showView('qr');
      setStatus('dot-warn', '等待扫码');
      $('#qr-container').innerHTML = '<div class="spinner"></div><p>正在获取二维码...</p>';
      $('#qr-hint').textContent = '打开微信 → 扫描二维码';
      break;
    case 'qr-ready':
      showView('qr');
      setStatus('dot-warn', '等待扫码');
      $('#qr-hint').textContent = '打开微信 → 扫描二维码';
      break;
    case 'qr-scanned':
      setStatus('dot-warn', '已扫码');
      $('#qr-hint').textContent = '已扫码，请在微信中确认...';
      break;
    case 'connected':
      showView('running');
      setStatus('dot-on', '运行中');
      btnStop.style.display = '';
      btnStart.style.display = 'none';
      startStatsTimer();
      break;
    case 'disconnected':
    case 'reconnecting':
      setStatus('dot-warn', '重连中...');
      break;
    case 'stopped':
      setStatus('dot-off', '已停止');
      btnStop.style.display = 'none';
      btnStart.style.display = '';
      stopStatsTimer();
      break;
  }
}

function onQR(dataUrl) {
  const container = $('#qr-container');
  container.innerHTML = `<img src="${dataUrl}" alt="微信扫码登录">`;
}

function onMessage(data) {
  addMessage(data);
  const el = $('#stat-messages');
  el.textContent = String(Number(el.textContent) + 1);
  if (data.direction === 'in') {
    const usersEl = $('#stat-users');
    usersEl.textContent = String(Math.max(Number(usersEl.textContent), 1));
  }
}

// ── 按钮事件 ────────────────────────────────────────────────────────────────

logToggle.addEventListener('click', () => {
  logPanel.classList.toggle('collapsed');
  logArrow.textContent = logPanel.classList.contains('collapsed') ? '▲' : '▼';
});

btnStop.addEventListener('click', () => { btnStop.disabled = true; api.stopBot(); setTimeout(() => btnStop.disabled = false, 2000); });
btnStart.addEventListener('click', () => { btnStart.disabled = true; showView('checking'); api.startBot(); setTimeout(() => btnStart.disabled = false, 2000); });
btnRetry.addEventListener('click', () => { showView('checking'); api.startBot(); });

// ── 初始化 ──────────────────────────────────────────────────────────────────

connectWS();
