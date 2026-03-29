"""
微信 iLink Bot API 封装
协议来源：@tencent-weixin/openclaw-weixin 官方插件
"""

import json
import os
import struct
import base64
import time
import logging
from pathlib import Path

import requests

from .config import WEIXIN_BASE_URL, LONG_POLL_TIMEOUT, STATE_DIR

log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _random_wechat_uin() -> str:
    uint32 = struct.unpack('>I', os.urandom(4))[0]
    return base64.b64encode(str(uint32).encode()).decode()


def _build_headers(token: str | None = None) -> dict:
    headers = {
        'Content-Type': 'application/json',
        'AuthorizationType': 'ilink_bot_token',
        'X-WECHAT-UIN': _random_wechat_uin(),
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _api_post(endpoint: str, body: dict, token: str | None = None,
              timeout: float = 15) -> dict | None:
    """发送 POST 请求到微信 API"""
    url = f'{WEIXIN_BASE_URL}/{endpoint}'
    try:
        resp = requests.post(
            url,
            json=body,
            headers=_build_headers(token),
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f'HTTP {e.response.status_code}: {e.response.text[:200]}')


# ── 状态持久化 ──────────────────────────────────────────────────────────────

def _save_state(key: str, data: dict):
    STATE_DIR.mkdir(exist_ok=True)
    path = STATE_DIR / f'{key}.json'
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_state(key: str) -> dict | None:
    try:
        path = STATE_DIR / f'{key}.json'
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ── 二维码登录 ──────────────────────────────────────────────────────────────

def fetch_qr_code() -> dict:
    """获取登录二维码"""
    url = f'{WEIXIN_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3'
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def poll_qr_status(qrcode: str) -> dict:
    """轮询二维码扫码状态"""
    url = f'{WEIXIN_BASE_URL}/ilink/bot/get_qrcode_status?qrcode={requests.utils.quote(qrcode)}'
    try:
        resp = requests.get(
            url,
            headers={'iLink-App-ClientVersion': '1'},
            timeout=LONG_POLL_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {'status': 'wait'}


def validate_token(token: str) -> bool:
    """验证已保存的 token 是否有效"""
    try:
        resp = _api_post('ilink/bot/getupdates', {'get_updates_buf': ''}, token, timeout=10)
        if resp is None:
            return True
        if resp.get('errcode') == -14 or resp.get('ret') == -14:
            return False
        if resp.get('ret') and resp['ret'] != 0:
            return False
        return True
    except Exception:
        return False


def get_saved_account() -> dict | None:
    return _load_state('account')


def save_account(account: dict):
    _save_state('account', account)


def clear_auth():
    for name in ('account', 'sync-buf'):
        try:
            (STATE_DIR / f'{name}.json').unlink()
        except FileNotFoundError:
            pass


# ── 消息收发 ─────────────────────────────────────────────────────────────────

# 消息类型常量
MSG_TYPE_TEXT = 1
MSG_TYPE_IMAGE = 2
MSG_TYPE_VOICE = 3
MSG_TYPE_FILE = 4
MSG_TYPE_VIDEO = 5


def get_updates(token: str) -> dict:
    """获取新消息，返回 {'messages': [...], 'media': [...]}"""
    sync_buf = _load_state('sync-buf')
    resp = _api_post(
        'ilink/bot/getupdates',
        {'get_updates_buf': (sync_buf or {}).get('buf', '')},
        token,
        timeout=LONG_POLL_TIMEOUT,
    )

    if not resp:
        return {'messages': [], 'media': []}

    if resp.get('errcode') == -14 or resp.get('ret') == -14:
        raise SessionExpiredError()

    ret = resp.get('ret', 0)
    if ret and ret != 0:
        raise RuntimeError(f'getUpdates 错误: ret={ret} errmsg={resp.get("errmsg", "")}')

    if resp.get('get_updates_buf'):
        _save_state('sync-buf', {'buf': resp['get_updates_buf']})

    messages = []
    media = []

    for msg in resp.get('msgs', []):
        parsed = _parse_message(msg)
        if parsed:
            if parsed['type'] == 'text':
                messages.append(parsed)
            else:
                media.append(parsed)

    return {'messages': messages, 'media': media}


def _parse_message(msg: dict) -> dict | None:
    """解析微信消息"""
    if not msg.get('from_user_id') or not msg.get('item_list'):
        return None
    # 过滤 Bot 自己的消息（message_type: 1=USER, 2=BOT）
    if msg.get('message_type') == 2:
        return None

    base = {
        'from': msg['from_user_id'],
        'context_token': msg.get('context_token'),
        'timestamp': msg.get('create_time_ms'),
    }

    for item in msg['item_list']:
        item_type = item.get('type')

        if item_type == MSG_TYPE_TEXT:
            text = (item.get('text_item') or {}).get('text')
            if text:
                return {**base, 'type': 'text', 'text': text}

        elif item_type == MSG_TYPE_VOICE:
            voice_text = (item.get('voice_item') or {}).get('text')
            if voice_text:
                return {**base, 'type': 'text', 'text': voice_text, 'source': 'voice'}
            return {**base, 'type': 'voice_no_text'}

        elif item_type == MSG_TYPE_IMAGE:
            return {**base, 'type': 'image', 'image_item': item.get('image_item')}

        elif item_type == MSG_TYPE_VIDEO:
            return {**base, 'type': 'video', 'video_item': item.get('video_item')}

        elif item_type == MSG_TYPE_FILE:
            return {**base, 'type': 'file', 'file_item': item.get('file_item')}

    return None


def send_message(token: str, to: str, text: str, context_token: str | None = None):
    """发送文字消息"""
    client_id = f'wcb-{int(time.time() * 1000)}-{os.urandom(4).hex()}'
    resp = _api_post('ilink/bot/sendmessage', {
        'msg': {
            'from_user_id': '',
            'to_user_id': to,
            'client_id': client_id,
            'message_type': 2,
            'message_state': 2,
            'item_list': [{'type': 1, 'text_item': {'text': text}}],
            'context_token': context_token or '',
        },
    }, token)
    if resp and resp.get('ret') and resp['ret'] != 0:
        raise RuntimeError(f'发送失败: {resp.get("errmsg", resp.get("ret"))}')


def send_media_message(token: str, to: str, media_item: dict,
                       context_token: str | None = None, caption: str | None = None):
    """发送媒体消息（图片/文件/视频）"""
    items = []
    if caption:
        items.append({'type': 1, 'text_item': {'text': caption}})
    items.append(media_item)

    for item in items:
        client_id = f'wcb-{int(time.time() * 1000)}-{os.urandom(4).hex()}'
        resp = _api_post('ilink/bot/sendmessage', {
            'msg': {
                'from_user_id': '',
                'to_user_id': to,
                'client_id': client_id,
                'message_type': 2,
                'message_state': 2,
                'item_list': [item],
                'context_token': context_token or '',
            },
        }, token)
        if resp and resp.get('ret') and resp['ret'] != 0:
            raise RuntimeError(f'发送失败: {resp.get("errmsg", resp.get("ret"))}')


def send_typing(token: str, to: str, typing_ticket: str):
    """发送正在输入状态"""
    if not typing_ticket:
        return
    try:
        _api_post('ilink/bot/sendtyping', {
            'ilink_user_id': to,
            'typing_ticket': typing_ticket,
            'status': 1,
        }, token, timeout=5)
    except Exception:
        pass


def get_config(token: str, user_id: str, context_token: str | None = None) -> dict:
    """获取配置（typing ticket 等）"""
    try:
        resp = _api_post('ilink/bot/getconfig', {
            'ilink_user_id': user_id,
            'context_token': context_token or '',
        }, token, timeout=10)
        return {'typing_ticket': (resp or {}).get('typing_ticket', '')}
    except Exception:
        return {'typing_ticket': ''}


# ── 异常 ────────────────────────────────────────────────────────────────────

class SessionExpiredError(Exception):
    """微信会话过期"""
    pass
