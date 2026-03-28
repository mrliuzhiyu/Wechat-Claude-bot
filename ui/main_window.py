"""
微信 Claude Bot — PyQt6 主窗口
纯 PyQt 极简高级设计，自定义绘制气泡 + 动画
"""

import io
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSlot, QSize, QPropertyAnimation,
    QEasingCurve, QPoint, QRect, pyqtProperty,
)
from PyQt6.QtGui import (
    QPixmap, QIcon, QFont, QPainter, QColor, QBrush, QPen,
    QPainterPath, QLinearGradient, QFontMetrics,
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QTextEdit, QFrame,
    QSystemTrayIcon, QMenu, QApplication,
    QComboBox, QFileDialog, QLineEdit, QScrollArea, QCheckBox,
    QGraphicsOpacityEffect, QSizePolicy, QSpacerItem,
)

import qrcode
from qrcode.image.pil import PilImage

from .theme import COLORS, STYLESHEET
from core.config import MODELS, DEFAULT_CWD
from core.bot_engine import BotEngine, BotThread, fmt_uptime
from adapters.registry import ENGINES, create_adapter, load_config, save_config, detect_available_engines


# ── 颜色工具 ──────────────────────────────────────────────────────────────────

# 基于 user_id 生成稳定的柔和头像色
_AVATAR_PALETTE = [
    '#FF6B6B', '#FF8E72', '#FFA94D', '#FFD43B',
    '#69DB7C', '#38D9A9', '#4DABF7', '#748FFC',
    '#9775FA', '#DA77F2', '#F783AC', '#E599F7',
]

def _avatar_color(user_id: str) -> str:
    idx = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % len(_AVATAR_PALETTE)
    return _AVATAR_PALETTE[idx]

def _make_tray_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32):
        pm = QPixmap(s, s)
        pm.fill(QColor('#ffffff'))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#222222'))
        p.setFont(QFont('Arial', int(s * 0.48), QFont.Weight.Bold))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, 'C')
        p.end()
        icon.addPixmap(pm)
    return icon


# ── 自定义气泡组件 ────────────────────────────────────────────────────────────

class AvatarWidget(QWidget):
    """圆形字母头像"""
    def __init__(self, letter: str, color: str, size: int = 32):
        super().__init__()
        self.setFixedSize(size, size)
        self._letter = letter.upper()
        self._color = QColor(color)
        self._size = size

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 圆形背景
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self._size, self._size)
        # 字母
        p.setPen(QColor('white'))
        p.setFont(QFont('SF Pro Display', int(self._size * 0.38), QFont.Weight.DemiBold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._letter)
        p.end()


class BubbleWidget(QWidget):
    """单条消息气泡 — 自定义绘制圆角 + 微阴影"""
    def __init__(self, text: str, timestamp: str, user_id: str,
                 is_incoming: bool, parent=None):
        super().__init__(parent)
        self._text = text
        self._ts = timestamp
        self._user_id = user_id
        self._is_incoming = is_incoming  # True = 用户发来, False = AI 回复

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 4, 12, 4)
        root.setSpacing(8)

        if self._is_incoming:
            # 用户消息：[头像] [气泡]          [空白]
            root.addWidget(self._make_avatar())
            root.addWidget(self._make_bubble(), 0)
            root.addStretch(1)
        else:
            # AI 回复：  [空白]          [气泡] [头像]
            root.addStretch(1)
            root.addWidget(self._make_bubble(), 0)
            root.addWidget(self._make_ai_avatar())

    def _make_avatar(self) -> AvatarWidget:
        letter = self._user_id[0] if self._user_id else '?'
        color = _avatar_color(self._user_id)
        return AvatarWidget(letter, color, 30)

    def _make_ai_avatar(self) -> AvatarWidget:
        return AvatarWidget('C', COLORS['accent'], 30)

    def _make_bubble(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # 时间 + 名称行
        meta = QLabel(f'{self._user_id[:8]}  {self._ts}' if self._is_incoming
                      else f'{self._ts}  Claude')
        meta.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_tertiary']};
            letter-spacing: 0.5px;
            background: transparent;
        """)
        meta.setAlignment(
            Qt.AlignmentFlag.AlignLeft if self._is_incoming
            else Qt.AlignmentFlag.AlignRight
        )
        v.addWidget(meta)

        # 气泡体
        bubble = BubbleBody(self._text, self._is_incoming)
        v.addWidget(bubble)
        return container


class BubbleBody(QWidget):
    """气泡主体 — 自定义绘制圆角矩形"""
    _MAX_WIDTH = 280
    _PADDING = 12

    def __init__(self, text: str, is_incoming: bool):
        super().__init__()
        self._text = text
        self._is_incoming = is_incoming

        if is_incoming:
            self._bg = QColor(COLORS['card'])
            self._fg = QColor(COLORS['text'])
        else:
            self._bg = QColor(COLORS['accent'])
            self._fg = QColor('white')

        self._font = QFont('SF Pro Text', 10)
        self._font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(
            QRect(0, 0, self._MAX_WIDTH - 2 * self._PADDING, 10000),
            Qt.TextFlag.TextWordWrap, self._text
        )
        w = min(text_rect.width() + 2 * self._PADDING + 4,
                self._MAX_WIDTH)
        h = text_rect.height() + 2 * self._PADDING
        self.setFixedSize(max(w, 40), max(h, 36))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = 14

        # 微阴影
        shadow_path = QPainterPath()
        shadow_rect = rect.adjusted(0, 1, 0, 1)
        shadow_path.addRoundedRect(shadow_rect.toRectF(), radius, radius)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 8))
        p.drawPath(shadow_path)

        # 气泡体
        path = QPainterPath()
        path.addRoundedRect(rect.toRectF(), radius, radius)
        p.setBrush(QBrush(self._bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

        # 文字
        p.setPen(self._fg)
        p.setFont(self._font)
        text_rect = rect.adjusted(self._PADDING, self._PADDING,
                                   -self._PADDING, -self._PADDING)
        p.drawText(text_rect, Qt.TextFlag.TextWordWrap, self._text)
        p.end()


# ── 消息流容器 ────────────────────────────────────────────────────────────────

class MessageFlow(QScrollArea):
    """可滚动的消息流，支持动画插入"""
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{
                background: {COLORS['bg']};
                border: none;
            }}
        """)

        self._container = QWidget()
        self._container.setStyleSheet(f'background: {COLORS["bg"]};')
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(2)
        self._layout.addStretch()  # 消息从底部往上长
        self.setWidget(self._container)

    def add_message(self, text: str, user_id: str, is_incoming: bool, animate: bool = True):
        ts = datetime.now().strftime('%H:%M')
        bubble = BubbleWidget(text, ts, user_id, is_incoming)

        # 在 stretch 之前插入
        count = self._layout.count()
        self._layout.insertWidget(count - 1, bubble)

        if animate:
            self._animate_in(bubble)

        # 滚到底部
        QTimer.singleShot(30, self._scroll_bottom)

    def _animate_in(self, widget: QWidget):
        """消息滑入 + 淡入动画"""
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        # 淡入
        fade = QPropertyAnimation(effect, b'opacity', widget)
        fade.setDuration(250)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _scroll_bottom(self):
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_messages(self):
        while self._layout.count() > 1:  # 保留 stretch
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ── 设置页组件 ────────────────────────────────────────────────────────────────

class WxCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"WxCard {{ background: {COLORS['card']}; border-radius: 8px; }}")


class WxCellItem(QFrame):
    def __init__(self, label: str, value: str = '', arrow: bool = False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]};')
        self.setFixedHeight(48)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(8)
        self._label = QLabel(label)
        self._label.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        h.addWidget(self._label, 1)
        self._value = QLabel(value)
        self._value.setStyleSheet(f'font-size: 13px; color: {COLORS["text_secondary"]};')
        h.addWidget(self._value)
        if arrow:
            arr = QLabel('›')
            arr.setStyleSheet(f'font-size: 16px; color: {COLORS["text_tertiary"]};')
            h.addWidget(arr)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, text: str):
        self._value.setText(text)


class CheckItem(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]};')
        self.setFixedHeight(48)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        self._label = QLabel(label)
        self._label.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        h.addWidget(self._label, 1)
        self._status = QLabel('等待')
        self._status.setStyleSheet(f'font-size: 12px; color: {COLORS["text_tertiary"]};')
        h.addWidget(self._status)

    def set_active(self, text: str = '检测中...'):
        self._status.setText(text)
        self._status.setStyleSheet(f'font-size: 12px; color: {COLORS["warn"]};')

    def set_done(self, text: str = ''):
        self._status.setText(f'✓ {text}' if text else '✓')
        self._status.setStyleSheet(f'font-size: 12px; color: {COLORS["accent"]};')

    def set_error(self, text: str = ''):
        self._status.setText(f'✗ {text}' if text else '✗')
        self._status.setStyleSheet(f'font-size: 12px; color: {COLORS["error"]};')


