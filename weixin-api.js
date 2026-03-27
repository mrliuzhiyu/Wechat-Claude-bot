/**
 * 微信 iLink Bot API 封装
 * 协议来源：@tencent-weixin/openclaw-weixin 官方插件逆向
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const BASE_URL = 'https://ilinkai.weixin.qq.com';
const LONG_POLL_TIMEOUT_MS = 35_000;
const STATE_DIR = path.join(__dirname, '.state');

// ── helpers ──────────────────────────────────────────────────────────────────

function randomWechatUin() {
  const uint32 = crypto.randomBytes(4).readUInt32BE(0);
  return Buffer.from(String(uint32), 'utf-8').toString('base64');
}

function buildHeaders(token) {
  const headers = {
    'Content-Type': 'application/json',
    'AuthorizationType': 'ilink_bot_token',
    'X-WECHAT-UIN': randomWechatUin(),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function apiPost(endpoint, body, token, timeoutMs = 15_000) {
  const url = `${BASE_URL}/${endpoint}`;
  const bodyStr = JSON.stringify(body);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { ...buildHeaders(token), 'Content-Length': String(Buffer.byteLength(bodyStr)) },
      body: bodyStr,
      signal: controller.signal,
    });
    clearTimeout(timer);
    const text = await res.text();
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
    return JSON.parse(text);
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') return null; // 长轮询超时，正常
    throw err;
  }
}

// ── state persistence ────────────────────────────────────────────────────────

function ensureStateDir() {
  fs.mkdirSync(STATE_DIR, { recursive: true });
}

function saveState(key, data) {
  ensureStateDir();
  const filePath = path.join(STATE_DIR, `${key}.json`);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  // 保护凭据文件权限（仅 owner 可读写）
  try { fs.chmodSync(filePath, 0o600); } catch {}
}

function loadState(key) {
  try {
    return JSON.parse(fs.readFileSync(path.join(STATE_DIR, `${key}.json`), 'utf-8'));
  } catch {
    return null;
  }
}

// ── QR login ─────────────────────────────────────────────────────────────────

export async function fetchQRCode() {
  const url = `${BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`获取二维码失败: ${res.status}`);
  return await res.json(); // { qrcode, qrcode_img_content }
}

export async function pollQRStatus(qrcode) {
  const url = `${BASE_URL}/ilink/bot/get_qrcode_status?qrcode=${encodeURIComponent(qrcode)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), LONG_POLL_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      headers: { 'iLink-App-ClientVersion': '1' },
      signal: controller.signal,
    });
    clearTimeout(timer);
    const text = await res.text();
    if (!res.ok) throw new Error(`轮询状态失败: ${res.status}`);
    return JSON.parse(text); // { status, bot_token?, ilink_bot_id?, baseurl?, ilink_user_id? }
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') return { status: 'wait' };
    throw err;
  }
}

/**
 * 完整登录流程：显示二维码 → 等待扫码 → 返回凭据
 */
