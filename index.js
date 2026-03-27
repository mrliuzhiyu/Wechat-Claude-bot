#!/usr/bin/env node

/**
 * 微信 Claude Code Bot
 *
 * 用户在微信中发消息 → 本机 Claude Code 处理 → 实时反馈回微信
 * Claude Code 拥有完整权限：读写文件、执行命令、搜索代码
 */

import dotenv from 'dotenv';
import * as weixin from './weixin-api.js';
import * as claude from './claude-code.js';

dotenv.config();

// ── 配置 ─────────────────────────────────────────────────────────────────────

const CWD = process.env.CLAUDE_CWD || process.cwd();
const MAX_REPLY_LENGTH = 4000;

// ── 模型管理 ─────────────────────────────────────────────────────────────────

const MODELS = {
  sonnet: { id: 'claude-sonnet-4-6', label: 'Sonnet', desc: '快速' },
  opus:   { id: 'claude-opus-4-6',   label: 'Opus',   desc: '最强但慢' },
  haiku:  { id: 'claude-haiku-4-5',  label: 'Haiku',  desc: '最快' },
};

let defaultModel = 'sonnet'; // 默认 sonnet，无需询问
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
  '/help': {
    handler: async (userId) => [
      '/new — 重置对话',
      '/model — 切换模型 (sonnet/opus/haiku)',
      '/status — 查看状态',
      '',
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

  // 静默排队，不发任何提示消息打扰用户
  userBusy.add(from);

  // typing（并行，不阻塞主流程）
  weixin.getConfig(account.token, from, contextToken).then(cfg => {
    if (!cfg.typingTicket) return;
    weixin.sendTyping(account.token, from, cfg.typingTicket);
    const iv = setInterval(() => weixin.sendTyping(account.token, from, cfg.typingTicket), 5000);
    // 存到 msg 上以便后面清理
    msg._typingInterval = iv;
  }).catch(() => {});

  try {
    const reply = await claude.chat(from, trimmed, {
      cwd: CWD,
      model: getModelId(getUserModel(from)),
      onProgress: (pt) => {
        const last = lastProgress.get(from);
        if (last && last.t === pt && Date.now() - last.ts < 5000) return;
        lastProgress.set(from, { t: pt, ts: Date.now() });
        send(account.token, from, pt).catch(() => {});
        log(`  📊 ${pt}`);
      },
    });

    if (msg._typingInterval) clearInterval(msg._typingInterval);

    const wx = md2wx(reply);
    for (const chunk of splitMsg(wx, MAX_REPLY_LENGTH)) {
      await send(account.token, from, chunk);
    }
    log(`🤖 ${sid(from)}: ${trunc(reply)} (${reply.length}字)`);
  } catch (err) {
    if (msg._typingInterval) clearInterval(msg._typingInterval);
    const e = err.message;
    const errMsg = e.includes('超时') ? '⏱️ 超时了，试试拆分成更小的步骤。'
      : e.includes('无法启动') ? '❌ Claude Code 未运行。'
      : `⚠️ ${e.slice(0, 200)}`;
    await send(account.token, from, errMsg);
    log(`❌ ${sid(from)}: ${e}`);
  } finally {
    userBusy.delete(from);
    lastProgress.delete(from);
  }
}

async function handleUnsupported(account, msg) {
  if (msg.contextToken) ctxTokens.set(msg.from, msg.contextToken);
  const labels = { image: '图片', voice_no_text: '语音', video: '视频', file: '文件' };
  await send(account.token, msg.from, `📎 暂不支持${labels[msg.type] || '此消息'}，请发文字。`);
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
      for (const m of r.unsupported) handleUnsupported(account, m).catch(() => {});
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
