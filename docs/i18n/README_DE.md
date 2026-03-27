# WeChat Claude Code Bot

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="Offizielle WeChat ClawBot Verbindung" width="280" />
  <img src="../images/wechat-usage.jpg" alt="Tatsächliche Nutzung" width="280" />
</p>

<p align="center">
  <strong>Steuere dein lokales Claude Code CLI per Fernzugriff über WeChat — verwalte deine Code-Projekte jederzeit und überall</strong>
</p>

<p align="center">
  <a href="../../README.md">中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_RU.md">Русский</a> · <a href="README_ES.md">Español</a> · <a href="README_FR.md">Français</a> · <a href="README_DE.md">Deutsch</a> · <a href="README_PT.md">Português</a> · <a href="README_AR.md">العربية</a>
</p>

<p align="center">
  Benutzer sendet Nachricht in WeChat → Lokales Claude Code verarbeitet → Echtzeit-Feedback in WeChat
</p>

---

## Inhaltsverzeichnis

- [Funktionen](#funktionen)
- [Vergleich mit direktem OpenClaw](#vergleich-mit-direktem-openclaw)
- [WeChat-Verbindung](#wechat-verbindung)
- [Funktionsweise](#funktionsweise)
- [Schnellstart](#schnellstart)
- [Konfiguration](#konfiguration)
- [Nutzungsanleitung](#nutzungsanleitung)
- [Anwendungsfälle](#anwendungsfälle)
- [Befehlsliste](#befehlsliste)
- [Projektstruktur](#projektstruktur)
- [Häufige Fragen](#häufige-fragen)

---

## Funktionen

### Kernfähigkeiten

- **Fernsteuerung über WeChat** — Steuere dein lokales Claude Code direkt über WeChat-Nachrichten, kein Terminal nötig
- **Funktioniert nach Schließen von WeChat** — Dank serverseitigem Long Polling werden Nachrichten auch nach dem Schließen der WeChat-App in die Warteschlange gestellt. Öffne WeChat erneut, um die Antworten zu sehen — der Bot läuft rund um die Uhr
- **Volle Computerkontrolle** — Claude Code kann deinen Computer wirklich steuern: beliebige Dateien lesen/schreiben, Befehle ausführen, Code suchen, Pakete installieren, Git-Operationen — nicht nur Chat
- **Arbeitet an echten Projekten** — Claude Code läuft in deinem lokalen Projektverzeichnis, ändert echte Code-Dateien direkt

### Benutzererfahrung

- **Echtzeit-Fortschritt** — Live-Updates in WeChat während Claude Code arbeitet (z.B. `📖 Lese Datei: src/app.js`)
- **Tipp-Indikator** — Zeigt „tippt" Status in WeChat während der Verarbeitung
- **Intelligente Teilung** — Lange Antworten werden an Codeblock-Grenzen geteilt mit Nummerierung
- **Markdown-Konvertierung** — Automatische Umwandlung von Markdown in WeChat-kompatiblen Text
- **Bilder/Dateien/Videos** — Empfang von Bildern, Dateien und Videos aus WeChat, automatischer Download und Analyse durch Claude Code; `/send` zum Senden lokaler Dateien
- **Sprachnachrichten** — WeChat Sprache-zu-Text Unterstützung, Befehle per Sprache senden
- **Slash-Befehle** — `/new` zurücksetzen, `/model` Modell wechseln, `/send` Datei senden, `/status` Status

### Stabilität und Sicherheit

- **Session-Isolierung** — Jeder Benutzer hat eine unabhängige Session mit durchgehendem Kontext
- **Parallelitätskontrolle** — Bis zu 3 gleichzeitige Aufgaben, Überschuss in Warteschlange
- **Auto-Reconnect** — Automatische Neuanmeldung bei Session-Ablauf
- **Session-Bereinigung** — Inaktive Sessions nach 1h automatisch bereinigt, max 100 Sessions
- **Gestaffelter Timeout-Schutz** — Erinnerung nach 2 Min, erzwungenes Ende nach 5 Min
- **Sauberes Herunterfahren** — Ctrl+C mit automatischer Bereinigung von Kindprozessen
- **Lokale Ausführung** — Code und Daten gehen nie über Drittanbieter-Server

---

## Vergleich mit direktem OpenClaw

WeChats offizielles OpenClaw (ClawBot) ermöglicht direkten KI-Chat in WeChat. Dieses Projekt verbindet **Claude Code CLI** darüber und bringt fundamentale Unterschiede:

| Dimension | Direktes OpenClaw | Dieses Projekt (WeChat Claude Code Bot) |
|-----------|-------------------|------------------------------------------|
| **Fähigkeiten** | Nur Text-Chat | Volle Kontrolle: Dateien lesen/schreiben, Befehle ausführen, Code suchen |
| **Token-Kosten** | API-Token pro Gespräch, nutzungsbasiert | Lokales Claude Code CLI, im Abo enthalten — keine Extra-Token |
| **Projektzugang** | Kein Zugriff auf lokale Dateien | Direkter Zugriff auf echten Projektcode |
| **Befehlsausführung** | Nicht unterstützt | Jeder Terminal-Befehl (npm, git, docker, etc.) |
| **Kontext** | Nur Chat-Text | Gesamtes Projektverzeichnis als Kontext |
| **Werkzeuge** | Keine | 10+ eingebaute: Read, Write, Edit, Bash, Glob, Grep, WebSearch, etc. |
| **Fortschritt** | Keiner | Echtzeit-Fortschritt jeder Operation |
| **Git-Operationen** | Nicht unterstützt | Commit, Push, Branches direkt erstellen |
| **Paketinstallation** | Nicht unterstützt | `npm install`, `pip install`, etc. |
| **Multi-Turn** | Begrenzter Kontext | Unabhängiges Session-Management mit persistentem Kontext |

### In einem Satz

> **Direktes OpenClaw** = Mit KI in WeChat chatten
>
> **Dieses Projekt** = Einen KI-Programmierer fernsteuern, der Code liest/schreibt, Befehle ausführt und Projekte verwaltet

---

## WeChat-Verbindung

Dieses Projekt basiert auf dem offiziellen WeChat **iLink Bot** (ClawBot) Protokoll, Verbindung über QR-Code-Scan:

<p align="center">
  <img src="../images/wechat-clawbot.jpg" alt="WeChat ClawBot Verbindungsmethode" width="260" />
</p>

<p align="center">
  <img src="../images/wechat-usage.jpg" alt="Tatsächliche Nutzung" width="260" />
</p>

> Links: offizielle WeChat ClawBot Plugin-Seite. Rechts: tatsächliche Nutzung. Nach dem Bot-Start wird ein QR-Code im Terminal angezeigt — scanne ihn mit WeChat zur Verbindung. Nach der Verbindung läuft der Bot weiter und verarbeitet Nachrichten, auch nachdem du WeChat geschlossen hast. Öffne WeChat erneut, um die Antworten zu sehen.

---

## Funktionsweise

```
┌──────────┐         ┌──────────────────┐         ┌─────────────┐
│  WeChat   │ ─Nachr.─▶│  iLink Bot API   │ ─Poll──▶│ Lokaler Bot │
│  (Handy)  │ ◀─Antw.── │ (weixin.qq.com)  │ ◀─Send── │  (Node.js)  │
└──────────┘         └──────────────────┘         └──────┬──────┘
                                                         │
                                                         │ CLI-Aufruf
                                                         ▼
                                                   ┌───────────┐
                                                   │ Claude Code│
                                                   │  (lokal)   │
                                                   └───────────┘
```

1. Bot empfängt Nachrichten über WeChat iLink Bot API (Long Polling)
2. Leitet Nachrichten an lokales Claude Code CLI weiter (Stream-JSON-Modus)
3. Analysiert Claude Codes Tool-Aufrufe in Echtzeit und sendet Fortschritt an WeChat
4. Nach Abschluss wird das Ergebnis formatiert und an WeChat gesendet

---

## Schnellstart

### Voraussetzungen

- **Node.js** >= 18
- **Claude Code CLI** global installiert (`npm install -g @anthropic-ai/claude-code`)
- **WeChat-Konto**

### Installation

```bash
# 1. Repository klonen
git clone https://github.com/mrliuzhiyu/Wechat-Claude-bot.git
cd Wechat-Claude-bot

# 2. Abhängigkeiten installieren
npm install

# 3. (Optional) Arbeitsverzeichnis konfigurieren
cp .env.example .env
# .env bearbeiten und CLAUDE_CWD auf deinen Projektpfad setzen

# 4. Bot starten
npm start
```

### Erste Verbindung

1. Nach dem Start wird ein QR-Code im Terminal angezeigt
2. WeChat öffnen → QR-Code scannen
3. Verbindung in WeChat bestätigen
4. Wenn `✅ Verbunden!` erscheint, ist der Bot bereit
5. Einfach eine Nachricht an den Bot in WeChat senden

> Nach der ersten Anmeldung wird der Token automatisch gespeichert. Beim nächsten Start muss nicht erneut gescannt werden (außer der Token läuft ab).

---

## Konfiguration

Konfiguration über `.env`-Datei oder Umgebungsvariablen:

| Variable | Beschreibung | Standard |
|----------|-------------|----------|
| `CLAUDE_CWD` | Arbeitsverzeichnis für Claude Code | Aktuelles Verzeichnis (`process.cwd()`) |
| `SYSTEM_PROMPT` | Zusätzlicher System-Prompt | Leer |

**Beispiel `.env`-Datei:**

```bash
# Projektverzeichnis für Claude Code angeben
CLAUDE_CWD=/home/user/my-project

# Benutzerdefinierter System-Prompt (optional)
SYSTEM_PROMPT=Du bist ein auf React-Entwicklung spezialisierter Assistent
```

---

## Nutzungsanleitung

### Grundlegende Nutzung

Sende natürlichsprachige Nachrichten in WeChat. Claude Code führt sie automatisch aus:

```
Du: Zeig mir die Projektstruktur
Bot: 🤖 Empfangen, verarbeite...
Bot: 🔍 Suche Dateien: **/*
Bot: Projektstruktur:
     ├── src/
     │   ├── components/
     │   ├── pages/
     │   └── utils/
     ├── package.json
     └── README.md
```

### Was Claude Code kann

Über WeChat-Nachrichten kannst du Claude Code anweisen:

- **Code lesen** — „Zeig mir den Inhalt von src/app.js"
- **Code schreiben** — „Erstelle eine Datum-Formatierungsfunktion in utils"
- **Code ändern** — „Ändere die Hintergrundfarbe der App-Komponente auf Blau"
- **Befehle ausführen** — „Führe npm test aus und zeig mir die Ergebnisse"
- **Code suchen** — „Finde alle Stellen, die useState verwenden"
- **Pakete installieren** — „Installiere axios und lodash"
- **Debuggen** — „Warum schlägt der Build fehl? Überprüfe das"
- **Code Review** — „Prüfe die letzten Änderungen auf Probleme"
- **Git-Operationen** — „Committe mit der Nachricht 'fix: Login-Bug beheben'"

### Echtzeit-Fortschritt

Bei Operationen erhältst du Live-Updates:

```
📖 Lese Datei: src/app.js
✏️ Bearbeite Datei: src/utils.js
⚡ Führe Befehl aus: npm test
🔍 Suche Dateien: **/*.ts
🔍 Suche Inhalt: handleClick
📝 Erstelle Datei: src/helper.js
📋 Plane Aufgaben
```

### Umgang mit langen Nachrichten

Wenn Claude Codes Antwort 4000 Zeichen überschreitet, werden Nachrichten intelligent geteilt:

- Bevorzugt Teilung an Codeblock-Grenzen
- Dann an Leerzeilen
- Jedes Fragment wird nummeriert, z.B.: `(Forts. 2/3)`

---

## Anwendungsfälle

### Fall 1: Bug-Fix auf dem Arbeitsweg

> Ein Kollege meldet einen kritischen Produktions-Bug, während du in der U-Bahn bist.

```
Du: Zeig mir die login-Funktion in src/api/auth.js
Bot: [zeigt Code]

Du: Die Token-Validierung in Zeile 42 ist falsch, es sollte > statt >= sein
Bot: ✏️ Bearbeite Datei: api/auth.js
Bot: Korrigiert, >= zu > geändert

Du: Führe die Tests aus
Bot: ⚡ Führe aus: npm test
Bot: Alle 23 Tests bestanden ✓

Du: Committe mit "fix: Token-Ablauf-Grenzbedingung korrigiert"
Bot: Committed und zum Remote gepusht
```

### Fall 2: Mobile Funktionsentwicklung

> Wochenende unterwegs, plötzlich eine Feature-Idee.

```
Du: Erstelle eine ThemeToggle-Komponente in src/components mit Dark/Light-Modus
Bot: 📝 Erstelle: components/ThemeToggle.jsx
Bot: ✏️ Bearbeite: App.jsx
Bot: ThemeToggle-Komponente erstellt und in App.jsx importiert...
```

### Fall 3: Code Review und Lernen

> Neues Projekt beigetreten, möchte die Codebasis schnell verstehen.

```
Du: Wie ist die Gesamtarchitektur dieses Projekts?
Bot: [analysiert Struktur, Hauptmodule, Tech-Stack...]

Du: Wo ist die Datenbankverbindungslogik?
Bot: 🔍 Suche: database|connection|mongoose
Bot: Die Datenbankverbindung befindet sich in src/config/db.js...
```

### Fall 4: DevOps und Monitoring

> Unterwegs den Servicestatus prüfen.

```
Du: Prüfe den Status der Docker-Container
Bot: ⚡ Führe aus: docker ps
Bot: [zeigt Container-Liste...]

Du: Prüfe die letzten Logs auf Fehler
Bot: ⚡ Führe aus: docker logs --tail 50 my-app
Bot: [zeigt Logs...]
```

---

## Befehlsliste

| Befehl | Beschreibung |
|--------|-------------|
| `/help` | Hilfe anzeigen |
| `/new` | Gespräch zurücksetzen, neue Session starten |
| `/model` | Modell wechseln (sonnet / opus / haiku) |
| `/send <Pfad>` | Lokale Datei an WeChat senden (Bilder, Dateien, etc.) |
| `/status` | Bot-Status anzeigen (Version, Laufzeit, Arbeitsverzeichnis) |

> Alle Nachrichten außer Slash-Befehlen werden an Claude Code zur Verarbeitung gesendet.

---

## Projektstruktur

```
Wechat-Claude-bot/
├── index.js          # Haupteinstieg: Nachrichtenrouting, Slash-Befehle, Markdown-Konvertierung
├── weixin-api.js     # WeChat iLink Bot API Wrapper: Login, Nachrichten, Tipp-Indikator
├── claude-code.js    # Claude Code CLI Interaktion: Session-Verwaltung, Stream-Parsing, Fortschritts-Callbacks
├── media.js          # Medien: CDN Upload/Download, AES-128-ECB Verschlüsselung
├── package.json
├── .env.example      # Beispiel Umgebungsvariablen
├── .gitignore
├── docs/             # Mehrsprachige Dokumentation und Ressourcen
│   ├── images/       # Bildressourcen
│   └── README_*.md   # Übersetzungen
└── .state/           # (zur Laufzeit erstellt) Anmeldedaten und Sync-Status
```

---

## Häufige Fragen

### F: „claude Befehl nicht gefunden" beim Start

Stelle sicher, dass Claude Code CLI global installiert ist:

```bash
npm install -g @anthropic-ai/claude-code
```

Überprüfe mit `claude --version`.

### F: QR-Code wird nicht korrekt angezeigt

Wenn dein Terminal kein Unicode unterstützt, wird der QR-Code möglicherweise nicht richtig dargestellt. Das Startlog enthält eine URL — öffne sie im Browser zum Scannen.

### F: Was passiert, wenn der Token abläuft?

Der Bot erkennt den Token-Ablauf automatisch und zeigt einen neuen QR-Code an. Keine manuelle Aktion nötig.

### F: Können mehrere Personen gleichzeitig nutzen?

Ja. Jeder WeChat-Benutzer hat eine unabhängige Session. Bis zu 3 gleichzeitige Anfragen werden unterstützt; überschüssige werden automatisch eingereiht.

### F: Anfrage-Timeout

Standard-Timeout ist 5 Minuten pro Anfrage. Bei komplexen Aufgaben in kleinere Schritte aufteilen — z.B. zuerst Claude die Projektstruktur erkunden lassen, dann spezifische Operationen.

### F: Werden Bilder/Dateien unterstützt?

Ja. Der Bot kann Bilder, Dateien und Videos aus WeChat empfangen, automatisch herunterladen und zur Analyse an Claude Code übergeben. Mit `/send <Pfad>` kannst du lokale Dateien an WeChat senden. Sprachnachrichten erfordern die Sprache-zu-Text-Funktion von WeChat.

### F: Wie sicher ist es?

- Der Bot läuft lokal auf deinem Rechner — Code geht nie über Drittanbieter-Server
- Claude Code läuft im `bypassPermissions`-Modus mit vollem Datei- und Befehlszugriff
- Anmeldedaten werden lokal in `.state/` mit Nur-Eigentümer-Berechtigungen gespeichert
- `.env` ist in `.gitignore` und wird nicht in Git committed

> **Warnung**: Da Claude Code volle Berechtigungen hat, stelle sicher, dass nur vertrauenswürdige Personen dem Bot Nachrichten senden können.

---

## License

MIT
