"""微信原生设计风格主题"""

COLORS = {
    'bg': '#EDEDED',
    'card': '#FFFFFF',
    'nav_bg': '#F7F7F7',
    'text': '#1C1C1E',
    'text_secondary': '#808080',
    'text_tertiary': '#B2B2B2',
    'divider': '#E5E5E5',
    'accent': '#07C160',
    'accent_hover': '#06AD56',
    'accent_light': '#E8F8EE',
    'warn': '#FA9D3B',
    'error': '#FA5151',
    'link': '#576B95',
    'shadow': 'rgba(0,0,0,0.06)',
}

STYLESHEET = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Microsoft YaHei UI", "PingFang SC", -apple-system, sans-serif;
    font-size: 14px;
}}
QMainWindow {{
    background-color: {COLORS['bg']};
}}

/* 按钮 */
QPushButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}
QPushButton:pressed {{
    background-color: #058c4a;
}}
QPushButton:disabled {{
    background-color: #C8C8C8;
    color: white;
}}
QPushButton[class="danger-text"] {{
    background: transparent;
    color: {COLORS['error']};
    border: none;
    padding: 6px 12px;
    font-size: 13px;
}}
QPushButton[class="danger-text"]:hover {{
    color: #d43d3d;
}}
QPushButton[class="text"] {{
    background: transparent;
    color: {COLORS['link']};
    border: none;
    padding: 6px 12px;
    font-size: 14px;
}}
QPushButton[class="text"]:hover {{
    color: #3d5580;
}}
QPushButton[class="icon"] {{
    background: transparent;
    border: none;
    padding: 4px;
    font-size: 18px;
    color: {COLORS['text_tertiary']};
}}
QPushButton[class="icon"]:hover {{
    color: {COLORS['text_secondary']};
}}

/* 标签 */
QLabel {{
    background: transparent;
    border: none;
}}

/* 文本框 */
QTextEdit {{
    background-color: #FAFAFA;
    color: {COLORS['text_secondary']};
    border: none;
    border-radius: 0;
    font-family: Consolas, "Courier New", monospace;
    font-size: 11px;
    padding: 10px 16px;
    selection-background-color: {COLORS['accent']};
    selection-color: white;
}}

/* 下拉框 */
QComboBox {{
    background: {COLORS['card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['divider']};
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 14px;
}}
QComboBox:hover {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {COLORS['card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['divider']};
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['text']};
    outline: none;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #D0D0D0;
    border-radius: 2px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: #B0B0B0;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 0;
}}

/* 工具提示 */
QToolTip {{
    background: {COLORS['text']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* 菜单 */
QMenu {{
    background: {COLORS['card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['divider']};
    border-radius: 4px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 8px 24px;
}}
QMenu::item:selected {{
    background: {COLORS['accent_light']};
}}
QMenu::separator {{
    height: 1px;
    background: {COLORS['divider']};
    margin: 4px 0;
}}
"""
