# 微信 Claude Code Bot

<p align="center">
  <img src="docs/images/wechat-clawbot.jpg" alt="微信 ClawBot 官方连接" width="280" />
  <img src="docs/images/wechat-usage.jpg" alt="实际使用效果" width="280" />
</p>

<p align="center">
  <strong>通过微信远程控制本机 Claude Code CLI —— 随时随地用微信操控你的代码项目</strong>
</p>

<p align="center">
  <a href="#微信-claude-code-bot">中文</a> · <a href="docs/i18n/README_EN.md">English</a> · <a href="docs/i18n/README_JA.md">日本語</a> · <a href="docs/i18n/README_KO.md">한국어</a> · <a href="docs/i18n/README_RU.md">Русский</a> · <a href="docs/i18n/README_ES.md">Español</a> · <a href="docs/i18n/README_FR.md">Français</a> · <a href="docs/i18n/README_DE.md">Deutsch</a> · <a href="docs/i18n/README_PT.md">Português</a> · <a href="docs/i18n/README_AR.md">العربية</a>
</p>

<p align="center">
  用户在微信中发消息 → 本机 Claude Code 处理 → 实时反馈回微信
</p>

---

## 目录

- [功能特性](#功能特性)
- [为什么不直接用 OpenClaw？](#为什么不直接用-openclaw)
- [微信连接方式](#微信连接方式)
- [工作原理](#工作原理)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用指南](#使用指南)
- [用户场景](#用户场景)
- [命令列表](#命令列表)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 功能特性

### 核心能力

- **微信远程操控** — 通过微信消息直接操控本机 Claude Code，无需打开电脑终端
- **退出微信也能用** — 基于服务端长轮询，关闭微信 App 后消息仍会排队，重新打开即可收到回复，Bot 7×24 不间断运行
- **完整电脑操作能力** — Claude Code 能真正操作你的电脑：读写任意文件、执行任意终端命令、搜索代码、安装依赖、Git 操作等，不只是聊天
- **直接操作真实项目** — Claude Code 运行在你的本机项目目录中，直接修改真实代码文件，改完即生效

### 交互体验

- **实时进度反馈** — Claude Code 读文件、写代码、执行命令时，实时推送进度到微信（如 `📖 正在读取文件: src/app.js`）
- **Typing 状态指示** — 处理中在微信显示"正在输入"，让你知道 Bot 在工作
- **智能消息拆分** — 长回复自动按代码块边界智能拆分，不会从代码中间截断，分片标注序号
- **Markdown 转换** — 自动将 Claude 的 Markdown 输出转为微信友好的纯文本格式
- **图片/文件/视频支持** — 接收微信发来的图片、文件、视频，自动下载并交给 Claude Code 分析；用 `/send` 发回本机文件
- **语音消息支持** — 支持微信语音转文字，语音发指令也能用
- **斜杠命令** — `/new` 重置对话、`/model` 切换模型、`/send` 发送文件、`/status` 查看状态

### 稳定性与安全

- **多用户会话隔离** — 每个微信用户独立 session，对话上下文连续，互不干扰
- **并发控制** — 最多同时处理 3 个任务，超出自动排队等待，不会丢消息
- **自动重连** — Session 过期自动重新登录，Token 持久化免重复扫码
- **会话过期清理** — 超过 1 小时不活跃的会话自动回收，最多保留 100 个会话
- **分级超时保护** — 2 分钟无响应发送提醒，5 分钟强制结束，防止任务卡死
- **优雅退出** — 支持 Ctrl+C 安全退出，自动清理所有子进程
- **本机运行** — 代码和数据不经过任何第三方服务器，凭据文件权限仅 owner 可读写

---

## 为什么不直接用 OpenClaw？

微信官方的 [OpenClaw](https://github.com/nicepkg/openclaw) 是一个功能丰富的 AI 智能体框架，支持接入多种模型后端并通过 ClawBot 协议连接微信。它是一个完整的平台级方案，适合需要自定义 AI 能力的场景。

但如果你的目标是 **通过微信远程操控本机 Claude Code**，OpenClaw 并不是最优解。以下是两者的核心差异：

### 轻量 vs 重量

| 对比维度 | OpenClaw | 本项目 (WeChat Claude Code Bot) |
|---------|----------|-------------------------------|
| **定位** | 通用 AI 智能体框架，支持多种模型和插件 | 专注一件事：微信连 Claude Code CLI |
| **安装** | 框架本身 + API Key + 模型配置 + 插件系统 + 依赖链 | **3 步**：`git clone` → `npm install` → `npm start` |
| **依赖** | 框架庞大，依赖众多，安装易出问题 | **仅 2 个依赖**（dotenv + qrcode-terminal） |
| **维护** | 框架更新频繁，需跟进升级，版本兼容容易踩坑 | 几乎不需要维护，代码简洁透明 |
| **代码量** | 完整框架，数千文件 | **4 个核心文件**，总计 ~1000 行 |

### Token 成本

这是最关键的区别：

| | OpenClaw | 本项目 |
|-|----------|--------|
| **计费方式** | 每次对话调用 Claude API，按 Token 计费 | 使用本机 Claude Code CLI，走订阅额度 |
| **成本特点** | 长对话、代码分析、多轮交互 Token 消耗大，费用不可控 | **零额外 Token 费用**，已有 Claude Code 订阅即可 |
| **API Key** | 必须配置 | 不需要 |

### Claude Code 的独特能力

本项目之所以选择连接 Claude Code CLI 而非直接调 API，是因为 Claude Code 本身提供了 **API 调用无法替代的能力**：

- **完整电脑操控** — 读写任意文件、执行任意终端命令、搜索整个代码库，不是简单的文字对话
- **项目级上下文** — 整个项目目录都是 Claude Code 的上下文，它能理解完整的代码库结构
- **10+ 内置工具** — Read、Write、Edit、Bash、Glob、Grep、WebSearch 等，工具链完整
- **真正的代码操作** — 直接修改真实文件、执行 Git 操作、安装依赖，改完即生效
- **实时进度反馈** — 每一步操作（读文件、执行命令、编辑代码）都实时推送到微信
- **会话连续** — 独立 session 管理，对话上下文跨多轮保持

这些能力通过 API 调用 + 自行实现工具链也能做到，但 Claude Code CLI 已经是一个打磨好的成熟产品，没必要重复造轮子。

### 一句话总结

> **OpenClaw** = 功能齐全的 AI 框架，适合需要自定义 AI 能力的通用场景，但重、贵、装起来费劲
>
> **本项目** = 4 个文件、零额外成本、专注做一件事：让你在微信里远程操控 Claude Code

### 怎么选

- **想搭建通用 AI 微信机器人**，接入不同模型、自定义插件 → OpenClaw
- **想通过微信远程操控电脑、修改代码、执行命令** → 本项目
- **已经有 Claude Code 订阅**，想零成本获得微信远程控制能力 → 本项目

---

## 微信连接方式

本项目基于微信官方 **iLink Bot** (ClawBot) 协议，通过微信扫码建立连接：

<p align="center">
  <img src="docs/images/wechat-clawbot.jpg" alt="微信 ClawBot 连接方式" width="260" />
</p>

<p align="center">
  <img src="docs/images/wechat-usage.jpg" alt="实际使用效果" width="260" />
</p>

> 左图为微信官方 ClawBot 插件页面，右图为实际使用效果。启动 Bot 后终端显示二维码，用微信扫码即可连接。连接后即使退出微信，Bot 仍持续运行并处理消息，重新打开微信即可看到回复。

---

## 工作原理

```
┌──────────┐         ┌──────────────────┐         ┌───────────┐
│  微信用户  │ ──消息──▶│  iLink Bot API   │ ──轮询──▶│  本机 Bot  │
│  (手机端)  │ ◀─回复── │ (weixin.qq.com)  │ ◀─发送── │  (Node.js) │
└──────────┘         └──────────────────┘         └─────┬─────┘
                                                        │
                                                        │ 调用 CLI
                                                        ▼
                                                  ┌───────────┐
                                                  │ Claude Code│
                                                  │   (本机)    │
                                                  └───────────┘
```

1. Bot 通过微信 iLink Bot API（长轮询）接收用户消息
2. 将消息转发给本机 Claude Code CLI（stream-json 模式）
3. 实时解析 Claude Code 的工具调用（读文件、写代码、执行命令等），推送进度到微信
4. Claude Code 完成后，将最终结果格式化发送回微信

---

## 快速开始

### 前置条件

- **Node.js** >= 18
- **Claude Code CLI** 已全局安装（`npm install -g @anthropic-ai/claude-code`）
- **微信账号**

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. 安装依赖
npm install

# 3. (可选) 配置工作目录
cp .env.example .env
# 编辑 .env 设置 CLAUDE_CWD 为你的项目路径

# 4. 启动 Bot
npm start
```

### 首次连接

1. 启动后终端会显示一个二维码
2. 打开微信 → 扫描二维码
3. 在微信中确认连接
4. 看到 `✅ 连接成功` 后即可使用
5. 在微信中直接发消息给 Bot 即可

> 首次登录后 Token 会自动保存，下次启动无需重复扫码（除非 Token 过期）。

---

## 配置说明

通过 `.env` 文件或环境变量配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CLAUDE_CWD` | Claude Code 的工作目录 | 当前目录 (`process.cwd()`) |
| `SYSTEM_PROMPT` | 附加的系统提示词 | 空 |

**示例 `.env` 文件：**

```bash
# 指定 Claude Code 操作的项目目录
CLAUDE_CWD=/home/user/my-project

# 自定义系统提示词（可选）
SYSTEM_PROMPT=你是一个专注于 React 开发的助手，请用中文回答
```

---

## 使用指南

### 基本用法

在微信中直接用自然语言描述你的需求，Claude Code 会自动执行：

```
你: 看看项目结构
Bot: 🤖 收到，正在处理...
Bot: 🔍 正在搜索文件: **/*
Bot: 项目结构如下：
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### Claude Code 能做什么

通过微信发消息，你可以让 Claude Code：

- **读取代码** — "看看 src/app.js 的内容"
- **编写代码** — "在 utils 目录下创建一个日期格式化函数"
- **修改代码** — "把 App 组件的背景色改成蓝色"
- **执行命令** — "运行 npm test 看看测试结果"
- **搜索代码** — "搜索所有用到 useState 的地方"
- **安装依赖** — "安装 axios 和 lodash"
- **调试问题** — "为什么构建报错了？帮我看看"
- **代码审查** — "审查一下最近的改动有没有问题"
- **Git 操作** — "提交当前的改动，消息写'修复登录bug'"

### 实时进度

Claude Code 执行操作时，你会收到实时进度反馈：

```
📖 正在读取文件: src/app.js
✏️ 正在编辑文件: src/utils.js
⚡ 正在执行命令: npm test
🔍 正在搜索文件: **/*.ts
🔍 正在搜索内容: handleClick
📝 正在创建文件: src/helper.js
📋 正在规划任务
```

### 长消息处理

当 Claude Code 的回复超过 4000 字时，消息会被智能拆分：

- 优先在代码块边界断开
- 其次在空行断开
- 每个分片标注序号，如 `(续 2/3)`

---

## 用户场景

### 场景 1：通勤路上修 Bug

> 同事反馈线上有个紧急 Bug，你正在地铁上。

```
你: 看看 src/api/auth.js 的 login 函数
Bot: [显示代码内容]

你: 第 42 行的 token 校验逻辑有问题，过期时间应该用 > 而不是 >=
Bot: ✏️ 正在编辑文件: api/auth.js
Bot: 已修改，将 >= 改为 >

你: 跑一下测试
Bot: ⚡ 正在执行命令: npm test
Bot: 全部 23 个测试通过 ✓

你: 提交改动，消息写"fix: 修复 token 过期判断边界条件"
Bot: 已提交并推送到远程仓库
```

### 场景 2：手机上开发新功能

> 周末在外面，突然有个灵感想快速加个功能。

```
你: 在 src/components 下创建一个 ThemeToggle 组件，支持深色/浅色模式切换
Bot: 📝 正在创建文件: components/ThemeToggle.jsx
Bot: ✏️ 正在编辑文件: App.jsx
Bot: 已创建 ThemeToggle 组件并在 App.jsx 中引入...
```

### 场景 3：代码审查和学习

> 接手一个新项目，想快速了解代码结构。

```
你: 这个项目的整体架构是什么样的？
Bot: [分析项目结构、主要模块、技术栈...]

你: 数据库连接的逻辑在哪里？
Bot: 🔍 正在搜索内容: database|connection|mongoose
Bot: 数据库连接在 src/config/db.js 中...
```

### 场景 4：运维和监控

> 在外面需要检查服务状态。

```
你: 看看 docker 容器运行状态
Bot: ⚡ 正在执行命令: docker ps
Bot: [显示容器列表...]

你: 看看最近的日志有没有报错
Bot: ⚡ 正在执行命令: docker logs --tail 50 my-app
Bot: [显示日志...]
```

---

## 命令列表

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/new` | 重置对话，开始新会话 |
| `/model` | 切换模型（sonnet / opus / haiku） |
| `/send <路径>` | 发送本机文件到微信（图片、文件等） |
| `/status` | 查看 Bot 状态（版本、运行时间、工作目录） |

> 除斜杠命令外，所有消息都会发送给 Claude Code 处理。

---

## 项目结构

```
Wechat-Claude-bot/
├── index.js          # 主入口：消息路由、斜杠命令、Markdown 转换
├── weixin-api.js     # 微信 iLink Bot API 封装：登录、收发消息、typing
├── claude-code.js    # Claude Code CLI 交互层：会话管理、stream 解析、进度回调
├── media.js          # 媒体收发：CDN 上传下载、AES-128-ECB 加解密
├── package.json
├── .env.example      # 环境变量示例
├── .gitignore
├── docs/             # 文档资源
│   ├── images/       # 图片资源
│   │   ├── wechat-clawbot.jpg  # 微信官方连接方式截图
│   │   └── wechat-usage.jpg    # 实际使用效果截图
│   └── i18n/         # 多语言翻译
│       ├── README_EN.md  # English
│       ├── README_JA.md  # 日本語
│       ├── README_KO.md  # 한국어
│       ├── README_RU.md  # Русский
│       ├── README_ES.md  # Español
│       ├── README_FR.md  # Français
│       ├── README_DE.md  # Deutsch
│       ├── README_PT.md  # Português
│       └── README_AR.md  # العربية
└── .state/           # (运行时生成) 登录凭据和同步状态
```

---

## 常见问题

### Q: 启动时提示"未检测到 claude 命令"

确保已全局安装 Claude Code CLI：

```bash
npm install -g @anthropic-ai/claude-code
```

并确认 `claude --version` 能正常输出。

### Q: 二维码显示异常

终端如果不支持 Unicode 字符，二维码可能无法正常显示。启动日志中会打印二维码的 URL，可以在浏览器中打开扫码。

### Q: Token 过期了怎么办？

Bot 会自动检测 Token 过期并重新显示二维码，无需手动操作。

### Q: 可以同时多人使用吗？

可以。每个微信用户有独立的会话，最多同时处理 3 个并发请求，超出自动排队。

### Q: 消息处理超时了

默认单次请求超时 5 分钟。如果任务太复杂，可以拆分成小步骤，比如先让 Claude 了解项目结构，再执行具体操作。

### Q: 支持发送图片/文件吗？

支持。Bot 能接收微信发来的图片、文件、视频，自动下载到本机并交给 Claude Code 分析。也可以用 `/send <文件路径>` 将本机文件发送回微信。语音消息需微信开启语音转文字。

### Q: 安全性如何？

- Bot 运行在你的本机，代码不经过第三方服务器
- Claude Code 以 `bypassPermissions` 模式运行，拥有完整的文件和命令权限
- 登录凭据保存在本地 `.state/` 目录，文件权限设为仅 owner 可读写
- `.env` 文件已在 `.gitignore` 中，不会被提交到 Git

> **注意**：由于 Claude Code 拥有完整权限，请确保只有你信任的人能向 Bot 发消息。

---

## License

MIT
