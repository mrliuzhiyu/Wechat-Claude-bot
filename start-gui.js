#!/usr/bin/env node

/**
 * 带 Web GUI 的启动入口
 * 同时启动微信 Bot + 本地 Web 控制面板
 *
 * 用法：node start-gui.js 或 npm run gui
 */

import { exec } from 'node:child_process';
import QRCode from 'qrcode';
import BotCore from './bot-core.js';
import { startServer, broadcast, setCommandHandler, stopServer } from './gui-server.js';

// ── 启动 GUI 服务器 ────────────────────────────────────────────────────────

const port = await startServer();
const url = `http://localhost:${port}`;
console.log(`\n🖥️  控制面板: ${url}\n`);

// 自动打开浏览器
try {
  const cmd = process.platform === 'win32' ? `start ${url}`
    : process.platform === 'darwin' ? `open ${url}`
    : `xdg-open ${url}`;
  exec(cmd);
} catch {}

// ── 启动 Bot ────────────────────────────────────────────────────────────────

let bot = new BotCore();

// 事件转发到 WebSocket
bot.on('log', (level, message) => {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  broadcast('bot:log', { level, message, time });
  // 同时输出到终端
  console.log(`[${time}] ${message}`);
});

bot.on('status', (state, data) => {
  broadcast('bot:status', { state, ...data });
});

bot.on('qr', async (qrContent) => {
  try {
    const dataUrl = await QRCode.toDataURL(qrContent, {
      width: 280, margin: 2,
      color: { dark: '#1a1a2e', light: '#ffffff' },
    });
    broadcast('bot:qr', dataUrl);
  } catch {}

  // 同时在终端显示（兼容无浏览器环境）
  const qrcodeterminal = await import('qrcode-terminal');
  await new Promise(resolve => {
    qrcodeterminal.default.generate(qrContent, { small: true }, (code) => {
      console.log(code);
      resolve();
    });
  });
});

bot.on('message-in', (userId, text) => {
  broadcast('bot:message', { direction: 'in', userId: userId.slice(0, 8), text: text.slice(0, 100) });
});

bot.on('message-out', (userId, text) => {
  broadcast('bot:message', { direction: 'out', userId: userId.slice(0, 8), text: text.slice(0, 100) });
});

// GUI 命令处理
setCommandHandler(async (action) => {
  switch (action) {
    case 'start':
      if (!bot) {
        bot = new BotCore();
        bindEvents(bot);
      }
      bot.start();
      break;
    case 'stop':
      if (bot) {
        await bot.stop();
        bot = null;
      }
      break;
  }
});

function bindEvents(b) {
  b.on('log', (level, message) => {
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    broadcast('bot:log', { level, message, time });
    console.log(`[${time}] ${message}`);
  });
  b.on('status', (state, data) => broadcast('bot:status', { state, ...data }));
  b.on('qr', async (qrContent) => {
    try {
      const dataUrl = await QRCode.toDataURL(qrContent, { width: 280, margin: 2, color: { dark: '#1a1a2e', light: '#ffffff' } });
      broadcast('bot:qr', dataUrl);
    } catch {}
  });
  b.on('message-in', (userId, text) => broadcast('bot:message', { direction: 'in', userId: userId.slice(0, 8), text: text.slice(0, 100) }));
  b.on('message-out', (userId, text) => broadcast('bot:message', { direction: 'out', userId: userId.slice(0, 8), text: text.slice(0, 100) }));
}

// ── 优雅退出 ────────────────────────────────────────────────────────────────

let stopping = false;
async function shutdown(sig) {
  if (stopping) return;
  stopping = true;
  console.log(`\n🛑 ${sig}，退出中...`);
  if (bot) await bot.stop();
  await stopServer();
  process.exit(0);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
if (process.platform === 'win32') process.on('SIGHUP', () => shutdown('SIGHUP'));

// 启动 Bot
bot.start();
