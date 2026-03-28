"""
Claude Code CLI 适配器
通过 stream-json 模式与本机 Claude Code CLI 交互
"""

import json
import os
import subprocess
import threading
import time
import logging
from pathlib import Path

from .base import ModelAdapter, ChatResult
from core.config import STATE_DIR, PROCESS_TIMEOUT

log = logging.getLogger(__name__)

# ── 工具标签映射 ─────────────────────────────────────────────────────────────

TOOL_LABELS = {
    'Read': '📖 正在读取文件',
    'Edit': '✏️ 正在编辑文件',
    'Write': '📝 正在创建文件',
    'Bash': '⚡ 正在执行命令',
    'Glob': '🔍 正在搜索文件',
    'Grep': '🔍 正在搜索内容',
    'WebSearch': '🌐 正在搜索网页',
    'WebFetch': '🌐 正在获取网页',
    'TodoWrite': '📋 正在规划任务',
}

SESSION_FILE = STATE_DIR / 'sessions.json'


def _describe_tool_use(tool_name: str, tool_input: dict | None) -> str:
    label = TOOL_LABELS.get(tool_name, f'🔧 {tool_name}')
    if not tool_input:
        return label
    if tool_name in ('Read', 'Edit', 'Write'):
        fp = tool_input.get('file_path', '')
        parts = fp.replace('\\', '/').split('/')
        return f'{label}: {"/".join(parts[-2:])}'
    if tool_name == 'Bash':
        cmd = tool_input.get('command') or tool_input.get('description') or ''
        return f'{label}: {cmd[:60]}{"..." if len(cmd) > 60 else ""}'
    if tool_name == 'Glob':
        return f'{label}: {tool_input.get("pattern", "")}'
    if tool_name == 'Grep':
        pat = tool_input.get('pattern', '')
        return f'{label}: {pat[:40]}{"..." if len(pat) > 40 else ""}'
    return label


# ── 平台适配 ─────────────────────────────────────────────────────────────────

IS_WINDOWS = os.name == 'nt'
_spawn_cache = None


def _resolve_claude_spawn() -> dict:
    """解析 Claude Code CLI 启动方式"""
    global _spawn_cache
    if _spawn_cache:
        return _spawn_cache

    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ['where', 'claude.cmd'],
                capture_output=True, text=True, shell=True, timeout=5,
            )
            cmd_path = result.stdout.strip().splitlines()[0].strip()
            if cmd_path:
                dir_path = Path(cmd_path).parent
                cli_js = dir_path / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js'
                if cli_js.exists():
                    import sys
                    # 用 node 直接调用 cli.js，绕过 cmd.exe 编码问题
                    node_path = subprocess.run(
                        ['where', 'node'], capture_output=True, text=True, shell=True, timeout=5
                    ).stdout.strip().splitlines()[0].strip()
                    _spawn_cache = {'bin': node_path, 'extra_args': [str(cli_js)], 'shell': False}
                    return _spawn_cache
        except Exception:
            pass
        _spawn_cache = {'bin': 'claude', 'extra_args': [], 'shell': True}
        return _spawn_cache

    # macOS / Linux
    try:
        result = subprocess.run(['which', 'claude'], capture_output=True, text=True, timeout=5)
        bin_path = result.stdout.strip() or 'claude'
    except Exception:
        bin_path = 'claude'
    _spawn_cache = {'bin': bin_path, 'extra_args': [], 'shell': False}
    return _spawn_cache


def _clean_env() -> dict:
    """构造干净的环境变量"""
    env = os.environ.copy()
    env.pop('CLAUDECODE', None)
    return env


# ── Claude Code 适配器 ──────────────────────────────────────────────────────

