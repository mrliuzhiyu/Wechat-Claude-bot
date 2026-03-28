"""
PyQt6 主窗口 — 完整桌面客户端
视图: 启动检测 → 扫码登录 → 运行仪表盘 + 设置页
"""

import io
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QTextEdit, QFrame,
    QSystemTrayIcon, QMenu, QApplication, QGridLayout,
    QComboBox, QFileDialog, QCheckBox, QSizePolicy,
)

import qrcode
from qrcode.image.pil import PilImage

from .theme import COLORS, STYLESHEET
from core.config import MODELS, DEFAULT_CWD
from core.bot_engine import BotEngine, BotThread, fmt_uptime
from adapters.claude_code import ClaudeCodeAdapter


# ── 图标工厂 ─────────────────────────────────────────────────────────────────

def make_icon(fg: str, bg: str, size: int = 32) -> QIcon:
    """生成 C 字母图标"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(bg)))
    p.setPen(Qt.PenStyle.NoPen)
    r = size * 0.2
    p.drawRoundedRect(0, 0, size, size, r, r)
    p.setPen(QColor(fg))
    p.setFont(QFont('Arial', int(size * 0.5), QFont.Weight.Bold))
    p.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'C')
    p.end()
    return QIcon(pixmap)


def make_dot_pixmap(color: str, size: int = 10) -> QPixmap:
    """生成圆形状态点"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pm


# ── 可复用组件 ────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    """统计卡片"""
    def __init__(self, label: str, value: str = '0', clickable: bool = False):
        super().__init__()
        self.setStyleSheet(f"""
            StatCard {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            StatCard:hover {{
                border-color: {COLORS['border_light'] if clickable else COLORS['border']};
            }}
        """)
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(2)

        self._label = QLabel(label)
        self._label.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 11px;')
        v.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setStyleSheet(f'color: {COLORS["text"]}; font-size: 22px; font-weight: bold;')
        v.addWidget(self._value)

    def set_value(self, text: str):
        self._value.setText(text)


