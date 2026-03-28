"""
微信 CDN 媒体收发
收图/文件：CDN 下载 → AES-128-ECB 解密 → 保存本地
发图/文件：读文件 → AES-128-ECB 加密 → CDN 上传 → 发消息
"""

import math
import os
import time
import base64
import struct
import logging
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

from .config import MEDIA_DIR, CDN_BASE_URL, MAX_UPLOAD_SIZE

log = logging.getLogger(__name__)

# ── AES-128-ECB ──────────────────────────────────────────────────────────────

def _encrypt_aes_ecb(plaintext: bytes, key: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def _decrypt_aes_ecb(ciphertext: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    dec = cipher.decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _aes_ecb_padded_size(size: int) -> int:
    return math.ceil((size + 1) / 16) * 16


def _parse_aes_key(aes_key_b64: str) -> bytes:
    """解析 aes_key：base64 → 16字节 raw key"""
    decoded = base64.b64decode(aes_key_b64)
    if len(decoded) == 16:
        return decoded
    if len(decoded) == 32:
        try:
            hex_str = decoded.decode('ascii')
            if all(c in '0123456789abcdefABCDEF' for c in hex_str):
                return bytes.fromhex(hex_str)
        except (UnicodeDecodeError, ValueError):
            pass
    raise ValueError(f'Invalid aes_key length: {len(decoded)}')


# ── CDN 下载 ─────────────────────────────────────────────────────────────────

def _fetch_cdn_bytes(encrypted_query_param: str) -> bytes:
    url = f'{CDN_BASE_URL}/download?encrypted_query_param={requests.utils.quote(encrypted_query_param)}'
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def download_and_decrypt(encrypted_query_param: str, aes_key_b64: str) -> bytes:
    key = _parse_aes_key(aes_key_b64)
    encrypted = _fetch_cdn_bytes(encrypted_query_param)
    return _decrypt_aes_ecb(encrypted, key)


# ── CDN 上传 ─────────────────────────────────────────────────────────────────

def _upload_buffer_to_url(buf: bytes, url: str, aes_key: bytes) -> str:
    """加密上传，返回 download_param"""
    ciphertext = _encrypt_aes_ecb(buf, aes_key)
    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                url,
                data=ciphertext,
                headers={'Content-Type': 'application/octet-stream'},
                timeout=60,
            )
            if 400 <= resp.status_code < 500:
                raise RuntimeError(f'CDN upload client error: {resp.status_code}')
            resp.raise_for_status()
            download_param = resp.headers.get('x-encrypted-param')
            if not download_param:
                raise RuntimeError('CDN response missing x-encrypted-param')
            return download_param
        except Exception as e:
            last_err = e
            if attempt == 3 or 'client error' in str(e):
                raise
    raise last_err or RuntimeError('CDN upload failed')


# ── 媒体类型 ─────────────────────────────────────────────────────────────────

UPLOAD_MEDIA_TYPE = {'IMAGE': 1, 'VIDEO': 2, 'FILE': 3, 'VOICE': 4}

EXT_TO_MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
    '.webp': 'image/webp', '.bmp': 'image/bmp', '.mp4': 'video/mp4', '.mov': 'video/quicktime',
    '.pdf': 'application/pdf', '.doc': 'application/msword', '.zip': 'application/zip',
    '.txt': 'text/plain', '.csv': 'text/csv', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
}


