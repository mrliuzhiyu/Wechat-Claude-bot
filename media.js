/**
 * 微信 CDN 媒体收发
 *
 * 收图/文件：CDN 下载 → AES-128-ECB 解密 → 保存本地
 * 发图/文件：读文件 → AES-128-ECB 加密 → CDN 上传 → 发消息
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MEDIA_DIR = path.join(__dirname, '.state', 'media');
const CDN_BASE_URL = 'https://novac2c.cdn.weixin.qq.com/c2c';

// ── AES-128-ECB ──────────────────────────────────────────────────────────────

function encryptAesEcb(plaintext, key) {
  const cipher = crypto.createCipheriv('aes-128-ecb', key, null);
  return Buffer.concat([cipher.update(plaintext), cipher.final()]);
}

function decryptAesEcb(ciphertext, key) {
  const decipher = crypto.createDecipheriv('aes-128-ecb', key, null);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

function aesEcbPaddedSize(size) {
  return Math.ceil((size + 1) / 16) * 16;
}

/**
 * 解析 aes_key：base64 → 16字节 raw key
 * 两种格式：base64(16 bytes raw) 或 base64(32 hex chars)
 */
function parseAesKey(aesKeyBase64) {
  const decoded = Buffer.from(aesKeyBase64, 'base64');
  if (decoded.length === 16) return decoded;
  if (decoded.length === 32 && /^[0-9a-fA-F]{32}$/.test(decoded.toString('ascii'))) {
    return Buffer.from(decoded.toString('ascii'), 'hex');
  }
  throw new Error(`Invalid aes_key length: ${decoded.length}`);
}

// ── CDN 下载 ─────────────────────────────────────────────────────────────────

function buildDownloadUrl(encryptedQueryParam) {
  return `${CDN_BASE_URL}/download?encrypted_query_param=${encodeURIComponent(encryptedQueryParam)}`;
}

async function fetchCdnBytes(encryptedQueryParam) {
  const url = buildDownloadUrl(encryptedQueryParam);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`CDN download failed: ${res.status}`);
  return Buffer.from(await res.arrayBuffer());
}

/**
 * 从 CDN 下载并解密媒体文件
 */
export async function downloadAndDecrypt(encryptedQueryParam, aesKeyBase64) {
  const key = parseAesKey(aesKeyBase64);
  const encrypted = await fetchCdnBytes(encryptedQueryParam);
  return decryptAesEcb(encrypted, key);
}

/**
 * 从 CDN 下载（无需解密）
 */
export async function downloadPlain(encryptedQueryParam) {
  return fetchCdnBytes(encryptedQueryParam);
}

// ── CDN 上传 ─────────────────────────────────────────────────────────────────

function buildUploadUrl(uploadParam, filekey) {
  return `${CDN_BASE_URL}/upload?encrypted_query_param=${encodeURIComponent(uploadParam)}&filekey=${encodeURIComponent(filekey)}`;
}

/**
 * 加密并上传 buffer 到 CDN
 * 返回 { downloadParam } 用于构造消息
 */
async function uploadBufferToCdn(buf, uploadParam, filekey, aeskey) {
  const ciphertext = encryptAesEcb(buf, aeskey);
  const url = buildUploadUrl(uploadParam, filekey);

  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: new Uint8Array(ciphertext),
      });
      if (res.status >= 400 && res.status < 500) {
        throw new Error(`CDN upload client error: ${res.status}`);
      }
      if (!res.ok) throw new Error(`CDN upload: ${res.status}`);
      const downloadParam = res.headers.get('x-encrypted-param');
      if (!downloadParam) throw new Error('CDN response missing x-encrypted-param');
      return { downloadParam };
    } catch (err) {
      lastErr = err;
      if (attempt === 3 || (err.message && err.message.includes('client error'))) throw err;
    }
  }
  throw lastErr || new Error('CDN upload failed');
}

// ── 媒体类型 ─────────────────────────────────────────────────────────────────

const UPLOAD_MEDIA_TYPE = { IMAGE: 1, VIDEO: 2, FILE: 3, VOICE: 4 };

const EXT_TO_MIME = {
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
  '.webp': 'image/webp', '.bmp': 'image/bmp', '.mp4': 'video/mp4', '.mov': 'video/quicktime',
  '.pdf': 'application/pdf', '.doc': 'application/msword', '.zip': 'application/zip',
  '.txt': 'text/plain', '.csv': 'text/csv', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
};

export function getMime(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return EXT_TO_MIME[ext] || 'application/octet-stream';
}

function getUploadMediaType(filePath) {
  const mime = getMime(filePath);
  if (mime.startsWith('image/')) return UPLOAD_MEDIA_TYPE.IMAGE;
  if (mime.startsWith('video/')) return UPLOAD_MEDIA_TYPE.VIDEO;
  return UPLOAD_MEDIA_TYPE.FILE;
}

// ── 高级 API：接收媒体 ──────────────────────────────────────────────────────

function ensureMediaDir() {
  fs.mkdirSync(MEDIA_DIR, { recursive: true });
}

/**
 * 下载微信图片消息，保存到本地，返回文件路径
 */
