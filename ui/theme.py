"""UI 主题"""

COLORS = {
    'bg': '#1a1a2e',
    'bg_card': '#16213e',
    'bg_hover': '#1f3054',
    'bg_input': '#0f1a2e',
    'text': '#e8e8e8',
    'text_dim': '#8892a4',
    'text_muted': '#5a6478',
    'accent': '#07C160',
    'accent_dim': '#059c4d',
    'accent_light': '#0ed66e',
    'danger': '#e74c3c',
    'danger_dim': '#c0392b',
    'border': '#2a2a4a',
    'border_light': '#3a3a5a',
    'warn': '#f0ad4e',
    'info': '#5dade2',
    'log_bg': '#0d1117',
    'success': '#2ecc71',
    'card_shadow': 'rgba(0,0,0,0.3)',
}

STYLESHEET = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background-color: {COLORS['bg']};
}}

/* 按钮 */
QPushButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {COLORS['accent_dim']};
}}
QPushButton:pressed {{
    background-color: {COLORS['accent_light']};
}}
QPushButton:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_muted']};
}}
QPushButton[class="danger"] {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid {COLORS['danger']};
}}
QPushButton[class="danger"]:hover {{
    background-color: {COLORS['danger']};
    color: white;
}}
QPushButton[class="ghost"] {{
    background-color: transparent;
    color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']};
}}
QPushButton[class="ghost"]:hover {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text']};
}}
QPushButton[class="icon"] {{
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 16px;
}}
QPushButton[class="icon"]:hover {{
    background: {COLORS['bg_hover']};
    border-radius: 6px;
}}

/* 标签 */
QLabel {{
    background-color: transparent;
    border: none;
}}

/* 文本框 */
QTextEdit {{
    background-color: {COLORS['log_bg']};
    color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 8px;
    selection-background-color: {COLORS['accent']};
}}

/* 下拉框 */
QComboBox {{
    background: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['accent']};
}}

/* 开关 (QCheckBox) */
QCheckBox {{
    spacing: 8px;
    color: {COLORS['text_dim']};
}}
QCheckBox::indicator {{
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background: {COLORS['border']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['border_light']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 0;
}}

/* 工具提示 */
QToolTip {{
    background: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
"""
