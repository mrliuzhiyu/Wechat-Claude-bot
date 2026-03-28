/**
 * Web GUI 服务器
 * 提供本地 HTTP 服务 + WebSocket 实时通信
 * 无需额外依赖（使用 Node.js 原生 http 模块）
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RENDERER_DIR = path.join(__dirname, 'gui');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

// ── WebSocket 极简实现 ─────────────────────────────────────────────────────

const wsClients = new Set();

function wsUpgrade(req, socket) {
  const key = req.headers['sec-websocket-key'];
  if (!key) { socket.destroy(); return; }

  const accept = crypto
    .createHash('sha1')
    .update(key + '258EAFA5-E914-47DA-95CA-5AB5DC11650E')
    .digest('base64');

  socket.write([
    'HTTP/1.1 101 Switching Protocols',
    'Upgrade: websocket',
    'Connection: Upgrade',
    `Sec-WebSocket-Accept: ${accept}`,
    '', '',
  ].join('\r\n'));

  wsClients.add(socket);
  socket.on('close', () => wsClients.delete(socket));
  socket.on('error', () => wsClients.delete(socket));

  // 处理收到的消息（GUI 的控制命令）
  let buf = Buffer.alloc(0);
  socket.on('data', (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    while (buf.length >= 2) {
      const secondByte = buf[1];
      const masked = (secondByte & 0x80) !== 0;
      let payloadLen = secondByte & 0x7f;
      let offset = 2;

      if (payloadLen === 126) {
        if (buf.length < 4) return;
        payloadLen = buf.readUInt16BE(2);
        offset = 4;
      } else if (payloadLen === 127) {
        if (buf.length < 10) return;
        payloadLen = Number(buf.readBigUInt64BE(2));
        offset = 10;
      }

      if (masked) offset += 4;
      if (buf.length < offset + payloadLen) return;

      let data = buf.subarray(offset, offset + payloadLen);
      if (masked) {
        const mask = buf.subarray(offset - 4, offset);
        for (let i = 0; i < data.length; i++) data[i] ^= mask[i % 4];
      }

      const opcode = buf[0] & 0x0f;
      if (opcode === 0x01) { // text frame
        try {
          const msg = JSON.parse(data.toString());
          handleWsMessage(msg);
        } catch {}
      } else if (opcode === 0x08) { // close
        socket.end();
        wsClients.delete(socket);
      } else if (opcode === 0x09) { // ping
        wsSendRaw(socket, data, 0x0a); // pong
      }

      buf = buf.subarray(offset + payloadLen);
    }
  });
}

function wsSendRaw(socket, data, opcode = 0x01) {
  const payload = Buffer.isBuffer(data) ? data : Buffer.from(data);
  const len = payload.length;
  let header;

  if (len < 126) {
    header = Buffer.alloc(2);
    header[0] = 0x80 | opcode;
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }

  try { socket.write(Buffer.concat([header, payload])); } catch {}
}

export function broadcast(channel, data) {
  const msg = JSON.stringify({ channel, data });
  for (const client of wsClients) {
    wsSendRaw(client, msg);
  }
}

// ── 命令处理 ────────────────────────────────────────────────────────────────

let onCommand = () => {}; // 由外部注册
export function setCommandHandler(handler) { onCommand = handler; }

function handleWsMessage(msg) {
  if (msg.action) onCommand(msg.action, msg.payload);
}

// ── HTTP 服务器 ─────────────────────────────────────────────────────────────

const server = http.createServer((req, res) => {
  // 去掉查询参数
  const urlPath = (req.url || '/').split('?')[0];
  let filePath = urlPath === '/' ? 'index.html' : urlPath.replace(/^\//, '');

  // 安全：阻止路径穿越
  filePath = path.normalize(filePath).replace(/^(\.\.[\/\\])+/, '').replace(/^[\/\\]+/, '');
  const fullPath = path.join(RENDERER_DIR, filePath);

  // 确保在 gui 目录内
  if (!fullPath.startsWith(RENDERER_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  const ext = path.extname(fullPath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  fs.readFile(fullPath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
});
server.setMaxListeners(20);

// WebSocket upgrade
server.on('upgrade', (req, socket, head) => {
  if (req.url === '/ws') {
    wsUpgrade(req, socket);
  } else {
    socket.destroy();
  }
});

export function startServer(port = 3456) {
  return new Promise((resolve, reject) => {
    const tryListen = (p) => {
      server.once('error', (err) => {
        if (err.code === 'EADDRINUSE' && p < port + 10) {
          tryListen(p + 1);
        } else {
          reject(err);
        }
      });
      server.listen(p, '127.0.0.1', () => resolve(p));
    };
    tryListen(port);
  });
}

export function stopServer() {
  return new Promise(r => server.close(r));
}
