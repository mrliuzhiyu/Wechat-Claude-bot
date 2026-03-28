/**
 * Bot 核心逻辑（EventEmitter 封装）
 * 供 CLI (index.js) 和 Electron (electron/main.js) 共用
 *
 * Events:
 *   'log'        (level, message)
 *   'status'     (state, data?)        — init | checking-env | env-ready | env-error |
 *                                         need-login | qr-ready | qr-scanned | connected |
 *                                         disconnected | reconnecting | stopped
 *   'qr'         (qrContentUrl)        — 二维码内容 URL
 *   'message-in' (userId, text)
 *   'message-out'(userId, text)
 *   'stats'      (statsObj)
 */

import EventEmitter from 'node:events';
import dotenv from 'dotenv';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as weixin from './weixin-api.js';
import * as claude from './claude-code.js';
import * as media from './media.js';

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTBOX_DIR = path.join(__dirname, '.state', 'outbox');
fs.mkdirSync(OUTBOX_DIR, { recursive: true });

// ── 常量 ────────────────────────────────────────────────────────────────────

const MAX_REPLY_LENGTH = 4000;

const MODELS = {
  sonnet: { id: 'claude-sonnet-4-6', label: 'Sonnet', desc: '快速' },
  opus:   { id: 'claude-opus-4-6',   label: 'Opus',   desc: '最强但慢' },
  haiku:  { id: 'claude-haiku-4-5',  label: 'Haiku',  desc: '最快' },
};

const WECHAT_SYSTEM_PROMPT = [
  '你正在通过微信与用户对话。回复显示在微信中（纯文本，不支持 Markdown）。',
  '保持简洁，适合手机。不要用 Markdown 语法。',
  '',
  '文件发送：当你用 Read 工具查看图片/PDF/文档等文件时，系统会自动把该文件发送给用户。',
  '用户说"把文件发给我"时，直接用 Read 工具读取该文件即可，系统自动处理发送。',
  '你用 Write 工具或 Bash 创建的新文件也会自动发送。',
  '',
  '工作时先简短说明你要做什么，让用户知道进展。',
].join('\n');

const AUTO_SEND_EXTS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
  '.mp4', '.mov',
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.csv', '.txt', '.zip', '.rar', '.7z',
  '.mp3', '.wav', '.html',
]);

// ── BotCore 类 ──────────────────────────────────────────────────────────────

export default class BotCore extends EventEmitter {
  constructor(options = {}) {
    super();
    this.defaultCwd = options.cwd || process.env.CLAUDE_CWD || process.cwd();
    this.stopping = false;
    this.account = null;

    this.userCwd = new Map();
    this.userModels = new Map();
    this.defaultModel = 'sonnet';
    this.ctxTokens = new Map();
    this.lastProgress = new Map();
    this.userBusy = new Set();

    this.stats = {
      startTime: null,
      messageCount: 0,
      activeUsers: new Set(),
    };
  }

  // ── 公共方法 ────────────────────────────────────────────────────────────

  async start() {
    this.stopping = false;
    this.stats.startTime = Date.now();
    this._log('info', '🤖 微信 Claude Code Bot 启动中...');
    this.emit('status', 'init');

    // 1. 环境检测
    this.emit('status', 'checking-env');
    const version = await claude.checkClaudeAvailable();
    if (!version) {
      this._log('error', '❌ 未检测到 claude。请安装: npm i -g @anthropic-ai/claude-code');
      this.emit('status', 'env-error', { missing: 'claude-code' });
      return;
    }

    this._log('info', `✅ Claude Code ${version}`);
    this._log('info', `📁 ${this.defaultCwd}`);
    this._log('info', `🧠 默认模型: ${MODELS[this.defaultModel].label}`);
    this.emit('status', 'env-ready', { version, cwd: this.defaultCwd, model: this.defaultModel });

    // 2. 登录 + 消息循环
    while (!this.stopping) {
      try {
        const account = await this._login();
        if (!account) break; // 被停止
        this.account = account;
        this.emit('status', 'connected', { botId: account.botId });
        this._log('info', '📡 监听中...');

        const result = await this._messageLoop(account);
        if (result === 'RECONNECT') {
          this._log('info', '🔄 重连...');
          this.emit('status', 'reconnecting');
          await this._sleep(3000);
          continue;
        }
        break;
      } catch (err) {
        if (this.stopping) break;
        this._log('error', `❌ ${err.message}，5秒后重试...`);
        this.emit('status', 'disconnected', { error: err.message });
        await this._sleep(5000);
      }
    }

    this.emit('status', 'stopped');
  }

