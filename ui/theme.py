"""极简高级主题 — 受 Linear / Raycast / Apple 启发"""

COLORS = {
    'bg': '#F5F5F7',
    'card': '#FFFFFF',
    'nav_bg': '#F7F7F7',
    'text': '#1D1D1F',
    'text_secondary': '#86868B',
    'text_tertiary': '#AEAEB2',
    'divider': '#E8E8ED',
    'accent': '#07C160',
    'accent_hover': '#06AD56',
    'accent_light': '#E8F8EE',
    'warn': '#FF9F0A',
    'error': '#FF3B30',
    'link': '#576B95',
    'shadow': 'rgba(0,0,0,0.04)',
    'bubble_in': '#FFFFFF',
    'bubble_out': '#07C160',
}

STYLESHEET = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "SF Pro Display", "SF Pro Text", "Segoe UI", "Microsoft YaHei UI", -apple-system, sans-serif;
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
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.2px;
}}
QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}
QPushButton:pressed {{
    background-color: #058c4a;
}}
QPushButton:disabled {{
    background-color: #D1D1D6;
    color: white;
}}
QPushButton[class="danger-text"] {{
    background: transparent;
    color: {COLORS['error']};
    border: none;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
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
    font-weight: 500;
}}
QPushButton[class="text"]:hover {{
    color: {COLORS['accent']};
}}
QPushButton[class="icon"] {{
    background: transparent;
    border: none;
    padding: 4px;
    font-size: 16px;
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
    background-color: {COLORS['bg']};
    color: {COLORS['text_secondary']};
    border: none;
    border-radius: 0;
    font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
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
    border-radius: 8px;
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
    border-radius: 8px;
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['text']};
    outline: none;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #D1D1D6;
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEAEB2;
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
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* 菜单 */
QMenu {{
    background: {COLORS['card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['divider']};
    border-radius: 8px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    background: {COLORS['accent_light']};
}}
QMenu::separator {{
    height: 1px;
    background: {COLORS['divider']};
    margin: 4px 8px;
}}
"""