class ClaudeCodeAdapter(ModelAdapter):

    def __init__(self):
        self._sessions: dict = self._load_sessions()
        self._locks: dict[str, threading.Lock] = {}
        self._active_procs: set = set()
        self._active_count = 0
        self._count_lock = threading.Lock()
        self._max_concurrent = 3
        self._max_sessions = 100

    @property
    def name(self) -> str:
        return 'claude-code'

    # ── 会话管理 ────────────────────────────────────────────────────────

    def _load_sessions(self) -> dict:
        try:
            return json.loads(SESSION_FILE.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_sessions(self):
        try:
            STATE_DIR.mkdir(exist_ok=True)
            SESSION_FILE.write_text(json.dumps(self._sessions), encoding='utf-8')
        except Exception:
            pass

    def clear_session(self, user_id: str):
        self._sessions.pop(user_id, None)
        self._save_sessions()

    def _cleanup_oldest(self):
        if len(self._sessions) <= self._max_sessions:
            return
        sorted_items = sorted(self._sessions.items(), key=lambda x: x[1].get('lastActive', 0))
        for uid, _ in sorted_items[:len(self._sessions) - self._max_sessions]:
            del self._sessions[uid]
        self._save_sessions()

    # ── 核心 API ────────────────────────────────────────────────────────

    def check_available(self) -> str | None:
        try:
            spawn = _resolve_claude_spawn()
            result = subprocess.run(
                [spawn['bin'], *spawn['extra_args'], '--version'],
                capture_output=True, text=True,
                shell=spawn['shell'],
                env=_clean_env(),
                timeout=10,
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    def chat(self, user_id: str, message: str, *,
             cwd: str | None = None,
             model: str | None = None,
             system_prompt: str | None = None,
             on_progress=None) -> ChatResult:

        # 同用户串行
        lock = self._locks.setdefault(user_id, threading.Lock())
        lock.acquire()
        try:
            # 全局并发等待
            while True:
                with self._count_lock:
                    if self._active_count < self._max_concurrent:
                        self._active_count += 1
                        break
                time.sleep(1)

            return self._do_chat(user_id, message, cwd=cwd, model=model,
                                 system_prompt=system_prompt, on_progress=on_progress)
        finally:
            with self._count_lock:
                self._active_count = max(0, self._active_count - 1)
            lock.release()

    def _do_chat(self, user_id: str, message: str, *,
                 cwd: str | None, model: str | None,
                 system_prompt: str | None, on_progress,
                 retry_count: int = 0) -> ChatResult:

        self._cleanup_oldest()
        session_id = (self._sessions.get(user_id) or {}).get('sessionId')

        spawn = _resolve_claude_spawn()
        args = [
            spawn['bin'], *spawn['extra_args'],
            '-p',
            '--output-format', 'stream-json',
            '--verbose',
            '--dangerously-skip-permissions',
        ]

        if session_id:
            args.extend(['-r', session_id])
        if model:
            args.extend(['--model', model])
        if system_prompt:
            args.extend(['--append-system-prompt', system_prompt])
        args.append(message)

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=spawn['shell'],
            cwd=cwd or None,
            env=_clean_env(),
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
        self._active_procs.add(proc)

        assistant_text = ''
        final_result = ''
        new_session_id = None
        written_files = []
        read_media_files = []
        last_progress_time = 0
        first_event = False
        timed_out = False

        # 3 秒无响应发"思考中"
        thinking_sent = False

        def read_stdout():
            nonlocal assistant_text, final_result, new_session_id
            nonlocal last_progress_time, first_event, thinking_sent

            buf = ''
            for raw_line in iter(proc.stdout.readline, b''):
                line = raw_line.decode('utf-8', errors='replace').strip()
                if not line:
                    continue

                if not first_event:
                    first_event = True

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get('type') == 'assistant':
                    if event.get('session_id'):
                        new_session_id = event['session_id']
                    for block in (event.get('message') or {}).get('content', []):
                        if block.get('type') == 'text':
                            assistant_text += block['text']
                        elif block.get('type') == 'tool_use':
                            inp = block.get('input') or {}
                            # 记录文件操作
                            if block.get('name') == 'Write' and inp.get('file_path'):
                                written_files.append(inp['file_path'])
                            if block.get('name') == 'Read' and inp.get('file_path'):
                                ext = Path(inp['file_path']).suffix.lower()
                                media_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
                                              '.mp4', '.mov', '.pdf', '.doc', '.docx',
                                              '.xls', '.xlsx', '.csv', '.zip', '.mp3', '.wav'}
                                if ext in media_exts:
                                    read_media_files.append(inp['file_path'])
                            # 进度回调
                            now = time.time()
                            if on_progress and now - last_progress_time >= 3:
                                desc = _describe_tool_use(block['name'], inp)
                                on_progress(desc)
                                last_progress_time = now

                elif event.get('type') == 'result':
                    if event.get('session_id'):
                        new_session_id = event['session_id']
                    if event.get('result') and isinstance(event['result'], str):
                        final_result = event['result']

        reader_thread = threading.Thread(target=read_stdout, daemon=True)
        reader_thread.start()

        # 3 秒思考提示
        def thinking_timer():
            nonlocal thinking_sent
            time.sleep(3)
            if not first_event and on_progress:
                on_progress('🧠 正在思考...')
                thinking_sent = True

        thinking_t = threading.Thread(target=thinking_timer, daemon=True)
        thinking_t.start()

        # 等待完成（带超时）
        try:
            proc.wait(timeout=PROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        reader_thread.join(timeout=5)
        self._active_procs.discard(proc)

        stderr = proc.stderr.read().decode('utf-8', errors='replace') if proc.stderr else ''
        reply = final_result or assistant_text

        if timed_out:
            return ChatResult(
                text=reply or '⏱️ Claude Code 处理超时（5分钟），请拆分成更小的步骤。',
                written_files=written_files,
                read_media_files=read_media_files,
            )

        if proc.returncode != 0 and not reply:
            if retry_count < 1 and session_id and ('session' in stderr or 'conversation' in stderr):
                self._sessions.pop(user_id, None)
                return self._do_chat(user_id, message, cwd=cwd, model=model,
                                     system_prompt=system_prompt, on_progress=on_progress,
                                     retry_count=retry_count + 1)
            raise RuntimeError(f'Claude Code 退出码 {proc.returncode}: {stderr[:500]}')

        # 更新会话
        if new_session_id:
            self._sessions[user_id] = {'sessionId': new_session_id, 'lastActive': time.time()}
            self._save_sessions()
        elif user_id in self._sessions:
            self._sessions[user_id]['lastActive'] = time.time()

        return ChatResult(
            text=reply or '(Claude Code 无响应)',
            written_files=written_files,
            read_media_files=read_media_files,
        )

    def kill_all(self):
        for proc in list(self._active_procs):
            try:
                proc.terminate()
            except Exception:
                pass
        self._active_procs.clear()
