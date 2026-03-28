"""
Open Interpreter 适配器
多模型支持（GPT-4/Claude/Gemini/Ollama 等）+ 电脑操控
"""

import threading
import time
import json
import logging

from .base import ModelAdapter, ChatResult

log = logging.getLogger(__name__)


class OpenInterpreterAdapter(ModelAdapter):

    def __init__(self, model: str = 'gpt-4o', api_key: str = '', api_base: str = ''):
        from interpreter import interpreter
        self._interpreter = interpreter
        self._interpreter.auto_run = True  # 自动执行，不需确认
        self._interpreter.llm.model = model
        if api_key:
            self._interpreter.llm.api_key = api_key
        if api_base:
            self._interpreter.llm.api_base = api_base

        self._sessions: dict[str, list] = {}  # user_id → messages history
        self._locks: dict[str, threading.Lock] = {}
        self._active_count = 0
        self._count_lock = threading.Lock()
        self._max_concurrent = 3
        self._model = model

    @property
    def name(self) -> str:
        return f'open-interpreter ({self._model})'

    def set_model(self, model: str, api_key: str = '', api_base: str = ''):
        """动态切换模型"""
        self._model = model
        self._interpreter.llm.model = model
        if api_key:
            self._interpreter.llm.api_key = api_key
        if api_base:
            self._interpreter.llm.api_base = api_base

    def check_available(self) -> str | None:
        try:
            from interpreter import interpreter
            return f'Open Interpreter ({self._model})'
        except ImportError:
            return None

    def chat(self, user_id: str, message: str, *,
             cwd: str | None = None,
             model: str | None = None,
             system_prompt: str | None = None,
             on_progress=None) -> ChatResult:

        lock = self._locks.setdefault(user_id, threading.Lock())
        lock.acquire()
        try:
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
                 system_prompt: str | None, on_progress) -> ChatResult:

        import os
        old_cwd = None
        if cwd:
            old_cwd = os.getcwd()
            try:
                os.chdir(cwd)
            except OSError:
                pass

        # 设置系统提示
        if system_prompt:
            self._interpreter.system_message = system_prompt

        # 恢复会话历史
        if user_id in self._sessions:
            self._interpreter.messages = self._sessions[user_id].copy()
        else:
            self._interpreter.messages = []

        # 3 秒思考提示
        thinking_sent = False
        start_time = time.time()

        def check_thinking():
            nonlocal thinking_sent
            time.sleep(3)
            if not thinking_sent and on_progress:
                on_progress('🧠 正在思考...')
                thinking_sent = True

        thinking_t = threading.Thread(target=check_thinking, daemon=True)
        thinking_t.start()

        # 执行对话
        full_response = ''
        written_files = []
        read_files = []
        last_progress_time = 0

        try:
            for chunk in self._interpreter.chat(message, stream=True, display=False):
                thinking_sent = True  # 收到任何输出就取消思考提示

                if chunk.get('type') == 'message':
                    content = chunk.get('content', '')
                    if content:
                        full_response += content

                elif chunk.get('type') == 'code':
                    # 执行代码时发进度
                    lang = chunk.get('format', '')
                    code = chunk.get('content', '')
                    now = time.time()
                    if on_progress and now - last_progress_time >= 3:
                        if lang == 'python':
                            on_progress(f'⚡ 执行 Python 代码...')
                        elif lang in ('bash', 'shell', 'sh'):
                            cmd_preview = code.strip().split('\n')[0][:60]
                            on_progress(f'⚡ 执行命令: {cmd_preview}')
                        elif lang == 'javascript':
                            on_progress(f'⚡ 执行 JavaScript...')
                        else:
                            on_progress(f'⚡ 执行 {lang}...')
                        last_progress_time = now

                elif chunk.get('type') == 'confirmation':
                    # 自动确认（auto_run=True 时不应触发）
                    pass

                elif chunk.get('type') == 'console':
                    # 命令输出，可以用来检测文件操作
                    output = chunk.get('content', '')
                    if isinstance(output, str):
                        # 检测文件写入
                        for marker in ['写入', 'wrote', 'created', 'saved']:
                            if marker in output.lower():
                                # 尝试提取路径
                                pass

            # 保存会话
            self._sessions[user_id] = self._interpreter.messages.copy()

        except Exception as e:
            full_response = f'错误: {str(e)[:300]}'
        finally:
            if old_cwd:
                try:
                    os.chdir(old_cwd)
                except OSError:
                    pass

        return ChatResult(
            text=full_response or '(无响应)',
            written_files=written_files,
            read_media_files=read_files,
        )

    def clear_session(self, user_id: str):
        self._sessions.pop(user_id, None)
        self._interpreter.messages = []

    def kill_all(self):
        try:
            self._interpreter.messages = []
        except Exception:
            pass
