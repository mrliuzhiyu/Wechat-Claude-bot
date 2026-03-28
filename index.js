#!/usr/bin/env node

/**
 * 微信 Claude Code Bot
 *
 * 用户在微信中发消息 → 本机 Claude Code 处理 → 实时反馈回微信
 * Claude Code 拥有完整权限：读写文件、执行命令、搜索代码
 */

import dotenv from 'dotenv';
import fs from 'node:fs';
import path from 'node:path';
import * as weixin from './weixin-api.js';
import * as claude from './claude-code.js';
import * as media from './media.js';

dotenv.config();

// ── 配置 ─────────────────────────────────────────────────────────────────────

const CWD = process.env.CLAUDE_CWD || process.cwd();
const MAX_REPLY_LENGTH = 4000;

// 告诉 Claude Code 它运行在微信环境中
const WECHAT_SYSTEM_PROMPT = [
  '你正在通过微信与用户对话，回复会显示在微信中（纯文本，不支持 Markdown 渲染）。',
  '保持回复简洁，适合手机阅读。',
  '你无法直接发送文件/图片给用户。如果用户要求发送文件，请告知文件的完整路径，并提示用户在微信中发送 /send <路径> 来接收文件。',
].join('\n');

// ── 模型管理 ─────────────────────────────────────────────────────────────────

const MODELS = {
  sonnet: { id: 'claude-sonnet-4-6', label: 'Sonnet', desc: '快速' },
  opus:   { id: 'claude-opus-4-6',   label: 'Opus',   desc: '最强但慢' },
  haiku:  { id: 'claude-haiku-4-5',  label: 'Haiku',  desc: '最快' },
};

let defaultModel = 'sonnet';
let currentAccount = null; // 当前微信连接，供 /send 等命令使用
const userModels = new Map(); // 每用户可独立切换

function getUserModel(userId) {
  return userModels.get(userId) || defaultModel;
}

function getModelId(shortName) {
  return MODELS[shortName]?.id || MODELS.sonnet.id;
}

// ── 斜杠命令 ─────────────────────────────────────────────────────────────────

const COMMANDS = {
  '/new': {
    handler: async (userId) => {
      claude.clearSession(userId);
      return '🔄 对话已重置。';
    },
  },
  '/model': {
    handler: async (userId, args) => {
      const target = args.trim().toLowerCase();

      if (!target) {
        const cur = getUserModel(userId);
        const lines = [];
        for (const [k, m] of Object.entries(MODELS)) {
          lines.push(`  ${k === cur ? '→ ' : '  '}${k} — ${m.label} (${m.desc})`);
        }
        return `当前模型: ${MODELS[cur].label}\n\n${lines.join('\n')}\n\n切换: /model sonnet`;
      }

      if (!MODELS[target]) return `❌ 未知模型: ${target}\n可选: ${Object.keys(MODELS).join(', ')}`;
      if (target === getUserModel(userId)) return `已经是 ${MODELS[target].label} 了。`;

      userModels.set(userId, target);
      claude.clearSession(userId);
      return `✅ 切换到 ${MODELS[target].label}，对话已重置。`;
    },
  },
  '/send': {
    handler: async (userId, args) => {
      const filePath = args.trim();
      if (!filePath) return '用法: /send <文件路径>\n例如: /send C:\\project\\output.png';
      if (!fs.existsSync(filePath)) return `❌ 文件不存在: ${filePath}`;
      const stat = fs.statSync(filePath);
      if (stat.isDirectory()) return '❌ 不能发送文件夹';
      if (stat.size > 50 * 1024 * 1024) return `❌ 文件过大 (${(stat.size / 1024 / 1024).toFixed(1)}MB)，上限 50MB`;
      if (stat.size === 0) return '❌ 文件为空';

      try {
        const account = currentAccount;
        if (!account) return '❌ 未连接微信';
        const ctx = ctxTokens.get(userId);
        const uploaded = await media.uploadMedia(filePath, userId, account.token, account.baseUrl || 'https://ilinkai.weixin.qq.com');
        const item = media.buildMediaItem(uploaded);
        await weixin.sendMediaMessage(account.token, userId, item, ctx);
        return `✅ 已发送: ${path.basename(filePath)}`;
      } catch (err) {
        return `❌ 发送失败: ${err.message.slice(0, 150)}`;
      }
    },
  },
  '/help': {
    handler: async (userId) => [
      '/new — 重置对话',
      '/model — 切换模型 (sonnet/opus/haiku)',
      '/send <路径> — 发送本机文件到微信',
      '/status — 查看状态',
      '',
      '支持接收: 文字、语音、图片、文件',
      `模型: ${MODELS[getUserModel(userId)].label}`,
      `目录: ${CWD}`,
    ].join('\n'),
  },
  '/status': {
    handler: async (userId) => {
      const v = await claude.checkClaudeAvailable();
      return [
        `Claude Code: ${v || '❌'}`,
        `模型: ${MODELS[getUserModel(userId)].label}`,
        `目录: ${CWD}`,
        `运行: ${fmtUp(process.uptime())}`,
      ].join('\n');
    },
  },
};

