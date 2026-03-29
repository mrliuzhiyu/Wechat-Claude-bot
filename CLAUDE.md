# CLAUDE.md — 微信 AI 助手

## 项目定位
通过微信远程操控电脑的 AI agent 桌面客户端。
不是聊天机器人——AI 能真正读写文件、执行命令、修改代码。

## 技术栈
- **语言**: Python 3.11+
- **GUI**: PyQt6（极简高级风格，受 Linear/Raycast/Apple 启发）
- **AI 引擎**: 三个适配器（Claude Code CLI / Open Interpreter / 纯 API）
- **微信连接**: iLink Bot API（官方 ClawBot 协议）
- **加密**: AES-128-ECB（媒体文件加解密，cryptography 库）

## 项目结构
```
main.py                # 入口（PyQt6 启动 + 高 DPI + 系统托盘）
core/                  # 核心逻辑
  config.py            # 全局常量（路径、API、模型定义、限制值）
  weixin_api.py        # 微信 iLink Bot API 封装（登录、收发、typing）
  media.py             # 媒体收发（CDN 上传下载 + AES-128-ECB 加解密）
  bot_engine.py        # Bot 引擎（QThread + Qt Signals + 消息路由）
adapters/              # AI 模型适配器
  base.py              # 抽象基类 ModelAdapter + ChatResult 数据类
  claude_code.py       # Claude Code CLI（stream-json 解析 + 会话持久化）
  open_interpreter.py  # Open Interpreter（多模型：GPT-4/Claude/Gemini/Ollama）
  direct_api.py        # 纯 API（Anthropic/OpenAI/DeepSeek，纯对话无电脑操控）
  registry.py          # 适配器注册中心（工厂 + 引擎检测 + 配置持久化）
ui/                    # PyQt6 界面
  main_window.py       # 主窗口（5 个视图 + 8 个自定义组件）
  theme.py             # 极简高级主题（颜色令牌 + QSS 样式表）
docs/                  # 文档
  i18n/                # 9 种语言的 README 翻译
  images/              # 截图和二维码图片
.state/                # 运行时状态（自动生成，不入 Git）
  account.json         # 微信登录凭据
  engine-config.json   # 引擎选择 + API Key
  sessions.json        # 用户会话映射（sessionId 持久化）
  sync-buf.json        # 消息同步缓冲
  media/               # 接收的媒体文件
  outbox/              # 待发送文件
```

## 关键架构
- **线程模型**: BotEngine 在 QThread 中运行，通过 Qt Signals 与 UI 通信（sig_log / sig_status / sig_qr / sig_message_in / sig_message_out / sig_action）
- **并发控制**: ThreadPoolExecutor(3) + 每用户串行锁 + 全局计数器
- **会话隔离**: 每个微信用户独立 session / 工作目录 / 模型选择
- **适配器模式**: ModelAdapter 抽象基类 → chat() 返回 ChatResult(text, written_files, read_media_files)
- **消息管道**: 收到消息 → 命令判断 → AI 处理 → md2wx 转换 → split_msg 拆分 → 发送 → 自动发文件

## 设计系统
**必须**在做任何 UI 改动前读 DESIGN.md。
所有颜色、字体、间距、交互方式都定义在里面。
极简高级风格——浅灰底(#F5F5F7)、白色卡片、微信绿(#07C160)强调。

## 开发规范
- Git commit 消息用中文：`类型：内容`（如 `优化：改进仪表盘`、`修复：token 验证`）
- 新增适配器放 `adapters/` 目录，实现 `ModelAdapter` 基类
- 配置持久化在 `.state/` 目录
- 不引入不必要的依赖
- 凭据文件权限设为 0o600（仅 owner 可读写）

## 斜杠命令
`/new` 重置会话 · `/model` 切换模型 · `/cwd` 切换目录 · `/send` 发文件 · `/help` 帮助 · `/status` 状态

## 启动方式
```bash
pip install -r requirements.txt
python main.py
```
