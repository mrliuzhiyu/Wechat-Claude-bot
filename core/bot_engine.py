"""
Bot 核心引擎
协调微信 API、模型适配器、消息处理
通过 Qt 信号与 GUI 通信
"""

import os
import re
import time
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .config import (
    DEFAULT_CWD, MODELS, MAX_REPLY_LENGTH, AUTO_SEND_EXTS,
    WECHAT_SYSTEM_PROMPT, OUTBOX_DIR,
)
from . import weixin_api
from . import media as media_mod
from adapters.base import ModelAdapter

log = logging.getLogger(__name__)


# ── 纯函数工具 ──────────────────────────────────────────────────────────────

def md2wx(text: str) -> str:
    """Markdown → 微信纯文本"""
    blocks = []

    def replace_code_block(m):
        i = len(blocks)
        blocks.append(f'--- {m.group(1)} ---\n{m.group(2).rstrip()}\n---')
        return f'\x00CB{i}\x00'

    r = re.sub(r'```(\w*)\n([\s\S]*?)```', replace_code_block, text)
    r = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', r)
    r = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', r)
    r = re.sub(r'^\|[\s:|\-]+\|$', '', r, flags=re.MULTILINE)
    r = re.sub(r'^\|(.+)\|$', lambda m: '  '.join(c.strip() for c in m.group(1).split('|')), r, flags=re.MULTILINE)
    r = re.sub(r'\*\*(.+?)\*\*', r'\1', r)
    r = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', r)
    r = re.sub(r'^#{1,6}\s+(.+)$', r'【\1】', r, flags=re.MULTILINE)
    r = re.sub(r'`([^`]+)`', r'\1', r)
    r = re.sub(r'\x00CB(\d+)\x00', lambda m: blocks[int(m.group(1))], r)
    return r.strip()


def split_msg(text: str, max_len: int) -> list[str]:
    """智能拆分长消息"""
    if len(text) <= max_len:
        return [text]
    chunks = []
    rest = text
    while rest:
        if len(rest) <= max_len:
            chunks.append(rest)
            break
        at = -1
        cb = rest.rfind('\n---\n', 0, max_len)
        if cb > max_len * 0.3:
            at = cb + 5
        if at < 0:
            e = rest.rfind('\n\n', 0, max_len)
            if e > max_len * 0.3:
                at = e + 1
        if at < 0:
            n = rest.rfind('\n', 0, max_len)
            if n > max_len * 0.3:
                at = n + 1
        if at < 0:
            at = max_len
        chunks.append(rest[:at])
        rest = rest[at:]
    if len(chunks) > 1:
        return [c if i == 0 else f'({i + 1}/{len(chunks)})\n{c}' for i, c in enumerate(chunks)]
    return chunks


def extract_file_paths(text: str) -> list[str]:
    """从文本中提取文件路径"""
    paths = []
    patterns = [
        re.compile(r'[A-Z]:\\(?:[\w\u4e00-\u9fff.\-\s]+\\)*[\w\u4e00-\u9fff.\-\s]+\.\w{2,5}', re.IGNORECASE),
        re.compile(r'/(?:[\w\u4e00-\u9fff.\-]+/)+[\w\u4e00-\u9fff.\-]+\.\w{2,5}'),
    ]
    for pat in patterns:
        paths.extend(m.group(0).strip() for m in pat.finditer(text))
    return list(set(paths))