function fmtUp(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h${m}m` : `${m}m`;
}

// ── Markdown → 微信 ─────────────────────────────────────────────────────────

function md2wx(text) {
  const blocks = [];
  let r = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const i = blocks.length;
    blocks.push(`--- ${lang} ---\n${code.trimEnd()}\n---`);
    return `\x00CB${i}\x00`;
  });
  r = r.replace(/!\[[^\]]*\]\([^)]*\)/g, '');
  r = r.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  r = r.replace(/^\|[\s:|-]+\|$/gm, '');
  r = r.replace(/^\|(.+)\|$/gm, (_, i) => i.split('|').map(c => c.trim()).join('  '));
  r = r.replace(/\*\*(.+?)\*\*/g, '$1');
  r = r.replace(/(?<!\w)\*(.+?)\*(?!\w)/g, '$1');
  r = r.replace(/^#{1,6}\s+(.+)$/gm, '【$1】');
  r = r.replace(/`([^`]+)`/g, '$1');
  r = r.replace(/\x00CB(\d+)\x00/g, (_, i) => blocks[Number(i)]);
  return r.trim();
}

// ── 智能拆分 ─────────────────────────────────────────────────────────────────

function splitMsg(text, max) {
  if (text.length <= max) return [text];
  const chunks = [];
  let rest = text;
  while (rest.length > 0) {
    if (rest.length <= max) { chunks.push(rest); break; }
    let at = -1;
    const cb = rest.lastIndexOf('\n---\n', max); if (cb > max * 0.3) at = cb + 5;
    if (at < 0) { const e = rest.lastIndexOf('\n\n', max); if (e > max * 0.3) at = e + 1; }
    if (at < 0) { const n = rest.lastIndexOf('\n', max); if (n > max * 0.3) at = n + 1; }
    if (at < 0) at = max;
    chunks.push(rest.slice(0, at));
    rest = rest.slice(at);
  }
  return chunks.length > 1
    ? chunks.map((c, i) => i === 0 ? c : `(${i + 1}/${chunks.length})\n${c}`)
    : chunks;
}

// ── 消息处理 ─────────────────────────────────────────────────────────────────

const ctxTokens = new Map();
const lastProgress = new Map();
const userBusy = new Set();

async function handleMessage(account, msg) {
  const { from, text, contextToken } = msg;
  const trimmed = text.trim();
  if (contextToken) ctxTokens.set(from, contextToken);
  if (!trimmed) return;

  log(`👤 ${sid(from)}: ${trunc(trimmed)}`);

  // 斜杠命令
  const sp = trimmed.indexOf(' ');
  const cmd = (sp > 0 ? trimmed.slice(0, sp) : trimmed).toLowerCase();
  const args = sp > 0 ? trimmed.slice(sp + 1) : '';
  if (COMMANDS[cmd]) {
    await send(account.token, from, await COMMANDS[cmd].handler(from, args));
    return;
  }

  userBusy.add(from);

  // typing：用共享变量追踪 interval，确保一定能清理
  let typingIv = null;
  let typingStopped = false;
  const stopTyping = () => { typingStopped = true; if (typingIv) { clearInterval(typingIv); typingIv = null; } };

  weixin.getConfig(account.token, from, contextToken).then(cfg => {
    if (typingStopped || !cfg.typingTicket) return;
    weixin.sendTyping(account.token, from, cfg.typingTicket);
    typingIv = setInterval(() => weixin.sendTyping(account.token, from, cfg.typingTicket), 5000);
  }).catch(() => {});

  try {
    const reply = await claude.chat(from, trimmed, {
      cwd: CWD,
      model: getModelId(getUserModel(from)),
      systemPrompt: WECHAT_SYSTEM_PROMPT,
      onProgress: (pt) => {
        const last = lastProgress.get(from);
        if (last && last.t === pt && Date.now() - last.ts < 5000) return;
        lastProgress.set(from, { t: pt, ts: Date.now() });
        send(account.token, from, pt).catch(() => {});
        log(`  📊 ${pt}`);
      },
    });

    stopTyping();
    for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
      await send(account.token, from, chunk);
    }
    log(`🤖 ${sid(from)}: ${trunc(reply)} (${reply.length}字)`);
  } catch (err) {
    stopTyping();
    const e = err.message;
    const errMsg = e.includes('超时') ? '⏱️ 超时了，试试拆分成更小的步骤。'
      : e.includes('无法启动') ? '❌ Claude Code 未运行。'
      : `⚠️ ${e.slice(0, 200)}`;
    await send(account.token, from, errMsg);
    log(`❌ ${sid(from)}: ${e}`);
  } finally {
    stopTyping(); // 兜底：无论如何都清理
    userBusy.delete(from);
    lastProgress.delete(from);
  }
}

