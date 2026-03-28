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
  '保持回复简洁，适合手机阅读。不要用 Markdown 语法。',
  '当你用 Write 工具创建图片、PDF、文档等文件时，系统会自动发送给用户，无需额外操作。',
  '对于已有的文件，告知用户完整路径并提示发送 /send <路径> 来接收。',
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
      // 支持 /send 路径 | 说明文字
      const pipeIdx = args.indexOf('|');
      const filePath = (pipeIdx > 0 ? args.slice(0, pipeIdx) : args).trim();
      const caption = pipeIdx > 0 ? args.slice(pipeIdx + 1).trim() : '';

      if (!filePath) return '用法: /send <文件路径>\n带说明: /send 路径 | 说明文字\n例如: /send C:\\output.png | 处理结果';
      if (!fs.existsSync(filePath)) return `❌ 文件不存在: ${filePath}`;
      const stat = fs.statSync(filePath);
      if (stat.isDirectory()) return '❌ 不能发送文件夹';
      if (stat.size > 50 * 1024 * 1024) return `❌ 文件过大 (${(stat.size / 1024 / 1024).toFixed(1)}MB)，上限 50MB`;
      if (stat.size === 0) return '❌ 文件为空';

      try {
        const account = currentAccount;
        if (!account) return '❌ 未连接微信';
        const ctx = ctxTokens.get(userId)?.token;
        if (stat.size > 5 * 1024 * 1024) {
          await send(account.token, userId, `📤 正在发送 ${path.basename(filePath)} (${(stat.size / 1024 / 1024).toFixed(1)}MB)...`);
        }
        const uploaded = await media.uploadMedia(filePath, userId, account.token, account.baseUrl || 'https://ilinkai.weixin.qq.com');
        const item = media.buildMediaItem(uploaded);
        await weixin.sendMediaMessage(account.token, userId, item, ctx, caption || undefined);
        return `✅ 已发送: ${path.basename(filePath)}`;
      } catch (err) {
        return `❌ 发送失败: ${err.message.slice(0, 150)}`;
      }
    },
  },
  '/help': {
    handler: async (userId) => [
      '命令:',
      '  /new — 重置对话',
      '  /model — 切换模型 (sonnet/opus/haiku)',
      '  /send <路径> — 发送本机文件到微信',
      '  /send <路径> | 说明 — 带说明发送',
      '  /status — 查看状态',
      '',
      '支持接收: 文字、语音、图片、文件、视频',
      'Claude 创建的文件会自动发送给你',
      `模型: ${MODELS[getUserModel(userId)].label} | 目录: ${CWD}`,
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

// ── 工具函数 ─────────────────────────────────────────────────────────────────

const ctxTokens = new Map();    // userId → { token, ts }
const lastProgress = new Map();
const userBusy = new Set();

/** 自动发送的文件类型白名单 */
const AUTO_SEND_EXTS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
  '.mp4', '.mov',
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.csv', '.txt', '.zip', '.rar', '.7z',
  '.mp3', '.wav', '.html',
]);

/** 包裹异步操作，自动管理 typing 状态指示 */
async function withTyping(account, userId, contextToken, fn) {
  let typingIv = null;
  let stopped = false;
  const stop = () => { stopped = true; if (typingIv) { clearInterval(typingIv); typingIv = null; } };

  weixin.getConfig(account.token, userId, contextToken).then(cfg => {
    if (stopped || !cfg.typingTicket) return;
    weixin.sendTyping(account.token, userId, cfg.typingTicket);
    typingIv = setInterval(() => weixin.sendTyping(account.token, userId, cfg.typingTicket), 5000);
  }).catch(() => {});

  try {
    return await fn();
  } finally {
    stop();
  }
}

/** 自动发送 Claude Code 创建的文件给用户 */
async function autoSendFiles(account, userId, writtenFiles) {
  if (!writtenFiles?.length) return;
  for (const filePath of writtenFiles) {
    try {
      if (!fs.existsSync(filePath)) continue;
      const ext = path.extname(filePath).toLowerCase();
      if (!AUTO_SEND_EXTS.has(ext)) continue;
      const stat = fs.statSync(filePath);
      if (stat.size === 0 || stat.size > 50 * 1024 * 1024) continue;

      const ctx = ctxTokens.get(userId)?.token;
      const uploaded = await media.uploadMedia(filePath, userId, account.token, account.baseUrl || 'https://ilinkai.weixin.qq.com');
      const item = media.buildMediaItem(uploaded);
      await weixin.sendMediaMessage(account.token, userId, item, ctx, path.basename(filePath));
      log(`📤 ${sid(userId)}: 自动发送 ${path.basename(filePath)}`);
    } catch (err) {
      log(`⚠️ 自动发送失败 ${path.basename(filePath)}: ${err.message.slice(0, 80)}`);
    }
  }
}