def build_media_prompt(msg_type: str, file_path: str, original_name: str = '') -> str:
    """根据文件类型生成 prompt"""
    name = original_name or Path(file_path).name
    ext = Path(name).suffix.lower()
    prompts = {
        'image': f'用户发来一张图片，已保存到: {file_path}\n请用 Read 工具查看并描述这张图片的内容。',
        'video': f'用户发来一个视频，已保存到: {file_path}\n请用 Bash 工具尝试运行 ffprobe 获取视频元数据。如果不可用，告知用户视频已保存。',
    }
    if msg_type in prompts:
        return prompts[msg_type]
    if ext == '.pdf':
        return f'用户发来 PDF 文档 "{name}"，已保存到: {file_path}\n请用 Read 工具读取并总结文档要点。'
    if ext in ('.csv', '.xls', '.xlsx'):
        return f'用户发来数据文件 "{name}"，已保存到: {file_path}\n请读取并分析数据。'
    if ext in ('.js', '.ts', '.py', '.java', '.go', '.rs', '.c', '.cpp', '.h', '.rb', '.php'):
        return f'用户发来代码文件 "{name}"，已保存到: {file_path}\n请读取代码，解释功能并指出潜在问题。'
    if ext in ('.zip', '.rar', '.7z', '.tar', '.gz'):
        return f'用户发来压缩包 "{name}"，已保存到: {file_path}\n请告知用户文件已保存，并询问是否需要解压。'
    return f'用户发来文件 "{name}"，已保存到: {file_path}\n请读取并分析这个文件的内容。'


def fmt_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}h{m}m'
    if m > 0:
        return f'{m}m{s}s'
    return f'{s}s'


# ── BotEngine（在 QThread 中运行）────────────────────────────────────────────