  async stop() {
    this.stopping = true;
    claude.killAll();
    this._log('info', '🛑 正在停止...');
    await this._sleep(500);
  }

  getStatus() {
    return {
      running: !this.stopping && !!this.account,
      uptime: this.stats.startTime ? Date.now() - this.stats.startTime : 0,
      messageCount: this.stats.messageCount,
      activeUsers: this.stats.activeUsers.size,
      model: this.defaultModel,
      cwd: this.defaultCwd,
      connected: !!this.account,
    };
  }

  getCwd(userId) {
    return this.userCwd.get(userId) || this.defaultCwd;
  }

  // ── 登录流程 ────────────────────────────────────────────────────────────

  async _login() {
    // 检查已保存的 token
    const saved = weixin.getSavedAccount();
    if (saved?.token) {
      this._log('info', '🔑 发现已保存的凭据，验证中...');
      const valid = await weixin.validateToken(saved.token);
      if (valid) {
        this._log('info', '✅ 凭据有效，恢复连接');
        return saved;
      }
      this._log('warn', '⚠️ 凭据已失效，重新扫码');
      weixin.clearAuth();
    }

    this.emit('status', 'need-login');

    const MAX_QR_REFRESH = 3;
    let refreshCount = 0;

    while (refreshCount < MAX_QR_REFRESH && !this.stopping) {
      refreshCount++;
      this._log('info', '正在获取登录二维码...');
      const qr = await weixin.fetchQRCode();

      // 通知 GUI 显示二维码
      this.emit('qr', qr.qrcode_img_content);
      this.emit('status', 'qr-ready');
      this._log('info', '📱 请用微信扫描二维码');

      const deadline = Date.now() + 3 * 60_000;
      let scannedEmitted = false;
      let shouldRefresh = false;

      while (Date.now() < deadline && !this.stopping) {
        const status = await weixin.pollQRStatus(qr.qrcode);

        switch (status.status) {
          case 'wait':
            break;
          case 'scaned':
            if (!scannedEmitted) {
              this._log('info', '👀 已扫码，请在微信确认...');
              this.emit('status', 'qr-scanned');
              scannedEmitted = true;
            }
            break;
          case 'confirmed': {
            if (!status.ilink_bot_id) throw new Error('登录失败：服务器未返回 bot_id');
            const account = {
              token: status.bot_token,
              botId: status.ilink_bot_id,
              baseUrl: status.baseurl || 'https://ilinkai.weixin.qq.com',
              userId: status.ilink_user_id,
            };
            weixin.saveAccount(account);
            this._log('info', `✅ 连接成功！Bot ID: ${account.botId}`);
            return account;
          }
          case 'expired':
            this._log('info', '⏳ 二维码已过期');
            shouldRefresh = true;
            break;
        }

        if (shouldRefresh) break;
        await this._sleep(1000);
      }
    }

    if (this.stopping) return null;
    throw new Error(`登录失败：二维码 ${MAX_QR_REFRESH} 次过期，请重试`);
  }

  // ── 消息循环 ────────────────────────────────────────────────────────────

  async _messageLoop(account) {
    let errCount = 0;
    while (!this.stopping) {
      try {
        const r = await weixin.getUpdates(account.token);
        errCount = 0;
        for (const m of r.messages) this._handleMessage(account, m).catch(e => this._log('error', `❌ ${e.message}`));
        for (const m of r.media) this._handleMediaMessage(account, m).catch(e => this._log('error', `❌ 媒体: ${e.message}`));
      } catch (err) {
        if (this.stopping) break;
        if (err.message === 'SESSION_EXPIRED') {
          this._log('warn', '⚠️ Session 过期，重连...');
          weixin.clearAuth();
          return 'RECONNECT';
        }
        errCount++;
        this._log('error', `❌ 轮询错误 (${errCount}/5): ${err.message}`);
        await this._sleep(errCount >= 5 ? (errCount = 0, 30000) : 2000);
      }
    }
    return 'SHUTDOWN';
  }