class StepItem(QWidget):
    """步骤指示器项"""
    def __init__(self, text: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(10)

        self._dot = QLabel()
        self._dot.setFixedSize(20, 20)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_state('pending')
        h.addWidget(self._dot)

        self._text = QLabel(text)
        self._text.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 13px;')
        h.addWidget(self._text, 1)

        self._status = QLabel('')
        self._status.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 12px;')
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        h.addWidget(self._status)

    def _set_state(self, state: str):
        colors = {
            'pending': COLORS['border'],
            'active': COLORS['warn'],
            'done': COLORS['accent'],
            'error': COLORS['danger'],
        }
        c = colors.get(state, COLORS['border'])
        symbols = {'pending': '○', 'active': '◌', 'done': '✓', 'error': '✗'}
        sym = symbols.get(state, '○')
        fg = 'white' if state in ('done', 'error') else COLORS['text_dim']
        self._dot.setStyleSheet(f'background: {c}; color: {fg}; border-radius: 10px; font-size: 11px; font-weight: bold;')
        self._dot.setText(sym)

    def set_active(self, status_text: str = ''):
        self._set_state('active')
        self._text.setStyleSheet(f'color: {COLORS["text"]}; font-size: 13px;')
        self._status.setText(status_text)
        self._status.setStyleSheet(f'color: {COLORS["warn"]}; font-size: 12px;')

    def set_done(self, status_text: str = ''):
        self._set_state('done')
        self._text.setStyleSheet(f'color: {COLORS["accent"]}; font-size: 13px;')
        self._status.setText(status_text)
        self._status.setStyleSheet(f'color: {COLORS["accent"]}; font-size: 12px;')

    def set_error(self, status_text: str = ''):
        self._set_state('error')
        self._text.setStyleSheet(f'color: {COLORS["danger"]}; font-size: 13px;')
        self._status.setText(status_text)
        self._status.setStyleSheet(f'color: {COLORS["danger"]}; font-size: 12px;')


# ── 主窗口 ────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('微信 Claude Bot')
        self.setMinimumSize(480, 640)
        self.resize(520, 720)
        self.setStyleSheet(STYLESHEET)

        # 窗口图标（黑C白底）
        self._app_icon = make_icon('#222222', '#ffffff', 64)
        self.setWindowIcon(self._app_icon)

        # 引擎
        self.adapter = ClaudeCodeAdapter()
        self.engine = BotEngine(self.adapter)
        self.bot_thread = BotThread(self.engine)
        self._connect_signals()

        # 状态
        self.start_time = None
        self.message_count = 0
        self._log_unread = 0

        # UI
        self._build_ui()
        self._build_tray()

        # 定时器
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(self._update_uptime)

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

        # 内容区
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_checking_view())   # 0
        self.stack.addWidget(self._build_env_error_view())  # 1
        self.stack.addWidget(self._build_qr_view())         # 2
        self.stack.addWidget(self._build_running_view())     # 3
        self.stack.addWidget(self._build_settings_view())    # 4
        root.addWidget(self.stack, 1)

        root.addWidget(self._build_log_panel())
        root.addWidget(self._build_footer())

    # ── 头部 ──

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(f'QFrame {{ background: {COLORS["bg"]}; border-bottom: 1px solid {COLORS["border"]}; }}')
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(10)

        logo = QLabel('C')
        logo.setFixedSize(30, 30)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f'background: {COLORS["accent"]}; color: white; border-radius: 7px; font-weight: bold; font-size: 16px;')
        h.addWidget(logo)

        title = QLabel('微信 Claude Bot')
        title.setStyleSheet('font-size: 15px; font-weight: bold;')
        h.addWidget(title)
        h.addStretch()

        # 状态
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self._set_dot('off')
        h.addWidget(self.status_dot)

        self.status_text = QLabel('未启动')
        self.status_text.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 12px;')
        h.addWidget(self.status_text)

        # 设置按钮
        self.btn_settings = QPushButton('⚙')
        self.btn_settings.setProperty('class', 'icon')
        self.btn_settings.setFixedSize(32, 32)
        self.btn_settings.setToolTip('设置')
        self.btn_settings.clicked.connect(self._toggle_settings)
        h.addWidget(self.btn_settings)

        return header

    # ── 视图0: 启动检测 ──

    def _build_checking_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(40, 60, 40, 40)
        v.setSpacing(8)

        title = QLabel('启动检测')
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        sub = QLabel('正在检查运行环境')
        sub.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 13px; margin-bottom: 24px;')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)

        self.step_claude = StepItem('Claude Code CLI')
        self.step_weixin = StepItem('微信连接')
        self.step_ready = StepItem('就绪')

        v.addWidget(self.step_claude)
        v.addWidget(self.step_weixin)
        v.addWidget(self.step_ready)
        v.addStretch()
        return w

    # ── 视图1: 环境错误 ──

    def _build_env_error_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(12)

        icon = QLabel('✗')
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f'background: {COLORS["danger"]}; color: white; border-radius: 28px; font-size: 28px; font-weight: bold;')
        v.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self.env_error_title = QLabel('环境检测失败')
        self.env_error_title.setStyleSheet('font-size: 18px; font-weight: bold;')
        self.env_error_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.env_error_title)

        self.env_error_detail = QLabel('未检测到 Claude Code CLI')
        self.env_error_detail.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 13px;')
        self.env_error_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.env_error_detail)

        cmd_box = QLabel('npm install -g @anthropic-ai/claude-code')
        cmd_box.setStyleSheet(f'background: {COLORS["bg_card"]}; color: {COLORS["accent"]}; border: 1px solid {COLORS["border"]}; border-radius: 6px; padding: 10px 16px; font-family: Consolas, monospace; font-size: 12px;')
        cmd_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cmd_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(cmd_box, alignment=Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton('重新检测')
        btn.setFixedWidth(120)
        btn.clicked.connect(self._start_bot)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── 视图2: 扫码登录 ──

    def _build_qr_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(16)

        title = QLabel('连接微信')
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        # 二维码容器
        qr_frame = QFrame()
        qr_frame.setFixedSize(260, 260)
        qr_frame.setStyleSheet('background: white; border-radius: 12px;')
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(0, 0, 0, 0)
        self.qr_label = QLabel('获取中...')
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 13px; background: white; border-radius: 12px;')
        qr_layout.addWidget(self.qr_label)
        v.addWidget(qr_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # 步骤引导
        steps_w = QWidget()
        steps_w.setFixedWidth(280)
        sv = QVBoxLayout(steps_w)
        sv.setContentsMargins(0, 8, 0, 0)
        sv.setSpacing(4)

        self.qr_step1 = StepItem('打开微信')
        self.qr_step2 = StepItem('扫描上方二维码')
        self.qr_step3 = StepItem('在微信中点击确认')
        self.qr_step1.set_active()

        sv.addWidget(self.qr_step1)
        sv.addWidget(self.qr_step2)
        sv.addWidget(self.qr_step3)
        v.addWidget(steps_w, alignment=Qt.AlignmentFlag.AlignCenter)

        # 刷新提示
        self.qr_refresh_btn = QPushButton('二维码过期？点击刷新')
        self.qr_refresh_btn.setProperty('class', 'ghost')
        self.qr_refresh_btn.setFixedWidth(200)
        self.qr_refresh_btn.setVisible(False)
        v.addWidget(self.qr_refresh_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    # ── 视图3: 运行仪表盘 ──

    def _build_running_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 8)
        v.setSpacing(12)

        # 统计卡片 2x2
        grid = QGridLayout()
        grid.setSpacing(10)

        self.card_uptime = StatCard('运行时间', '0m')
        self.card_messages = StatCard('消息数', '0')
        self.card_users = StatCard('活跃用户', '0')
        self.card_model = StatCard('当前模型', 'Sonnet', clickable=True)
        self.card_model.mousePressEvent = lambda _: self._show_model_menu()

        grid.addWidget(self.card_uptime, 0, 0)
        grid.addWidget(self.card_messages, 0, 1)
        grid.addWidget(self.card_users, 1, 0)
        grid.addWidget(self.card_model, 1, 1)
        v.addLayout(grid)

        # 最近消息标题
        msg_header = QHBoxLayout()
        msg_title = QLabel('最近消息')
        msg_title.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 11px;')
        msg_header.addWidget(msg_title)
        msg_header.addStretch()
        v.addLayout(msg_header)

        # 消息列表
        self.msg_list = QTextEdit()
        self.msg_list.setReadOnly(True)
        self.msg_list.setPlaceholderText('等待消息...')
        self.msg_list.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 12px;
                font-family: "Microsoft YaHei UI", sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }}
        """)
        v.addWidget(self.msg_list, 1)

        return w

    # ── 视图4: 设置 ──

    def _build_settings_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(0)

        # 标题栏
        th = QHBoxLayout()
        back_btn = QPushButton('← 返回')
        back_btn.setProperty('class', 'ghost')
        back_btn.setFixedHeight(32)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        th.addWidget(back_btn)
        th.addStretch()
        title = QLabel('设置')
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        th.addWidget(title)
        th.addStretch()
        # 占位平衡
        spacer = QWidget()
        spacer.setFixedWidth(60)
        th.addWidget(spacer)
        v.addLayout(th)

        v.addSpacing(20)

        # 模型选择
        v.addWidget(self._settings_section('模型'))
        self.settings_model = QComboBox()
        for key, m in MODELS.items():
            self.settings_model.addItem(f'{m["label"]} — {m["desc"]}', key)
        self.settings_model.currentIndexChanged.connect(self._on_model_changed)
        v.addWidget(self.settings_model)
        v.addSpacing(16)

        # 工作目录
        v.addWidget(self._settings_section('工作目录'))
        dir_row = QHBoxLayout()
        self.settings_cwd_label = QLabel(DEFAULT_CWD)
        self.settings_cwd_label.setStyleSheet(f'color: {COLORS["text"]}; font-size: 12px; background: {COLORS["bg_input"]}; border: 1px solid {COLORS["border"]}; border-radius: 6px; padding: 8px 12px;')
        self.settings_cwd_label.setWordWrap(True)
        dir_row.addWidget(self.settings_cwd_label, 1)
        browse_btn = QPushButton('选择')
        browse_btn.setProperty('class', 'ghost')
        browse_btn.setFixedSize(56, 34)
        browse_btn.clicked.connect(self._browse_cwd)
        dir_row.addWidget(browse_btn)
        v.addLayout(dir_row)
        v.addSpacing(16)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f'background: {COLORS["border"]};')
        v.addWidget(sep)
        v.addSpacing(16)

        # 信息区
        v.addWidget(self._settings_section('连接信息'))

        self.info_grid = QGridLayout()
        self.info_grid.setSpacing(8)
        self.info_labels = {}
        for i, (key, label) in enumerate([('bot_id', 'Bot ID'), ('claude_ver', 'Claude Code'), ('connect_time', '连接时间')]):
            lbl = QLabel(label)
            lbl.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 12px;')
            val = QLabel('—')
            val.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 12px;')
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.info_grid.addWidget(lbl, i, 0)
            self.info_grid.addWidget(val, i, 1)
            self.info_labels[key] = val
        v.addLayout(self.info_grid)

        v.addStretch()
        return w

    def _settings_section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f'color: {COLORS["text_dim"]}; font-size: 11px; margin-bottom: 6px;')
        return lbl

    # ── 日志面板 ──

    def _build_log_panel(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f'QFrame {{ border-top: 1px solid {COLORS["border"]}; }}')
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(16, 0, 16, 0)

        self.log_toggle_btn = QPushButton('日志')
        self.log_toggle_btn.setProperty('class', 'icon')
        self.log_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']}; color: {COLORS['text_muted']};
                border: none; border-radius: 0; padding: 5px 12px;
                font-size: 12px; text-align: left;
            }}
            QPushButton:hover {{ color: {COLORS['text']}; }}
        """)
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        toggle_row.addWidget(self.log_toggle_btn)

        self.log_badge = QLabel()
        self.log_badge.setFixedSize(18, 18)
        self.log_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_badge.setStyleSheet(f'background: {COLORS["danger"]}; color: white; border-radius: 9px; font-size: 10px; font-weight: bold;')
        self.log_badge.setVisible(False)
        toggle_row.addWidget(self.log_badge)

        toggle_row.addStretch()

        self.log_arrow = QLabel('▲')
        self.log_arrow.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 10px;')
        toggle_row.addWidget(self.log_arrow)

        toggle_frame = QFrame()
        toggle_frame.setStyleSheet(f'QFrame {{ background: {COLORS["bg_card"]}; }}')
        toggle_frame.setFixedHeight(28)
        toggle_frame.setLayout(toggle_row)
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
        footer.setStyleSheet(f'QFrame {{ background: {COLORS["bg_card"]}; border-top: 1px solid {COLORS["border"]}; }}')
        footer.setFixedHeight(42)
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 0, 12, 0)

        hint = QLabel('关闭窗口 → 最小化到托盘')
        hint.setStyleSheet(f'color: {COLORS["text_muted"]}; font-size: 11px;')
        h.addWidget(hint)
        h.addStretch()

        self.btn_stop = QPushButton('停止')
        self.btn_stop.setProperty('class', 'danger')
        self.btn_stop.setFixedSize(56, 28)
        self.btn_stop.clicked.connect(self._stop_bot)
        self.btn_stop.setVisible(False)
        h.addWidget(self.btn_stop)

        self.btn_start = QPushButton('启动')
        self.btn_start.setFixedSize(56, 28)
        self.btn_start.clicked.connect(self._start_bot)
        self.btn_start.setVisible(False)
        h.addWidget(self.btn_start)

        return footer

    # ── 系统托盘（黑C白底）──

    def _build_tray(self):
        self._tray_icon = make_icon('#222222', '#ffffff', 16)
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._tray_icon)
        self.tray.setToolTip('微信 Claude Bot')

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background: {COLORS['bg_card']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; padding: 4px; }}
            QMenu::item {{ padding: 6px 20px; }}
            QMenu::item:selected {{ background: {COLORS['bg_hover']}; }}
        """)
        show_action = menu.addAction('显示主窗口')
        show_action.triggered.connect(self._show_window)
        menu.addSeparator()
        quit_action = menu.addAction('退出')
        quit_action.triggered.connect(self._quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ══════════════════════════════════════════════════════════════════════
    #  信号连接 & 处理
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
        cmap = {'info': COLORS['text_dim'], 'warn': COLORS['warn'], 'error': COLORS['danger']}
        c = cmap.get(level, COLORS['text_dim'])
        self.log_text.append(f'<span style="color:{c}">[{ts}] {message}</span>')

        # 日志红点（折叠时）
        if not self.log_text.isVisible() and level in ('warn', 'error'):
            self._log_unread += 1
            self.log_badge.setText(str(min(self._log_unread, 99)))
            self.log_badge.setVisible(True)

    @pyqtSlot(str, dict)
    def _on_status(self, state: str, data: dict):
        if state in ('init', 'checking-env'):
            self.stack.setCurrentIndex(0)
            self._set_status('warn', '检测中')
            self.step_claude.set_active('检测中...')

        elif state == 'env-ready':
            ver = data.get('version', '')
            self.step_claude.set_done(ver)
            self.step_weixin.set_active('连接中...')
            self._set_status('warn', '等待连接')
            # 更新设置页信息
            self.info_labels['claude_ver'].setText(ver)

        elif state == 'env-error':
            self.stack.setCurrentIndex(1)
            self._set_status('err', '环境异常')
            self.step_claude.set_error('未找到')
            self.btn_stop.setVisible(False)
            self.btn_start.setVisible(False)

        elif state == 'need-login':
            self.stack.setCurrentIndex(2)
            self._set_status('warn', '等待扫码')
            self.qr_step1.set_active()
            self.qr_step2 and None  # reset
            self.qr_refresh_btn.setVisible(False)

        elif state == 'qr-ready':
            self.stack.setCurrentIndex(2)
            self._set_status('warn', '等待扫码')
            self.qr_step1.set_done()
            self.qr_step2.set_active('等待扫码')

        elif state == 'qr-scanned':
            self._set_status('warn', '已扫码')
            self.qr_step2.set_done('已扫码')
            self.qr_step3.set_active('请确认')

        elif state == 'connected':
            # 先在检测页显示完成
            self.step_weixin.set_done('已连接')
            self.step_ready.set_done()
            # 延迟切换到仪表盘（给用户看到"全绿"的感觉）
            QTimer.singleShot(600, lambda: self._enter_running(data))

        elif state in ('disconnected', 'reconnecting'):
            self._set_status('warn', '重连中...')

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
        self.uptime_timer.start(10000)
        self._update_uptime()
        # 设置页信息
        bot_id = data.get('bot_id', '')
        self.info_labels['bot_id'].setText(bot_id[:20] + '...' if len(bot_id) > 20 else bot_id)
        self.info_labels['connect_time'].setText(datetime.now().strftime('%Y-%m-%d %H:%M'))

    @pyqtSlot(str)
    def _on_qr(self, qr_content: str):
        img = qrcode.make(qr_content, image_factory=PilImage, box_size=6, border=2)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        self.qr_label.setPixmap(pixmap.scaled(
            240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    @pyqtSlot(str, str)
    def _on_message_in(self, user_id: str, text: str):
        self.message_count += 1
        self.card_messages.set_value(str(self.message_count))
        users = self.engine.stats.get('active_users', set())
        self.card_users.set_value(str(len(users) if isinstance(users, set) else 0))

        ts = datetime.now().strftime('%H:%M')
        self.msg_list.append(
            f'<p style="margin:2px 0"><span style="color:{COLORS["text_muted"]};font-size:11px">{ts}</span> '
            f'<span style="color:{COLORS["info"]}">▼ 收</span> '
            f'<span style="color:{COLORS["text_dim"]}">{user_id[:8]}</span> '
            f'<span style="color:{COLORS["text"]}">{text[:120]}</span></p>'
        )

        # 通知（窗口隐藏时）
        if not self.isVisible():
            self.tray.showMessage('新消息', f'{user_id[:8]}: {text[:50]}', QSystemTrayIcon.MessageIcon.Information, 3000)

    @pyqtSlot(str, str)
    def _on_message_out(self, user_id: str, text: str):
        ts = datetime.now().strftime('%H:%M')
        self.msg_list.append(
            f'<p style="margin:2px 0"><span style="color:{COLORS["text_muted"]};font-size:11px">{ts}</span> '
            f'<span style="color:{COLORS["accent"]}">▲ 发</span> '
            f'<span style="color:{COLORS["text_dim"]}">{user_id[:8]}</span> '
            f'<span style="color:{COLORS["text"]}">{text[:120]}</span></p>'
        )

    # ══════════════════════════════════════════════════════════════════════
    #  操作
    # ══════════════════════════════════════════════════════════════════════

    def _start_bot(self):
        if self.bot_thread.isRunning():
            return
        # 重置检测步骤
        self.step_claude = self.step_claude  # already built
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
        self.log_arrow.setText('▼' if visible else '▲')
        if visible:
            self._log_unread = 0
            self.log_badge.setVisible(False)

    def _toggle_settings(self):
        if self.stack.currentIndex() == 4:
            self.stack.setCurrentIndex(3)
        else:
            self.stack.setCurrentIndex(4)

    def _show_model_menu(self):
        """点击模型卡片弹出切换菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {COLORS['bg_card']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; padding: 4px; }}
            QMenu::item {{ padding: 8px 24px; }}
            QMenu::item:selected {{ background: {COLORS['accent']}; color: white; }}
        """)
        current = self.engine.default_model
        for key, m in MODELS.items():
            prefix = '● ' if key == current else '  '
            action = menu.addAction(f'{prefix}{m["label"]} — {m["desc"]}')
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self._switch_model(k))
        menu.exec(self.card_model.mapToGlobal(self.card_model.rect().bottomLeft()))

    def _switch_model(self, key: str):
        self.engine.default_model = key
        self.card_model.set_value(MODELS[key]['label'])
        # 同步设置页下拉
        for i in range(self.settings_model.count()):
            if self.settings_model.itemData(i) == key:
                self.settings_model.blockSignals(True)
                self.settings_model.setCurrentIndex(i)
                self.settings_model.blockSignals(False)
                break

    def _on_model_changed(self, index: int):
        key = self.settings_model.itemData(index)
        if key:
            self._switch_model(key)

    def _browse_cwd(self):
        path = QFileDialog.getExistingDirectory(self, '选择工作目录', DEFAULT_CWD)
        if path:
            self.settings_cwd_label.setText(path)
            # 通知引擎（全局默认 CWD 更新）
            from core import config
            config.DEFAULT_CWD = path

    def _update_uptime(self):
        if self.start_time:
            self.card_uptime.set_value(fmt_uptime(time.time() - self.start_time))

    # ══════════════════════════════════════════════════════════════════════
    #  辅助
    # ══════════════════════════════════════════════════════════════════════

    def _set_status(self, dot: str, text: str):
        self._set_dot(dot)
        self.status_text.setText(text)
        self.tray.setToolTip(f'微信 Claude Bot — {text}')

    def _set_dot(self, dot_type: str):
        c = {'off': '#555', 'on': COLORS['accent'], 'warn': COLORS['warn'], 'err': COLORS['danger']}.get(dot_type, '#555')
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
        self.tray.showMessage('微信 Claude Bot', '仍在后台运行，双击托盘图标打开',
                              QSystemTrayIcon.MessageIcon.Information, 2000)