async function handleMediaMessage(account, msg) {
  if (msg.contextToken) ctxTokens.set(msg.from, msg.contextToken);
  const { from, type } = msg;

  if (type === 'voice_no_text') {
    await send(account.token, from, '📎 语音未转文字，请开启微信语音转文字后重试。');
    return;
  }

  // 下载媒体到本地
  let filePath = null;
  let desc = '';
  try {
    if (type === 'image' && msg.imageItem) {
      filePath = await media.downloadImage(msg.imageItem);
      desc = '图片';
    } else if (type === 'file' && msg.fileItem) {
      const r = await media.downloadFile(msg.fileItem);
      if (r) { filePath = r.filePath; desc = `文件 ${r.originalName}`; }
    } else if (type === 'video' && msg.videoItem) {
      filePath = await media.downloadVideo(msg.videoItem);
      desc = '视频';
    }
  } catch (err) {
    log(`⚠️ 媒体下载失败: ${err.message}`);
    await send(account.token, from, `⚠️ 下载失败: ${err.message.slice(0, 100)}`);
    return;
  }

  if (!filePath) {
    await send(account.token, from, '📎 无法处理此媒体，请发文字。');
    return;
  }

  log(`📎 ${sid(from)}: 收到${desc} → ${filePath}`);

  // 视频：Claude Code 无法分析视频内容，只告知保存路径
  if (type === 'video') {
    await send(account.token, from, `📹 视频已保存到: ${filePath}\n(视频内容无法直接分析，如需处理请用 /send 发回或告诉我你想做什么)`);
    return;
  }

  // 图片/文件：传给 Claude Code 分析
  userBusy.add(from);

  // typing
  let typingIv = null;
  let typingStopped = false;
  const stopTyping = () => { typingStopped = true; if (typingIv) { clearInterval(typingIv); typingIv = null; } };
  weixin.getConfig(account.token, from, msg.contextToken).then(cfg => {
    if (typingStopped || !cfg.typingTicket) return;
    weixin.sendTyping(account.token, from, cfg.typingTicket);
    typingIv = setInterval(() => weixin.sendTyping(account.token, from, cfg.typingTicket), 5000);
  }).catch(() => {});

  try {
    const prompt = type === 'image'
      ? `用户发来了一张图片，已保存到: ${filePath}\n请用 Read 工具查看并描述这张图片。`
      : `用户发来了${desc}，已保存到: ${filePath}\n请读取并分析这个文件的内容。`;

    const reply = await claude.chat(from, prompt, {
      cwd: CWD,
      model: getModelId(getUserModel(from)),
      systemPrompt: WECHAT_SYSTEM_PROMPT,
      onProgress: (pt) => {
        const last = lastProgress.get(from);
        if (last && last.t === pt && Date.now() - last.ts < 5000) return;
        lastProgress.set(from, { t: pt, ts: Date.now() });
        send(account.token, from, pt).catch(() => {});
      },
    });

    stopTyping();
    for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
      await send(account.token, from, chunk);
    }
  } catch (err) {
    stopTyping();
    await send(account.token, from, `⚠️ 分析失败: ${err.message.slice(0, 150)}`);
  } finally {
    stopTyping();
    userBusy.delete(from);
    lastProgress.delete(from);
  }
}