export async function login() {
  // 先检查已有 token，并验证有效性
  const saved = loadState('account');
  if (saved?.token) {
    console.log('🔑 发现已保存的登录凭据，验证中...');
    const valid = await validateToken(saved.token);
    if (valid) {
      console.log('✅ 凭据有效，恢复连接');
      return saved;
    }
    console.log('⚠️  凭据已失效，需要重新扫码');
    clearAuth();
  }

  const qrcodeterminal = await import('qrcode-terminal');

  console.log('正在获取登录二维码...');
  const qr = await fetchQRCode();

  console.log('\n📱 请用微信扫描以下二维码：\n');
  await new Promise(resolve => {
    qrcodeterminal.default.generate(qr.qrcode_img_content, { small: true }, (code) => {
      console.log(code);
      resolve();
    });
  });
  console.log('如果二维码显示异常，请用浏览器打开：');
  console.log(qr.qrcode_img_content);

  console.log('\n⏳ 等待扫码...');
  const deadline = Date.now() + 5 * 60_000;
  let scannedPrinted = false;

  while (Date.now() < deadline) {
    const status = await pollQRStatus(qr.qrcode);

    switch (status.status) {
      case 'wait':
        break;
      case 'scaned':
        if (!scannedPrinted) {
          console.log('👀 已扫码，请在微信确认...');
          scannedPrinted = true;
        }
        break;
      case 'confirmed': {
        if (!status.ilink_bot_id) throw new Error('登录失败：服务器未返回 bot_id');
        const account = {
          token: status.bot_token,
          botId: status.ilink_bot_id,
          baseUrl: status.baseurl || BASE_URL,
          userId: status.ilink_user_id,
        };
        saveState('account', account);
        console.log(`✅ 连接成功！Bot ID: ${account.botId}`);
        return account;
      }
      case 'expired':
        throw new Error('二维码已过期，请重新启动');
      default:
        break;
    }

    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error('登录超时');
}

// ── token validation ─────────────────────────────────────────────────────────

/**
 * 验证 token 是否仍然有效
 * 用一次短超时的 getUpdates 探测，如果返回正常（或空消息）则有效
 */
async function validateToken(token) {
  try {
    const resp = await apiPost('ilink/bot/getupdates', {
      get_updates_buf: '',
    }, token, 10_000);
    if (!resp) return true; // 超时也算正常（长轮询特性）
    if (resp.errcode === -14 || resp.ret === -14) return false; // session 过期
    if (resp.ret && resp.ret !== 0) return false;
    return true;
  } catch {
    return false;
  }
}

// ── getUpdates ───────────────────────────────────────────────────────────────

export async function getUpdates(token) {
  const syncBuf = loadState('sync-buf');
  const resp = await apiPost('ilink/bot/getupdates', {
    get_updates_buf: syncBuf?.buf || '',
  }, token, LONG_POLL_TIMEOUT_MS);

  if (!resp) return []; // 超时

  // 检查错误
  if (resp.errcode === -14 || resp.ret === -14) {
    throw new Error('SESSION_EXPIRED');
  }
  if (resp.ret && resp.ret !== 0) {
    throw new Error(`getUpdates 错误: ret=${resp.ret} errmsg=${resp.errmsg || ''}`);
  }

  // 保存 sync buf
  if (resp.get_updates_buf) {
    saveState('sync-buf', { buf: resp.get_updates_buf });
  }

  return (resp.msgs || []).map(parseMessage).filter(Boolean);
}

function parseMessage(msg) {
  if (!msg.from_user_id || !msg.item_list?.length) return null;

  let text = '';
  for (const item of msg.item_list) {
    if (item.type === 1 && item.text_item?.text) {
      text = item.text_item.text;
      break;
    }
    // 语音转文字
    if (item.type === 3 && item.voice_item?.text) {
      text = item.voice_item.text;
      break;
    }
  }

  if (!text) return null;

  return {
    from: msg.from_user_id,
    text,
    contextToken: msg.context_token,
    timestamp: msg.create_time_ms,
  };
}

// ── sendMessage ──────────────────────────────────────────────────────────────

export async function sendMessage(token, to, text, contextToken) {
  const clientId = `wechat-claude-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await apiPost('ilink/bot/sendmessage', {
    msg: {
      from_user_id: '',
      to_user_id: to,
      client_id: clientId,
      message_type: 2, // BOT
      message_state: 2, // FINISH
      item_list: [{ type: 1, text_item: { text } }],
      context_token: contextToken || undefined,
    },
  }, token);
}

// ── sendTyping ───────────────────────────────────────────────────────────────

export async function sendTyping(token, to, typingTicket) {
  if (!typingTicket) return;
  try {
    await apiPost('ilink/bot/sendtyping', {
      ilink_user_id: to,
      typing_ticket: typingTicket,
      status: 1,
    }, token, 5000);
  } catch {
    // 忽略 typing 失败
  }
}

export async function getConfig(token, userId, contextToken) {
  try {
    const resp = await apiPost('ilink/bot/getconfig', {
      ilink_user_id: userId,
      context_token: contextToken,
    }, token, 10_000);
    return { typingTicket: resp?.typing_ticket || '' };
  } catch {
    return { typingTicket: '' };
  }
}

// ── 清除登录状态 ─────────────────────────────────────────────────────────────

export function clearAuth() {
  try { fs.unlinkSync(path.join(STATE_DIR, 'account.json')); } catch {}
  try { fs.unlinkSync(path.join(STATE_DIR, 'sync-buf.json')); } catch {}
}
