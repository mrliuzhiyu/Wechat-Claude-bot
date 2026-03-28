# Design System — 微信 Claude Bot

## Product Context
- **What this is:** 本地桌面客户端，用户的超级 AI 助手入口
- **Who it's for:** 技术爱好者和普通用户，通过微信远程控制本机 AI 模型
- **Space/industry:** 微信生态 AI 工具
- **Project type:** PyQt6 桌面应用

## Aesthetic Direction
- **Direction:** 微信原生 — 平静、可信赖、用户熟悉的视觉语言
- **Decoration level:** Minimal — 零装饰元素，微信的克制
- **Mood:** 像微信的自然延伸，不是独立的开发者工具。用户打开后感觉"这就是微信的一部分"

## Typography
- **所有文字:** Microsoft YaHei UI / PingFang SC / system — 不加载任何外部字体
- **标题:** 16-18px, weight 600
- **正文:** 14px, weight 400
- **辅助文字:** 12px, weight 400
- **数据数字:** 28px, weight 700 (统计卡片)
- **日志:** Consolas / Courier New (等宽)，11px

## Color
- **Approach:** Restrained — 微信绿为唯一强调色，颜色稀缺而珍贵
- **背景:** #EDEDED
- **卡片:** #FFFFFF
- **主文字:** #1C1C1E
- **次要文字:** #808080
- **辅助文字:** #B2B2B2
- **分割线:** #E5E5E5
- **导航栏背景:** #F7F7F7
- **强调色（微信绿）:** #07C160
- **强调色 hover:** #06AD56
- **强调色浅底:** #E8F8EE
- **警告:** #FA9D3B
- **错误:** #FA5151
- **链接蓝:** #576B95
- **Dark mode:** 不做。微信桌面端也没有 dark mode。保持一致。

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48
- **卡片内边距:** 16px
- **卡片间距:** 12px (垂直) / 8px (紧凑)
- **卡片圆角:** 8px

## Layout
- **Approach:** 微信式卡片布局
- **结构:** 白色卡片浮在浅灰背景上，用 box-shadow: 0 1px 3px rgba(0,0,0,0.06)
- **分割线:** 1px solid #E5E5E5，在卡片内部分割项目
- **设置列表:** 微信 cell 风格（标签 + 值 + 箭头 ›）
- **统计网格:** 2x2 网格，用分割线而不是独立卡片

## Motion
- **Approach:** Minimal-functional
- **原则:** 微信几乎没有动画。只有视图切换的即时反馈。
- **唯一动效:** 启动检测完成后延迟 600ms 切换到仪表盘（让用户看到"全绿"）

## Component Patterns
- **按钮:** 微信绿实心（主操作）、文字按钮（次操作）、红色文字（危险操作）
- **警告条:** 左侧 3px 色条 + 白底，标题 + 描述
- **状态点:** 7px 圆形（绿=运行、黄=等待、红=错误、灰=离线）
- **托盘图标:** 黑色 C + 白色背景，16x16
- **窗口图标:** 黑色 C + 白色背景，64x64

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | 微信原生设计方向 | 产品是用户的 AI 通道，应感觉是微信的自然延伸 |
| 2026-03-28 | 浅色主题，不做 dark mode | 与微信桌面端保持一致 |
| 2026-03-28 | 系统字体，不加载外部字体 | 微信从不用花哨字体，保持轻量 |
| 2026-03-28 | 从暗色工业风切换到微信风格 | 用户明确要求严格对齐微信设计语言 |
