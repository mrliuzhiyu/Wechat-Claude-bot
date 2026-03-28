/**
 * Claude Code CLI 交互层
 *
 * 核心设计：
 * - 每个微信用户一个独立 session（对话连续）
 * - 通过 stream-json 实时解析 Claude 的动作（读文件、写文件、执行命令）
 * - 通过 onProgress 回调实时反馈给用户
 * - 使用 --dangerously-skip-permissions 赋予完整的代码操作能力
 */

import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

// ── 状态管理 ─────────────────────────────────────────────────────────────────

const sessions = new Map();   // userId → { sessionId, lastActive }
const locks = new Map();      // userId → Promise（同用户串行）

let activeProcesses = 0;
const MAX_CONCURRENT = 3;
const MAX_SESSIONS = 100;
const SESSION_EXPIRE_MS = 60 * 60 * 1000;

const activeChildren = new Set();

// ── 工具名称友好映射 ─────────────────────────────────────────────────────────

const TOOL_LABELS = {
  Read: '📖 正在读取文件',
  Edit: '✏️ 正在编辑文件',
  Write: '📝 正在创建文件',
  Bash: '⚡ 正在执行命令',
  Glob: '🔍 正在搜索文件',
  Grep: '🔍 正在搜索内容',
  WebSearch: '🌐 正在搜索网页',
  WebFetch: '🌐 正在获取网页',
  TodoWrite: '📋 正在规划任务',
};

/**
 * 从 tool_use 事件中提取友好的进度描述
 */
function describeToolUse(toolName, input) {
  const label = TOOL_LABELS[toolName] || `🔧 ${toolName}`;

  if (!input) return label;

  switch (toolName) {
    case 'Read':
      return `${label}: ${extractFilename(input.file_path)}`;
    case 'Edit':
      return `${label}: ${extractFilename(input.file_path)}`;
    case 'Write':
      return `${label}: ${extractFilename(input.file_path)}`;
    case 'Bash':
      return `${label}: ${truncate(input.command || input.description || '', 60)}`;
    case 'Glob':
      return `${label}: ${input.pattern || ''}`;
    case 'Grep':
      return `${label}: ${truncate(input.pattern || '', 40)}`;
    default:
      return label;
  }
}

function extractFilename(filepath) {
  if (!filepath) return '';
  const parts = filepath.replace(/\\/g, '/').split('/');
  return parts.slice(-2).join('/');
}

function truncate(str, maxLen) {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + '...';
}

// ── 主要 API ─────────────────────────────────────────────────────────────────

/**
 * 发送消息给 Claude Code
 * @param {string} userId - 微信用户ID
 * @param {string} message - 用户消息
 * @param {object} opts
 * @param {string} opts.cwd - 工作目录
 * @param {function} opts.onProgress - 进度回调 (progressText: string) => void
 * @returns {Promise<string>} Claude 的回复
 */
export async function chat(userId, message, opts = {}) {
  // 同用户串行
  while (locks.get(userId)) {
    await locks.get(userId);
  }

  // 全局并发等待（静默排队，不发消息打扰用户）
  while (activeProcesses >= MAX_CONCURRENT) {
    await new Promise(r => setTimeout(r, 1000));
  }

  let resolveLock;
  const lockPromise = new Promise(r => { resolveLock = r; });
  locks.set(userId, lockPromise);

  try {
    return await _doChat(userId, message, opts);
  } finally {
    locks.delete(userId);
    resolveLock();
  }
}

