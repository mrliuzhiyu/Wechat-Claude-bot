"""
适配器注册中心
管理所有 AI 引擎的创建、切换、配置持久化
"""

import json
import logging
from pathlib import Path

from .base import ModelAdapter
from core.config import STATE_DIR

log = logging.getLogger(__name__)

CONFIG_FILE = STATE_DIR / 'engine-config.json'

# 引擎定义
ENGINES = {
    'claude_code': {
        'label': 'Claude Code',
        'desc': '完整电脑操控，最强代码能力',
        'requires': '需安装 Claude Code CLI + Claude 订阅',
        'needs_api_key': False,
        'has_computer_control': True,
    },
    'open_interpreter': {
        'label': 'Open Interpreter',
        'desc': '多模型 + 电脑操控',
        'requires': '需要 API Key（支持 GPT/Claude/Gemini/本地模型）',
        'needs_api_key': True,
        'has_computer_control': True,
    },
    'direct_api': {
        'label': '纯 API 对话',
        'desc': '最轻量，纯文字对话',
        'requires': '需要 API Key',
        'needs_api_key': True,
        'has_computer_control': False,
    },
}


def load_config() -> dict:
    """加载已保存的引擎配置"""
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config: dict):
    """保存引擎配置"""
    STATE_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')


def create_adapter(engine: str = '', config: dict | None = None) -> ModelAdapter:
    """
    创建适配器实例

    Args:
        engine: 引擎类型 ('claude_code' / 'open_interpreter' / 'direct_api')
        config: 配置 {'api_key': ..., 'model': ..., 'provider': ..., 'api_base': ...}
    """
    if config is None:
        config = load_config()
    if not engine:
        engine = config.get('engine', 'claude_code')

    if engine == 'claude_code':
        from .claude_code import ClaudeCodeAdapter
        return ClaudeCodeAdapter()

    elif engine == 'open_interpreter':
        from .open_interpreter import OpenInterpreterAdapter
        return OpenInterpreterAdapter(
            model=config.get('model', 'gpt-4o'),
            api_key=config.get('api_key', ''),
            api_base=config.get('api_base', ''),
        )

    elif engine == 'direct_api':
        from .direct_api import DirectAPIAdapter
        return DirectAPIAdapter(
            provider=config.get('provider', 'anthropic'),
            api_key=config.get('api_key', ''),
            model=config.get('model', ''),
            api_base=config.get('api_base', ''),
        )

    else:
        # 默认 Claude Code
        from .claude_code import ClaudeCodeAdapter
        return ClaudeCodeAdapter()


def detect_available_engines() -> dict[str, bool]:
    """检测哪些引擎可用"""
    result = {}

    # Claude Code: 检测 CLI
    try:
        from .claude_code import ClaudeCodeAdapter
        result['claude_code'] = ClaudeCodeAdapter().check_available() is not None
    except Exception:
        result['claude_code'] = False

    # Open Interpreter: 检测是否安装
    try:
        import interpreter
        result['open_interpreter'] = True
    except ImportError:
        result['open_interpreter'] = False

    # 纯 API: 始终可用（只要有 key）
    result['direct_api'] = True

    return result
