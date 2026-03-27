# WeChat Claude Code Bot

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="WeChat ClawBot 공식 연결" width="280" />
  <img src="../images/wechat-usage.jpg" alt="실제 사용 화면" width="280" />
</p>

<p align="center">
  <strong>WeChat으로 로컬 Claude Code CLI를 원격 제어 — 언제 어디서나 스마트폰으로 코드 프로젝트를 관리</strong>
</p>

<p align="center">
  <a href="../../README.md">中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_RU.md">Русский</a> · <a href="README_ES.md">Español</a> · <a href="README_FR.md">Français</a> · <a href="README_DE.md">Deutsch</a> · <a href="README_PT.md">Português</a> · <a href="README_AR.md">العربية</a>
</p>

<p align="center">
  사용자가 WeChat에서 메시지 전송 → 로컬 Claude Code가 처리 → 실시간으로 WeChat에 피드백
</p>

---

## 목차

- [기능](#기능)
- [OpenClaw 직접 연결과의 비교](#openclaw-직접-연결과의-비교)
- [WeChat 연결 방법](#wechat-연결-방법)
- [작동 원리](#작동-원리)
- [빠른 시작](#빠른-시작)
- [설정](#설정)
- [사용 가이드](#사용-가이드)
- [사용 시나리오](#사용-시나리오)
- [명령어 목록](#명령어-목록)
- [프로젝트 구조](#프로젝트-구조)
- [자주 묻는 질문](#자주-묻는-질문)

---

## 기능

### 핵심 기능

- **WeChat 원격 제어** — WeChat 메시지로 로컬 Claude Code를 직접 제어, PC 터미널을 열 필요 없음
- **WeChat 종료 후에도 작동** — 서버 측 롱 폴링 기반으로, WeChat 앱을 닫아도 메시지가 대기열에 저장됩니다. 다시 열면 응답을 확인할 수 있으며, Bot은 24시간 중단 없이 실행
- **완전한 컴퓨터 제어** — Claude Code는 컴퓨터를 실제로 조작 가능: 파일 읽기/쓰기, 터미널 명령 실행, 코드 검색, 패키지 설치, Git 작업 등 — 단순한 채팅이 아닙니다
- **실제 프로젝트 직접 조작** — Claude Code가 로컬 프로젝트 디렉토리에서 실행되어 실제 코드 파일을 직접 수정, 변경 즉시 반영

### 사용자 경험

- **실시간 진행 상황** — Claude Code 작업 중 WeChat에 실시간 진행 알림 (예: `📖 파일 읽기 중: src/app.js`)
- **타이핑 표시** — 처리 중 WeChat에서 "입력 중" 표시
- **스마트 메시지 분할** — 긴 응답은 코드 블록 경계에서 자동 분할, 순서 번호 표시
- **Markdown 변환** — Markdown 출력을 WeChat 친화적 텍스트로 자동 변환
- **이미지/파일/동영상 지원** — WeChat에서 보낸 이미지, 파일, 동영상 수신, 자동 다운로드 후 Claude Code 분석; `/send`로 로컬 파일 전송
- **음성 메시지 지원** — WeChat 음성-텍스트 변환 지원, 음성으로도 명령 전송 가능
- **슬래시 명령** — `/new` 대화 초기화, `/model` 모델 전환, `/send` 파일 전송, `/status` 상태 확인

### 안정성 및 보안

- **다중 사용자 세션 격리** — 각 사용자 독립 세션, 대화 컨텍스트 지속
- **동시성 제어** — 최대 3개 작업 동시 처리, 초과분은 자동 대기열, 메시지 손실 없음
- **자동 재연결** — 세션 만료 시 자동 재로그인, 토큰 영구 저장
- **세션 만료 정리** — 1시간 비활성 세션 자동 회수, 최대 100개 세션 유지
- **단계적 타임아웃 보호** — 2분 무응답 시 알림, 5분 시 강제 종료로 작업 중단 방지
- **정상 종료** — Ctrl+C 안전 종료, 자식 프로세스 자동 정리
- **로컬 실행** — 코드와 데이터는 제3자 서버를 거치지 않음, 자격 증명 파일은 소유자만 읽기/쓰기 가능

---

## OpenClaw 직접 연결과의 비교

WeChat 공식 OpenClaw(ClawBot)는 WeChat에서 AI와 직접 대화할 수 있습니다. 본 프로젝트는 그 위에 **Claude Code CLI**를 연결하여 본질적인 차이를 만듭니다:

| 비교 항목 | OpenClaw 직접 연결 | 본 프로젝트 (WeChat Claude Code Bot) |
|----------|-------------------|-------------------------------------|
| **기능 범위** | 텍스트 채팅만 가능 | 컴퓨터 완전 제어: 파일 읽기/쓰기, 명령 실행, 코드 검색 |
| **토큰 비용** | 대화마다 API 토큰 소비, 사용량 과금 | 로컬 Claude Code CLI 사용, 구독에 포함되어 추가 토큰 불필요 |
| **프로젝트 접근** | 로컬 파일 접근 불가 | 실제 프로젝트 코드 직접 조작, 변경 즉시 반영 |
| **명령 실행** | 미지원 | 모든 터미널 명령 실행 가능 (npm, git, docker 등) |
| **컨텍스트** | 채팅 텍스트만 | 전체 프로젝트 디렉토리가 컨텍스트, Claude가 전체 코드베이스 이해 |
| **도구 호출** | 없음 | 10개 이상 내장 도구: Read, Write, Edit, Bash, Glob, Grep, WebSearch 등 |
| **진행 피드백** | 없음 | 모든 작업의 실시간 진행 알림 |
| **Git 작업** | 미지원 | commit, push, 브랜치 생성 직접 실행 |
| **패키지 설치** | 미지원 | `npm install`, `pip install` 등 실행 가능 |
| **다중 턴** | 제한된 컨텍스트 | 독립 세션 관리, 대화 컨텍스트 영구 유지 |

### 한마디로

> **OpenClaw 직접 연결** = WeChat에서 AI와 채팅
>
> **본 프로젝트** = WeChat에서 코드를 읽고 쓰고, 명령을 실행하고, 프로젝트를 관리하는 AI 프로그래머를 원격 제어

---

## WeChat 연결 방법

이 프로젝트는 WeChat 공식 **iLink Bot** (ClawBot) 프로토콜을 기반으로 하며, WeChat QR 코드 스캔으로 연결을 설정합니다:

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="WeChat ClawBot 연결 방법" width="260" />
</p>

<p align="center">
  <img src="../images/wechat-usage.jpg" alt="실제 사용 화면" width="260" />
</p>

> 왼쪽: WeChat 공식 ClawBot 플러그인 페이지. 오른쪽: 실제 사용 화면. Bot 시작 후 터미널에 QR 코드가 표시되며, WeChat으로 스캔하면 연결됩니다. 연결 후 WeChat을 닫아도 Bot은 계속 실행되며 메시지를 처리합니다. WeChat을 다시 열면 응답을 확인할 수 있습니다.

---

## 작동 원리

```
┌──────────┐         ┌──────────────────┐         ┌───────────┐
│  WeChat   │ ─메시지─▶│  iLink Bot API   │ ─폴링──▶│ 로컬 Bot  │
│  (스마트폰) │ ◀─응답── │ (weixin.qq.com)  │ ◀─전송── │ (Node.js) │
└──────────┘         └──────────────────┘         └─────┬─────┘
                                                        │
                                                        │ CLI 호출
                                                        ▼
                                                  ┌───────────┐
                                                  │ Claude Code│
                                                  │  (로컬)    │
                                                  └───────────┘
```

1. Bot이 WeChat iLink Bot API(롱 폴링)를 통해 사용자 메시지 수신
2. 메시지를 로컬 Claude Code CLI(stream-json 모드)로 전달
3. Claude Code의 도구 호출(파일 읽기, 코드 작성, 명령 실행 등)을 실시간 분석하여 진행 상황을 WeChat에 전송
4. Claude Code 완료 후, 최종 결과를 포맷하여 WeChat으로 전송

---

## 빠른 시작

### 사전 요구 사항

- **Node.js** >= 18
- **Claude Code CLI** 전역 설치 (`npm install -g @anthropic-ai/claude-code`)
- **WeChat 계정**

### 설치 단계

```bash
# 1. 리포지토리 클론
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. 의존성 설치
npm install

# 3. (선택사항) 작업 디렉토리 설정
cp .env.example .env
# .env를 편집하여 CLAUDE_CWD를 프로젝트 경로로 설정

# 4. Bot 시작
npm start
```

### 첫 연결

1. 시작 후 터미널에 QR 코드가 표시됨
2. WeChat 열기 → QR 코드 스캔
3. WeChat에서 연결 확인
4. `✅ 연결 성공`이 표시되면 사용 가능
5. WeChat에서 Bot에게 메시지를 보내면 됨

> 첫 로그인 후 토큰이 자동 저장됩니다. 다음 시작 시 재스캔 불필요 (토큰 만료 제외).

---

## 설정

`.env` 파일 또는 환경 변수로 설정:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `CLAUDE_CWD` | Claude Code의 작업 디렉토리 | 현재 디렉토리 (`process.cwd()`) |
| `SYSTEM_PROMPT` | 추가 시스템 프롬프트 | 비어 있음 |

**`.env` 파일 예시:**

```bash
# Claude Code가 작업할 프로젝트 디렉토리 지정
CLAUDE_CWD=/home/user/my-project

# 커스텀 시스템 프롬프트 (선택사항)
SYSTEM_PROMPT=당신은 React 개발에 특화된 어시스턴트입니다
```

---

## 사용 가이드

### 기본 사용법

WeChat에서 자연어로 필요한 사항을 설명하면 Claude Code가 자동으로 실행합니다:

```
당신: 프로젝트 구조를 보여줘
Bot: 🤖 수신 완료, 처리 중...
Bot: 🔍 파일 검색 중: **/*
Bot: 프로젝트 구조:
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### Claude Code가 할 수 있는 것

WeChat 메시지를 통해 Claude Code에게:

- **코드 읽기** — "src/app.js 내용을 보여줘"
- **코드 작성** — "utils 디렉토리에 날짜 포맷 함수를 만들어줘"
- **코드 수정** — "App 컴포넌트의 배경색을 파란색으로 변경해줘"
- **명령 실행** — "npm test를 실행하고 결과를 보여줘"
- **코드 검색** — "useState를 사용하는 모든 곳을 찾아줘"
- **패키지 설치** — "axios와 lodash를 설치해줘"
- **디버깅** — "왜 빌드가 실패하는지 확인해줘"
- **코드 리뷰** — "최근 변경 사항에 문제가 없는지 리뷰해줘"
- **Git 작업** — "현재 변경 사항을 '로그인 버그 수정' 메시지로 커밋해줘"

### 실시간 진행 상황

Claude Code가 작업을 수행할 때 실시간 진행 피드백을 받습니다:

```
📖 파일 읽기 중: src/app.js
✏️ 파일 편집 중: src/utils.js
⚡ 명령 실행 중: npm test
🔍 파일 검색 중: **/*.ts
🔍 콘텐츠 검색 중: handleClick
📝 파일 생성 중: src/helper.js
📋 작업 계획 중
```

### 긴 메시지 처리

Claude Code의 응답이 4000자를 초과하면 메시지가 스마트하게 분할됩니다:

- 코드 블록 경계에서 분할 우선
- 빈 줄에서 분할 차선
- 각 청크에 순서 번호 표시, 예: `(계속 2/3)`

---

## 사용 시나리오

### 시나리오 1: 출퇴근 중 버그 수정

> 동료가 프로덕션 긴급 버그를 보고, 당신은 지하철 안.

```
당신: src/api/auth.js의 login 함수를 보여줘
Bot: [코드 표시]

당신: 42줄의 토큰 검증 로직에 문제가 있어, 만료는 > 여야 해, >= 가 아니라
Bot: ✏️ 파일 편집 중: api/auth.js
Bot: 수정 완료, >= 를 > 로 변경

당신: 테스트를 실행해
Bot: ⚡ 명령 실행 중: npm test
Bot: 전체 23개 테스트 통과 ✓

당신: "fix: 토큰 만료 판정 경계 조건 수정" 으로 커밋해
Bot: 커밋하고 원격에 푸시 완료
```

### 시나리오 2: 모바일에서 새 기능 개발

> 주말 외출 중, 갑자기 아이디어가 떠올라 빠르게 기능을 추가하고 싶음.

```
당신: src/components에 다크/라이트 모드 전환 ThemeToggle 컴포넌트를 만들어줘
Bot: 📝 파일 생성 중: components/ThemeToggle.jsx
Bot: ✏️ 파일 편집 중: App.jsx
Bot: ThemeToggle 컴포넌트를 생성하고 App.jsx에 임포트 완료...
```

### 시나리오 3: 코드 리뷰 및 학습

> 새 프로젝트에 합류, 코드 구조를 빠르게 이해하고 싶음.

```
당신: 이 프로젝트의 전체 아키텍처는 어떻게 되어 있어?
Bot: [프로젝트 구조, 주요 모듈, 기술 스택 분석...]

당신: 데이터베이스 연결 로직은 어디에 있어?
Bot: 🔍 콘텐츠 검색 중: database|connection|mongoose
Bot: 데이터베이스 연결은 src/config/db.js에 있습니다...
```

### 시나리오 4: DevOps 및 모니터링

> 외출 중 서비스 상태를 확인해야 함.

```
당신: Docker 컨테이너 실행 상태를 확인해
Bot: ⚡ 명령 실행 중: docker ps
Bot: [컨테이너 목록 표시...]

당신: 최근 로그에 에러가 있는지 확인해
Bot: ⚡ 명령 실행 중: docker logs --tail 50 my-app
Bot: [로그 표시...]
```

---

## 명령어 목록

| 명령어 | 설명 |
|--------|------|
| `/help` | 도움말 정보 표시 |
| `/new` | 대화 초기화, 새 세션 시작 |
| `/model` | 모델 전환 (sonnet / opus / haiku) |
| `/send <경로>` | 로컬 파일을 WeChat으로 전송 (이미지, 파일 등) |
| `/status` | Bot 상태 보기 (버전, 가동 시간, 작업 디렉토리) |

> 슬래시 명령어를 제외한 모든 메시지는 Claude Code로 전송되어 처리됩니다.

---

## 프로젝트 구조

```
Wechat-Claude-bot/
├── index.js          # 메인 엔트리: 메시지 라우팅, 슬래시 명령, Markdown 변환
├── weixin-api.js     # WeChat iLink Bot API 래퍼: 로그인, 메시지 송수신, 타이핑 표시
├── claude-code.js    # Claude Code CLI 상호작용: 세션 관리, 스트림 파싱, 진행 콜백
├── media.js          # 미디어 송수신: CDN 업로드/다운로드, AES-128-ECB 암호화
├── package.json
├── .env.example      # 환경 변수 예시
├── .gitignore
├── docs/             # 다국어 문서 및 리소스
│   ├── images/       # 이미지 리소스
│   └── README_*.md   # 번역본
└── .state/           # (실행 시 생성) 로그인 자격 증명 및 동기화 상태
```

---

## 자주 묻는 질문

### Q: 시작 시 "claude 명령을 찾을 수 없습니다"

Claude Code CLI가 전역 설치되어 있는지 확인:

```bash
npm install -g @anthropic-ai/claude-code
```

`claude --version`으로 확인하세요.

### Q: QR 코드가 제대로 표시되지 않음

터미널이 유니코드를 지원하지 않으면 QR 코드가 제대로 표시되지 않을 수 있습니다. 시작 로그에 URL이 포함되어 있으니 브라우저에서 열어 스캔하세요.

### Q: 토큰이 만료되면?

Bot이 자동으로 토큰 만료를 감지하고 새 QR 코드를 표시합니다. 수동 작업이 필요 없습니다.

### Q: 여러 명이 동시에 사용할 수 있나요?

네. 각 WeChat 사용자는 독립 세션을 가집니다. 최대 3개의 동시 요청을 지원하며, 초과분은 자동으로 대기열에 들어갑니다.

### Q: 요청이 타임아웃됨

기본 타임아웃은 요청당 5분입니다. 복잡한 작업의 경우 작은 단계로 나누세요. 예: 먼저 Claude에게 프로젝트 구조를 탐색하게 한 후 구체적인 작업을 실행.

### Q: 이미지/파일 전송을 지원하나요?

네. Bot은 WeChat에서 보낸 이미지, 파일, 동영상을 수신하여 자동으로 로컬에 다운로드하고 Claude Code에 분석을 맡깁니다. `/send <파일경로>`로 로컬 파일을 WeChat으로 보낼 수도 있습니다. 음성 메시지는 WeChat의 음성-텍스트 변환 기능이 필요합니다.

### Q: 보안은 어떤가요?

- Bot은 로컬 머신에서 실행되며, 코드는 제3자 서버를 거치지 않습니다
- Claude Code는 `bypassPermissions` 모드로 실행되어 완전한 파일 및 명령 접근 권한을 가집니다
- 로그인 자격 증명은 로컬 `.state/`에 소유자만 읽기/쓰기 가능한 권한으로 저장됩니다
- `.env`는 `.gitignore`에 포함되어 Git에 커밋되지 않습니다

> **주의**: Claude Code는 완전한 권한을 가지므로, 신뢰할 수 있는 사람만 Bot에 메시지를 보낼 수 있도록 하세요.

---

## License

MIT
