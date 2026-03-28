# WeChat Claude Code Bot

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="Conexão oficial WeChat ClawBot" width="280" />
  <img src="../images/wechat-usage.jpg" alt="Uso real" width="280" />
</p>

<p align="center">
  <strong>Controle seu Claude Code CLI local remotamente pelo WeChat — gerencie seus projetos de código a qualquer hora, em qualquer lugar</strong>
</p>

<p align="center">
  <a href="../../README.md">中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_RU.md">Русский</a> · <a href="README_ES.md">Español</a> · <a href="README_FR.md">Français</a> · <a href="README_DE.md">Deutsch</a> · <a href="README_PT.md">Português</a> · <a href="README_AR.md">العربية</a>
</p>

<p align="center">
  Usuário envia mensagem no WeChat → Claude Code local processa → Feedback em tempo real no WeChat
</p>

---

## Índice

- [Funcionalidades](#funcionalidades)
- [Comparação com OpenClaw direto](#comparação-com-openclaw-direto)
- [Conexão WeChat](#conexão-wechat)
- [Como funciona](#como-funciona)
- [Início rápido](#início-rápido)
- [Configuração](#configuração)
- [Guia de uso](#guia-de-uso)
- [Casos de uso](#casos-de-uso)
- [Lista de comandos](#lista-de-comandos)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Perguntas frequentes](#perguntas-frequentes)

---

## Funcionalidades

### Capacidades principais

- **Controle remoto via WeChat** — Controle seu Claude Code local diretamente por mensagens do WeChat, sem precisar abrir um terminal
- **Funciona após fechar o WeChat** — Baseado em long polling do servidor, as mensagens ficam na fila mesmo após fechar o app do WeChat. Reabra o WeChat para ver as respostas — o Bot funciona 24/7 sem parar
- **Controle total do computador** — Claude Code pode operar seu computador de verdade: ler/escrever arquivos, executar comandos, buscar código, instalar pacotes, operações Git — não é apenas chat
- **Opera em projetos reais** — Claude Code roda no diretório do seu projeto local, modifica arquivos de código reais com efeito imediato

### Experiência do usuário

- **Progresso em tempo real** — Atualizações ao vivo no WeChat enquanto Claude Code trabalha (ex: `📖 Lendo arquivo: src/app.js`)
- **Indicador de digitação** — Mostra status "digitando" no WeChat durante processamento
- **Divisão inteligente** — Respostas longas divididas nos limites de blocos de código com numeração
- **Conversão Markdown** — Conversão automática de Markdown para texto compatível com WeChat
- **Imagens/arquivos/vídeos** — Recebe imagens, arquivos e vídeos do WeChat, download automático e análise pelo Claude Code; `/send` para enviar arquivos locais
- **Mensagens de voz** — Suporte a voz-para-texto do WeChat, envie comandos por voz
- **Comandos slash** — `/new` reiniciar, `/model` trocar modelo, `/send` enviar arquivo, `/status` estado

### Estabilidade e segurança

- **Isolamento de sessões** — Cada usuário tem sessão independente com contexto contínuo
- **Controle de concorrência** — Até 3 tarefas simultâneas, excedentes em fila sem perda
- **Reconexão automática** — Reautenticação automática quando sessão expira
- **Limpeza de sessões** — Sessões inativas limpas após 1h, máximo 100 sessões
- **Proteção de timeout escalonada** — Lembrete em 2 min, encerramento forçado em 5 min
- **Encerramento gracioso** — Ctrl+C com limpeza automática de processos filhos
- **Execução local** — Código e dados nunca passam por servidores de terceiros

---

## Por que não usar o OpenClaw diretamente?

O [OpenClaw](https://github.com/nicepkg/openclaw) oficial do WeChat é um framework completo de agentes IA com suporte a múltiplos modelos e plugins. Solução de nível plataforma para cenários que precisam de capacidades IA personalizáveis.

Mas se o objetivo é **controlar o Claude Code local pelo WeChat**, o OpenClaw não é a escolha ideal:

### Leve vs pesado

| Dimensão | OpenClaw | Este projeto |
|----------|----------|--------------|
| **Propósito** | Framework IA universal, múltiplos modelos e plugins | Uma coisa: conectar WeChat ao Claude Code CLI |
| **Instalação** | Framework + API Key + config + plugins + dependências | **3 passos**: `git clone` → `npm install` → `npm start` |
| **Dependências** | Framework massivo, muitas dependências | **Apenas 2** (dotenv + qrcode-terminal) |
| **Manutenção** | Atualizações frequentes, problemas de compatibilidade | Quase zero, código simples e transparente |
| **Código** | Milhares de arquivos | **4 arquivos core**, ~1000 linhas |

### Custo de tokens

| | OpenClaw | Este projeto |
|-|----------|--------------|
| **Cobrança** | Chama Claude API por conversa, cobrança por token | Claude Code CLI local, cota de assinatura |
| **Custo** | Conversas longas e análises de código queimam tokens rápido | **Zero custo extra de tokens** |
| **API Key** | Necessária | Não necessária |

### Capacidades únicas do Claude Code

Claude Code CLI oferece **capacidades que chamadas API sozinhas não replicam**: controle total do PC, contexto de todo o projeto, 10+ ferramentas integradas (Read, Write, Edit, Bash, Glob, Grep...), operações reais de código com efeito imediato, progresso em tempo real e sessões persistentes.

### Em uma frase

> **OpenClaw** = Framework IA completo para cenários gerais — mas pesado, caro e complexo de instalar
>
> **Este projeto** = 4 arquivos, custo zero extra, foco: controlar Claude Code pelo WeChat

### Como escolher?

- **Bot IA geral para WeChat** com múltiplos modelos → OpenClaw
- **Controlar PC, código e comandos pelo WeChat** → este projeto
- **Já tem assinatura Claude Code** → este projeto (custo zero adicional)

---

## Conexão WeChat

Este projeto usa o protocolo oficial do WeChat **iLink Bot** (ClawBot), conectando via escaneamento de QR code:

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="Método de conexão WeChat ClawBot" width="260" />
</p>

<p align="center">
  <img src="../images/wechat-usage.jpg" alt="Uso real" width="260" />
</p>

> Esquerda: página oficial do plugin ClawBot do WeChat. Direita: uso real. Após iniciar o Bot, um QR code aparece no terminal — escaneie com o WeChat para conectar. Uma vez conectado, o Bot continua funcionando e processando mensagens mesmo após fechar o WeChat. Reabra o WeChat para ver as respostas.

---

## Como funciona

```
┌──────────┐         ┌──────────────────┐         ┌───────────┐
│  WeChat   │ ─msg──▶│  iLink Bot API   │ ─poll──▶│ Bot local │
│(celular)  │ ◀resp.─│ (weixin.qq.com)  │ ◀envio─ │ (Node.js) │
└──────────┘         └──────────────────┘         └─────┬─────┘
                                                        │
                                                        │ Chamada CLI
                                                        ▼
                                                  ┌───────────┐
                                                  │ Claude Code│
                                                  │  (local)   │
                                                  └───────────┘
```

1. Bot recebe mensagens via WeChat iLink Bot API (long polling)
2. Encaminha mensagens para o Claude Code CLI local (modo stream-json)
3. Analisa chamadas de ferramentas do Claude Code em tempo real, enviando progresso ao WeChat
4. Após conclusão, formata e envia o resultado final de volta ao WeChat

---

## Início rápido

### Pré-requisitos

- **Node.js** >= 18
- **Claude Code CLI** instalado globalmente (`npm install -g @anthropic-ai/claude-code`)
- **Conta WeChat**

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. Instalar dependências
npm install

# 3. (Opcional) Configurar diretório de trabalho
cp .env.example .env
# Edite .env para definir CLAUDE_CWD com o caminho do seu projeto

# 4. Iniciar o Bot
npm start
```

### Primeira conexão

1. Após iniciar, um QR code será exibido no terminal
2. Abra o WeChat → Escaneie o QR code
3. Confirme a conexão no WeChat
4. Quando vir `✅ Conectado!`, o bot está pronto
5. Envie uma mensagem para o Bot no WeChat para começar

> Após o primeiro login, o token é salvo automaticamente. Não precisa escanear novamente na próxima inicialização (exceto se o token expirar).

---

## Configuração

Configure via arquivo `.env` ou variáveis de ambiente:

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `CLAUDE_CWD` | Diretório de trabalho do Claude Code | Diretório atual (`process.cwd()`) |
| `SYSTEM_PROMPT` | Prompt de sistema adicional | Vazio |

**Exemplo de arquivo `.env`:**

```bash
# Especificar o diretório do projeto para Claude Code
CLAUDE_CWD=/home/user/my-project

# Prompt de sistema personalizado (opcional)
SYSTEM_PROMPT=Você é um assistente especializado em desenvolvimento React
```

---

## Guia de uso

### Uso básico

Envie mensagens em linguagem natural no WeChat descrevendo o que precisa. Claude Code executará automaticamente:

```
Você: Mostre a estrutura do projeto
Bot: 🤖 Recebido, processando...
Bot: 🔍 Buscando arquivos: **/*
Bot: Estrutura do projeto:
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### Progresso em tempo real

Quando Claude Code executa operações, você recebe atualizações em tempo real:

```
📖 Lendo arquivo: src/app.js
✏️ Editando arquivo: src/utils.js
⚡ Executando comando: npm test
🔍 Buscando arquivos: **/*.ts
🔍 Buscando conteúdo: handleClick
📝 Criando arquivo: src/helper.js
📋 Planejando tarefas
```

### Tratamento de mensagens longas

Quando a resposta do Claude Code excede 4000 caracteres, as mensagens são divididas inteligentemente:

- Prioridade para dividir nos limites de blocos de código
- Depois em linhas em branco
- Cada fragmento é rotulado com número de sequência, ex.: `(cont. 2/3)`

---

## Casos de uso

### Caso 1: Corrigir bug no trajeto

> Um colega reporta um bug urgente em produção enquanto você está no metrô.

```
Você: Mostre a função login em src/api/auth.js
Bot: [exibe código]

Você: A validação do token na linha 42 está errada, deveria ser > e não >=
Bot: ✏️ Editando arquivo: api/auth.js
Bot: Corrigido, >= alterado para >

Você: Execute os testes
Bot: ⚡ Executando comando: npm test
Bot: Todos os 23 testes passaram ✓

Você: Faça commit com "fix: corrigir condição limite de expiração do token"
Bot: Commit realizado e enviado ao remoto
```

### Caso 2: Desenvolver funcionalidades no celular

> É fim de semana, você está fora e tem uma ideia rápida.

```
Você: Crie um componente ThemeToggle em src/components com modo escuro/claro
Bot: 📝 Criando arquivo: components/ThemeToggle.jsx
Bot: ✏️ Editando arquivo: App.jsx
Bot: Componente ThemeToggle criado e importado no App.jsx...
```

### Caso 3: Code review e aprendizado

> Entrou em um novo projeto e quer entender rapidamente a base de código.

```
Você: Qual é a arquitetura geral deste projeto?
Bot: [analisa estrutura, módulos principais, stack tecnológica...]

Você: Onde está a lógica de conexão com o banco de dados?
Bot: 🔍 Buscando conteúdo: database|connection|mongoose
Bot: A conexão com o banco está em src/config/db.js...
```

### Caso 4: DevOps e monitoramento

> Precisa verificar o status do serviço estando fora.

```
Você: Verifique o status dos containers Docker
Bot: ⚡ Executando comando: docker ps
Bot: [mostra lista de containers...]

Você: Verifique os logs recentes procurando erros
Bot: ⚡ Executando comando: docker logs --tail 50 my-app
Bot: [mostra logs...]
```

---

## Lista de comandos

| Comando | Descrição |
|---------|-----------|
| `/help` | Mostrar informações de ajuda |
| `/new` | Reiniciar conversa, iniciar nova sessão |
| `/model` | Trocar modelo (sonnet / opus / haiku) |
| `/send <caminho>` | Enviar arquivo local ao WeChat (imagens, arquivos, etc.) |
| `/status` | Ver status do Bot (versão, tempo ativo, diretório de trabalho) |

> Todas as mensagens exceto comandos slash são enviadas ao Claude Code para processamento.

---

## Estrutura do projeto

```
Wechat-Claude-bot/
├── index.js          # Entrada principal: roteamento de mensagens, comandos slash, conversão Markdown
├── weixin-api.js     # Wrapper WeChat iLink Bot API: login, mensagens, indicador de digitação
├── claude-code.js    # Interação Claude Code CLI: gerenciamento de sessões, parsing de streams, callbacks de progresso
├── media.js          # Mídia: upload/download CDN, criptografia AES-128-ECB
├── package.json
├── .env.example      # Exemplo de variáveis de ambiente
├── .gitignore
├── docs/             # Documentação multilíngue e recursos
│   ├── images/       # Recursos de imagem
│   └── README_*.md   # Traduções
└── .state/           # (gerado em execução) Credenciais e estado de sincronização
```

---

## Perguntas frequentes

### P: "comando claude não encontrado" ao iniciar

Certifique-se de que o Claude Code CLI está instalado globalmente:

```bash
npm install -g @anthropic-ai/claude-code
```

Verifique com `claude --version`.

### P: QR code não é exibido corretamente

Se seu terminal não suporta Unicode, o QR code pode não renderizar corretamente. O log de inicialização inclui uma URL — abra no navegador para escanear.

### P: E se o token expirar?

O bot detecta automaticamente a expiração do token e exibe um novo QR code. Nenhuma ação manual necessária.

### P: Várias pessoas podem usar simultaneamente?

Sim. Cada usuário do WeChat tem uma sessão independente. Até 3 requisições simultâneas são suportadas; excedentes são enfileiradas automaticamente.

### P: Requisição expirou

O timeout padrão é de 5 minutos por requisição. Para tarefas complexas, divida em passos menores — por exemplo, primeiro peça ao Claude para explorar a estrutura do projeto, depois execute operações específicas.

### P: Suporta imagens/arquivos?

Sim. O Bot pode receber imagens, arquivos e vídeos do WeChat, baixando-os automaticamente para Claude Code analisar. Também é possível usar `/send <caminho>` para enviar arquivos locais ao WeChat. Mensagens de voz requerem a conversão voz-para-texto do WeChat.

### P: Quão seguro é?

- O bot roda localmente na sua máquina — código nunca passa por servidores de terceiros
- Claude Code roda em modo `bypassPermissions` com acesso total a arquivos e comandos
- Credenciais são armazenadas localmente em `.state/` com permissões apenas do proprietário
- `.env` está no `.gitignore` e não será commitado no Git

> **Atenção**: Como o Claude Code tem permissões totais, garanta que apenas pessoas confiáveis possam enviar mensagens ao Bot.

---

## License

GPL-3.0