/** 根据文件类型生成智能 prompt */
function buildMediaPrompt(type, filePath, originalName) {
  const name = originalName || path.basename(filePath);
  const ext = path.extname(name).toLowerCase();

  if (type === 'image') {
    return `用户发来一张图片，已保存到: ${filePath}\n请用 Read 工具查看并描述这张图片的内容。`;
  }
  if (type === 'video') {
    return `用户发来一个视频，已保存到: ${filePath}\n请用 Bash 工具尝试运行 ffprobe（如果可用）获取视频时长、分辨率等元数据。如果 ffprobe 不可用，告知用户视频已保存并询问需要做什么。`;
  }
  if (ext === '.pdf') {
    return `用户发来 PDF 文档 "${name}"，已保存到: ${filePath}\n请用 Read 工具读取并总结文档要点。如果包含表格，提取关键数据。`;
  }
  if (ext === '.csv' || ext === '.xls' || ext === '.xlsx') {
    return `用户发来数据文件 "${name}"，已保存到: ${filePath}\n请读取并分析数据：描述列名、行数、关键统计信息或规律。`;
  }
  if (['.js', '.ts', '.py', '.java', '.go', '.rs', '.c', '.cpp', '.h', '.rb', '.php', '.swift', '.kt'].includes(ext)) {
    return `用户发来代码文件 "${name}"，已保存到: ${filePath}\n请读取代码，解释功能并指出潜在问题或改进建议。`;
  }
  if (['.txt', '.md', '.log', '.json', '.yaml', '.yml', '.xml', '.toml', '.ini', '.conf'].includes(ext)) {
    return `用户发来文本文件 "${name}"，已保存到: ${filePath}\n请读取并总结内容。`;
  }
  if (['.zip', '.rar', '.7z', '.tar', '.gz'].includes(ext)) {
    return `用户发来压缩包 "${name}"，已保存到: ${filePath}\n请告知用户文件已保存，并询问是否需要解压或做其他处理。`;
  }
  return `用户发来文件 "${name}"，已保存到: ${filePath}\n请读取并分析这个文件的内容。`;
}

// ── 消息处理 ─────────────────────────────────────────────────────────────────

async function handleMessage(account, msg) {
  const { from, text, contextToken } = msg;
  const trimmed = text.trim();
  if (contextToken) ctxTokens.set(from, { token: contextToken, ts: Date.now() });
  if (!trimmed) return;

  // 正在处理中的用户，提示等待
  if (userBusy.has(from)) {
    await send(account.token, from, '⏳ 上一条还在处理，请稍等...');
    return;
  }

  // 语音来源标注
  const isVoice = msg.source === 'voice';
  log(`👤 ${sid(from)}${isVoice ? '🎤' : ''}: ${trunc(trimmed)}`);

  // 斜杠命令
  const sp = trimmed.indexOf(' ');
  const cmd = (sp > 0 ? trimmed.slice(0, sp) : trimmed).toLowerCase();
  const cmdArgs = sp > 0 ? trimmed.slice(sp + 1) : '';
  if (COMMANDS[cmd]) {
    await send(account.token, from, await COMMANDS[cmd].handler(from, cmdArgs));
    return;
  }

  userBusy.add(from);

  try {
    const prompt = isVoice ? `(用户通过语音输入，以下为语音转文字，可能有错字) ${trimmed}` : trimmed;

    const result = await withTyping(account, from, contextToken, () =>
      claude.chat(from, prompt, {
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
      })
    );

    const { text: reply, writtenFiles } = result;

    for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
      await send(account.token, from, chunk);
    }
    log(`🤖 ${sid(from)}: ${trunc(reply)} (${reply.length}字)`);

    // 自动发送 Claude Code 创建的文件
    await autoSendFiles(account, from, writtenFiles);
  } catch (err) {
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

async function handleMediaMessage(account, msg) {
  if (msg.contextToken) ctxTokens.set(msg.from, { token: msg.contextToken, ts: Date.now() });
  const { from, type } = msg;

  if (userBusy.has(from)) {
    await send(account.token, from, '⏳ 上一条还在处理，请稍等...');
    return;
  }

  if (type === 'voice_no_text') {
    await send(account.token, from, '🎤 语音未转文字。请开启微信「语音转文字」功能，或直接打字发送。');
    return;
  }

  // 下载媒体到本地
  let filePath = null;
  let originalName = '';
  let desc = '';
  try {
    if (type === 'image' && msg.imageItem) {
      filePath = await media.downloadImage(msg.imageItem);
      desc = '图片';
    } else if (type === 'file' && msg.fileItem) {
      const r = await media.downloadFile(msg.fileItem);
      if (r) { filePath = r.filePath; originalName = r.originalName; desc = `文件 ${r.originalName}`; }
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

  // 所有媒体类型都交给 Claude Code 处理（包括视频用 ffprobe 提取元数据）
  userBusy.add(from);

  try {
    const prompt = buildMediaPrompt(type, filePath, originalName);

    const result = await withTyping(account, from, msg.contextToken, () =>
      claude.chat(from, prompt, {
        cwd: CWD,
        model: getModelId(getUserModel(from)),
        systemPrompt: WECHAT_SYSTEM_PROMPT,
        onProgress: (pt) => {
          const last = lastProgress.get(from);
          if (last && last.t === pt && Date.now() - last.ts < 5000) return;
          lastProgress.set(from, { t: pt, ts: Date.now() });
          send(account.token, from, pt).catch(() => {});
        },
      })
    );

    const { text: reply, writtenFiles } = result;

    for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
      await send(account.token, from, chunk);
    }

    await autoSendFiles(account, from, writtenFiles);
  } catch (err) {
    await send(account.token, from, `⚠️ 分析失败: ${err.message.slice(0, 150)}`);
  } finally {
    userBusy.delete(from);
    lastProgress.delete(from);
  }
}

async function send(token, to, text) {
  try {
    await weixin.sendMessage(token, to, text, ctxTokens.get(to)?.token);
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
