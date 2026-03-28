"""全局配置"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
STATE_DIR = ROOT_DIR / '.state'
MEDIA_DIR = STATE_DIR / 'media'
OUTBOX_DIR = STATE_DIR / 'outbox'

# 确保目录存在
STATE_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)
OUTBOX_DIR.mkdir(exist_ok=True)

# 默认工作目录
DEFAULT_CWD = os.environ.get('CLAUDE_CWD', str(Path.cwd()))

# 微信 API
WEIXIN_BASE_URL = 'https://ilinkai.weixin.qq.com'
LONG_POLL_TIMEOUT = 35  # 秒
CDN_BASE_URL = 'https://novac2c.cdn.weixin.qq.com/c2c'

# Bot 限制
MAX_REPLY_LENGTH = 4000
MAX_CONCURRENT = 3
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
PROCESS_TIMEOUT = 5 * 60  # 5 分钟

# 模型定义
MODELS = {
    'sonnet': {'id': 'claude-sonnet-4-6', 'label': 'Sonnet', 'desc': '快速'},
    'opus':   {'id': 'claude-opus-4-6',   'label': 'Opus',   'desc': '最强但慢'},
    'haiku':  {'id': 'claude-haiku-4-5',  'label': 'Haiku',  'desc': '最快'},
}

# 自动发送的文件类型
AUTO_SEND_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
    '.mp4', '.mov',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.csv', '.txt', '.zip', '.rar', '.7z',
    '.mp3', '.wav', '.html',
}

# 微信系统提示词
WECHAT_SYSTEM_PROMPT = '\n'.join([
    '你正在通过微信与用户对话。回复显示在微信中（纯文本，不支持 Markdown）。',
    '保持简洁，适合手机。不要用 Markdown 语法。',
    '',
    '文件发送：当你用 Read 工具查看图片/PDF/文档等文件时，系统会自动把该文件发送给用户。',
    '用户说"把文件发给我"时，直接用 Read 工具读取该文件即可，系统自动处理发送。',
    '你用 Write 工具或 Bash 创建的新文件也会自动发送。',
    '',
    '工作时先简短说明你要做什么，让用户知道进展。',
])
