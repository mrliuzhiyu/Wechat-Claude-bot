# Design System — 微信 AI 助手

## Product Context
- **What this is:** 本地桌面客户端，通过微信远程操控电脑的 AI agent
- **Who it's for:** 技术爱好者和普通用户，通过微信远程控制本机 AI 模型
- **Space/industry:** 微信生态 AI 工具
- **Project type:** PyQt6 桌面应用

## Aesthetic Direction
- **Direction:** 极简高级 — 受 Linear / Raycast / Apple 启发，干净、精致、克制
- **Decoration level:** Minimal — 零装饰元素，信息密度优先
- **Mood:** 专业工具感，不是花哨的玩具。打开后感觉像一个精致的本地控制台

## Typography
- **字体栈:** SF Pro Display, SF Pro Text, Segoe UI, Microsoft YaHei UI, -apple-system, sans-serif
- **标题:** 16-18px, weight 600
- **正文:** 14px, weight 400-500
- **辅助文字:** 12-13px, weight 400
- **数据数字:** 28px, weight 700 (统计卡片)
- **日志/代码:** SF Mono, Cascadia Code, Consolas, monospace — 11px
- **按钮:** 14px, weight 500, letter-spacing 0.2px

## Color
- **Approach:** Restrained — 微信绿为唯一强调色，颜色稀缺而珍贵
- **背景:** #F5F5F7（Apple 浅灰）
- **卡片:** #FFFFFF
- **导航栏背景:** #F7F7F7
- **主文字:** #1D1D1F
- **次要文字:** #86868B
- **辅助文字:** #AEAEB2
- **分割线:** #E8E8ED
- **强调色（微信绿）:** #07C160
- **强调色 hover:** #06AD56
- **强调色 pressed:** #058C4A
- **强调色浅底:** #E8F8EE
- **警告:** #FF9F0A
- **错误:** #FF3B30
- **链接蓝:** #576B95
- **阴影:** rgba(0,0,0,0.04)
- **禁用态:** #D1D1D6
- **气泡（收到）:** #FFFFFF
- **气泡（发出）:** #07C160
- **Dark mode:** 不做。保持单一主题，减少维护成本。

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48
- **卡片内边距:** 16px
- **卡片间距:** 12px (垂直) / 8px (紧凑)
- **卡片圆角:** 8px
- **按钮圆角:** 8px
- **下拉框圆角:** 8px
- **菜单圆角:** 8px
- **工具提示圆角:** 6px

## Layout
- **Approach:** 卡片式布局，白卡浮在浅灰背景上
- **阴影:** box-shadow: 0 1px 3px rgba(0,0,0,0.04) — 极淡
- **分割线:** 1px solid #E8E8ED，在卡片内部分割项目
- **设置列表:** cell 风格（标签 + 值 + 箭头 ›）
- **滚动条:** 6px 宽，圆角 3px，hover 变深（#D1D1D6 → #AEAEB2）

## Motion
- **Approach:** Minimal-functional
- **原则:** 几乎没有动画。只有视图切换的即时反馈。
- **唯一动效:** 启动检测完成后延迟 600ms 切换到操作视图（让用户看到"全绿"）

## Component Patterns
- **按钮:** 微信绿实心（主操作）、文字按钮（次操作，链接蓝）、红色文字（危险操作）、透明图标按钮
- **警告条:** 左侧 3px 色条 + 白底，标题 + 描述
- **状态点:** 7px 圆形（绿=运行、黄=等待、红=错误、灰=离线）
- **气泡:** 圆角矩形，左侧收到（白底），右侧发出（绿底白字）
- **托盘图标:** 黑色 C + 白色背景，16x16
- **窗口图标:** 黑色 C + 白色背景，64x64
- **工具提示:** 深色底（#1D1D1F）+ 白字，圆角 6px

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | 微信原生设计方向 | 产品是用户的 AI 通道，应感觉是微信的自然延伸 |
| 2026-03-28 | 浅色主题，不做 dark mode | 与微信桌面端保持一致 |
| 2026-03-28 | 系统字体，不加载外部字体 | 微信从不用花哨字体，保持轻量 |
| 2026-03-28 | 从暗色工业风切换到微信风格 | 用户明确要求严格对齐微信设计语言 |
| 2026-03-29 | 主题升级为极简高级风格 | 受 Linear/Raycast/Apple 启发，背景 #F5F5F7，圆角 8px，SF Pro 字体栈 |
| 2026-03-29 | 仪表盘从统计面板改为操作视图 | CEO review 结论：用户需要看到 AI 在做什么，不是消息统计 |
| 2026-03-29 | 清理全部 JS 旧代码 | 项目完全迁移到 Python，-4400 行 |