  // ── 消息处理 ────────────────────────────────────────────────────────────

  async _handleMessage(account, msg) {
    const { from, text, contextToken } = msg;
    const trimmed = text.trim();
    if (contextToken) this.ctxTokens.set(from, { token: contextToken, ts: Date.now() });
    if (!trimmed) return;

    if (this.userBusy.has(from)) {
      await this._send(account.token, from, '⏳ 上一条还在处理，请稍等...');
      return;
    }

    const isVoice = msg.source === 'voice';
    this._log('info', `👤 ${this._sid(from)}${isVoice ? '🎤' : ''}: ${this._trunc(trimmed)}`);
    this.emit('message-in', from, trimmed);
    this.stats.messageCount++;
    this.stats.activeUsers.add(from);

    // 斜杠命令
    const sp = trimmed.indexOf(' ');
    const cmd = (sp > 0 ? trimmed.slice(0, sp) : trimmed).toLowerCase();
    const cmdArgs = sp > 0 ? trimmed.slice(sp + 1) : '';
    const cmdResult = await this._handleCommand(cmd, from, cmdArgs, account);
    if (cmdResult !== null) {
      await this._send(account.token, from, cmdResult);
      return;
    }

    this.userBusy.add(from);

    try {
      const prompt = isVoice ? `(用户通过语音输入，以下为语音转文字，可能有错字) ${trimmed}` : trimmed;
      const result = await this._withTyping(account, from, contextToken, () =>
        claude.chat(from, prompt, {
          cwd: this.getCwd(from),
          model: this._getModelId(this._getUserModel(from)),
          systemPrompt: WECHAT_SYSTEM_PROMPT,
          onProgress: (pt) => {
            const last = this.lastProgress.get(from);
            if (last && last.t === pt && Date.now() - last.ts < 5000) return;
            this.lastProgress.set(from, { t: pt, ts: Date.now() });
            this._send(account.token, from, pt).catch(() => {});
            this._log('info', `  📊 ${pt}`);
          },
        })
      );

      const { text: reply, writtenFiles, readMediaFiles } = result;
      for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
        await this._send(account.token, from, chunk);
      }
      this._log('info', `🤖 ${this._sid(from)}: ${this._trunc(reply)} (${reply.length}字)`);
      this.emit('message-out', from, reply);

      await this._autoSendFiles(account, from, writtenFiles, readMediaFiles, reply);
    } catch (err) {
      const e = err.message;
      const errMsg = e.includes('超时') ? '⏱️ 超时了，试试拆分成更小的步骤。'
        : e.includes('无法启动') ? '❌ Claude Code 未运行。'
        : `⚠️ ${e.slice(0, 200)}`;
      await this._send(account.token, from, errMsg);
      this._log('error', `❌ ${this._sid(from)}: ${e}`);
    } finally {
      this.userBusy.delete(from);
      this.lastProgress.delete(from);
    }
  }

  async _handleMediaMessage(account, msg) {
    if (msg.contextToken) this.ctxTokens.set(msg.from, { token: msg.contextToken, ts: Date.now() });
    const { from, type } = msg;

    if (this.userBusy.has(from)) {
      await this._send(account.token, from, '⏳ 上一条还在处理，请稍等...');
      return;
    }

    if (type === 'voice_no_text') {
      await this._send(account.token, from, '🎤 语音未转文字。请开启微信「语音转文字」功能，或直接打字发送。');
      return;
    }

    let filePath = null, originalName = '', desc = '';
    try {
      if (type === 'image' && msg.imageItem) { filePath = await media.downloadImage(msg.imageItem); desc = '图片'; }
      else if (type === 'file' && msg.fileItem) { const r = await media.downloadFile(msg.fileItem); if (r) { filePath = r.filePath; originalName = r.originalName; desc = `文件 ${r.originalName}`; } }
      else if (type === 'video' && msg.videoItem) { filePath = await media.downloadVideo(msg.videoItem); desc = '视频'; }
    } catch (err) {
      await this._send(account.token, from, `⚠️ 下载失败: ${err.message.slice(0, 100)}`);
      return;
    }

    if (!filePath) { await this._send(account.token, from, '📎 无法处理此媒体，请发文字。'); return; }
    this._log('info', `📎 ${this._sid(from)}: 收到${desc} → ${filePath}`);
    this.stats.messageCount++;
    this.stats.activeUsers.add(from);

    this.userBusy.add(from);
    try {
      const prompt = buildMediaPrompt(type, filePath, originalName);
      const result = await this._withTyping(account, from, msg.contextToken, () =>
        claude.chat(from, prompt, {
          cwd: this.getCwd(from),
          model: this._getModelId(this._getUserModel(from)),
          systemPrompt: WECHAT_SYSTEM_PROMPT,
          onProgress: (pt) => {
            const last = this.lastProgress.get(from);
            if (last && last.t === pt && Date.now() - last.ts < 5000) return;
            this.lastProgress.set(from, { t: pt, ts: Date.now() });
            this._send(account.token, from, pt).catch(() => {});
          },
        })
      );
      const { text: reply, writtenFiles, readMediaFiles } = result;
      for (const chunk of splitMsg(md2wx(reply), MAX_REPLY_LENGTH)) {
        await this._send(account.token, from, chunk);
      }
      await this._autoSendFiles(account, from, writtenFiles, readMediaFiles, reply);
    } catch (err) {
      await this._send(account.token, from, `⚠️ 分析失败: ${err.message.slice(0, 150)}`);
    } finally {
      this.userBusy.delete(from);
      this.lastProgress.delete(from);
    }
  }

  // ── 斜杠命令 ────────────────────────────────────────────────────────────

  async _handleCommand(cmd, userId, args, account) {
    switch (cmd) {
      case '/new':
        claude.clearSession(userId);
        return '🔄 对话已重置。';

      case '/model': {
        const target = args.trim().toLowerCase();
        if (!target) {
          const cur = this._getUserModel(userId);
          const lines = Object.entries(MODELS).map(([k, m]) =>
            `  ${k === cur ? '→ ' : '  '}${k} — ${m.label} (${m.desc})`);
          return `当前模型: ${MODELS[cur].label}\n\n${lines.join('\n')}\n\n切换: /model sonnet`;
        }
        if (!MODELS[target]) return `❌ 未知模型: ${target}\n可选: ${Object.keys(MODELS).join(', ')}`;
        if (target === this._getUserModel(userId)) return `已经是 ${MODELS[target].label} 了。`;
        this.userModels.set(userId, target);
        claude.clearSession(userId);
        return `✅ 切换到 ${MODELS[target].label}，对话已重置。`;
      }

      case '/send': {
        const pipeIdx = args.indexOf('|');
        const filePath = (pipeIdx > 0 ? args.slice(0, pipeIdx) : args).trim();
        const caption = pipeIdx > 0 ? args.slice(pipeIdx + 1).trim() : '';
        if (!filePath) return '用法: /send <文件路径>';
        if (!fs.existsSync(filePath)) return `❌ 文件不存在: ${filePath}`;
        const stat = fs.statSync(filePath);
        if (stat.isDirectory()) return '❌ 不能发送文件夹';
        if (stat.size > 50 * 1024 * 1024) return `❌ 文件过大 (${(stat.size / 1024 / 1024).toFixed(1)}MB)，上限 50MB`;
        if (stat.size === 0) return '❌ 文件为空';
        try {
          if (!account) return '❌ 未连接微信';
          const ctx = this.ctxTokens.get(userId)?.token;
          if (stat.size > 5 * 1024 * 1024) {
            await this._send(account.token, userId, `📤 正在发送 ${path.basename(filePath)} (${(stat.size / 1024 / 1024).toFixed(1)}MB)...`);
          }
          const uploaded = await media.uploadMedia(filePath, userId, account.token, account.baseUrl || 'https://ilinkai.weixin.qq.com');
          const item = media.buildMediaItem(uploaded);
          await weixin.sendMediaMessage(account.token, userId, item, ctx, caption || undefined);
          return `✅ 已发送: ${path.basename(filePath)}`;
        } catch (err) {
          return `❌ 发送失败: ${err.message.slice(0, 150)}`;
        }
      }

      case '/cwd': {
        const target = args.trim();
        if (!target) return `当前工作目录: ${this.getCwd(userId)}\n\n切换: /cwd <路径>`;
        const resolved = path.resolve(target);
        if (!fs.existsSync(resolved)) return `❌ 目录不存在: ${resolved}`;
        if (!fs.statSync(resolved).isDirectory()) return `❌ 不是目录: ${resolved}`;
        this.userCwd.set(userId, resolved);
        claude.clearSession(userId);
        return `✅ 工作目录切换到: ${resolved}\n对话已重置。`;
      }

      case '/help':
        return [
          '命令:',
          '  /new — 重置对话',
          '  /model — 切换模型 (sonnet/opus/haiku)',
          '  /cwd <路径> — 切换工作目录/项目',
          '  /send <路径> — 发送本机文件到微信',
          '  /status — 查看状态',
          '',
          `模型: ${MODELS[this._getUserModel(userId)].label} | 目录: ${this.getCwd(userId)}`,
        ].join('\n');

      case '/status': {
        const v = await claude.checkClaudeAvailable();
        return [
          `Claude Code: ${v || '❌'}`,
          `模型: ${MODELS[this._getUserModel(userId)].label}`,
          `目录: ${this.getCwd(userId)}`,
          `运行: ${fmtUp((Date.now() - (this.stats.startTime || Date.now())) / 1000)}`,
        ].join('\n');
      }

      default:
        return null; // 不是命令
    }
  }

  // ── 辅助方法 ────────────────────────────────────────────────────────────

  _getUserModel(userId) { return this.userModels.get(userId) || this.defaultModel; }
  _getModelId(shortName) { return MODELS[shortName]?.id || MODELS.sonnet.id; }

  async _send(token, to, text) {
    try {
      await weixin.sendMessage(token, to, text, this.ctxTokens.get(to)?.token);
    } catch (err) {
      this._log('warn', `⚠️ 发送失败: ${err.message.slice(0, 80)}`);
    }
  }

  async _withTyping(account, userId, contextToken, fn) {
    let typingIv = null;
    let stopped = false;
    const stop = () => { stopped = true; if (typingIv) { clearInterval(typingIv); typingIv = null; } };

    weixin.getConfig(account.token, userId, contextToken).then(cfg => {
      if (stopped || !cfg.typingTicket) return;
      weixin.sendTyping(account.token, userId, cfg.typingTicket);
      typingIv = setInterval(() => weixin.sendTyping(account.token, userId, cfg.typingTicket), 5000);
    }).catch(() => {});

    try { return await fn(); } finally { stop(); }
  }

  async _autoSendFiles(account, userId, writtenFiles, readMediaFiles, replyText) {
    const sent = new Set();

    const fromReply = extractFilePathsFromReply(replyText || '');
    const allTracked = [...new Set([...(writtenFiles || []), ...(readMediaFiles || []), ...fromReply])];

    for (const filePath of allTracked) {
      const ext = path.extname(filePath).toLowerCase();
      if (!AUTO_SEND_EXTS.has(ext) || sent.has(filePath)) continue;
      try {
        if (await this._sendFileToUser(account, userId, filePath)) sent.add(filePath);
      } catch (err) {
        this._log('warn', `⚠️ 自动发送失败 ${path.basename(filePath)}: ${err.message.slice(0, 80)}`);
      }
    }

    try {
      const outboxFiles = fs.readdirSync(OUTBOX_DIR).filter(f => !f.startsWith('.'));
      for (const name of outboxFiles) {
        const fp = path.join(OUTBOX_DIR, name);
        if (sent.has(fp)) continue;
        try {
          const stat = fs.statSync(fp);
          if (!stat.isFile()) continue;
          if (await this._sendFileToUser(account, userId, fp)) sent.add(fp);
          fs.unlinkSync(fp);
        } catch (err) {
          this._log('warn', `⚠️ 发件箱发送失败 ${name}: ${err.message.slice(0, 80)}`);
          try { fs.unlinkSync(fp); } catch {}
        }
      }
    } catch {}
  }

  async _sendFileToUser(account, userId, filePath) {
    filePath = path.isAbsolute(filePath) ? filePath : path.resolve(this.getCwd(userId), filePath);
    if (!fs.existsSync(filePath)) return false;
    const stat = fs.statSync(filePath);
    if (stat.size === 0 || stat.size > 50 * 1024 * 1024) return false;

    const ctx = this.ctxTokens.get(userId)?.token;
    const uploaded = await media.uploadMedia(filePath, userId, account.token, account.baseUrl || 'https://ilinkai.weixin.qq.com');
    const item = media.buildMediaItem(uploaded);
    await weixin.sendMediaMessage(account.token, userId, item, ctx, path.basename(filePath));
    this._log('info', `📤 ${this._sid(userId)}: 发送 ${path.basename(filePath)}`);
    return true;
  }

  _log(level, message) {
    this.emit('log', level, message);
  }

  _sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
  _sid(id) { return id.slice(0, 8) + '..'; }
  _trunc(t) { const s = t.replace(/\n/g, ' ').slice(0, 80); return t.length > 80 ? s + '...' : s; }
}