def get_mime(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return EXT_TO_MIME.get(ext, 'application/octet-stream')


def _get_upload_media_type(file_path: str) -> int:
    mime = get_mime(file_path)
    if mime.startswith('image/'):
        return UPLOAD_MEDIA_TYPE['IMAGE']
    if mime.startswith('video/'):
        return UPLOAD_MEDIA_TYPE['VIDEO']
    return UPLOAD_MEDIA_TYPE['FILE']


# ── 接收媒体 ─────────────────────────────────────────────────────────────────

def _detect_image_ext(buf: bytes) -> str:
    if len(buf) >= 2:
        if buf[0] == 0xFF and buf[1] == 0xD8:
            return '.jpg'
        if buf[0] == 0x89 and buf[1] == 0x50:
            return '.png'
        if buf[0] == 0x47 and buf[1] == 0x49:
            return '.gif'
        if buf[0] == 0x52 and buf[1] == 0x49:
            return '.webp'
    return '.jpg'


def download_image(image_item: dict) -> str | None:
    """下载微信图片，返回本地路径"""
    media_info = image_item.get('media')
    if not media_info or not media_info.get('encrypt_query_param'):
        return None

    # aeskey 来源优先级
    aes_key_b64 = None
    if image_item.get('aeskey'):
        aes_key_b64 = base64.b64encode(bytes.fromhex(image_item['aeskey'])).decode()
    elif media_info.get('aes_key'):
        aes_key_b64 = media_info['aes_key']
    if not aes_key_b64:
        return None

    buf = download_and_decrypt(media_info['encrypt_query_param'], aes_key_b64)
    MEDIA_DIR.mkdir(exist_ok=True)
    ext = _detect_image_ext(buf)
    filename = f'img_{int(time.time())}_{os.urandom(4).hex()}{ext}'
    file_path = MEDIA_DIR / filename
    file_path.write_bytes(buf)
    return str(file_path)


def download_file(file_item: dict) -> dict | None:
    """下载微信文件，返回 {'file_path': ..., 'original_name': ...}"""
    media_info = file_item.get('media')
    if not media_info or not media_info.get('encrypt_query_param') or not media_info.get('aes_key'):
        return None

    buf = download_and_decrypt(media_info['encrypt_query_param'], media_info['aes_key'])
    MEDIA_DIR.mkdir(exist_ok=True)
    orig_name = file_item.get('file_name', 'file.bin')
    import re
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', orig_name).replace('..', '_')
    filename = f'file_{int(time.time())}_{os.urandom(4).hex()}_{safe_name}'
    file_path = MEDIA_DIR / filename
    file_path.write_bytes(buf)
    return {'file_path': str(file_path), 'original_name': orig_name}


def download_video(video_item: dict) -> str | None:
    """下载微信视频，返回本地路径"""
    media_info = video_item.get('media')
    if not media_info or not media_info.get('encrypt_query_param') or not media_info.get('aes_key'):
        return None

    buf = download_and_decrypt(media_info['encrypt_query_param'], media_info['aes_key'])
    MEDIA_DIR.mkdir(exist_ok=True)
    filename = f'video_{int(time.time())}_{os.urandom(4).hex()}.mp4'
    file_path = MEDIA_DIR / filename
    file_path.write_bytes(buf)
    return str(file_path)


# ── 发送媒体 ─────────────────────────────────────────────────────────────────

def upload_media(file_path: str, to_user_id: str, token: str,
                 base_url: str = 'https://ilinkai.weixin.qq.com') -> dict:
    """上传本地文件到微信 CDN"""
    plaintext = Path(file_path).read_bytes()
    if len(plaintext) > MAX_UPLOAD_SIZE:
        raise RuntimeError(f'文件过大 ({len(plaintext) / 1024 / 1024:.1f}MB)，上限 50MB')

    import hashlib
    raw_size = len(plaintext)
    raw_md5 = hashlib.md5(plaintext).hexdigest()
    file_size = _aes_ecb_padded_size(raw_size)
    file_key = os.urandom(16).hex()
    aes_key = os.urandom(16)
    media_type = _get_upload_media_type(file_path)

    # 1. 获取上传 URL
    uin = struct.unpack('>I', os.urandom(4))[0]
    resp = requests.post(
        f'{base_url}/ilink/bot/getuploadurl',
        json={
            'filekey': file_key,
            'media_type': media_type,
            'to_user_id': to_user_id,
            'rawsize': raw_size,
            'rawfilemd5': raw_md5,
            'filesize': file_size,
            'no_need_thumb': True,
            'aeskey': aes_key.hex(),
        },
        headers={
            'Content-Type': 'application/json',
            'AuthorizationType': 'ilink_bot_token',
            'Authorization': f'Bearer {token}',
            'X-WECHAT-UIN': base64.b64encode(str(uin).encode()).decode(),
        },
        timeout=15,
    )
    resp.raise_for_status()
    upload_resp = resp.json()

    upload_full_url = upload_resp.get('upload_full_url')
    upload_param = upload_resp.get('upload_param')
    if not upload_full_url and not upload_param:
        raise RuntimeError('getUploadUrl: no upload URL')

    # 2. 加密上传
    if upload_full_url:
        download_param = _upload_buffer_to_url(plaintext, upload_full_url, aes_key)
    else:
        url = f'{CDN_BASE_URL}/upload?encrypted_query_param={requests.utils.quote(upload_param)}&filekey={requests.utils.quote(file_key)}'
        download_param = _upload_buffer_to_url(plaintext, url, aes_key)

    return {
        'file_key': file_key,
        'download_param': download_param,
        'aes_key': aes_key.hex(),
        'file_size': raw_size,
        'file_size_ciphertext': file_size,
        'media_type': media_type,
        'file_name': Path(file_path).name,
    }


def build_media_item(uploaded: dict) -> dict:
    """构建媒体消息的 item"""
    aes_key_b64 = base64.b64encode(uploaded['aes_key'].encode()).decode()
    media_ref = {
        'encrypt_query_param': uploaded['download_param'],
        'aes_key': aes_key_b64,
        'encrypt_type': 1,
    }
    mt = uploaded['media_type']
    if mt == UPLOAD_MEDIA_TYPE['IMAGE']:
        return {'type': 2, 'image_item': {'media': media_ref, 'mid_size': uploaded['file_size_ciphertext']}}
    elif mt == UPLOAD_MEDIA_TYPE['VIDEO']:
        return {'type': 5, 'video_item': {'media': media_ref, 'video_size': uploaded['file_size_ciphertext']}}
    else:
        return {'type': 4, 'file_item': {'media': media_ref, 'file_name': uploaded['file_name'], 'len': str(uploaded['file_size'])}}
