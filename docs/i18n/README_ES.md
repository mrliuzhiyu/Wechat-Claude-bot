# WeChat Claude Code Bot

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="Conexión oficial WeChat ClawBot" width="280" />
  <img src="../images/wechat-usage.jpg" alt="Uso real" width="280" />
</p>

<p align="center">
  <strong>Controla tu Claude Code CLI local de forma remota a través de WeChat — gestiona tus proyectos de código en cualquier momento y lugar</strong>
</p>

<p align="center">
  <a href="../../README.md">中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_RU.md">Русский</a> · <a href="README_ES.md">Español</a> · <a href="README_FR.md">Français</a> · <a href="README_DE.md">Deutsch</a> · <a href="README_PT.md">Português</a> · <a href="README_AR.md">العربية</a>
</p>

<p align="center">
  El usuario envía un mensaje en WeChat → Claude Code local lo procesa → Retroalimentación en tiempo real en WeChat
</p>

---

## Tabla de contenidos

- [Características](#características)
- [Comparación con OpenClaw directo](#comparación-con-openclaw-directo)
- [Conexión WeChat](#conexión-wechat)
- [Cómo funciona](#cómo-funciona)
- [Inicio rápido](#inicio-rápido)
- [Configuración](#configuración)
- [Guía de uso](#guía-de-uso)
- [Casos de uso](#casos-de-uso)
- [Lista de comandos](#lista-de-comandos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Preguntas frecuentes](#preguntas-frecuentes)

---

## Características

### Capacidades principales

- **Control remoto por WeChat** — Controla Claude Code local directamente a través de mensajes de WeChat, sin necesidad de abrir una terminal
- **Funciona después de cerrar WeChat** — Basado en long polling del servidor, los mensajes se encolan incluso después de cerrar la app de WeChat. Al reabrirla verás las respuestas — el Bot funciona 24/7 sin interrupciones
- **Control total del ordenador** — Claude Code puede operar tu ordenador realmente: leer/escribir archivos, ejecutar comandos, buscar código, instalar paquetes, operaciones Git — no es solo un chat
- **Opera sobre proyectos reales** — Claude Code se ejecuta en tu directorio de proyecto local, modifica archivos de código reales con cambios inmediatos

### Experiencia de usuario

- **Progreso en tiempo real** — Actualizaciones en vivo en WeChat mientras Claude Code trabaja (ej: `📖 Leyendo archivo: src/app.js`)
- **Indicador de escritura** — Muestra estado "escribiendo" en WeChat durante el procesamiento
- **División inteligente de mensajes** — Respuestas largas divididas en los límites de bloques de código con números de secuencia
- **Conversión Markdown** — Conversión automática de Markdown a texto compatible con WeChat
- **Imágenes/archivos/videos** — Recibe imágenes, archivos y videos de WeChat, descarga automática y análisis por Claude Code; `/send` para enviar archivos locales
- **Mensajes de voz** — Soporte de voz-a-texto de WeChat, envía comandos por voz
- **Comandos slash** — `/new` reiniciar, `/model` cambiar modelo, `/send` enviar archivo, `/status` estado

### Estabilidad y seguridad

- **Aislamiento de sesiones** — Cada usuario tiene sesión independiente con contexto continuo
- **Control de concurrencia** — Hasta 3 tareas simultáneas, excedentes en cola sin pérdida de mensajes
- **Reconexión automática** — Reautenticación automática al expirar la sesión
- **Limpieza de sesiones** — Sesiones inactivas se limpian tras 1 hora, máximo 100 sesiones
- **Protección de timeout escalonada** — Recordatorio a los 2 min, terminación forzada a los 5 min
- **Apagado elegante** — Ctrl+C con limpieza automática de procesos hijos
- **Ejecución local** — Código y datos nunca pasan por servidores de terceros

---

## Comparación con OpenClaw directo

El OpenClaw oficial (ClawBot) de WeChat permite chatear con IA directamente. Este proyecto conecta **Claude Code CLI** encima, trayendo diferencias fundamentales:

| Dimensión | OpenClaw directo | Este proyecto (WeChat Claude Code Bot) |
|-----------|-----------------|----------------------------------------|
| **Capacidades** | Solo chat de texto | Control total: leer/escribir archivos, ejecutar comandos, buscar código |
| **Coste de tokens** | Consume tokens API por conversación | Usa Claude Code CLI local, incluido en tu suscripción — sin tokens extra |
| **Acceso al proyecto** | Sin acceso a archivos locales | Opera directamente sobre tu código real |
| **Ejecución de comandos** | No soportado | Cualquier comando de terminal (npm, git, docker, etc.) |
| **Contexto** | Solo texto del chat | Todo el directorio del proyecto como contexto |
| **Herramientas** | Ninguna | 10+ herramientas: Read, Write, Edit, Bash, Glob, Grep, WebSearch, etc. |
| **Progreso** | Ninguno | Progreso en tiempo real de cada operación |
| **Operaciones Git** | No soportado | Commit, push, crear ramas directamente |
| **Instalar paquetes** | No soportado | `npm install`, `pip install`, etc. |
| **Multi-turno** | Contexto limitado | Gestión de sesiones independiente con contexto persistente |

### En una frase

> **OpenClaw directo** = Chatear con IA en WeChat
>
> **Este proyecto** = Controlar remotamente un programador IA que lee/escribe código, ejecuta comandos y gestiona proyectos

---

## Conexión WeChat

Este proyecto se basa en el protocolo oficial de WeChat **iLink Bot** (ClawBot), conectándose mediante escaneo de código QR:

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="Método de conexión WeChat ClawBot" width="260" />
</p>

<p align="center">
  <img src="../images/wechat-usage.jpg" alt="Uso real" width="260" />
</p>

> Izquierda: página oficial del plugin ClawBot de WeChat. Derecha: uso real. Después de iniciar el Bot, aparece un código QR en la terminal — escanéalo con WeChat para conectarte. Una vez conectado, el Bot sigue funcionando y procesando mensajes incluso después de cerrar WeChat. Reabre WeChat para ver las respuestas.

---

## Cómo funciona

```
┌──────────┐         ┌──────────────────┐         ┌───────────┐
│  WeChat   │ ─msg──▶│  iLink Bot API   │ ─poll──▶│ Bot local │
│ (teléfono)│ ◀resp.─│ (weixin.qq.com)  │ ◀envío─ │ (Node.js) │
└──────────┘         └──────────────────┘         └─────┬─────┘
                                                        │
                                                        │ Llamada CLI
                                                        ▼
                                                  ┌───────────┐
                                                  │ Claude Code│
                                                  │  (local)   │
                                                  └───────────┘
```

1. El Bot recibe mensajes a través de WeChat iLink Bot API (long polling)
2. Reenvía los mensajes al Claude Code CLI local (modo stream-json)
3. Analiza en tiempo real las llamadas a herramientas de Claude Code, enviando progreso a WeChat
4. Al completarse, formatea y envía el resultado final de vuelta a WeChat

---

## Inicio rápido

### Requisitos previos

- **Node.js** >= 18
- **Claude Code CLI** instalado globalmente (`npm install -g @anthropic-ai/claude-code`)
- **Cuenta de WeChat**

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. Instalar dependencias
npm install

# 3. (Opcional) Configurar directorio de trabajo
cp .env.example .env
# Editar .env para establecer CLAUDE_CWD con la ruta de tu proyecto

# 4. Iniciar el Bot
npm start
```

### Primera conexión

1. Después de iniciar, se mostrará un código QR en la terminal
2. Abre WeChat → Escanea el código QR
3. Confirma la conexión en WeChat
4. Cuando veas `✅ ¡Conectado!`, el bot está listo
5. Envía un mensaje al Bot en WeChat para comenzar

> Después del primer inicio de sesión, el token se guarda automáticamente. No necesitas escanear de nuevo en el próximo inicio (a menos que el token expire).

---

## Configuración

Configura mediante archivo `.env` o variables de entorno:

| Variable | Descripción | Predeterminado |
|----------|-------------|----------------|
| `CLAUDE_CWD` | Directorio de trabajo de Claude Code | Directorio actual (`process.cwd()`) |
| `SYSTEM_PROMPT` | Prompt de sistema adicional | Vacío |

**Ejemplo de archivo `.env`:**

```bash
# Especificar el directorio del proyecto para Claude Code
CLAUDE_CWD=/home/user/my-project

# Prompt de sistema personalizado (opcional)
SYSTEM_PROMPT=Eres un asistente especializado en desarrollo React
```

---

## Guía de uso

### Uso básico

Envía mensajes en lenguaje natural en WeChat describiendo lo que necesitas. Claude Code lo ejecutará automáticamente:

```
Tú: Muéstrame la estructura del proyecto
Bot: 🤖 Recibido, procesando...
Bot: 🔍 Buscando archivos: **/*
Bot: Estructura del proyecto:
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### Qué puede hacer Claude Code

A través de mensajes de WeChat, puedes hacer que Claude Code:

- **Leer código** — "Muéstrame el contenido de src/app.js"
- **Escribir código** — "Crea una función de formateo de fechas en utils"
- **Modificar código** — "Cambia el color de fondo del componente App a azul"
- **Ejecutar comandos** — "Ejecuta npm test y muéstrame los resultados"
- **Buscar código** — "Encuentra todos los lugares donde se usa useState"
- **Instalar paquetes** — "Instala axios y lodash"
- **Depurar problemas** — "¿Por qué falla la compilación? Revísalo"
- **Revisión de código** — "Revisa los cambios recientes en busca de problemas"
- **Operaciones Git** — "Haz commit con el mensaje 'fix: corregir bug de login'"

### Progreso en tiempo real

Cuando Claude Code ejecuta operaciones, recibes actualizaciones en tiempo real:

```
📖 Leyendo archivo: src/app.js
✏️ Editando archivo: src/utils.js
⚡ Ejecutando comando: npm test
🔍 Buscando archivos: **/*.ts
🔍 Buscando contenido: handleClick
📝 Creando archivo: src/helper.js
📋 Planificando tareas
```

### Manejo de mensajes largos

Cuando la respuesta de Claude Code supera los 4000 caracteres, los mensajes se dividen inteligentemente:

- Prioridad en dividir en los límites de bloques de código
- Luego en líneas vacías
- Cada fragmento se etiqueta con un número de secuencia, ej.: `(cont. 2/3)`

---

## Casos de uso

### Caso 1: Corregir un bug durante el viaje al trabajo

> Un colega reporta un bug urgente en producción mientras estás en el metro.

```
Tú: Muéstrame la función login en src/api/auth.js
Bot: [muestra el código]

Tú: La validación del token en la línea 42 está mal, debería ser > no >=
Bot: ✏️ Editando archivo: api/auth.js
Bot: Corregido, >= cambiado a >

Tú: Ejecuta los tests
Bot: ⚡ Ejecutando comando: npm test
Bot: Los 23 tests pasaron ✓

Tú: Haz commit con "fix: corregir condición límite de expiración de token"
Bot: Commit realizado y enviado al remoto
```

### Caso 2: Desarrollar funciones desde el móvil

> Es fin de semana, estás fuera y tienes una idea rápida.

```
Tú: Crea un componente ThemeToggle en src/components con modo oscuro/claro
Bot: 📝 Creando archivo: components/ThemeToggle.jsx
Bot: ✏️ Editando archivo: App.jsx
Bot: Componente ThemeToggle creado e importado en App.jsx...
```

### Caso 3: Revisión de código y aprendizaje

> Te uniste a un nuevo proyecto y quieres entender rápidamente la base de código.

```
Tú: ¿Cuál es la arquitectura general de este proyecto?
Bot: [analiza estructura, módulos principales, stack tecnológico...]

Tú: ¿Dónde está la lógica de conexión a la base de datos?
Bot: 🔍 Buscando contenido: database|connection|mongoose
Bot: La conexión a la base de datos está en src/config/db.js...
```

### Caso 4: DevOps y monitoreo

> Necesitas verificar el estado del servicio estando fuera.

```
Tú: Revisa el estado de los contenedores Docker
Bot: ⚡ Ejecutando comando: docker ps
Bot: [muestra lista de contenedores...]

Tú: Revisa los logs recientes en busca de errores
Bot: ⚡ Ejecutando comando: docker logs --tail 50 my-app
Bot: [muestra logs...]
```

---

## Lista de comandos

| Comando | Descripción |
|---------|-------------|
| `/help` | Mostrar información de ayuda |
| `/new` | Reiniciar conversación, iniciar nueva sesión |
| `/model` | Cambiar modelo (sonnet / opus / haiku) |
| `/send <ruta>` | Enviar archivo local a WeChat (imágenes, archivos, etc.) |
| `/status` | Ver estado del Bot (versión, tiempo activo, directorio de trabajo) |

> Todos los mensajes excepto los comandos slash se envían a Claude Code para su procesamiento.

---

## Estructura del proyecto

```
Wechat-Claude-bot/
├── index.js          # Entrada principal: enrutamiento de mensajes, comandos slash, conversión Markdown
├── weixin-api.js     # Wrapper de WeChat iLink Bot API: login, mensajería, indicador de escritura
├── claude-code.js    # Interacción con Claude Code CLI: gestión de sesiones, parsing de streams, callbacks de progreso
├── media.js          # Medios: carga/descarga CDN, cifrado AES-128-ECB
├── package.json
├── .env.example      # Ejemplo de variables de entorno
├── .gitignore
├── docs/             # Documentación multilingüe y recursos
│   ├── images/       # Recursos de imagen
│   └── README_*.md   # Traducciones
└── .state/           # (generado en ejecución) Credenciales y estado de sincronización
```

---

## Preguntas frecuentes

### P: "comando claude no encontrado" al iniciar

Asegúrate de que Claude Code CLI esté instalado globalmente:

```bash
npm install -g @anthropic-ai/claude-code
```

Verifica con `claude --version`.

### P: El código QR no se muestra correctamente

Si tu terminal no soporta Unicode, el código QR puede no renderizarse bien. El log de inicio incluye una URL — ábrela en un navegador para escanear.

### P: ¿Qué pasa si el token expira?

El bot detecta automáticamente la expiración del token y muestra un nuevo código QR. No se requiere acción manual.

### P: ¿Pueden varias personas usarlo simultáneamente?

Sí. Cada usuario de WeChat tiene una sesión independiente. Se soportan hasta 3 solicitudes simultáneas; las demás se ponen en cola automáticamente.

### P: La solicitud expiró

El timeout predeterminado es de 5 minutos por solicitud. Para tareas complejas, divídelas en pasos más pequeños — por ejemplo, primero pide a Claude que explore la estructura del proyecto, luego realiza operaciones específicas.

### P: ¿Soporta imágenes/archivos?

Sí. El Bot puede recibir imágenes, archivos y videos de WeChat, descargándolos automáticamente para que Claude Code los analice. También puedes usar `/send <ruta>` para enviar archivos locales a WeChat. Los mensajes de voz requieren la conversión voz-a-texto de WeChat.

### P: ¿Qué tan seguro es?

- El bot se ejecuta localmente en tu máquina — el código nunca pasa por servidores de terceros
- Claude Code se ejecuta en modo `bypassPermissions` con acceso completo a archivos y comandos
- Las credenciales se almacenan localmente en `.state/` con permisos solo para el propietario
- `.env` está en `.gitignore` y no se commitea en Git

> **Advertencia**: Como Claude Code tiene permisos completos, asegúrate de que solo personas de confianza puedan enviar mensajes al Bot.

---

## License

MIT
