# CLAUDE.md — 微信 AI 助手

## 项目定位
通过微信远程操控电脑的 AI agent 桌面客户端。
不是聊天机器人——AI 能真正读写文件、执行命令、修改代码。

## 技术栈
- **语言**: Python 3.11+
- **GUI**: PyQt6（微信原生设计风格）
- **AI 引擎**: 三个适配器（Claude Code CLI / Open Interpreter / 纯 API）
- **微信连接**: iLink Bot API（官方 ClawBot 协议）

## 项目结构
```
main.py              # 入口
core/                # 核心逻辑
  config.py          # 全局配置
  weixin_api.py      # 微信 API 封装
  media.py           # 媒体收发（AES-128-ECB）
  bot_engine.py      # Bot 引擎（QThread + Qt Signals）
adapters/            # AI 模型适配器
  base.py            # 抽象基类 ModelAdapter
  claude_code.py     # Claude Code CLI
  open_interpreter.py # Open Interpreter（多模型）
  direct_api.py      # 纯 API（Anthropic/OpenAI/DeepSeek）
  registry.py        # 适配器注册中心
ui/                  # PyQt6 界面
  main_window.py     # 主窗口
  theme.py           # 微信风格主题
```

## 设计系统
**必须**在做任何 UI 改动前读 DESIGN.md。
所有颜色、字体、间距、交互方式都定义在里面。
微信原生设计风格——浅灰底(#EDEDED)、白色卡片、微信绿(#07C160)强调。

## 开发规范
- Git commit 消息用中文：`类型：内容`（如 `优化：改进仪表盘`、`修复：token 验证`）
- 新增适配器放 `adapters/` 目录，实现 `ModelAdapter` 基类
- 配置持久化在 `.state/` 目录
- 不引入不必要的依赖

## 启动方式
```bash
python main.py
```
