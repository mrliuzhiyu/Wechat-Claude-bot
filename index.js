#!/usr/bin/env node

/**
 * 微信 Claude Code Bot
 * 通过微信 iLink Bot API 连接本机 Claude Code CLI
 *
 * 用法：node index.js
 */

import dotenv from 'dotenv';
import * as weixin from './weixin-api.js';
import * as claude from './claude-code.js';

dotenv.config();

// ── 配置 ─────────────────────────────────────────────────────────────────────

const CWD = process.env.CLAUDE_CWD || process.cwd();
const MAX_REPLY_LENGTH = 4000; // 微信单条消息上限

// ── 斜杠命令 ─────────────────────────────────────────────────────────────────

const COMMANDS = {
  '/new': {
    desc: '开始新对话',
    handler: async (userId) => {
      claude.clearSession(userId);
      return '🔄 对话已重置，开始新对话。';
    },
  },
  '/help': {
    desc: '显示帮助',
    handler: async () => {
      const lines = ['📖 可用命令：', ''];
      for (const [cmd, { desc }] of Object.entries(COMMANDS)) {
        lines.push(`  ${cmd} — ${desc}`);
      }
      lines.push('', '直接发文字或语音，Claude Code 会帮你处理。');
      lines.push('Claude Code 可以读写文件、执行命令、搜索代码。');
      lines.push(`当前工作目录：${CWD}`);
      return lines.join('\n');
    },
  },
  '/status': {
    desc: '查看状态',
    handler: async () => {
      const version = await claude.checkClaudeAvailable();
      return [
        '📊 状态',
        `Claude Code: ${version || '未检测到'}`,
        `工作目录: ${CWD}`,
        `运行时间: ${formatUptime(process.uptime())}`,
      ].join('\n');
    },
  },
};

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}小时${m}分钟`;
  return `${m}分钟`;
}

// ── 消息处理 ─────────────────────────────────────────────────────────────────

// 每个用户的最新 contextToken（确保回复用最新的）
const latestContextTokens = new Map();

async function handleMessage(account, msg) {
  const { from, text, contextToken } = msg;
  const trimmed = text.trim();

  // 更新该用户最新的 contextToken
  if (contextToken) {
    latestContextTokens.set(from, contextToken);
  }

  log(`👤 ${from.slice(0, 8)}...: ${trimmed.slice(0, 80)}${trimmed.length > 80 ? '...' : ''}`);

  // 处理斜杠命令
  const cmdKey = trimmed.toLowerCase().split(' ')[0];
  if (COMMANDS[cmdKey]) {
    const reply = await COMMANDS[cmdKey].handler(from);
    await safeSend(account.token, from, reply);
    log(`🤖 [命令] ${cmdKey}`);
    return;
  }

  // 发送 typing 状态
  const config = await weixin.getConfig(account.token, from, contextToken);
  const typingInterval = setInterval(() => {
    weixin.sendTyping(account.token, from, config.typingTicket);
  }, 5000);
  weixin.sendTyping(account.token, from, config.typingTicket);

  try {
    log('🤖 正在思考...');
    const reply = await claude.chat(from, trimmed, { cwd: CWD });

    clearInterval(typingInterval);

    // 检查 Claude Code 是否需要权限确认（关键边界问题）
    const processedReply = handlePermissionDenials(reply);

    // 拆分长消息
    const chunks = splitMessage(processedReply, MAX_REPLY_LENGTH);
    for (const chunk of chunks) {
      await safeSend(account.token, from, chunk);
    }

    const preview = processedReply.slice(0, 80).replace(/\n/g, ' ');
    log(`🤖 Claude: ${preview}${processedReply.length > 80 ? '...' : ''} (${processedReply.length}字)`);
  } catch (err) {
    clearInterval(typingInterval);
    const errMsg = `⚠️ 处理失败: ${err.message.slice(0, 200)}`;
    await safeSend(account.token, from, errMsg);
    log(`❌ 错误: ${err.message}`);
  }
}

/**
 * 处理 Claude Code 权限拒绝的情况
 * claude -p 在 default 权限模式下，遇到需要确认的操作会被拒绝
 * 返回的文本中会包含 permission denied 相关信息
 */
function handlePermissionDenials(reply) {
  if (!reply) return reply;
  // 如果回复为空或仅包含权限拒绝信息，提示用户
  if (reply === '(Claude Code 无响应)') {
    return '⚠️ Claude Code 无法完成此操作。可能是权限不足或操作被拒绝。\n\n提示：可以在启动时设置 CLAUDE_CWD 指定工作目录，或检查 Claude Code 的权限配置。';
  }
  return reply;
}

/**
 * 安全发送消息，使用最新的 contextToken
 */
async function safeSend(token, to, text) {
  const ctx = latestContextTokens.get(to);
  try {
    await weixin.sendMessage(token, to, text, ctx);
  } catch (err) {
    log(`⚠️ 发送消息失败: ${err.message}`);
    // 不再抛出，避免因发送失败导致整个处理链断裂
  }
}

function splitMessage(text, maxLen) {
  if (text.length <= maxLen) return [text];
  const chunks = [];
  let rest = text;
  while (rest.length > 0) {
    if (rest.length <= maxLen) {
      chunks.push(rest);
      break;
    }
    // 尝试在换行处断开
    let splitAt = rest.lastIndexOf('\n', maxLen);
    if (splitAt < maxLen * 0.3) splitAt = maxLen;
    chunks.push(rest.slice(0, splitAt));
    rest = rest.slice(splitAt).replace(/^\n/, '');
  }
  return chunks;
}

// ── 消息循环（带自动重连）────────────────────────────────────────────────────

async function messageLoop(account) {
  let consecutiveErrors = 0;

  while (!shuttingDown) {
    try {
      const messages = await weixin.getUpdates(account.token);
      consecutiveErrors = 0;

      for (const msg of messages) {
        handleMessage(account, msg).catch(err => {
          log(`❌ 处理消息异常: ${err.message}`);
        });
      }
    } catch (err) {
      if (shuttingDown) break;

      if (err.message === 'SESSION_EXPIRED') {
        log('⚠️  Session 过期，尝试重新登录...');
        weixin.clearAuth();
        // 自动重连而非退出
        return 'RECONNECT';
      }

      consecutiveErrors++;
      log(`❌ 轮询错误 (${consecutiveErrors}/5): ${err.message}`);

      if (consecutiveErrors >= 5) {
        log('❌ 连续错误过多，等待 30 秒...');
        await sleep(30_000);
        consecutiveErrors = 0;
      } else {
        await sleep(2000);
      }
    }
  }
  return 'SHUTDOWN';
}

// ── 优雅退出 ─────────────────────────────────────────────────────────────────

let shuttingDown = false;

function setupGracefulShutdown() {
  const handler = async (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n🛑 收到 ${signal}，正在退出...`);

    // 杀掉所有 claude 子进程
    claude.killAll();

    // 给子进程 3 秒优雅退出
    await sleep(1000);
    console.log('👋 已退出');
    process.exit(0);
  };

  process.on('SIGINT', () => handler('SIGINT'));
  process.on('SIGTERM', () => handler('SIGTERM'));

  // Windows: 处理终端关闭
  if (process.platform === 'win32') {
    process.on('SIGHUP', () => handler('SIGHUP'));
  }
}