// ── 从 index.js 复用的纯函数 ────────────────────────────────────────────────

function fmtUp(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h${m}m` : `${m}m`;
}

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

function extractFilePathsFromReply(text) {
  const paths = [];
  const patterns = [
    /[A-Z]:\\(?:[\w\u4e00-\u9fff.\-\s]+\\)*[\w\u4e00-\u9fff.\-\s]+\.\w{2,5}/gi,
    /\/(?:[\w\u4e00-\u9fff.\-]+\/)+[\w\u4e00-\u9fff.\-]+\.\w{2,5}/g,
  ];
  for (const pat of patterns) {
    let m;
    while ((m = pat.exec(text)) !== null) paths.push(m[0].trim());
  }
  return [...new Set(paths)];
}

function buildMediaPrompt(type, filePath, originalName) {
  const name = originalName || path.basename(filePath);
  const ext = path.extname(name).toLowerCase();
  if (type === 'image') return `用户发来一张图片，已保存到: ${filePath}\n请用 Read 工具查看并描述这张图片的内容。`;
  if (type === 'video') return `用户发来一个视频，已保存到: ${filePath}\n请用 Bash 工具尝试运行 ffprobe（如果可用）获取视频时长、分辨率等元数据。如果 ffprobe 不可用，告知用户视频已保存并询问需要做什么。`;
  if (ext === '.pdf') return `用户发来 PDF 文档 "${name}"，已保存到: ${filePath}\n请用 Read 工具读取并总结文档要点。`;
  if (ext === '.csv' || ext === '.xls' || ext === '.xlsx') return `用户发来数据文件 "${name}"，已保存到: ${filePath}\n请读取并分析数据。`;
  if (['.js','.ts','.py','.java','.go','.rs','.c','.cpp','.h','.rb','.php','.swift','.kt'].includes(ext)) return `用户发来代码文件 "${name}"，已保存到: ${filePath}\n请读取代码，解释功能并指出潜在问题。`;
  if (['.txt','.md','.log','.json','.yaml','.yml','.xml','.toml','.ini','.conf'].includes(ext)) return `用户发来文本文件 "${name}"，已保存到: ${filePath}\n请读取并总结内容。`;
  if (['.zip','.rar','.7z','.tar','.gz'].includes(ext)) return `用户发来压缩包 "${name}"，已保存到: ${filePath}\n请告知用户文件已保存，并询问是否需要解压。`;
  return `用户发来文件 "${name}"，已保存到: ${filePath}\n请读取并分析这个文件的内容。`;
}

export { MODELS };
