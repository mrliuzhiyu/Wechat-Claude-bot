# WeChat Claude Code Bot

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="WeChat ClawBot Official Connection" width="280" />
  <img src="../images/wechat-usage.jpg" alt="Actual Usage" width="280" />
</p>

<p align="center">
  <strong>Control your local Claude Code CLI remotely through WeChat — manage your code projects anytime, anywhere</strong>
</p>

<p align="center">
  <a href="../../README.md">中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_RU.md">Русский</a> · <a href="README_ES.md">Español</a> · <a href="README_FR.md">Français</a> · <a href="README_DE.md">Deutsch</a> · <a href="README_PT.md">Português</a> · <a href="README_AR.md">العربية</a>
</p>

<p align="center">
  User sends message in WeChat → Local Claude Code processes → Real-time feedback back to WeChat
</p>

---

## Table of Contents

- [Features](#features)
- [Comparison with Direct OpenClaw](#comparison-with-direct-openclaw)
- [WeChat Connection](#wechat-connection)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Use Cases](#use-cases)
- [Commands](#commands)
- [Project Structure](#project-structure)
- [FAQ](#faq)

---

## Features

### Core Capabilities

- **Remote Control via WeChat** — Control your local Claude Code directly through WeChat messages, no need to open a terminal
- **Works After Closing WeChat** — Based on server-side long polling, messages queue even after closing the WeChat app. Reopen WeChat to see replies — the Bot runs 24/7 non-stop
- **Full Computer Control** — Claude Code can truly operate your computer: read/write any files, execute any terminal commands, search code, install packages, Git operations, and more — not just chat
- **Operate on Real Projects** — Claude Code runs in your local project directory, directly modifying real code files with changes taking effect immediately

### User Experience

- **Real-time Progress** — Live progress updates pushed to WeChat as Claude Code works (e.g., `📖 Reading file: src/app.js`)
- **Typing Indicator** — Shows "typing" status in WeChat while processing, so you know the Bot is working
- **Smart Message Splitting** — Long replies are intelligently split at code block boundaries with sequence numbers
- **Markdown Conversion** — Automatically converts Claude's Markdown output to WeChat-friendly plain text
- **Voice Message Support** — Supports WeChat voice-to-text, send commands by voice
- **Slash Commands** — `/new` to reset conversation, `/status` to check status, `/help` for help

### Stability & Security

- **Multi-user Session Isolation** — Each WeChat user gets an independent session with continuous context
- **Concurrency Control** — Up to 3 concurrent tasks, excess requests are queued without message loss
- **Auto Reconnect** — Automatically re-authenticates on session expiration, token persistence avoids repeated QR scanning
- **Session Cleanup** — Inactive sessions auto-expire after 1 hour, max 100 sessions retained
- **Tiered Timeout Protection** — 2-minute inactivity reminder, 5-minute forced termination to prevent stuck tasks
- **Graceful Shutdown** — Supports Ctrl+C safe exit with automatic child process cleanup
- **Runs Locally** — Code and data never pass through third-party servers, credential files are owner-only readable

---

## Comparison with Direct OpenClaw

WeChat's official OpenClaw (ClawBot) allows direct AI chat in WeChat. This project connects **Claude Code CLI** on top of that, bringing fundamental differences:

| Dimension | Direct OpenClaw | This Project (WeChat Claude Code Bot) |
|-----------|----------------|---------------------------------------|
| **Capabilities** | Text chat only | Full computer control: read/write files, run commands, search code |
| **Token Cost** | Consumes API tokens per conversation, pay-per-use | Uses local Claude Code CLI, included in your subscription — no extra API tokens |
| **Project Access** | Cannot access local files | Directly operates on your real project code, changes take effect immediately |
| **Command Execution** | Not supported | Run any terminal command (npm, git, docker, etc.) |
| **Context** | Chat text only | Entire project directory as context, Claude understands the full codebase |
| **Tool Calls** | None | 10+ built-in tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, etc. |
| **Progress Feedback** | None | Real-time progress updates for every operation |
| **Git Operations** | Not supported | Commit, push, create branches directly |
| **Install Packages** | Not supported | Run `npm install`, `pip install`, etc. |
| **Multi-turn** | Limited context | Independent session management with persistent conversation context |

### In One Sentence

> **Direct OpenClaw** = Chat with AI in WeChat
>
> **This Project** = Remote control an AI programmer in WeChat that can read/write code, run commands, and manage your projects

---

## WeChat Connection

This project is built on WeChat's official **iLink Bot** (ClawBot) protocol, connecting via WeChat QR code scanning:

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="WeChat ClawBot Connection" width="260" />
</p>

<p align="center">
  <img src="../images/wechat-usage.jpg" alt="Actual Usage" width="260" />
</p>

> Left: the official WeChat ClawBot plugin page. Right: actual usage. After starting the Bot, a QR code appears in the terminal — scan it with WeChat to connect. Once connected, the Bot continues running and processing messages even after you close WeChat. Reopen WeChat to see the replies.

---

## How It Works

```
┌──────────┐         ┌──────────────────┐         ┌───────────┐
│  WeChat   │ ─msg──▶│  iLink Bot API   │ ─poll──▶│ Local Bot │
│  (Phone)  │ ◀reply─│ (weixin.qq.com)  │ ◀send── │ (Node.js) │
└──────────┘         └──────────────────┘         └─────┬─────┘
                                                        │
                                                        │ CLI call
                                                        ▼
                                                  ┌───────────┐
                                                  │ Claude Code│
                                                  │  (Local)   │
                                                  └───────────┘
```

1. Bot receives user messages via WeChat iLink Bot API (long polling)
2. Forwards messages to local Claude Code CLI (stream-json mode)
3. Parses Claude Code's tool calls in real-time (read files, write code, run commands), pushing progress updates to WeChat
4. Once complete, formats and sends the final result back to WeChat

---

## Quick Start

### Prerequisites

- **Node.js** >= 18
- **Claude Code CLI** installed globally (`npm install -g @anthropic-ai/claude-code`)
- **WeChat account**

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. Install dependencies
npm install

# 3. (Optional) Configure working directory
cp .env.example .env
# Edit .env to set CLAUDE_CWD to your project path

# 4. Start the Bot
npm start
```

### First Connection

1. A QR code will be displayed in the terminal after startup
2. Open WeChat → Scan the QR code
3. Confirm the connection in WeChat
4. Once you see `✅ Connected!`, the bot is ready
5. Send a message to the Bot in WeChat to start

> After the first login, the token is saved automatically. No need to scan again on next startup (unless the token expires).

---

## Configuration

Configure via `.env` file or environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_CWD` | Working directory for Claude Code | Current directory (`process.cwd()`) |
| `SYSTEM_PROMPT` | Additional system prompt | Empty |

**Example `.env` file:**

```bash
# Specify the project directory for Claude Code
CLAUDE_CWD=/home/user/my-project

# Custom system prompt (optional)
SYSTEM_PROMPT=You are a React development assistant
```

---

## Usage Guide

### Basic Usage

Send natural language messages in WeChat describing what you need. Claude Code will handle it automatically:

```
You: Show me the project structure
Bot: 🤖 Received, processing...
Bot: 🔍 Searching files: **/*
Bot: Here's the project structure:
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### What Claude Code Can Do

Through WeChat messages, you can have Claude Code:

- **Read code** — "Show me the content of src/app.js"
- **Write code** — "Create a date formatting utility in the utils directory"
- **Modify code** — "Change the App component's background color to blue"
- **Run commands** — "Run npm test and show me the results"
- **Search code** — "Find all places that use useState"
- **Install packages** — "Install axios and lodash"
- **Debug issues** — "Why is the build failing? Help me check"
- **Code review** — "Review the recent changes for any issues"
- **Git operations** — "Commit the current changes with message 'fix login bug'"

### Real-time Progress

When Claude Code performs operations, you receive live progress updates:

```
📖 Reading file: src/app.js
✏️ Editing file: src/utils.js
⚡ Running command: npm test
🔍 Searching files: **/*.ts
🔍 Searching content: handleClick
📝 Creating file: src/helper.js
📋 Planning tasks
```

### Long Message Handling

When Claude Code's reply exceeds 4000 characters, messages are intelligently split:

- Prefers splitting at code block boundaries
- Falls back to splitting at blank lines
- Each chunk is labeled with a sequence number, e.g., `(cont. 2/3)`

---

## Use Cases

### Case 1: Fix a Bug During Commute

> A colleague reports an urgent production bug while you're on the subway.

```
You: Show me the login function in src/api/auth.js
Bot: [displays code]

You: The token validation on line 42 is wrong, expiry should use > not >=
Bot: ✏️ Editing file: api/auth.js
Bot: Fixed, changed >= to >

You: Run the tests
Bot: ⚡ Running command: npm test
Bot: All 23 tests passed ✓

You: Commit with message "fix: correct token expiry boundary condition"
Bot: Committed and pushed to remote
```

### Case 2: Develop Features on Mobile

> You're out on the weekend and have a quick feature idea.

```
You: Create a ThemeToggle component in src/components that supports dark/light mode
Bot: 📝 Creating file: components/ThemeToggle.jsx
Bot: ✏️ Editing file: App.jsx
Bot: Created ThemeToggle component and imported it in App.jsx...
```

### Case 3: Code Review and Learning

> You've joined a new project and want to quickly understand the codebase.

```
You: What's the overall architecture of this project?
Bot: [analyzes project structure, main modules, tech stack...]

You: Where is the database connection logic?
Bot: 🔍 Searching content: database|connection|mongoose
Bot: Database connection is in src/config/db.js...
```

### Case 4: DevOps and Monitoring

> You need to check service status while away.

```
You: Check the Docker container status
Bot: ⚡ Running command: docker ps
Bot: [shows container list...]

You: Check recent logs for errors
Bot: ⚡ Running command: docker logs --tail 50 my-app
Bot: [shows logs...]
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help information |
| `/new` | Reset conversation, start a new session |
| `/status` | View Bot status (version, uptime, working directory) |

> All messages except slash commands are sent to Claude Code for processing.

---

## Project Structure

```
Wechat-Claude-bot/
├── index.js          # Main entry: message routing, slash commands, Markdown conversion
├── weixin-api.js     # WeChat iLink Bot API wrapper: login, messaging, typing indicator
├── claude-code.js    # Claude Code CLI interaction: session management, stream parsing, progress callbacks
├── package.json
├── .env.example      # Environment variable example
├── .gitignore
├── docs/             # Multi-language docs and assets
│   ├── images/       # Image assets
│   └── README_*.md   # Translations
└── .state/           # (generated at runtime) Login credentials and sync state
```

---

## FAQ

### Q: "claude command not found" on startup

Make sure Claude Code CLI is installed globally:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify with `claude --version`.

### Q: QR code doesn't display correctly

If your terminal doesn't support Unicode, the QR code may not render properly. The startup log includes a URL — open it in a browser to scan.

### Q: What if the token expires?

The bot automatically detects token expiration and displays a new QR code. No manual action needed.

### Q: Can multiple people use it simultaneously?

Yes. Each WeChat user gets an independent session. Up to 3 concurrent requests are supported; excess requests are queued automatically.

### Q: Request timed out

The default timeout is 5 minutes per request. For complex tasks, break them into smaller steps — e.g., first have Claude explore the project structure, then perform specific operations.

### Q: Does it support images/files?

Currently only text messages and voice messages (with voice-to-text enabled) are supported. Images, videos, and files are not yet supported.

### Q: How secure is it?

- The bot runs locally on your machine — code never passes through third-party servers
- Claude Code runs in `bypassPermissions` mode with full file and command access
- Login credentials are stored locally in `.state/` with owner-only file permissions
- `.env` is in `.gitignore` and won't be committed to Git

> **Warning**: Since Claude Code has full permissions, ensure only trusted people can send messages to the Bot.

---

## License

MIT
