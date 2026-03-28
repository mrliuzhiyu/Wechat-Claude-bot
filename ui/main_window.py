"""
微信 Claude Bot — PyQt6 主窗口
严格遵循微信原生设计语言（DESIGN.md）
"""

import io
import os
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QTextEdit, QFrame,
    QSystemTrayIcon, QMenu, QApplication, QGridLayout,
    QComboBox, QFileDialog, QSizePolicy, QListWidget,
    QListWidgetItem, QAbstractItemView,
)

import qrcode
from qrcode.image.pil import PilImage

from .theme import COLORS, STYLESHEET
from core.config import MODELS, DEFAULT_CWD
from core.bot_engine import BotEngine, BotThread, fmt_uptime
from adapters.registry import ENGINES, create_adapter, load_config, save_config, detect_available_engines


# ── 图标工厂 ─────────────────────────────────────────────────────────────────

def make_icon(fg: str, bg: str, size: int = 32) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(bg))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(fg))
    p.setFont(QFont('Arial', int(size * 0.48), QFont.Weight.Bold))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, 'C')
    p.end()
    return QIcon(pm)


# ── 微信式组件 ────────────────────────────────────────────────────────────────

class WxCard(QFrame):
    """微信白色卡片"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            WxCard {{
                background: {COLORS['card']};
                border-radius: 8px;
            }}
        """)


class WxCellItem(QFrame):
    """微信 settings cell（标签 + 值 + 箭头）"""
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
    """启动检测项"""
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
    """扫码步骤"""
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


