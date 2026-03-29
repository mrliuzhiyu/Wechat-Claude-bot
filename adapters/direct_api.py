"""
纯 API 对话适配器
最轻量：只需 API Key，纯文字对话，无电脑操控
支持 Anthropic / OpenAI / 兼容 API
"""

import time
import threading
import logging

from .base import ModelAdapter, ChatResult
from core.config import MAX_CONCURRENT

log = logging.getLogger(__name__)


class DirectAPIAdapter(ModelAdapter):
    """直接调用 AI API，纯对话模式"""

    # 预定义提供商配置
    PROVIDERS = {
        'anthropic': {
            'label': 'Anthropic (Claude)',
            'default_model': 'claude-sonnet-4-20250514',
            'models': [
                ('claude-sonnet-4-20250514', 'Claude Sonnet 4 — 快速'),
                ('claude-opus-4-20250514', 'Claude Opus 4 — 最强'),
                ('claude-haiku-4-20250514', 'Claude Haiku 4 — 最快'),
            ],
        },
        'openai': {
            'label': 'OpenAI (GPT)',
            'default_model': 'gpt-4o',
            'models': [
                ('gpt-4o', 'GPT-4o — 均衡'),
                ('gpt-4o-mini', 'GPT-4o Mini — 快速'),
                ('o3-mini', 'o3-mini — 推理'),
            ],
        },
        'deepseek': {
            'label': 'DeepSeek',
            'default_model': 'deepseek-chat',
            'models': [
                ('deepseek-chat', 'DeepSeek Chat'),
                ('deepseek-reasoner', 'DeepSeek Reasoner'),
            ],
            'api_base': 'https://api.deepseek.com',
        },
    }

    def __init__(self, provider: str = 'anthropic', api_key: str = '',
                 model: str = '', api_base: str = ''):
        self._provider = provider
        self._api_key = api_key
        self._model = model or self.PROVIDERS.get(provider, {}).get('default_model', 'gpt-4o')
        self._api_base = api_base or self.PROVIDERS.get(provider, {}).get('api_base', '')
        self._sessions: dict[str, list] = {}  # user_id → message history
        self._locks: dict[str, threading.Lock] = {}
        self._active_count = 0
        self._count_lock = threading.Lock()
        self._max_concurrent = MAX_CONCURRENT
        self._anthropic_client = None
        self._openai_client = None

    @property
    def name(self) -> str:
        label = self.PROVIDERS.get(self._provider, {}).get('label', self._provider)
        return f'{label}'

    def set_config(self, provider: str, api_key: str, model: str = '', api_base: str = ''):
        self._provider = provider
        self._api_key = api_key
        self._model = model or self.PROVIDERS.get(provider, {}).get('default_model', 'gpt-4o')
        self._api_base = api_base or self.PROVIDERS.get(provider, {}).get('api_base', '')
        self._anthropic_client = None
        self._openai_client = None

    def check_available(self) -> str | None:
        if not self._api_key:
            return None
        return f'{self.name} ({self._model})'

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
                time.sleep(0.5)
            return self._do_chat(user_id, message, model=model,
                                 system_prompt=system_prompt, on_progress=on_progress)
        finally:
            with self._count_lock:
                self._active_count = max(0, self._active_count - 1)
            lock.release()

    def _do_chat(self, user_id: str, message: str, *,
                 model: str | None, system_prompt: str | None,
                 on_progress) -> ChatResult:

        if on_progress:
            on_progress('🧠 正在思考...')

        history = self._sessions.get(user_id, [])
        use_model = model or self._model

        try:
            if self._provider == 'anthropic':
                reply = self._call_anthropic(history, message, use_model, system_prompt)
            else:
                reply = self._call_openai_compat(history, message, use_model, system_prompt)
        except Exception as e:
            return ChatResult(text=f'API 调用失败: {str(e)[:300]}')

        # 更新历史
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': reply})
        # 保留最近 40 条
        if len(history) > 40:
            history = history[-40:]
        self._sessions[user_id] = history

        return ChatResult(text=reply or '(无响应)')

    def _get_anthropic_client(self):
        import anthropic
        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic(api_key=self._api_key)
        return self._anthropic_client

    def _get_openai_client(self):
        import openai
        if self._openai_client is None:
            kwargs = {}
            if self._api_base:
                kwargs['base_url'] = self._api_base
            self._openai_client = openai.OpenAI(api_key=self._api_key, **kwargs)
        return self._openai_client

    def _call_anthropic(self, history: list, message: str,
                        model: str, system_prompt: str | None) -> str:
        client = self._get_anthropic_client()

        messages = [{'role': m['role'], 'content': m['content']} for m in history]
        messages.append({'role': 'user', 'content': message})

        kwargs = {'model': model, 'max_tokens': 4096, 'messages': messages}
        if system_prompt:
            kwargs['system'] = system_prompt

        resp = client.messages.create(**kwargs)
        if not resp.content:
            return ''
        return ''.join(block.text for block in resp.content if hasattr(block, 'text'))

    def _call_openai_compat(self, history: list, message: str,
                            model: str, system_prompt: str | None) -> str:
        """OpenAI 兼容 API（OpenAI / DeepSeek / 其他）"""
        client = self._get_openai_client()

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.extend({'role': m['role'], 'content': m['content']} for m in history)
        messages.append({'role': 'user', 'content': message})

        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=4096)
        if not resp.choices:
            return ''
        return resp.choices[0].message.content or ''

    def clear_session(self, user_id: str):
        self._sessions.pop(user_id, None)

    def kill_all(self):
        pass