// ── 主流程 ───────────────────────────────────────────────────────────────────

async function main() {
  console.log('');
  console.log('🤖 微信 Claude Code Bot');
  console.log('━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');

  setupGracefulShutdown();

  // 1. 检查 Claude Code CLI
  const version = await claude.checkClaudeAvailable();
  if (!version) {
    console.error('❌ 未检测到 claude 命令。');
    console.error('   请先安装 Claude Code CLI: npm install -g @anthropic-ai/claude-code');
    process.exit(1);
  }
  console.log(`✅ Claude Code: ${version}`);
  console.log(`📁 工作目录: ${CWD}`);
  console.log('');
  console.log('💡 提示：Claude Code 使用 -p (print) 模式运行。');
  console.log('   如需更多工具权限，可在 Claude Code 设置中调整 permission mode。');
  console.log('');

  // 2. 登录循环（支持自动重连）
  while (!shuttingDown) {
    try {
      // 微信登录（含 token 验证）
      const account = await weixin.login();
      console.log('');
      console.log('📡 开始监听微信消息... (Ctrl+C 退出)');
      console.log('   在微信中发消息给此账号即可与 Claude Code 对话');
      console.log('   发送 /help 查看可用命令');
      console.log('');

      // 3. 消息循环
      const result = await messageLoop(account);

      if (result === 'RECONNECT') {
        log('🔄 正在重新连接...');
        await sleep(3000);
        continue; // 重新登录
      }
      break; // SHUTDOWN
    } catch (err) {
      if (shuttingDown) break;
      log(`❌ 连接失败: ${err.message}`);
      log('   5 秒后重试...');
      await sleep(5000);
    }
  }
}

// ── utils ────────────────────────────────────────────────────────────────────

function log(msg) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  console.log(`[${time}] ${msg}`);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── 启动 ─────────────────────────────────────────────────────────────────────

main().catch(err => {
  console.error('❌ 启动失败:', err.message);
  process.exit(1);
});
