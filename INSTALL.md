# 🚀 Installazione - HomeMind AI Assistant

Segui questa guida per installare e configurare HomeMind AI Assistant.

## 📋 Prerequisiti

- **Home Assistant** 2024.1+ (installato su HAOS, Docker, o standalone)
- **Python** 3.11+ (se non usi Docker)
- **Docker** e **Docker Compose** (raccomandato)
- **Account Telegram** (per il bot)
- **Almeno un provider AI** (Gemini e Groq sono gratuiti)

## 🐳 Installazione con Docker (Raccomandata)

### 1. Clona il Repository

```bash
git clone https://github.com/tu-username/homemind-ai.git
cd homemind-ai
```

### 2. Configura le Variabili d'Ambiente

```bash
# Copia il file di esempio
cp .env.example .env

# Edit il file con le tue configurazioni
nano .env
```

### 3. Configura le API Keys

#### Telegram Bot
1. Apri Telegram e cerca [@BotFather](https://t.me/botfather)
2. Invia `/newbot` e segui le istruzioni
3. Copia il token ottenuto in `TELEGRAM_BOT_TOKEN`
4. Cerca [@userinfobot](https://t.me/userinfobot) per ottenere il tuo chat ID
5. Inseriscilo in `TELEGRAM_CHAT_ID`

#### Provider AI (scegli almeno uno)

**Gemini (Google) - Gratis:**
1. Vai su [AI Studio](https://aistudio.google.com)
2. Crea un nuovo progetto o usane uno esistente
3. Genera una API key
4. Inseriscila in `GEMINI_API_KEY`

**Groq - Gratis e veloce:**
1. Vai su [Groq Console](https://console.groq.com)
2. Registrati e crea una API key
3. Inseriscila in `GROQ_API_KEY`

**Altri provider:**
- **Cerebras**: [cloud.cerebras.ai](https://cloud.cerebras.ai) - Gratis e velocissimo
- **DeepSeek**: [platform.deepseek.com](https://platform.deepseek.com) - Economico
- **Claude**: [console.anthropic.com](https://console.anthropic.com) - A pagamento
- **OpenAI**: [platform.openai.com](https://platform.openai.com) - A pagamento

#### Home Assistant
1. Apri Home Assistant
2. Vai su **Profilo** (in basso a sinistra)
3. Scorri fino a **Token di accesso di lunga durata**
4. Crea un nuovo token
5. Inseriscilo in `HA_TOKEN`
6. Inserisci l'URL di Home Assistant in `HA_URL`

### 4. Avvia il Servizio

```bash
# Avvia con Docker Compose
docker-compose up -d

# Controlla i log
docker-compose logs -f homemind-ai
```

### 5. Verifica l'Installazione

Apri `http://localhost:8080` nel browser o controlla lo stato di salute:

```bash
curl http://localhost:8080/health
```

## 🔧 Installazione Manuale

### 1. Clona e Installa Dipendenze

```bash
git clone https://github.com/tu-username/homemind-ai.git
cd homemind-ai
python -m venv venv
source venv/bin/activate  # Su Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configura

```bash
# Copia e modifica la configurazione
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

### 3. Avvia l'Applicazione

```bash
python src/main.py
```

## 🏠 Configurazione Home Assistant

### 1. Abilita l'API WebSocket

Assicurati che l'API WebSocket sia abilitata in `configuration.yaml`:

```yaml
# configuration.yaml
http:
  cors_allowed_origins:
    - http://localhost:8080
```

### 2. Riavvia Home Assistant

Dopo aver modificato la configurazione, riavvia Home Assistant.

## 📱 Configurazione Telegram

### Comandi Disponibili

Una volta avviato il bot, puoi usare questi comandi:

- `/start` - Messaggio di benvenuto
- `/help` - Lista comandi disponibili
- `/status` - Stato generale della casa
- `/briefing` - Briefing personalizzato
- `/energy` - Analisi energetica
- `/security` - Stato sicurezza
- `/memory` - Gestione memoria

### Esempi di Comandi Naturali

```
Accendi la luce del salotto
Quanta energia sto consumando?
Arma l'allarme
Temperatura attuale?
Qualcuno è a casa?
Avvia la lavatrice
```

### Messaggi Vocali

Puoi anche inviare messaggi vocali! Il bot li trascriverà automaticamente.

## 🔍 Verifica del Funzionamento

### 1. Controlla i Log

```bash
# Docker
docker-compose logs homemind-ai

# Manuale
tail -f homemind.log
```

### 2. Testa l'API

```bash
# Health check
curl http://localhost:8080/api/v1/health

# Chat test
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Ciao, come stai?", "user_id": "test"}'
```

### 3. Testa Telegram

Invia un messaggio al bot e verifica che riceva una risposta.

## 🛠️ Troubleshooting

### Problemi Comuni

**Bot non risponde su Telegram:**
- Verifica che `TELEGRAM_BOT_TOKEN` sia corretto
- Controlla che `TELEGRAM_CHAT_ID` sia quello giusto
- Controlla i log per errori di connessione

**Errore di connessione con Home Assistant:**
- Verifica che `HA_URL` sia corretto e raggiungibile
- Controlla che `HA_TOKEN` sia valido
- Assicurati che l'API WebSocket sia abilitata

**Provider AI non funzionante:**
- Verifica che la API key sia valida
- Controlla di avere crediti disponibili
- Prova un altro provider (il sistema usa fallback automatico)

**Porta già in uso:**
- Modifica `web_port` nel file di configurazione
- Oppure ferma altri servizi sulla porta 8080

### Log Utili

```bash
# Log dettagliati
export LOG_LEVEL=DEBUG
python src/main.py

# Log Docker in tempo reale
docker-compose logs -f --tail=100 homemind-ai
```

## 📊 Monitoraggio

### Interfaccia Web

Apri `http://localhost:8080` per:

- Dashboard di sistema
- Stato Home Assistant
- Statistiche AI
- Analisi energetica
- Gestione memoria

### API Endpoints

- `GET /api/v1/health` - Stato sistema
- `GET /api/v1/status` - Stato completo
- `POST /api/v1/chat` - Chat con AI
- `GET /api/v1/home/status` - Stato casa
- `GET /api/v1/energy/status` - Energia

## 🔄 Aggiornamenti

### Docker

```bash
# Pull nuove immagini
docker-compose pull

# Riavvia con nuove versioni
docker-compose up -d --force-recreate
```

### Manuale

```bash
git pull
pip install -r requirements.txt
python src/main.py
```

## 🆘 Supporto

Se riscontri problemi:

1. Controlla i log per errori specifici
2. Verifica la configurazione
3. Controlla la [documentazione](docs/)
4. Apri una issue su GitHub

## 🎉 Prossimi Passi

Una volta installato:

1. Esplora i comandi disponibili
2. Configura le tue preferenze
3. Crea automazioni personalizzate
4. Monitora i consumi energetici
5. Goditi il tuo assistente AI!