async function _doChat(userId, message, opts) {
  const session = sessions.get(userId);
  const now = Date.now();

  cleanupExpiredSessions();

  const isExpired = session && (now - session.lastActive > SESSION_EXPIRE_MS);
  const sessionId = (!isExpired && session?.sessionId) || null;

  const args = [
    '-p',
    '--output-format', 'stream-json',
    // 关键：赋予完整权限，让 Claude Code 能真正写代码、执行命令
    '--dangerously-skip-permissions',
  ];

  if (sessionId) {
    args.push('-r', sessionId);
  }

  if (opts.model) {
    args.push('--model', opts.model);
  }

  if (opts.allowedTools?.length) {
    args.push('--allowedTools', opts.allowedTools.join(','));
  }

  // 消息作为最后一个位置参数
  args.push(message);

  const { bin, extraArgs, shell } = resolveClaudeSpawn();
  const onProgress = opts.onProgress || (() => {});

  return new Promise((resolve, reject) => {
    activeProcesses++;

    const proc = spawn(bin, [...extraArgs, ...args], {
      stdio: ['pipe', 'pipe', 'pipe'],
      shell,
      cwd: opts.cwd || undefined,
      env: { ...process.env, CLAUDECODE: undefined },
    });

    activeChildren.add(proc);

    let stdout = '';
    let stderr = '';
    let assistantText = '';
    let finalResult = '';
    let newSessionId = null;
    let toolUseCount = 0;
    let lastProgressTime = 0;
    const PROGRESS_THROTTLE_MS = 3000; // 进度消息最少间隔 3 秒

    proc.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
      const lines = stdout.split('\n');
      stdout = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          handleEvent(JSON.parse(line));
        } catch {}
      }
    });

    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    function handleEvent(event) {
      switch (event.type) {
        case 'assistant': {
          if (event.session_id) newSessionId = event.session_id;
          if (!event.message?.content) break;

          for (const block of event.message.content) {
            if (block.type === 'text') {
              assistantText += block.text;
            }
            // 关键：解析 tool_use 事件，实时反馈给用户
            if (block.type === 'tool_use') {
              toolUseCount++;
              const now = Date.now();
              if (now - lastProgressTime >= PROGRESS_THROTTLE_MS) {
                const desc = describeToolUse(block.name, block.input);
                onProgress(desc);
                lastProgressTime = now;
              }
            }
          }
          break;
        }
        case 'result': {
          if (event.session_id) newSessionId = event.session_id;
          if (event.result && typeof event.result === 'string') {
            finalResult = event.result;
          }
          break;
        }
      }
    }

    function getReplyText() {
      return finalResult || assistantText;
    }

    function cleanup() {
      activeProcesses = Math.max(0, activeProcesses - 1);
      activeChildren.delete(proc);
    }

    proc.on('close', (code) => {
      cleanup();

      if (stdout.trim()) {
        try { handleEvent(JSON.parse(stdout)); } catch {}
      }

      if (code !== 0 && !getReplyText()) {
        if (sessionId && (stderr.includes('session') || stderr.includes('conversation'))) {
          sessions.delete(userId);
          _doChat(userId, message, opts).then(resolve).catch(reject);
          return;
        }
        reject(new Error(`Claude Code 退出码 ${code}: ${stderr.slice(0, 500)}`));
        return;
      }

      // 更新 session
      if (newSessionId) {
        sessions.set(userId, { sessionId: newSessionId, lastActive: Date.now() });
      } else if (session) {
        session.lastActive = Date.now();
      }

      resolve(getReplyText() || '(Claude Code 无响应)');
    });

    proc.on('error', (err) => {
      cleanup();
      reject(new Error(`无法启动 claude 命令: ${err.message}\n请确认已安装: npm install -g @anthropic-ai/claude-code`));
    });

    // 5分钟硬超时，不再发烦人的"仍在工作中"提醒
    const killTimer = setTimeout(() => {
      try { proc.kill('SIGTERM'); } catch {}
      setTimeout(() => { try { proc.kill('SIGKILL'); } catch {} }, 5000);
    }, 5 * 60_000);

    proc.on('close', () => clearTimeout(killTimer));
  });
}

// ── 辅助函数 ─────────────────────────────────────────────────────────────────

function cleanupExpiredSessions() {
  const now = Date.now();
  for (const [userId, session] of sessions) {
    if (now - session.lastActive > SESSION_EXPIRE_MS) {
      sessions.delete(userId);
    }
  }
  if (sessions.size > MAX_SESSIONS) {
    const sorted = [...sessions.entries()].sort((a, b) => a[1].lastActive - b[1].lastActive);
    for (const [userId] of sorted.slice(0, sessions.size - MAX_SESSIONS)) {
      sessions.delete(userId);
    }
  }
}

export function clearSession(userId) {
  sessions.delete(userId);
}

export function clearAllSessions() {
  sessions.clear();
}

export function killAll() {
  for (const proc of activeChildren) {
    try { proc.kill('SIGTERM'); } catch {}
  }
}

// ── 平台适配 ─────────────────────────────────────────────────────────────────

const IS_WINDOWS = process.platform === 'win32';

/**
 * 解析 Claude Code 的启动方式
 *
 * Windows 上 claude 是 .cmd 文件，通过 cmd.exe 执行会破坏中文参数编码。
 * 解决方案：找到 cli.js 入口，直接用 node 调用，完全绕过 cmd.exe。
 *
 * 返回 { bin, extraArgs, shell }：
 *   Windows: { bin: 'node', extraArgs: ['/.../cli.js'], shell: false }
 *   其他:    { bin: 'claude', extraArgs: [],              shell: false }
 */
let _spawnCache = null;
function resolveClaudeSpawn() {
  if (_spawnCache) return _spawnCache;

  if (IS_WINDOWS) {
    try {
      // 找到 claude.cmd 路径
      const result = execFileSync('where', ['claude'], {
        encoding: 'utf-8',
        shell: true,
        env: { ...process.env, CLAUDECODE: undefined },
      }).trim();
      const cmdPath = result.split('\n').map(l => l.trim()).find(l => l.endsWith('.cmd'));
      if (cmdPath) {
        // claude.cmd 和 node_modules 在同一目录
        const dir = path.dirname(cmdPath);
        const cliJs = path.join(dir, 'node_modules', '@anthropic-ai', 'claude-code', 'cli.js');
        if (fs.existsSync(cliJs)) {
          _spawnCache = { bin: process.execPath, extraArgs: [cliJs], shell: false };
          return _spawnCache;
        }
      }
    } catch {}
    // 兜底：仍用 cmd.exe（可能中文有问题，但至少能跑）
    _spawnCache = { bin: 'claude', extraArgs: [], shell: true };
    return _spawnCache;
  }

  // macOS / Linux：直接用 claude 命令
  try {
    const result = execFileSync('which', ['claude'], {
      encoding: 'utf-8',
      env: { ...process.env, CLAUDECODE: undefined },
    }).trim();
    _spawnCache = { bin: result || 'claude', extraArgs: [], shell: false };
  } catch {
    _spawnCache = { bin: 'claude', extraArgs: [], shell: false };
  }
  return _spawnCache;
}

export async function checkClaudeAvailable() {
  try {
    const { bin, extraArgs, shell } = resolveClaudeSpawn();
    const result = execFileSync(bin, [...extraArgs, '--version'], {
      encoding: 'utf-8',
      shell,
      env: { ...process.env, CLAUDECODE: undefined },
    });
    return result.trim();
  } catch {
    return null;
  }
}