export async function downloadImage(imageItem) {
  const media = imageItem.media;
  if (!media?.encrypt_query_param) return null;

  // aeskey 来源优先级：image_item.aeskey (hex) > media.aes_key (base64)
  let aesKeyBase64;
  if (imageItem.aeskey) {
    aesKeyBase64 = Buffer.from(imageItem.aeskey, 'hex').toString('base64');
  } else if (media.aes_key) {
    aesKeyBase64 = media.aes_key;
  } else {
    return null;
  }

  const buf = await downloadAndDecrypt(media.encrypt_query_param, aesKeyBase64);
  ensureMediaDir();
  // 通过 magic bytes 判断格式
  const ext = detectImageExt(buf);
  const filename = `img_${Date.now()}_${crypto.randomBytes(4).toString('hex')}${ext}`;
  const filePath = path.join(MEDIA_DIR, filename);
  fs.writeFileSync(filePath, buf);
  return filePath;
}

/**
 * 下载微信文件消息
 */
export async function downloadFile(fileItem) {
  const media = fileItem.media;
  if (!media?.encrypt_query_param || !media.aes_key) return null;

  const buf = await downloadAndDecrypt(media.encrypt_query_param, media.aes_key);
  ensureMediaDir();
  const origName = fileItem.file_name || 'file.bin';
  // 清理文件名：去掉路径分隔符和特殊字符，防止路径注入
  const safeName = origName.replace(/[\\/:*?"<>|]/g, '_').replace(/\.\./g, '_');
  const filename = `file_${Date.now()}_${crypto.randomBytes(4).toString('hex')}_${safeName}`;
  const filePath = path.join(MEDIA_DIR, filename);
  fs.writeFileSync(filePath, buf);
  return { filePath, originalName: origName };
}

/**
 * 下载微信视频消息
 */
export async function downloadVideo(videoItem) {
  const media = videoItem.media;
  if (!media?.encrypt_query_param || !media.aes_key) return null;

  const buf = await downloadAndDecrypt(media.encrypt_query_param, media.aes_key);
  ensureMediaDir();
  const filename = `video_${Date.now()}_${crypto.randomBytes(4).toString('hex')}.mp4`;
  const filePath = path.join(MEDIA_DIR, filename);
  fs.writeFileSync(filePath, buf);
  return filePath;
}

function detectImageExt(buf) {
  if (buf[0] === 0xFF && buf[1] === 0xD8) return '.jpg';
  if (buf[0] === 0x89 && buf[1] === 0x50) return '.png';
  if (buf[0] === 0x47 && buf[1] === 0x49) return '.gif';
  if (buf[0] === 0x52 && buf[1] === 0x49) return '.webp'; // RIFF
  return '.jpg'; // fallback
}

// ── 高级 API：发送媒体 ──────────────────────────────────────────────────────

/**
 * 上传本地文件到微信 CDN，返回发送所需的元数据
 * @param {string} filePath - 本地文件路径
 * @param {string} toUserId - 目标用户 ID
 * @param {string} token - bot token
 * @param {string} baseUrl - API base URL
 */
const MAX_UPLOAD_SIZE = 50 * 1024 * 1024; // 50MB

export async function uploadMedia(filePath, toUserId, token, baseUrl) {
  const plaintext = fs.readFileSync(filePath);
  if (plaintext.length > MAX_UPLOAD_SIZE) {
    throw new Error(`文件过大 (${(plaintext.length / 1024 / 1024).toFixed(1)}MB)，上限 50MB`);
  }
  const rawsize = plaintext.length;
  const rawfilemd5 = crypto.createHash('md5').update(plaintext).digest('hex');
  const filesize = aesEcbPaddedSize(rawsize);
  const filekey = crypto.randomBytes(16).toString('hex');
  const aeskey = crypto.randomBytes(16);
  const mediaType = getUploadMediaType(filePath);

  // 1. 获取上传 URL（需要带完整的 iLink 请求头）
  const apiUrl = `${baseUrl}/ilink/bot/getuploadurl`;
  const body = {
    filekey,
    media_type: mediaType,
    to_user_id: toUserId,
    rawsize,
    rawfilemd5,
    filesize,
    no_need_thumb: true,
    aeskey: aeskey.toString('hex'),
  };

  const uin = crypto.randomBytes(4).readUInt32BE(0);
  const res = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'AuthorizationType': 'ilink_bot_token',
      'Authorization': `Bearer ${token}`,
      'X-WECHAT-UIN': Buffer.from(String(uin), 'utf-8').toString('base64'),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`getUploadUrl failed: ${res.status}`);
  const uploadResp = await res.json();
  const uploadParam = uploadResp.upload_param;
  if (!uploadParam) throw new Error('getUploadUrl: no upload_param');

  // 2. 加密上传
  const { downloadParam } = await uploadBufferToCdn(plaintext, uploadParam, filekey, aeskey);

  return {
    filekey,
    downloadParam,
    aeskey: aeskey.toString('hex'),
    fileSize: rawsize,
    fileSizeCiphertext: filesize,
    mediaType,
    fileName: path.basename(filePath),
  };
}

/**
 * 构建媒体消息的 item_list
 */
export function buildMediaItem(uploaded) {
  const aesKeyBase64 = Buffer.from(uploaded.aeskey, 'hex').toString('base64');
  const mediaRef = {
    encrypt_query_param: uploaded.downloadParam,
    aes_key: aesKeyBase64,
    encrypt_type: 1,
  };

  switch (uploaded.mediaType) {
    case UPLOAD_MEDIA_TYPE.IMAGE:
      return { type: 2, image_item: { media: mediaRef, mid_size: uploaded.fileSizeCiphertext } };
    case UPLOAD_MEDIA_TYPE.VIDEO:
      return { type: 5, video_item: { media: mediaRef, video_size: uploaded.fileSizeCiphertext } };
    default:
      return { type: 4, file_item: { media: mediaRef, file_name: uploaded.fileName, len: String(uploaded.fileSize) } };
  }
}