# ── 主窗口 ────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('微信 Claude Bot')
        self.setMinimumSize(440, 620)
        self.resize(480, 700)
        self.setStyleSheet(STYLESHEET)

        self._app_icon = make_icon('#222222', '#ffffff', 64)
        self.setWindowIcon(self._app_icon)

        # 引擎（从保存的配置创建）
        self._engine_config = load_config()
        self.adapter = create_adapter(config=self._engine_config)
        self.engine = BotEngine(self.adapter)
        self.bot_thread = BotThread(self.engine)
        self._connect_signals()

        # 状态
        self.start_time = None
        self.message_count = 0
        self._log_unread = 0
        self._prev_view = 0          # 栈式导航：进入设置/文件页前的视图索引
        self._tray_hint_shown = False # 首次关闭窗口才弹提示

        # UI
        self._build_ui()
        self._build_tray()

        # 定时器
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(self._update_uptime)

        # 拖拽支持
        self.setAcceptDrops(True)

        # 自动启动
        QTimer.singleShot(200, self._start_bot)

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
        self.stack.addWidget(self._build_files_view())       # 5
        root.addWidget(self.stack, 1)

        root.addWidget(self._build_log_panel())
        root.addWidget(self._build_footer())

    # ── 头部 ──

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet(f'QFrame {{ background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]}; }}')
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(10)

        logo = QLabel('C')
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f'background: {COLORS["accent"]}; color: white; border-radius: 6px; font-weight: bold; font-size: 15px;')
        h.addWidget(logo)

        title = QLabel('微信 Claude Bot')
        title.setStyleSheet(f'font-size: 15px; font-weight: 600; color: {COLORS["text"]};')
        h.addWidget(title)
        h.addStretch()

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self._set_dot('off')
        h.addWidget(self.status_dot)

        self.status_text = QLabel('未启动')
        self.status_text.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 12px;')
        h.addWidget(self.status_text)

        btn_settings = QPushButton('⚙')
        btn_settings.setProperty('class', 'icon')
        btn_settings.setFixedSize(32, 32)
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

        # 检测列表（微信式白色卡片）
        card = WxCard()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self.check_claude = CheckItem('Claude Code CLI')
        self.check_weixin = CheckItem('微信连接')
        self.check_ready = CheckItem('就绪')
        # 去掉最后一项的下边框
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
        cmd.setStyleSheet(f'background: {COLORS["card"]}; color: {COLORS["text"]}; border: 1px solid {COLORS["divider"]}; border-radius: 4px; padding: 10px 16px; font-family: Consolas, monospace; font-size: 12px;')
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

        # QR 容器
        qr_card = QFrame()
        qr_card.setFixedSize(220, 220)
        qr_card.setStyleSheet(f'background: white; border-radius: 8px;')
        ql = QVBoxLayout(qr_card)
        ql.setContentsMargins(0, 0, 0, 0)
        # QR 占位骨架
        qr_placeholder = QWidget()
        qpl = QVBoxLayout(qr_placeholder)
        qpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qpl.setSpacing(8)
        qr_icon = QLabel('⏳')
        qr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_icon.setStyleSheet(f'font-size: 36px; color: {COLORS["text_tertiary"]};')
        qpl.addWidget(qr_icon)
        qr_hint = QLabel('二维码获取中...')
        qr_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_hint.setStyleSheet(f'color: {COLORS["text_tertiary"]}; font-size: 13px;')
        qpl.addWidget(qr_hint)
        self._qr_placeholder = qr_placeholder
        ql.addWidget(qr_placeholder)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setVisible(False)
        ql.addWidget(self.qr_label)
        v.addWidget(qr_card, alignment=Qt.AlignmentFlag.AlignCenter)

        # 步骤引导
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

    # ── 视图3: 仪表盘 ──

    def _build_running_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["bg"]};')
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 8)
        v.setSpacing(8)

        # 统计卡片（微信式：白色卡片内用分割线分隔）
        stats_card = WxCard()
        stats_grid = QGridLayout(stats_card)
        stats_grid.setContentsMargins(0, 0, 0, 0)
        stats_grid.setSpacing(0)

        self.stat_uptime = self._stat_cell('运行时间', '0m')
        self.stat_messages = self._stat_cell('消息数', '0')
        self.stat_users = self._stat_cell('活跃用户', '0')
        self.stat_model = self._stat_cell('当前模型', 'Sonnet', clickable=True)

        stats_grid.addWidget(self.stat_uptime, 0, 0)
        stats_grid.addWidget(self._vdivider(), 0, 1)
        stats_grid.addWidget(self.stat_messages, 0, 2)
        stats_grid.addWidget(self._hdivider(), 1, 0, 1, 3)
        stats_grid.addWidget(self.stat_users, 2, 0)
        stats_grid.addWidget(self._vdivider(), 2, 1)
        stats_grid.addWidget(self.stat_model, 2, 2)

        v.addWidget(stats_card)

        # 消息卡片
        msg_card = WxCard()
        ml = QVBoxLayout(msg_card)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        msg_header = QLabel('最近消息')
        msg_header.setStyleSheet(f'color: {COLORS["text_tertiary"]}; font-size: 12px; padding: 12px 16px 6px;')
        ml.addWidget(msg_header)

        self.msg_list = QTextEdit()
        self.msg_list.setReadOnly(True)
        self.msg_list.setPlaceholderText("微信消息会显示在这里")
        self.msg_list.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['card']};
                border: none;
                border-radius: 0 0 8px 8px;
                padding: 4px 16px 12px;
                font-family: "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
                color: {COLORS['text']};
            }}
        """)
        ml.addWidget(self.msg_list, 1)

        v.addWidget(msg_card, 1)

        # 快捷操作栏
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        btn_files = QPushButton('📁 文件收件箱')
        btn_files.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['card']}; color: {COLORS['link']};
                           border: 1px solid {COLORS['divider']}; border-radius: 8px;
                           padding: 12px; font-size: 13px; font-weight: 500; }}
            QPushButton:hover {{ background: #F5F5F5; border-color: {COLORS['accent']}; }}
        """)
        btn_files.clicked.connect(lambda: self._navigate_to(5))
        action_row.addWidget(btn_files)

        btn_send_file = QPushButton('📤 发送文件')
        btn_send_file.setProperty('class', 'text')
        btn_send_file.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['card']}; color: {COLORS['link']};
                           border: 1px solid {COLORS['divider']}; border-radius: 8px;
                           padding: 12px; font-size: 13px; font-weight: 500; }}
            QPushButton:hover {{ background: #F5F5F5; border-color: {COLORS['accent']}; }}
        """)
        btn_send_file.clicked.connect(self._send_file_dialog)
        action_row.addWidget(btn_send_file)

        v.addLayout(action_row)
        return w

    def _stat_cell(self, label: str, value: str, clickable: bool = False) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["card"]};')
        if clickable:
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            w.mousePressEvent = lambda e: self._show_model_menu()
        vl = QVBoxLayout(w)
        w.setMinimumHeight(76)
        vl.setContentsMargins(0, 18, 0, 18)
        vl.setSpacing(4)
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val = QLabel(value)
        val.setObjectName('stat_value')
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f'font-size: 22px; font-weight: 700; color: {COLORS["text"]};')
        vl.addWidget(val)

        lbl = QLabel(f'{label} ›' if clickable else label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f'font-size: 12px; color: {COLORS["text_tertiary"]};')
        vl.addWidget(lbl)

        return w

    def _vdivider(self) -> QFrame:
        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f'background: {COLORS["divider"]};')
        return d

    def _hdivider(self) -> QFrame:
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f'background: {COLORS["divider"]};')
        return d

    # ── 视图4: 设置 ──

    def _build_settings_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["bg"]};')
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 微信式设置头部
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

        # 可滚动内容区
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f'QScrollArea {{ border: none; background: {COLORS["bg"]}; }}')

        content = QWidget()
        content.setStyleSheet(f'background: {COLORS["bg"]};')
        cv = QVBoxLayout(content)
        cv.setContentsMargins(12, 12, 12, 12)
        cv.setSpacing(0)

        # ── AI 引擎 ──
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

            cell = WxCellItem(
                f'{prefix}{info["label"]}{suffix}',
                info['desc'],
                arrow=True
            )
            cell.mousePressEvent = lambda e, k=key: self._select_engine(k)

            if key != list(ENGINES.keys())[-1]:
                cell.setStyleSheet(f'background: {COLORS["card"]}; border-bottom: 1px solid {COLORS["divider"]};')
            else:
                cell.setStyleSheet(f'background: {COLORS["card"]};')

            el.addWidget(cell)
            self._engine_cells[key] = cell

        cv.addWidget(engine_card)
        cv.addSpacing(12)

        # ── API Key（引擎需要时显示）──
        self._apikey_group = QWidget()
        ag = QVBoxLayout(self._apikey_group)
        ag.setContentsMargins(0, 0, 0, 0)
        ag.setSpacing(0)
        ag.addWidget(self._group_title('API Key'))

        apikey_card = WxCard()
        al = QVBoxLayout(apikey_card)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(8)

        # 提供商选择（纯API模式用）
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

        # API Key 输入
        from PyQt6.QtWidgets import QLineEdit
        self._apikey_input = QLineEdit()
        self._apikey_input.setPlaceholderText('输入 API Key...')
        self._apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_input.setStyleSheet(f'''
            QLineEdit {{
                background: {COLORS["bg"]};
                border: 1px solid {COLORS["divider"]};
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                color: {COLORS["text"]};
            }}
            QLineEdit:focus {{ border-color: {COLORS["accent"]}; }}
        ''')
        saved_key = self._engine_config.get('api_key', '')
        if saved_key:
            self._apikey_input.setText(saved_key)

        # API Key 行：输入框 + 眼睛切换
        apikey_row = QHBoxLayout()
        apikey_row.setContentsMargins(0, 0, 0, 0)
        apikey_row.setSpacing(4)
        apikey_row.addWidget(self._apikey_input)
        self._apikey_eye = QPushButton('👁')
        self._apikey_eye.setFixedSize(32, 32)
        self._apikey_eye.setProperty('class', 'icon')
        self._apikey_eye.setToolTip('显示/隐���')
        self._apikey_eye.clicked.connect(self._toggle_apikey_visibility)
        apikey_row.addWidget(self._apikey_eye)
        al.addLayout(apikey_row)

        # OI 模型输入
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

        # 保存按钮
        self._save_btn = QPushButton('保存并重启 Bot')
        self._save_btn.clicked.connect(self._save_engine_config)
        al.addWidget(self._save_btn)

        ag.addWidget(apikey_card)
        cv.addWidget(self._apikey_group)

        # 根据当前引擎显示/隐藏 API Key 区域
        self._update_settings_visibility(current_engine)

        cv.addSpacing(16)

        # ── 微信模型（Claude Code 模式用）──
        cv.addWidget(self._group_title('微信消息模型'))
        self.settings_model_cell = WxCellItem('当前模型', 'Sonnet — 快速', arrow=True)
        self.settings_model_cell.mousePressEvent = lambda e: self._show_model_menu()
        self.settings_model_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        cv.addWidget(self.settings_model_cell)

        cv.addSpacing(16)

        # ── 工作目录 ──
        cv.addWidget(self._group_title('工作目录'))
        self.settings_cwd_cell = WxCellItem('路径', DEFAULT_CWD, arrow=True)
        self.settings_cwd_cell.mousePressEvent = lambda e: self._browse_cwd()
        self.settings_cwd_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        cv.addWidget(self.settings_cwd_cell)

        cv.addSpacing(16)

        # ── 开机自启 ──
        cv.addWidget(self._group_title('系统'))
        autostart_cell = QFrame()
        autostart_cell.setStyleSheet(f'background: {COLORS["card"]}; border-radius: 8px;')
        autostart_cell.setFixedHeight(48)
        ash = QHBoxLayout(autostart_cell)
        ash.setContentsMargins(16, 0, 16, 0)
        asl = QLabel('开机自动启动')
        asl.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]};')
        ash.addWidget(asl, 1)

        from PyQt6.QtWidgets import QCheckBox
        self._autostart_cb = QCheckBox()
        self._autostart_cb.setChecked(self.get_auto_start())
        self._autostart_cb.stateChanged.connect(lambda state: self.set_auto_start(state == 2))
        ash.addWidget(self._autostart_cb)
        cv.addWidget(autostart_cell)

        cv.addSpacing(16)

        # ── 连接信息 ──
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

    # ── 视图5: 文件收件箱 ──

    def _build_files_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {COLORS["bg"]};')
        w.setAcceptDrops(True)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 头部
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
        ftitle = QLabel('文件收件箱')
        ftitle.setStyleSheet(f'font-size: 16px; font-weight: 600; color: {COLORS["text"]};')
        hh.addWidget(ftitle)
        hh.addStretch()
        refresh_btn = QPushButton('刷新')
        refresh_btn.setProperty('class', 'text')
        refresh_btn.clicked.connect(self._refresh_files)
        hh.addWidget(refresh_btn)
        v.addWidget(header)

        # 拖拽提示区
        self._drop_hint = QLabel('将文件拖拽到此处\n发送到微信')
        self._drop_hint.setFixedHeight(64)
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setStyleSheet(self._drop_hint_normal_ss)
        v.addWidget(self._drop_hint)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['card']};
                border: none;
                border-radius: 8px;
                margin: 0 12px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px 16px;
                border-bottom: 1px solid {COLORS['divider']};
            }}
            QListWidget::item:hover {{
                background: #F5F5F5;
            }}
            QListWidget::item:selected {{
                background: {COLORS['accent_light']};
                color: {COLORS['text']};
            }}
        """)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.itemDoubleClicked.connect(self._open_file_item)
        v.addWidget(self.file_list, 1)

        # 操作栏
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(12, 8, 12, 8)
        action_bar.addStretch()

        btn_open = QPushButton('打开')
        btn_open.setFixedSize(72, 32)
        btn_open.clicked.connect(self._open_selected_file)
        action_bar.addWidget(btn_open)

        btn_save = QPushButton('另存为')
        btn_save.setProperty('class', 'text')
        btn_save.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['card']}; color: {COLORS['link']};
                           border: 1px solid {COLORS['divider']}; border-radius: 4px; padding: 6px 16px; }}
            QPushButton:hover {{ background: #F0F0F0; }}
        """)
        btn_save.setFixedHeight(32)
        btn_save.clicked.connect(self._save_file_as)
        action_bar.addWidget(btn_save)

        v.addLayout(action_bar)

        # 首次加载
        QTimer.singleShot(500, self._refresh_files)

        return w

    # ── 日志面板 ──

    def _build_log_panel(self) -> QWidget:
        w = QFrame()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 切换栏
        toggle_frame = QFrame()
        toggle_frame.setFixedHeight(32)
        toggle_frame.setStyleSheet(f'QFrame {{ background: {COLORS["nav_bg"]}; border-top: 1px solid {COLORS["divider"]}; }}')
        th = QHBoxLayout(toggle_frame)
        th.setContentsMargins(16, 0, 16, 0)

        self.log_toggle_btn = QPushButton('日志 ▸')
        self.log_toggle_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {COLORS['text_secondary']};
                           font-size: 12px; padding: 0; text-align: left; }}
            QPushButton:hover {{ color: {COLORS['text']}; }}
        """)
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        th.addWidget(self.log_toggle_btn)

        self.log_badge = QLabel()
        self.log_badge.setFixedHeight(16)
        self.log_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_badge.setStyleSheet(f'background: {COLORS["error"]}; color: white; border-radius: 8px; font-size: 10px; font-weight: 600; padding: 0 6px;')
        self.log_badge.setVisible(False)
        th.addWidget(self.log_badge)

        th.addStretch()
        self.log_arrow = QLabel('▸')
        self.log_arrow.setStyleSheet(f'color: {COLORS["text_tertiary"]}; font-size: 11px;')
        th.addWidget(self.log_arrow)

        v.addWidget(toggle_frame)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(140)
        self.log_text.setVisible(False)
        v.addWidget(self.log_text)

        return w

    # ── 底部 ──

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setFixedHeight(40)
        footer.setStyleSheet(f'QFrame {{ background: {COLORS["card"]}; border-top: 1px solid {COLORS["divider"]}; }}')
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 0, 12, 0)

        hint = QLabel('关闭窗口最小化到托盘')
        hint.setStyleSheet(f'font-size: 11px; color: {COLORS["text_tertiary"]};')
        h.addWidget(hint)
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

        return footer

    # ── 托盘（黑C白底）──

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        # 多尺寸托盘图标（适配高 DPI）
        tray_icon = QIcon()
        for s in (16, 24, 32):
            pm = QPixmap(s, s)
            pm.fill(QColor('#ffffff'))
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QColor('#222222'))
            p.setFont(QFont('Arial', int(s * 0.48), QFont.Weight.Bold))
            p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, 'C')
            p.end()
            tray_icon.addPixmap(pm)
        self.tray.setIcon(tray_icon)
        self.tray.setToolTip('微信 Claude Bot')

        menu = QMenu()
        show_action = menu.addAction('显示主窗口')
        show_action.triggered.connect(self._show_window)
        menu.addSeparator()
        quit_action = menu.addAction('退出')
        quit_action.triggered.connect(self._quit)
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

    @pyqtSlot(str, dict)
    def _on_check_timeout(self):
        """检测超时 — 如果仍在检测页则跳转到错误页"""
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
            # 30 秒检测超时
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
            self.btn_start.setVisible(True)   # 允许用户手动重连或停止

        elif state == 'stopped':
            self._set_status('off', '已停止')
            self.btn_stop.setVisible(False)
            self.btn_start.setVisible(True)
            self.uptime_timer.stop()

    def _enter_running(self, data: dict):
        self.stack.setCurrentIndex(3)
        self._set_status('on', '运行中')
        self.btn_stop.setVisible(True)
        self.btn_start.setVisible(False)
        self.start_time = time.time()
        self.uptime_timer.start(5000)  # 每5秒更新
        self._update_uptime()
        QTimer.singleShot(1000, self._update_uptime)  # 1秒后再更新一次
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

    @pyqtSlot(str, str)
    def _on_message_in(self, user_id: str, text: str):
        self.message_count += 1
        self._update_stat(self.stat_messages, str(self.message_count))
        users = self.engine.stats.get('active_users', set())
        self._update_stat(self.stat_users, str(len(users) if isinstance(users, set) else 0))
        ts = datetime.now().strftime('%H:%M')
        self.msg_list.append(
            f'<span style="color:{COLORS["text_tertiary"]};font-size:11px">{ts}</span> '
            f'<span style="color:{COLORS["accent"]}">← 收</span> '
            f'<span style="color:{COLORS["text_secondary"]}">{user_id[:6]}</span> '
            f'{text[:120]}'
        )
        if not self.isVisible():
            self.tray.showMessage('新消息', f'{user_id[:6]}: {text[:50]}',
                                  QSystemTrayIcon.MessageIcon.Information, 3000)

    @pyqtSlot(str, str)
    def _on_message_out(self, user_id: str, text: str):
        ts = datetime.now().strftime('%H:%M')
        self.msg_list.append(
            f'<span style="color:{COLORS["text_tertiary"]};font-size:11px">{ts}</span> '
            f'<span style="color:{COLORS["text_secondary"]}">→ 发</span> '
            f'<span style="color:{COLORS["text_tertiary"]}">{user_id[:6]}</span> '
            f'{text[:120]}'
        )

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
        """带记忆的导航：跳转前记录当前视图"""
        cur = self.stack.currentIndex()
        if cur not in (4, 5):          # 只记录非设置/文件的主视图
            self._prev_view = cur
        self.stack.setCurrentIndex(view_index)

    def _go_back(self):
        """返回上一个主视图"""
        self.stack.setCurrentIndex(self._prev_view)

    def _toggle_settings(self):
        if self.stack.currentIndex() == 4:
            self._go_back()
        else:
            self._navigate_to(4)

    def _select_engine(self, engine_key: str):
        """在设置页选中一个引擎"""
        for key, cell in self._engine_cells.items():
            info = ENGINES[key]
            is_selected = (key == engine_key)
            prefix = '● ' if is_selected else '○ '
            cell._label.setText(f'{prefix}{info["label"]}')
        self._engine_config['engine'] = engine_key
        self._update_settings_visibility(engine_key)

    def _toggle_apikey_visibility(self):
        from PyQt6.QtWidgets import QLineEdit
        if self._apikey_input.echoMode() == QLineEdit.EchoMode.Password:
            self._apikey_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._apikey_eye.setText('🔒')
        else:
            self._apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._apikey_eye.setText('👁')

    def _update_settings_visibility(self, engine_key: str):
        """根据引擎类型显示/隐藏 API Key 区域"""
        needs_key = ENGINES.get(engine_key, {}).get('needs_api_key', False)
        self._apikey_group.setVisible(needs_key)
        # 提供商下拉只在纯 API 模式显示
        self._provider_row.setVisible(engine_key == 'direct_api')
        # OI 模型输入只在 Open Interpreter 模式显示
        self._oi_model_row.setVisible(engine_key == 'open_interpreter')

    def _on_provider_changed(self, index: int):
        provider = self._provider_combo.itemData(index)
        if provider:
            self._engine_config['provider'] = provider

    def _save_engine_config(self):
        """保存引擎配置并重启 Bot"""
        self._save_btn.setText('保存中...')
        self._save_btn.setEnabled(False)

        engine = self._engine_config.get('engine', 'claude_code')
        self._engine_config['api_key'] = self._apikey_input.text().strip()

        if engine == 'open_interpreter':
            self._engine_config['model'] = self._oi_model_input.text().strip() or 'gpt-4o'
        elif engine == 'direct_api':
            self._engine_config['provider'] = self._provider_combo.currentData() or 'anthropic'

        save_config(self._engine_config)

        # 重建适配器并重启
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
        menu.exec(self.stat_model.mapToGlobal(self.stat_model.rect().bottomLeft()))

    def _switch_model(self, key: str):
        self.engine.default_model = key
        self._update_stat(self.stat_model, MODELS[key]['label'])
        self.settings_model_cell.set_value(f'{MODELS[key]["label"]} — {MODELS[key]["desc"]}')

    def _browse_cwd(self):
        path = QFileDialog.getExistingDirectory(self, '选择工作目录', DEFAULT_CWD)
        if path:
            self.settings_cwd_cell.set_value(path)
            from core import config
            config.DEFAULT_CWD = path
            # 持久化到引擎配置
            self._engine_config['cwd'] = path
            save_config(self._engine_config)

    def _update_uptime(self):
        if self.start_time:
            self._update_stat(self.stat_uptime, fmt_uptime(time.time() - self.start_time))

    def _update_stat(self, widget: QWidget, value: str):
        lbl = widget.findChild(QLabel, 'stat_value')
        if lbl:
            lbl.setText(value)

    # ══════════════════════════════════════════════════════════════════════
    #  文件收件箱
    # ══════════════════════════════════════════════════════════════════════

    def _refresh_files(self):
        """扫描 .state/media/ 目录，刷新文件列表"""
        from core.config import MEDIA_DIR
        self.file_list.clear()
        try:
            files = sorted(MEDIA_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        except Exception:
            files = []

        for f in files:
            if f.name.startswith('.') or not f.is_file():
                continue
            size = f.stat().st_size
            if size < 1024:
                size_str = f'{size}B'
            elif size < 1024 * 1024:
                size_str = f'{size / 1024:.1f}KB'
            else:
                size_str = f'{size / 1024 / 1024:.1f}MB'

            # 时间
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%m-%d %H:%M')

            item = QListWidgetItem(f'{f.name}\n{size_str} · {mtime}')
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.file_list.addItem(item)

        has_files = any(f.is_file() and not f.name.startswith('.') for f in files)
        if not has_files:
            item = QListWidgetItem()
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setSizeHint(QSize(0, 120))
            self.file_list.addItem(item)
            # 空状态居中 widget
            empty_w = QWidget()
            el = QVBoxLayout(empty_w)
            el.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.setSpacing(8)
            ei = QLabel('📭')
            ei.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ei.setStyleSheet('font-size: 36px; background: transparent;')
            el.addWidget(ei)
            et = QLabel('暂无文件')
            et.setAlignment(Qt.AlignmentFlag.AlignCenter)
            et.setStyleSheet(f'font-size: 14px; color: {COLORS["text"]}; font-weight: 500; background: transparent;')
            el.addWidget(et)
            es = QLabel('微信发送的文件会出现在这里')
            es.setAlignment(Qt.AlignmentFlag.AlignCenter)
            es.setStyleSheet(f'font-size: 12px; color: {COLORS["text_tertiary"]}; background: transparent;')
            el.addWidget(es)
            self.file_list.setItemWidget(item, empty_w)

    def _open_file_item(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            import subprocess
            subprocess.Popen(['explorer', '/select,', path.replace('/', '\\')])

    def _open_selected_file(self):
        item = self.file_list.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                os.startfile(path)

    def _save_file_as(self):
        item = self.file_list.currentItem()
        if not item:
            return
        src = item.data(Qt.ItemDataRole.UserRole)
        if not src:
            return
        src_path = Path(src)
        dest, _ = QFileDialog.getSaveFileName(self, '另存为', src_path.name)
        if dest:
            import shutil
            shutil.copy2(src, dest)

    def _send_file_dialog(self):
        """从文件对话框选择文件发送到微信"""
        path, _ = QFileDialog.getOpenFileName(self, '选择要发送的文件')
        if path:
            self._do_send_file(path)

    def _do_send_file(self, file_path: str):
        """发送文件到微信（给自己）"""
        if not self.engine.account:
            return
        account = self.engine.account
        # 发送给连接的用户（bot 自身的 userId）
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

    # ══════════════════════════════════════════════════════════════════════
    #  拖拽发文件
    # ══════════════════════════════════════════════════════════════════════

    _drop_hint_normal_ss = f"""
        QLabel {{
            background: {COLORS['accent_light']};
            color: {COLORS['accent']};
            border: 2px dashed {COLORS['accent']};
            border-radius: 8px;
            margin: 12px;
            font-size: 13px;
        }}
    """
    _drop_hint_active_ss = f"""
        QLabel {{
            background: {COLORS['accent']};
            color: white;
            border: 2px solid {COLORS['accent']};
            border-radius: 8px;
            margin: 12px;
            font-size: 13px;
            font-weight: 600;
        }}
    """

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_hint.setStyleSheet(self._drop_hint_active_ss)
            self._drop_hint.setText('松开发送文件')

    def dragLeaveEvent(self, event):
        self._drop_hint.setStyleSheet(self._drop_hint_normal_ss)
        self._drop_hint.setText('将文件拖拽到此处\n发送到微信')

    def dropEvent(self, event):
        self._drop_hint.setStyleSheet(self._drop_hint_normal_ss)
        self._drop_hint.setText('将文件拖拽到此处\n发送到微信')
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).is_file():
                self._do_send_file(path)

    # ══════════════════════════════════════════════════════════════════════
    #  开机自启
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def get_auto_start() -> bool:
        """检查是否设置了开机自启"""
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
        """设置/取消开机自启"""
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
        c = {'off': '#C8C8C8', 'on': COLORS['accent'], 'warn': COLORS['warn'], 'err': COLORS['error']}.get(dot_type, '#C8C8C8')
        self.status_dot.setStyleSheet(f'background: {c}; border-radius: 4px;')

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
