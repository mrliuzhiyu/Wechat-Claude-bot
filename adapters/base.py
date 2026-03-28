"""
模型适配器抽象基类
所有 AI 模型（Claude Code、OpenAI、Gemini 等）都实现这个接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ChatResult:
    """模型返回结果"""
    text: str
    written_files: list[str] = field(default_factory=list)
    read_media_files: list[str] = field(default_factory=list)


class ModelAdapter(ABC):
    """模型适配器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称，如 'claude-code'"""
        ...

    @abstractmethod
    def chat(self, user_id: str, message: str, *,
             cwd: str | None = None,
             model: str | None = None,
             system_prompt: str | None = None,
             on_progress: Callable[[str], None] | None = None) -> ChatResult:
        """
        发送消息并获取回复（同步阻塞）

        Args:
            user_id: 用户标识
            message: 用户消息
            cwd: 工作目录
            model: 模型 ID
            system_prompt: 系统提示词
            on_progress: 进度回调

        Returns:
            ChatResult 包含回复文本和文件列表
        """
        ...

    @abstractmethod
    def clear_session(self, user_id: str):
        """清除用户会话"""
        ...

    @abstractmethod
    def check_available(self) -> str | None:
        """检查是否可用，返回版本号或 None"""
        ...

    def kill_all(self):
        """终止所有活跃进程"""
        pass