class QrStepItem(QWidget):
    def __init__(self, number: str, text: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(10)
        self._dot = QLabel(number)
        self._dot.setFixedSize(22, 22)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot.setStyleSheet(f'background: {COLORS["divider"]}; color: {COLORS["text_tertiary"]}; border-radius: 11px; font-size: 12px; font-weight: 600;')
        h.addWidget(self._dot)
        self._text = QLabel(text)
        self._text.setStyleSheet(f'font-size: 14px; color: {COLORS["text_tertiary"]};')
        h.addWidget(self._text, 1)

    def set_done(self):
        self._dot.setText('✓')
        self._dot.setStyleSheet(f'background: {COLORS["accent"]}; color: white; border-radius: 11px; font-size: 12px; font-weight: 600;')
        self._text.setStyleSheet(f'font-size: 14px; color: {COLORS["accent"]};')

    def set_active(self):
        self._dot.setStyleSheet(f'background: {COLORS["warn"]}; color: white; border-radius: 11px; font-size: 12px; font-weight: 600;')
        self._text.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')


# ══════════════════════════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('微信 Claude Bot')
        self.setMinimumSize(400, 500)
        self.resize(420, 620)
        self.setStyleSheet(STYLESHEET)
        self.setWindowIcon(QIcon(self._make_app_pixmap()))

        # 引擎
        self._engine_config = load_config()
        self.adapter = create_adapter(config=self._engine_config)
        self.engine = BotEngine(self.adapter)
        self.bot_thread = BotThread(self.engine)
        self._connect_signals()

        # 状态
        self.start_time = None
        self.message_count = 0
        self._log_unread = 0
        self._prev_view = 0
        self._tray_hint_shown = False

        # UI
        self._build_ui()
        self._build_tray()

        # 定时器
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(self._update_uptime)

        # 拖拽
        self.setAcceptDrops(True)

        # 自动启动
        QTimer.singleShot(200, self._start_bot)

    @staticmethod
    def _make_app_pixmap(size=64):
        pm = QPixmap(size, size)
        pm.fill(QColor('#ffffff'))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#222222'))
        p.setFont(QFont('Arial', int(size * 0.48), QFont.Weight.Bold))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, 'C')
        p.end()
        return pm

    # ══════════════════════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_checking_view())   # 0
        self.stack.addWidget(self._build_env_error_view())  # 1
        self.stack.addWidget(self._build_qr_view())         # 2
        self.stack.addWidget(self._build_running_view())     # 3
        self.stack.addWidget(self._build_settings_view())    # 4
        root.addWidget(self.stack, 1)

        root.addWidget(self._build_footer())

    # ── 头部 ──

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['card']};
                border-bottom: 1px solid {COLORS['divider']};
            }}
        """)
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)
        h.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(6, 6)
        self._set_dot('off')
        h.addWidget(self.status_dot)

        self.status_text = QLabel('未启动')
        self.status_text.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 12px;
            font-weight: 400;
            letter-spacing: 0.3px;
        """)
        h.addWidget(self.status_text)

        h.addStretch()

        btn_settings = QPushButton('⚙')
        btn_settings.setProperty('class', 'icon')
        btn_settings.setFixedSize(28, 28)
        btn_settings.setToolTip('设置')
        btn_settings.clicked.connect(self._toggle_settings)
        h.addWidget(btn_settings)

        return header

    # ── 视图0: 启动检测 ──

    def _build_checking_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 48, 24, 24)
        v.setSpacing(4)

        title = QLabel('启动检测')
        title.setStyleSheet(f'font-size: 17px; font-weight: 600; color: {COLORS["text"]};')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        sub = QLabel('正在检查运行环境')
        sub.setStyleSheet(f'font-size: 13px; color: {COLORS["text_secondary"]}; margin-bottom: 24px;')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)

        card = WxCard()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.check_claude = CheckItem('Claude Code CLI')
        self.check_weixin = CheckItem('微信连接')
        self.check_ready = CheckItem('就绪')
        self.check_ready.setStyleSheet(f'background: {COLORS["card"]};')
        cl.addWidget(self.check_claude)
        cl.addWidget(self.check_weixin)
        cl.addWidget(self.check_ready)
        v.addWidget(card)
        v.addStretch()
        return w

    # ── 视图1: 环境错误 ──

    def _build_env_error_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(12)

        icon = QLabel('✗')
        icon.setFixedSize(52, 52)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f'background: {COLORS["error"]}; color: white; border-radius: 26px; font-size: 24px; font-weight: bold;')
        v.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel('环境检测失败')
        title.setStyleSheet(f'font-size: 17px; font-weight: 600; color: {COLORS["text"]};')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        detail = QLabel('未检测到 Claude Code CLI')
        detail.setStyleSheet(f'font-size: 13px; color: {COLORS["text_secondary"]};')
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(detail)

        cmd = QLabel('npm install -g @anthropic-ai/claude-code')
        cmd.setStyleSheet(f'background: {COLORS["card"]}; color: {COLORS["text"]}; border: 1px solid {COLORS["divider"]}; border-radius: 8px; padding: 10px 16px; font-family: "SF Mono", Consolas, monospace; font-size: 12px;')
        cmd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(cmd, alignment=Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton('重新检测')
        btn.setFixedWidth(120)
        btn.clicked.connect(self._start_bot)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── 视图2: 扫码 ──

    def _build_qr_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(16)

        title = QLabel('连接微信')
        title.setStyleSheet(f'font-size: 18px; font-weight: 600; color: {COLORS["text"]};')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        sub = QLabel('使用微信扫一扫连接你的 AI 助手')
        sub.setStyleSheet(f'font-size: 13px; color: {COLORS["text_secondary"]};')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)

        qr_card = QFrame()
        qr_card.setFixedSize(220, 220)
        qr_card.setStyleSheet('background: white; border-radius: 12px;')
        ql = QVBoxLayout(qr_card)
        ql.setContentsMargins(0, 0, 0, 0)

        qr_placeholder = QWidget()
        qpl = QVBoxLayout(qr_placeholder)
        qpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qpl.setSpacing(8)
        qr_icon = QLabel('·  ·  ·')
        qr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_icon.setStyleSheet(f'font-size: 24px; color: {COLORS["text_tertiary"]}; letter-spacing: 4px;')
        qpl.addWidget(qr_icon)
        self._qr_placeholder = qr_placeholder
        ql.addWidget(qr_placeholder)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setVisible(False)
        ql.addWidget(self.qr_label)
        v.addWidget(qr_card, alignment=Qt.AlignmentFlag.AlignCenter)

        steps_w = QWidget()
        steps_w.setFixedWidth(260)
        sv = QVBoxLayout(steps_w)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(2)
        self.qr_step1 = QrStepItem('1', '打开微信')
        self.qr_step2 = QrStepItem('2', '扫描上方二维码')
        self.qr_step3 = QrStepItem('3', '在微信中点击确认')
        sv.addWidget(self.qr_step1)
        sv.addWidget(self.qr_step2)
        sv.addWidget(self.qr_step3)
        v.addWidget(steps_w, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── 视图3: 消息流 ──

    def _build_running_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["bg"]};')
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 空状态
        self._empty_state = QWidget()
        self._empty_state.setStyleSheet(f'background: {COLORS["bg"]};')
        es = QVBoxLayout(self._empty_state)
        es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es.setSpacing(16)

        self._model_display = QLabel('Sonnet')
        self._model_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._model_display.setStyleSheet(f"""
            font-size: 42px;
            font-weight: 200;
            color: {COLORS['text']};
            letter-spacing: -1.5px;
        """)
        es.addWidget(self._model_display)

        hint = QLabel('在微信中发消息即可开始')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS['text_tertiary']};
            letter-spacing: 0.5px;
        """)
        es.addWidget(hint)

        v.addWidget(self._empty_state, 1)

        # 消息流
        self.msg_flow = MessageFlow()
        self.msg_flow.setVisible(False)
        v.addWidget(self.msg_flow, 1)

        return w

    # ── 视图4: 设置 ──

    def _build_settings_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["bg"]};')
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f'QFrame {{ background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]}; }}')
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 0, 16, 0)
        back_btn = QPushButton('‹ 返回')
        back_btn.setProperty('class', 'text')
        back_btn.clicked.connect(self._go_back)
        hh.addWidget(back_btn)
        hh.addStretch()
        stitle = QLabel('设置')
        stitle.setStyleSheet(f'font-size: 16px; font-weight: 600; color: {COLORS["text"]};')
        hh.addWidget(stitle)
        hh.addStretch()
        hh.addSpacing(60)
        v.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f'QScrollArea {{ border: none; background: {COLORS["bg"]}; }}')
        content = QWidget()
        content.setStyleSheet(f'background: {COLORS["bg"]};')
        cv = QVBoxLayout(content)
        cv.setContentsMargins(12, 12, 12, 12)
        cv.setSpacing(0)

        # AI 引擎
        cv.addWidget(self._group_title('AI 引擎'))
        engine_card = WxCard()
        el = QVBoxLayout(engine_card)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(0)
        available = detect_available_engines()
        current_engine = self._engine_config.get('engine', 'claude_code')
        self._engine_cells = {}
        for key, info in ENGINES.items():
            is_available = available.get(key, False)
            is_selected = (key == current_engine)
            prefix = '● ' if is_selected else '○ '
            suffix = '' if is_available or info['needs_api_key'] else '  (未安装)'
            cell = WxCellItem(f'{prefix}{info["label"]}{suffix}', info['desc'], arrow=True)
            cell.mousePressEvent = lambda e, k=key: self._select_engine(k)
            if key != list(ENGINES.keys())[-1]:
                cell.setStyleSheet(f'background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]};')
            else:
                cell.setStyleSheet(f'background: {COLORS["card"]};')
            el.addWidget(cell)
            self._engine_cells[key] = cell
        cv.addWidget(engine_card)
        cv.addSpacing(12)

        # API Key
        self._apikey_group = QWidget()
        ag = QVBoxLayout(self._apikey_group)
        ag.setContentsMargins(0, 0, 0, 0)
        ag.setSpacing(0)
        ag.addWidget(self._group_title('API Key'))
        apikey_card = WxCard()
        al = QVBoxLayout(apikey_card)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(8)

        self._provider_row = QWidget()
        pr = QHBoxLayout(self._provider_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pl = QLabel('提供商')
        pl.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        pr.addWidget(pl)
        pr.addStretch()
        self._provider_combo = QComboBox()
        self._provider_combo.setFixedWidth(180)
        from adapters.direct_api import DirectAPIAdapter
        for pkey, pinfo in DirectAPIAdapter.PROVIDERS.items():
            self._provider_combo.addItem(pinfo['label'], pkey)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        pr.addWidget(self._provider_combo)
        al.addWidget(self._provider_row)

        self._apikey_input = QLineEdit()
        self._apikey_input.setPlaceholderText('输入 API Key...')
        self._apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_input.setStyleSheet(f'''
            QLineEdit {{
                background: {COLORS["bg"]};
                border: 1px solid {COLORS["divider"]};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: {COLORS["text"]};
            }}
            QLineEdit:focus {{ border-color: {COLORS["accent"]}; }}
        ''')
        saved_key = self._engine_config.get('api_key', '')
        if saved_key:
            self._apikey_input.setText(saved_key)
        apikey_row = QHBoxLayout()
        apikey_row.setContentsMargins(0, 0, 0, 0)
        apikey_row.setSpacing(4)
        apikey_row.addWidget(self._apikey_input)
        self._apikey_eye = QPushButton('👁')
        self._apikey_eye.setFixedSize(32, 32)
        self._apikey_eye.setProperty('class', 'icon')
        self._apikey_eye.clicked.connect(self._toggle_apikey_visibility)
        apikey_row.addWidget(self._apikey_eye)
        al.addLayout(apikey_row)

        self._oi_model_row = QWidget()
        mr = QHBoxLayout(self._oi_model_row)
        mr.setContentsMargins(0, 0, 0, 0)
        ml = QLabel('模型名称')
        ml.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        mr.addWidget(ml)
        mr.addStretch()
        self._oi_model_input = QLineEdit()
        self._oi_model_input.setFixedWidth(180)
        self._oi_model_input.setPlaceholderText('如 gpt-4o')
        self._oi_model_input.setText(self._engine_config.get('model', 'gpt-4o'))
        self._oi_model_input.setStyleSheet(self._apikey_input.styleSheet())
        mr.addWidget(self._oi_model_input)
        al.addWidget(self._oi_model_row)

        self._save_btn = QPushButton('保存并重启 Bot')
        self._save_btn.clicked.connect(self._save_engine_config)
        al.addWidget(self._save_btn)
        ag.addWidget(apikey_card)
        cv.addWidget(self._apikey_group)
        self._update_settings_visibility(current_engine)
        cv.addSpacing(16)

        cv.addWidget(self._group_title('微信消息模型'))
        self.settings_model_cell = WxCellItem('当前模型', 'Sonnet — 快速', arrow=True)
        self.settings_model_cell.mousePressEvent = lambda e: self._show_model_menu()
        self.settings_model_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        cv.addWidget(self.settings_model_cell)
        cv.addSpacing(16)

        cv.addWidget(self._group_title('工作目录'))
        self.settings_cwd_cell = WxCellItem('路径', DEFAULT_CWD, arrow=True)
        self.settings_cwd_cell.mousePressEvent = lambda e: self._browse_cwd()
        self.settings_cwd_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        cv.addWidget(self.settings_cwd_cell)
        cv.addSpacing(16)

        cv.addWidget(self._group_title('系统'))
        autostart_cell = QFrame()
        autostart_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        autostart_cell.setFixedHeight(48)
        ash = QHBoxLayout(autostart_cell)
        ash.setContentsMargins(16, 0, 16, 0)
        asl = QLabel('开机自动启动')
        asl.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        ash.addWidget(asl, 1)
        self._autostart_cb = QCheckBox()
        self._autostart_cb.setChecked(self.get_auto_start())
        self._autostart_cb.stateChanged.connect(lambda state: self.set_auto_start(state == 2))
        ash.addWidget(self._autostart_cb)
        cv.addWidget(autostart_cell)
        cv.addSpacing(16)

        cv.addWidget(self._group_title('连接信息'))
        info_card = WxCard()
        il = QVBoxLayout(info_card)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(0)
        self.info_bot_id = WxCellItem('Bot ID', '—')
        self.info_engine = WxCellItem('AI 引擎', self.adapter.name)
        self.info_time = WxCellItem('连接时间', '—')
        self.info_time.setStyleSheet(f'background: {COLORS["card"]};')
        il.addWidget(self.info_bot_id)
        il.addWidget(self.info_engine)
        il.addWidget(self.info_time)
        cv.addWidget(info_card)
        cv.addStretch()

        scroll.setWidget(content)
        v.addWidget(scroll, 1)
        return w

    def _group_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f'font-size: 12px; color: {COLORS["text_tertiary"]}; padding: 0 16px 6px;')
        return lbl

    # ── 底部 ──

    def _build_footer(self) -> QWidget:
        w = QFrame()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(140)
        self.log_text.setVisible(False)
        wl.addWidget(self.log_text)

        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f'QFrame {{ background: {COLORS["card"]}; border-top: 1px solid {COLORS["divider"]}; }}')
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)

        self.log_toggle_btn = QPushButton('日志')
        self.log_toggle_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {COLORS['text_tertiary']};
                           font-size: 12px; padding: 0; }}
            QPushButton:hover {{ color: {COLORS['text_secondary']}; }}
        """)
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        h.addWidget(self.log_toggle_btn)

        self.log_badge = QLabel()
        self.log_badge.setFixedHeight(16)
        self.log_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_badge.setStyleSheet(f'background: {COLORS["error"]}; color: white; border-radius: 8px; font-size: 10px; font-weight: 600; padding: 0 6px;')
        self.log_badge.setVisible(False)
        h.addWidget(self.log_badge)

        self.log_arrow = QLabel('▸')
        self.log_arrow.setStyleSheet(f'color: {COLORS["text_tertiary"]}; font-size: 11px;')
        h.addWidget(self.log_arrow)

        h.addStretch()

        self.btn_stop = QPushButton('停止')
        self.btn_stop.setProperty('class', 'danger-text')
        self.btn_stop.setFixedHeight(28)
        self.btn_stop.clicked.connect(self._stop_bot)
        self.btn_stop.setVisible(False)
        h.addWidget(self.btn_stop)

        self.btn_start = QPushButton('启动')
        self.btn_start.setFixedSize(64, 28)
        self.btn_start.clicked.connect(self._start_bot)
        self.btn_start.setVisible(False)
        h.addWidget(self.btn_start)

        wl.addWidget(bar)
        return w

    # ── 托盘 ──

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(_make_tray_icon())
        self.tray.setToolTip('微信 Claude Bot')
        menu = QMenu()
        menu.addAction('显示主窗口').triggered.connect(self._show_window)
        menu.addSeparator()
        menu.addAction('退出').triggered.connect(self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ══════════════════════════════════════════════════════════════════════
    #  信号
    # ══════════════════════════════════════════════════════════════════════

    def _connect_signals(self):
        self.engine.sig_log.connect(self._on_log)
        self.engine.sig_status.connect(self._on_status)
        self.engine.sig_qr.connect(self._on_qr)
        self.engine.sig_message_in.connect(self._on_message_in)
        self.engine.sig_message_out.connect(self._on_message_out)

    @pyqtSlot(str, str)
    def _on_log(self, level: str, message: str):
        ts = datetime.now().strftime('%H:%M:%S')
        cmap = {'info': COLORS['text_secondary'], 'warn': COLORS['warn'], 'error': COLORS['error']}
        c = cmap.get(level, COLORS['text_secondary'])
        self.log_text.append(f'<span style="color:{c}">[{ts}] {message}</span>')
        if not self.log_text.isVisible() and level in ('warn', 'error'):
            self._log_unread += 1
            self.log_badge.setText(str(min(self._log_unread, 99)))
            self.log_badge.setVisible(True)

    def _on_check_timeout(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self._set_status('err', '检测超时')
            self.check_claude.set_error('超时')

    @pyqtSlot(str, dict)
    def _on_status(self, state: str, data: dict):
        if state in ('init', 'checking-env'):
            self.stack.setCurrentIndex(0)
            self._set_status('warn', '检测中')
            self.check_claude.set_active()
            QTimer.singleShot(30000, self._on_check_timeout)
        elif state == 'env-ready':
            ver = data.get('version', '')
            self.check_claude.set_done(ver)
            self.check_weixin.set_active('连接中...')
            self._set_status('warn', '等待连接')
            self.info_engine.set_value(f'{self.adapter.name} ({ver})')
        elif state == 'env-error':
            self.stack.setCurrentIndex(1)
            self._set_status('err', '环境异常')
            self.check_claude.set_error('未找到')
        elif state == 'need-login':
            self.stack.setCurrentIndex(2)
            self._set_status('warn', '等待扫码')
            self.qr_step1.set_active()
        elif state == 'qr-ready':
            self.stack.setCurrentIndex(2)
            self._set_status('warn', '等待扫码')
            self.qr_step1.set_done()
            self.qr_step2.set_active()
        elif state == 'qr-scanned':
            self._set_status('warn', '已扫码')
            self.qr_step2.set_done()
            self.qr_step3.set_active()
        elif state == 'connected':
            self.check_weixin.set_done('已连接')
            self.check_ready.set_done()
            QTimer.singleShot(600, lambda: self._enter_running(data))
        elif state in ('disconnected', 'reconnecting'):
            self._set_status('warn', '重连中...')
            self.btn_stop.setVisible(True)
            self.btn_start.setVisible(True)
        elif state == 'stopped':
            self._set_status('off', '已停止')
            self.btn_stop.setVisible(False)
            self.btn_start.setVisible(True)
            self.uptime_timer.stop()

    def _enter_running(self, data: dict):
        self.stack.setCurrentIndex(3)
        self._empty_state.setVisible(True)
        self.msg_flow.setVisible(False)
        self.msg_flow.clear_messages()
        self._set_status('on', '运行中')
        self.btn_stop.setVisible(True)
        self.btn_start.setVisible(False)
        self.start_time = time.time()
        self.uptime_timer.start(5000)
        self._update_uptime()
        bot_id = data.get('bot_id', '')
        self.info_bot_id.set_value(bot_id[:20] + '...' if len(bot_id) > 20 else bot_id)
        self.info_time.set_value(datetime.now().strftime('%Y-%m-%d %H:%M'))

    @pyqtSlot(str)
    def _on_qr(self, qr_content: str):
        img = qrcode.make(qr_content, image_factory=PilImage, box_size=5, border=2)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        self._qr_placeholder.setVisible(False)
        self.qr_label.setVisible(True)
        self.qr_label.setPixmap(pixmap.scaled(
            200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _ensure_msg_visible(self):
        if self._empty_state.isVisible():
            self._empty_state.setVisible(False)
            self.msg_flow.setVisible(True)

    @pyqtSlot(str, str)
    def _on_message_in(self, user_id: str, text: str):
        self.message_count += 1
        self._ensure_msg_visible()
        if text.startswith('[file:'):
            fname = Path(text[6:].rstrip(']')).name
            text = f'📎 {fname}'
        self.msg_flow.add_message(text, user_id, is_incoming=True)
        if not self.isVisible():
            self.tray.showMessage('新消息', f'{user_id[:6]}: {text[:50]}',
                                  QSystemTrayIcon.MessageIcon.Information, 3000)

    @pyqtSlot(str, str)
    def _on_message_out(self, user_id: str, text: str):
        self._ensure_msg_visible()
        self.msg_flow.add_message(text, user_id, is_incoming=False)

    # ══════════════════════════════════════════════════════════════════════
    #  操作
    # ══════════════════════════════════════════════════════════════════════

    def _start_bot(self):
        if self.bot_thread.isRunning():
            return
        self.stack.setCurrentIndex(0)
        self.engine = BotEngine(self.adapter)
        self._connect_signals()
        self.bot_thread = BotThread(self.engine)
        self.bot_thread.start()

    def _stop_bot(self):
        self.btn_stop.setEnabled(False)
        self.engine.stop()
        QTimer.singleShot(1000, lambda: self.btn_stop.setEnabled(True))

    def _toggle_log(self):
        visible = not self.log_text.isVisible()
        self.log_text.setVisible(visible)
        self.log_arrow.setText('▾' if visible else '▸')
        if visible:
            self._log_unread = 0
            self.log_badge.setVisible(False)

    def _navigate_to(self, view_index: int):
        cur = self.stack.currentIndex()
        if cur != 4:
            self._prev_view = cur
        self.stack.setCurrentIndex(view_index)

    def _go_back(self):
        self.stack.setCurrentIndex(self._prev_view)

    def _toggle_settings(self):
        if self.stack.currentIndex() == 4:
            self._go_back()
        else:
            self._navigate_to(4)

    def _select_engine(self, engine_key: str):
        for key, cell in self._engine_cells.items():
            info = ENGINES[key]
            prefix = '● ' if key == engine_key else '○ '
            cell._label.setText(f'{prefix}{info["label"]}')
        self._engine_config['engine'] = engine_key
        self._update_settings_visibility(engine_key)

    def _toggle_apikey_visibility(self):
        if self._apikey_input.echoMode() == QLineEdit.EchoMode.Password:
            self._apikey_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._apikey_eye.setText('🔒')
        else:
            self._apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._apikey_eye.setText('👁')

    def _update_settings_visibility(self, engine_key: str):
        needs_key = ENGINES.get(engine_key, {}).get('needs_api_key', False)
        self._apikey_group.setVisible(needs_key)
        self._provider_row.setVisible(engine_key == 'direct_api')
        self._oi_model_row.setVisible(engine_key == 'open_interpreter')

    def _on_provider_changed(self, index: int):
        provider = self._provider_combo.itemData(index)
        if provider:
            self._engine_config['provider'] = provider

    def _save_engine_config(self):
        self._save_btn.setText('保存中...')
        self._save_btn.setEnabled(False)
        engine = self._engine_config.get('engine', 'claude_code')
        self._engine_config['api_key'] = self._apikey_input.text().strip()
        if engine == 'open_interpreter':
            self._engine_config['model'] = self._oi_model_input.text().strip() or 'gpt-4o'
        elif engine == 'direct_api':
            self._engine_config['provider'] = self._provider_combo.currentData() or 'anthropic'
        save_config(self._engine_config)
        self.adapter = create_adapter(engine, self._engine_config)
        self.info_engine.set_value(self.adapter.name)
        self._stop_bot()
        self._save_btn.setText('已保存 ✓')
        QTimer.singleShot(1000, lambda: self.stack.setCurrentIndex(0))
        QTimer.singleShot(1500, self._start_bot)
        QTimer.singleShot(2000, lambda: (
            self._save_btn.setText('保存并重启 Bot'),
            self._save_btn.setEnabled(True),
        ))

    def _show_model_menu(self):
        menu = QMenu(self)
        current = self.engine.default_model
        for key, m in MODELS.items():
            prefix = '● ' if key == current else '   '
            action = menu.addAction(f'{prefix}{m["label"]} — {m["desc"]}')
            action.triggered.connect(lambda checked, k=key: self._switch_model(k))
        menu.exec(self.settings_model_cell.mapToGlobal(
            self.settings_model_cell.rect().bottomLeft()))

    def _switch_model(self, key: str):
        self.engine.default_model = key
        self.settings_model_cell.set_value(f'{MODELS[key]["label"]} — {MODELS[key]["desc"]}')
        self._model_display.setText(MODELS[key]['label'])

    def _browse_cwd(self):
        path = QFileDialog.getExistingDirectory(self, '选择工作目录', DEFAULT_CWD)
        if path:
            self.settings_cwd_cell.set_value(path)
            from core import config
            config.DEFAULT_CWD = path
            self._engine_config['cwd'] = path
            save_config(self._engine_config)

    def _update_uptime(self):
        if self.start_time:
            up = fmt_uptime(time.time() - self.start_time)
            self.status_text.setText(f'运行中 · {up}')

    # ══════════════════════════════════════════════════════════════════════
    #  拖拽
    # ══════════════════════════════════════════════════════════════════════

    def _do_send_file(self, file_path: str):
        if not self.engine.account:
            return
        account = self.engine.account
        user_id = account.get('userId', '')
        if not user_id:
            return
        try:
            from core import media as media_mod
            from core import weixin_api
            uploaded = media_mod.upload_media(
                file_path, user_id, account['token'],
                account.get('baseUrl', 'https://ilinkai.weixin.qq.com'))
            item = media_mod.build_media_item(uploaded)
            weixin_api.send_media_message(account['token'], user_id, item, None, Path(file_path).name)
            self.engine.sig_log.emit('info', f'📤 已发送: {Path(file_path).name}')
        except Exception as e:
            self.engine.sig_log.emit('error', f'发送失败: {str(e)[:100]}')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).is_file():
                self._do_send_file(path)

    # ══════════════════════════════════════════════════════════════════════
    #  开机自启
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def get_auto_start() -> bool:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, 'WeChatClaudeBot')
            winreg.CloseKey(key)
            return True
        except (FileNotFoundError, OSError):
            return False

    @staticmethod
    def set_auto_start(enabled: bool):
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
        if enabled:
            import sys
            exe = sys.executable
            script = str(Path(__file__).parent.parent / 'main.py')
            winreg.SetValueEx(key, 'WeChatClaudeBot', 0, winreg.REG_SZ, f'"{exe}" "{script}"')
        else:
            try:
                winreg.DeleteValue(key, 'WeChatClaudeBot')
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)

    # ══════════════════════════════════════════════════════════════════════
    #  辅助
    # ══════════════════════════════════════════════════════════════════════

    def _set_status(self, dot: str, text: str):
        self._set_dot(dot)
        self.status_text.setText(text)
        self.tray.setToolTip(f'微信 Claude Bot — {text}')

    def _set_dot(self, dot_type: str):
        c = {'off': '#D1D1D6', 'on': COLORS['accent'], 'warn': COLORS['warn'], 'err': COLORS['error']}.get(dot_type, '#D1D1D6')
        self.status_dot.setStyleSheet(f'background: {c}; border-radius: 3px;')

    def _show_window(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _quit(self):
        self.engine.stop()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage('微信 Claude Bot', '仍在后台运行，双击托盘图标打开',
                                  QSystemTrayIcon.MessageIcon.Information, 2000)