async function send(token, to, text) {
  try {
    await weixin.sendMessage(token, to, text, ctxTokens.get(to));
  } catch (err) {
    log(`⚠️ 发送失败: ${err.message.slice(0, 80)}`);
  }
}

// ── 消息循环 ─────────────────────────────────────────────────────────────────

async function messageLoop(account) {
  let errCount = 0;
  while (!stopping) {
    try {
      const r = await weixin.getUpdates(account.token);
      errCount = 0;
      for (const m of r.messages) handleMessage(account, m).catch(e => log(`❌ ${e.message}`));
      for (const m of r.media) handleMediaMessage(account, m).catch(e => log(`❌ 媒体: ${e.message}`));
    } catch (err) {
      if (stopping) break;
      if (err.message === 'SESSION_EXPIRED') {
        log('⚠️ Session 过期，重连...');
        weixin.clearAuth();
        return 'RECONNECT';
      }
      errCount++;
      log(`❌ 轮询错误 (${errCount}/5): ${err.message}`);
      await sleep(errCount >= 5 ? (errCount = 0, 30000) : 2000);
    }
  }
  return 'SHUTDOWN';
}

// ── 优雅退出 ─────────────────────────────────────────────────────────────────

let stopping = false;
function setupShutdown() {
  const h = async (sig) => {
    if (stopping) return;
    stopping = true;
    console.log(`\n🛑 ${sig}，退出中...`);
    claude.killAll();
    await sleep(1000);
    process.exit(0);
  };
  process.on('SIGINT', () => h('SIGINT'));
  process.on('SIGTERM', () => h('SIGTERM'));
  if (process.platform === 'win32') process.on('SIGHUP', () => h('SIGHUP'));
}

// ── 主流程 ───────────────────────────────────────────────────────────────────

async function main() {
  console.log('\n🤖 微信 Claude Code Bot\n━━━━━━━━━━━━━━━━━━━━━━\n');
  setupShutdown();

  const version = await claude.checkClaudeAvailable();
  if (!version) {
    console.error('❌ 未检测到 claude。请安装: npm i -g @anthropic-ai/claude-code');
    process.exit(1);
  }

  console.log(`✅ Claude Code ${version}`);
  console.log(`📁 ${CWD}`);
  console.log(`🧠 默认模型: ${MODELS[defaultModel].label} (微信发 /model 切换)\n`);

  while (!stopping) {
    try {
      const account = await weixin.login();
      currentAccount = account;
      console.log('\n📡 监听中... 微信发 /help 查看帮助\n');
      const r = await messageLoop(account);
      if (r === 'RECONNECT') { log('🔄 重连...'); await sleep(3000); continue; }
      break;
    } catch (err) {
      if (stopping) break;
      log(`❌ ${err.message}，5秒后重试...`);
      await sleep(5000);
    }
  }
}

// ── utils ────────────────────────────────────────────────────────────────────

function log(msg) { console.log(`[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${msg}`); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function sid(id) { return id.slice(0, 8) + '..'; }
function trunc(t) { const s = t.replace(/\n/g, ' ').slice(0, 80); return t.length > 80 ? s + '...' : s; }

main().catch(e => { console.error('❌', e.message); process.exit(1); });