class BotEngine(QObject):
    """Bot 核心引擎，在独立线程中运行"""

    # ── Qt 信号（线程安全通信）──
    sig_log = pyqtSignal(str, str)           # (level, message)
    sig_status = pyqtSignal(str, dict)        # (state, data)
    sig_qr = pyqtSignal(str)                  # (qr_content_url)
    sig_message_in = pyqtSignal(str, str)     # (user_id, text)
    sig_message_out = pyqtSignal(str, str)    # (user_id, text)
    sig_action = pyqtSignal(str, str, str)    # (icon, description, detail)

    def __init__(self, adapter: ModelAdapter, parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.stopping = False
        self.account = None
        self.start_time = None

        self.user_cwd: dict[str, str] = {}
        self.user_models: dict[str, str] = {}
        self.default_model = 'sonnet'
        self.ctx_tokens: dict[str, dict] = {}
        self.last_progress: dict[str, dict] = {}
        self.user_busy: set[str] = set()
        self.stats = {'message_count': 0, 'active_users': set()}

        self._executor = ThreadPoolExecutor(max_workers=3)

    # ── 公共方法 ────────────────────────────────────────────────────────

    def start(self):
        """启动 Bot（在工作线程中调用）"""
        self.stopping = False
        self.start_time = time.time()
        self._log('info', '🤖 微信 Claude Code Bot 启动中...')
        self.sig_status.emit('init', {})

        # 1. 环境检测
        self.sig_status.emit('checking-env', {})
        version = self.adapter.check_available()
        if not version:
            self._log('error', f'❌ 未检测到 {self.adapter.name}')
            self.sig_status.emit('env-error', {'missing': self.adapter.name})
            return

        self._log('info', f'✅ {self.adapter.name} {version}')
        self._log('info', f'📁 {DEFAULT_CWD}')
        self._log('info', f'🧠 默认模型: {MODELS[self.default_model]["label"]}')
        self.sig_status.emit('env-ready', {'version': version, 'cwd': DEFAULT_CWD, 'model': self.default_model})

        # 2. 登录 + 消息循环
        while not self.stopping:
            try:
                account = self._login()
                if not account:
                    break
                self.account = account
                self.sig_status.emit('connected', {'bot_id': account.get('botId', '')})
                self._log('info', '📡 监听中...')

                result = self._message_loop(account)
                if result == 'RECONNECT':
                    self._log('info', '🔄 重连...')
                    self.sig_status.emit('reconnecting', {})
                    time.sleep(3)
                    continue
                break
            except Exception as e:
                if self.stopping:
                    break
                self._log('error', f'❌ {e}，5秒后重试...')
                self.sig_status.emit('disconnected', {'error': str(e)})
                time.sleep(5)

        self.sig_status.emit('stopped', {})

    def stop(self):
        self.stopping = True
        self.adapter.kill_all()
        self._log('info', '🛑 正在停止...')

    def get_cwd(self, user_id: str) -> str:
        return self.user_cwd.get(user_id, DEFAULT_CWD)

    def get_status(self) -> dict:
        return {
            'running': not self.stopping and self.account is not None,
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'message_count': self.stats['message_count'],
            'active_users': len(self.stats['active_users']),
            'model': self.default_model,
            'cwd': DEFAULT_CWD,
        }

    # ── 登录流程 ────────────────────────────────────────────────────────

    def _login(self) -> dict | None:
        saved = weixin_api.get_saved_account()
        if saved and saved.get('token'):
            self._log('info', '🔑 发现已保存的凭据，验证中...')
            if weixin_api.validate_token(saved['token']):
                self._log('info', '✅ 凭据有效，恢复连接')
                return saved
            self._log('warn', '⚠️ 凭据已失效，重新扫码')
            weixin_api.clear_auth()

        self.sig_status.emit('need-login', {})
        max_qr_refresh = 3

        for refresh in range(max_qr_refresh):
            if self.stopping:
                return None
            self._log('info', '正在获取登录二维码...')
            qr = weixin_api.fetch_qr_code()
            self.sig_qr.emit(qr['qrcode_img_content'])
            self.sig_status.emit('qr-ready', {})
            self._log('info', '📱 请用微信扫描二维码')

            deadline = time.time() + 3 * 60
            scanned_emitted = False

            while time.time() < deadline and not self.stopping:
                status = weixin_api.poll_qr_status(qr['qrcode'])
                st = status.get('status')

                if st == 'scaned' and not scanned_emitted:
                    self._log('info', '👀 已扫码，请在微信确认...')
                    self.sig_status.emit('qr-scanned', {})
                    scanned_emitted = True
                elif st == 'confirmed':
                    if not status.get('ilink_bot_id'):
                        raise RuntimeError('登录失败：服务器未返回 bot_id')
                    account = {
                        'token': status['bot_token'],
                        'botId': status['ilink_bot_id'],
                        'baseUrl': status.get('baseurl', 'https://ilinkai.weixin.qq.com'),
                        'userId': status.get('ilink_user_id'),
                    }
                    weixin_api.save_account(account)
                    self._log('info', f'✅ 连接成功！Bot ID: {account["botId"]}')
                    return account
                elif st == 'expired':
                    self._log('info', '⏳ 二维码已过期')
                    break

                time.sleep(1)

        if self.stopping:
            return None
        raise RuntimeError(f'登录失败：二维码 {max_qr_refresh} 次过期')

    # ── 消息循环 ────────────────────────────────────────────────────────

    def _message_loop(self, account: dict) -> str:
        err_count = 0
        while not self.stopping:
            try:
                r = weixin_api.get_updates(account['token'])
                err_count = 0
                for m in r['messages']:
                    self._executor.submit(self._handle_message, account, m)
                for m in r['media']:
                    self._executor.submit(self._handle_media_message, account, m)
            except weixin_api.SessionExpiredError:
                if self.stopping:
                    break
                self._log('warn', '⚠️ Session 过期，重连...')
                weixin_api.clear_auth()
                return 'RECONNECT'
            except Exception as e:
                if self.stopping:
                    break
                err_count += 1
                self._log('error', f'❌ 轮询错误 ({err_count}/5): {e}')
                if err_count >= 5:
                    err_count = 0
                    time.sleep(30)
                else:
                    time.sleep(2)
        return 'SHUTDOWN'

    # ── 消息处理 ────────────────────────────────────────────────────────

    def _handle_message(self, account: dict, msg: dict):
        user_id = msg['from']
        text = msg.get('text', '').strip()
        ctx = msg.get('context_token')
        if ctx:
            self.ctx_tokens[user_id] = {'token': ctx, 'ts': time.time()}
        if not text:
            return

        if user_id in self.user_busy:
            self._send(account['token'], user_id, '⏳ 上一条还在处理，请稍等...')
            return

        is_voice = msg.get('source') == 'voice'
        sid = user_id[:8] + '..'
        self._log('info', f'👤 {sid}{"🎤" if is_voice else ""}: {text[:80]}')
        self.sig_message_in.emit(user_id, text)
        self.stats['message_count'] += 1
        self.stats['active_users'].add(user_id)

        # 斜杠命令
        parts = text.split(' ', 1)
        cmd = parts[0].lower()
        cmd_args = parts[1] if len(parts) > 1 else ''
        cmd_result = self._handle_command(cmd, user_id, cmd_args, account)
        if cmd_result is not None:
            self._send(account['token'], user_id, cmd_result)
            return

        self.user_busy.add(user_id)
        try:
            prompt = f'(用户通过语音输入，以下为语音转文字，可能有错字) {text}' if is_voice else text
            model_id = MODELS.get(self.user_models.get(user_id, self.default_model), MODELS['sonnet'])['id']

            # Typing 指示
            typing_stop = self._start_typing(account, user_id, ctx)

            try:
                result = self.adapter.chat(
                    user_id, prompt,
                    cwd=self.get_cwd(user_id),
                    model=model_id,
                    system_prompt=WECHAT_SYSTEM_PROMPT,
                    on_progress=lambda pt: self._on_progress(account['token'], user_id, pt),
                )
            finally:
                typing_stop()

            reply = result.text
            for chunk in split_msg(md2wx(reply), MAX_REPLY_LENGTH):
                self._send(account['token'], user_id, chunk)
            self._log('info', f'🤖 {sid}: {reply[:80]}... ({len(reply)}字)')
            self.sig_message_out.emit(user_id, reply)

            self._auto_send_files(account, user_id, result.written_files, result.read_media_files, reply)

        except Exception as e:
            err_msg = str(e)
            if '超时' in err_msg:
                reply = '⏱️ 超时了，试试拆分成更小的步骤。'
            elif '无法启动' in err_msg:
                reply = '❌ Claude Code 未运行。'
            else:
                reply = f'⚠️ {err_msg[:200]}'
            self._send(account['token'], user_id, reply)
            self._log('error', f'❌ {sid}: {err_msg}')
        finally:
            self.user_busy.discard(user_id)
            self.last_progress.pop(user_id, None)

    def _handle_media_message(self, account: dict, msg: dict):
        user_id = msg['from']
        ctx = msg.get('context_token')
        if ctx:
            self.ctx_tokens[user_id] = {'token': ctx, 'ts': time.time()}
        msg_type = msg['type']

        if user_id in self.user_busy:
            self._send(account['token'], user_id, '⏳ 上一条还在处理，请稍等...')
            return
        if msg_type == 'voice_no_text':
            self._send(account['token'], user_id, '🎤 语音未转文字。请开启微信「语音转文字」功能。')
            return

        # 下载媒体
        file_path = None
        original_name = ''
        desc = ''
        try:
            if msg_type == 'image' and msg.get('image_item'):
                file_path = media_mod.download_image(msg['image_item'])
                desc = '图片'
            elif msg_type == 'file' and msg.get('file_item'):
                r = media_mod.download_file(msg['file_item'])
                if r:
                    file_path, original_name = r['file_path'], r['original_name']
                    desc = f'文件 {original_name}'
            elif msg_type == 'video' and msg.get('video_item'):
                file_path = media_mod.download_video(msg['video_item'])
                desc = '视频'
        except Exception as e:
            self._send(account['token'], user_id, f'⚠️ 下载失败: {str(e)[:100]}')
            return

        if not file_path:
            self._send(account['token'], user_id, '📎 无法处理此媒体，请发文字。')
            return

        self._log('info', f'📎 {user_id[:8]}..: 收到{desc} → {file_path}')
        self.stats['message_count'] += 1
        self.stats['active_users'].add(user_id)

        self.user_busy.add(user_id)
        try:
            prompt = build_media_prompt(msg_type, file_path, original_name)
            model_id = MODELS.get(self.user_models.get(user_id, self.default_model), MODELS['sonnet'])['id']

            typing_stop = self._start_typing(account, user_id, ctx)
            try:
                result = self.adapter.chat(
                    user_id, prompt,
                    cwd=self.get_cwd(user_id),
                    model=model_id,
                    system_prompt=WECHAT_SYSTEM_PROMPT,
                    on_progress=lambda pt: self._on_progress(account['token'], user_id, pt),
                )
            finally:
                typing_stop()

            for chunk in split_msg(md2wx(result.text), MAX_REPLY_LENGTH):
                self._send(account['token'], user_id, chunk)
            self._auto_send_files(account, user_id, result.written_files, result.read_media_files, result.text)
        except Exception as e:
            self._send(account['token'], user_id, f'⚠️ 分析失败: {str(e)[:150]}')
        finally:
            self.user_busy.discard(user_id)
            self.last_progress.pop(user_id, None)

    # ── 斜杠命令 ────────────────────────────────────────────────────────

    def _handle_command(self, cmd: str, user_id: str, args: str, account: dict) -> str | None:
        if cmd == '/new':
            self.adapter.clear_session(user_id)
            return '🔄 对话已重置。'

        if cmd == '/model':
            target = args.strip().lower()
            if not target:
                cur = self.user_models.get(user_id, self.default_model)
                lines = [f'  {"→ " if k == cur else "  "}{k} — {m["label"]} ({m["desc"]})' for k, m in MODELS.items()]
                return f'当前模型: {MODELS[cur]["label"]}\n\n' + '\n'.join(lines) + '\n\n切换: /model sonnet'
            if target not in MODELS:
                return f'❌ 未知模型: {target}\n可选: {", ".join(MODELS.keys())}'
            cur = self.user_models.get(user_id, self.default_model)
            if target == cur:
                return f'已经是 {MODELS[target]["label"]} 了。'
            self.user_models[user_id] = target
            self.adapter.clear_session(user_id)
            return f'✅ 切换到 {MODELS[target]["label"]}，对话已重置。'

        if cmd == '/cwd':
            target = args.strip()
            if not target:
                return f'当前工作目录: {self.get_cwd(user_id)}\n\n切换: /cwd <路径>'
            resolved = str(Path(target).resolve())
            if not Path(resolved).exists():
                return f'❌ 目录不存在: {resolved}'
            if not Path(resolved).is_dir():
                return f'❌ 不是目录: {resolved}'
            self.user_cwd[user_id] = resolved
            self.adapter.clear_session(user_id)
            return f'✅ 工作目录切换到: {resolved}\n对话已重置。'

        if cmd == '/send':
            return self._cmd_send(user_id, args, account)

        if cmd == '/help':
            cur_model = MODELS.get(self.user_models.get(user_id, self.default_model), MODELS['sonnet'])
            return '\n'.join([
                '命令:', '  /new — 重置对话', '  /model — 切换模型',
                '  /cwd <路径> — 切换工作目录', '  /send <路径> — 发送文件',
                '  /status — 查看状态', '',
                f'模型: {cur_model["label"]} | 目录: {self.get_cwd(user_id)}',
            ])

        if cmd == '/status':
            v = self.adapter.check_available()
            uptime = fmt_uptime(time.time() - (self.start_time or time.time()))
            cur_model = MODELS.get(self.user_models.get(user_id, self.default_model), MODELS['sonnet'])
            return f'{self.adapter.name}: {v or "❌"}\n模型: {cur_model["label"]}\n目录: {self.get_cwd(user_id)}\n运行: {uptime}'

        return None  # 不是命令

    def _cmd_send(self, user_id: str, args: str, account: dict) -> str:
        pipe_idx = args.find('|')
        file_path = (args[:pipe_idx] if pipe_idx > 0 else args).strip()
        caption = args[pipe_idx + 1:].strip() if pipe_idx > 0 else ''
        if not file_path:
            return '用法: /send <文件路径>'
        p = Path(file_path)
        if not p.exists():
            return f'❌ 文件不存在: {file_path}'
        if p.is_dir():
            return '❌ 不能发送文件夹'
        if p.stat().st_size > 50 * 1024 * 1024:
            return f'❌ 文件过大 ({p.stat().st_size / 1024 / 1024:.1f}MB)，上限 50MB'
        if p.stat().st_size == 0:
            return '❌ 文件为空'
        try:
            ctx = (self.ctx_tokens.get(user_id) or {}).get('token')
            uploaded = media_mod.upload_media(file_path, user_id, account['token'],
                                             account.get('baseUrl', 'https://ilinkai.weixin.qq.com'))
            item = media_mod.build_media_item(uploaded)
            weixin_api.send_media_message(account['token'], user_id, item, ctx, caption or None)
            return f'✅ 已发送: {p.name}'
        except Exception as e:
            return f'❌ 发送失败: {str(e)[:150]}'

    # ── 辅助方法 ────────────────────────────────────────────────────────

    def _send(self, token: str, to: str, text: str):
        try:
            ctx = (self.ctx_tokens.get(to) or {}).get('token')
            weixin_api.send_message(token, to, text, ctx)
        except Exception as e:
            self._log('warn', f'⚠️ 发送失败: {str(e)[:80]}')

    def _on_progress(self, token: str, user_id: str, text: str):
        last = self.last_progress.get(user_id)
        if last and last.get('t') == text and time.time() - last.get('ts', 0) < 5:
            return
        self.last_progress[user_id] = {'t': text, 'ts': time.time()}
        self._send(token, user_id, text)
        self._log('info', f'  📊 {text}')
        # 解析操作事件发给 GUI
        icon = text[:2] if text else '🔧'
        desc = text[2:].strip() if len(text) > 2 else text
        self.sig_action.emit(icon, desc, user_id[:8])

    def _start_typing(self, account: dict, user_id: str, ctx: str | None):
        """启动 typing 指示，返回停止函数"""
        stopped = threading.Event()

        def typing_loop():
            try:
                cfg = weixin_api.get_config(account['token'], user_id, ctx)
                ticket = cfg.get('typing_ticket')
                if not ticket:
                    return
                weixin_api.send_typing(account['token'], user_id, ticket)
                while not stopped.wait(5):
                    weixin_api.send_typing(account['token'], user_id, ticket)
            except Exception:
                pass

        t = threading.Thread(target=typing_loop, daemon=True)
        t.start()
        return lambda: stopped.set()

    def _auto_send_files(self, account: dict, user_id: str,
                         written_files: list, read_media_files: list, reply_text: str):
        sent = set()
        from_reply = extract_file_paths(reply_text or '')
        all_tracked = list(set((written_files or []) + (read_media_files or []) + from_reply))

        for fp in all_tracked:
            ext = Path(fp).suffix.lower()
            if ext not in AUTO_SEND_EXTS or fp in sent:
                continue
            try:
                if self._send_file(account, user_id, fp):
                    sent.add(fp)
            except Exception as e:
                self._log('warn', f'⚠️ 自动发送失败 {Path(fp).name}: {str(e)[:80]}')

        # 发件箱
        try:
            for name in os.listdir(OUTBOX_DIR):
                if name.startswith('.'):
                    continue
                fp = str(OUTBOX_DIR / name)
                if fp in sent:
                    continue
                try:
                    p = Path(fp)
                    if not p.is_file():
                        continue
                    if self._send_file(account, user_id, fp):
                        sent.add(fp)
                    p.unlink()
                except Exception as e:
                    self._log('warn', f'⚠️ 发件箱发送失败 {name}: {str(e)[:80]}')
                    try:
                        Path(fp).unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    def _send_file(self, account: dict, user_id: str, file_path: str) -> bool:
        p = Path(file_path)
        if not p.is_absolute():
            p = Path(self.get_cwd(user_id)) / p
        if not p.exists() or p.stat().st_size == 0 or p.stat().st_size > 50 * 1024 * 1024:
            return False
        ctx = (self.ctx_tokens.get(user_id) or {}).get('token')
        uploaded = media_mod.upload_media(str(p), user_id, account['token'],
                                         account.get('baseUrl', 'https://ilinkai.weixin.qq.com'))
        item = media_mod.build_media_item(uploaded)
        weixin_api.send_media_message(account['token'], user_id, item, ctx, p.name)
        self._log('info', f'📤 {user_id[:8]}..: 发送 {p.name}')
        return True

    def _log(self, level: str, message: str):
        self.sig_log.emit(level, message)


# ── BotThread（QThread 包装）────────────────────────────────────────────────

class BotThread(QThread):
    """在独立线程中运行 BotEngine"""

    def __init__(self, engine: BotEngine, parent=None):
        super().__init__(parent)
        self.engine = engine

    def run(self):
        self.engine.start()

    def stop(self):
        self.engine.stop()
        self.wait(5000)
