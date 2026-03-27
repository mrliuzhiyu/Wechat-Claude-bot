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

- **Controle remoto via WeChat** — Controle seu Claude Code local diretamente por mensagens do WeChat, sem precisar abrir um terminal
- **Funciona após fechar o WeChat** — Baseado em long polling do servidor, as mensagens ficam na fila mesmo após fechar o app do WeChat. Reabra o WeChat para ver as respostas — o Bot funciona 24/7 sem parar
- **Progresso em tempo real** — Receba atualizações ao vivo quando Claude Code lê arquivos, escreve código ou executa comandos
- **Capacidades completas de código** — Claude Code tem permissões totais: leitura/escrita de arquivos, comandos de terminal, busca de código, instalação de pacotes
- **Isolamento de sessões multiusuário** — Cada usuário do WeChat tem uma sessão independente com contexto contínuo
- **Suporte a mensagens de voz** — Compatível com mensagens de voz do WeChat (requer conversão voz-para-texto ativada)
- **Divisão inteligente de mensagens** — Respostas longas são divididas automaticamente nos limites de blocos de código
- **Conversão Markdown** — Converte automaticamente a saída Markdown do Claude para texto compatível com WeChat
- **Reconexão automática** — Reautenticação automática quando a sessão expira, persistência de token
- **Controle de concorrência** — Até 3 tarefas simultâneas, excedentes são enfileiradas automaticamente
- **Encerramento gracioso** — Suporte a Ctrl+C com limpeza automática de processos filhos

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

### O que o Claude Code pode fazer

Através de mensagens no WeChat, você pode pedir ao Claude Code para:

- **Ler código** — "Mostre o conteúdo de src/app.js"
- **Escrever código** — "Crie uma função de formatação de data em utils"
- **Modificar código** — "Mude a cor de fundo do componente App para azul"
- **Executar comandos** — "Execute npm test e mostre os resultados"
- **Buscar código** — "Encontre todos os lugares que usam useState"
- **Instalar pacotes** — "Instale axios e lodash"
- **Depurar** — "Por que o build está falhando? Verifique"
- **Code review** — "Revise as mudanças recentes procurando problemas"
- **Operações Git** — "Faça commit com a mensagem 'fix: corrigir bug de login'"

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
| `/status` | Ver status do Bot (versão, tempo ativo, diretório de trabalho) |

> Todas as mensagens exceto comandos slash são enviadas ao Claude Code para processamento.

---

## Estrutura do projeto

```
Wechat-Claude-bot/
├── index.js          # Entrada principal: roteamento de mensagens, comandos slash, conversão Markdown
├── weixin-api.js     # Wrapper WeChat iLink Bot API: login, mensagens, indicador de digitação
├── claude-code.js    # Interação Claude Code CLI: gerenciamento de sessões, parsing de streams, callbacks de progresso
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

Atualmente apenas mensagens de texto e voz (com conversão de texto ativada) são suportadas. Imagens, vídeos e arquivos ainda não são suportados.

### P: Quão seguro é?

- O bot roda localmente na sua máquina — código nunca passa por servidores de terceiros
- Claude Code roda em modo `bypassPermissions` com acesso total a arquivos e comandos
- Credenciais são armazenadas localmente em `.state/` com permissões apenas do proprietário
- `.env` está no `.gitignore` e não será commitado no Git

> **Atenção**: Como o Claude Code tem permissões totais, garanta que apenas pessoas confiáveis possam enviar mensagens ao Bot.

---

## License

MIT
