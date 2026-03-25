# 🚀 Guida alla Pubblicazione - HomeMind AI Assistant

Guida completa per pubblicare HomeMind AI Assistant su GitHub, Docker Hub e HACS.

## 📋 Prerequisiti

- **Account GitHub** con repository creato
- **Account Docker Hub** (opzionale per immagini personalizzate)
- **Token GitHub** con permessi di scrittura
- **Home Assistant** installato e funzionante

## 🐙 Pubblicazione su GitHub

### 1. Crea il Repository

1. Vai su [GitHub](https://github.com) e crea un nuovo repository
2. Nome: `homemind-ai`
3. Descrizione: `Advanced AI-powered Home Assistant integration with proactive capabilities`
4. Scegli **Public** (per HACS)
5. Non aggiungere README, .gitignore o license (già presenti)

### 2. Push del Codice

```bash
# Se non hai ancora fatto il commit
git add .
git commit -m "Initial release - HomeMind AI Assistant v2.0.0"

# Aggiungi il remote
git remote add origin https://github.com/tu-username/homemind-ai.git

# Push del codice
git push -u origin main
```

### 3. Setup GitHub Actions

Il repository include già i workflow per CI/CD. Assicurati che:

1. Vai su `Settings > Secrets and variables > Actions`
2. Aggiungi eventuali secrets necessari (es. token per Docker Hub)

## 🐳 Pubblicazione su Docker Hub

### Opzione 1: GitHub Container Registry (Raccomandato)

Il workflow `.github/workflows/docker.yml` pubblica automaticamente su GitHub Container Registry:

```bash
# Pull dell'immagine
docker pull ghcr.io/tu-username/homemind-ai:latest

# Run dell'immagine
docker run -p 8080:8080 ghcr.io/tu-username/homemind-ai:latest
```

### Opzione 2: Docker Hub

1. Crea un account su [Docker Hub](https://hub.docker.com)
2. Crea un repository `homemind-ai`
3. Aggiungi i secrets su GitHub:
   - `DOCKER_USERNAME`: Il tuo username Docker Hub
   - `DOCKER_PASSWORD`: Il tuo access token Docker Hub

Modifica il workflow per usare Docker Hub se preferisci.

## 📦 Pubblicazione su HACS (Home Assistant Community Store)

### 1. Prepara il Repository per HACS

Crea la struttura HACS:

```bash
mkdir -p hacs
```

Crea il file `hacs/config.yaml`:

```yaml
name: HomeMind AI Assistant
description: Advanced AI-powered Home Assistant integration with proactive capabilities
version: 2.0.0
slug: homemind-ai
category: integration
url: https://github.com/tu-username/homemind-ai
icon: mdi:brain
homeassistant: 2024.1.0
arch:
  - aarch64
  - amd64
  - armhf
  - armv7
  - i386
```

### 2. Aggiungi Repository HACS

1. Vai su [HACS](https://hacs.xyz)
2. Segui le istruzioni per aggiungere un nuovo repository
3. Seleziona "Integration" come categoria
4. Inserisci l'URL del tuo repository GitHub
5. Attendi l'approvazione

### 3. Installazione da HACS

Una volta approvato, gli utenti possono installare:

1. Apri Home Assistant
2. Vai su HACS > Integrations
3. Cerca "HomeMind AI Assistant"
4. Clicca "Install" e riavvia Home Assistant

## 🏭 Deploy di Produzione

### 1. Server Setup

```bash
# Clona il repository
git clone https://github.com/tu-username/homemind-ai.git
cd homemind-ai

# Configura le variabili d'ambiente
cp .env.example .env
nano .env  # Inserisci le tue configurazioni

# Deploy in produzione
make quick-prod
```

### 2. Nginx e SSL

Il progetto include configurazione Nginx con SSL:

```bash
# Genera certificati SSL (usa Let's Encrypt in produzione)
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem

# Deploy con Nginx
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Monitoring

Il sistema include health checks:

```bash
# Controlla lo stato
curl http://localhost:8080/health

# Controlla i log
make logs
```

## 📊 CI/CD Automation

### GitHub Actions

Il repository include workflow automatici:

- **CI Tests**: Test automatici su ogni push/PR
- **Docker Build**: Build e push immagini Docker
- **Security Scan**: Scansione vulnerabilità
- **SBOM Generation**: Software Bill of Materials

### Badge per README

Aggiungi questi badge al README:

```markdown
![CI](https://github.com/tu-username/homemind-ai/workflows/CI%20Tests/badge.svg)
![Docker](https://github.com/tu-username/homemind-ai/workflows/Build%20and%20Push%20Docker%20Image/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![HACS](https://img.shields.io/badge/HACS-default-orange.svg)
```

## 🎯 Marketing e Promozione

### 1. Documentazione

- Assicurati che `README.md` sia completo
- Crea screenshot e GIF dimostrative
- Aggiungi esempi di configurazione

### 2. Community

- Pubblica su [Reddit](https://reddit.com/r/homeassistant)
- Condividi su [Discord Home Assistant](https://discord.gg/cqDhJJk)
- Partecipa alle discussioni su GitHub

### 3. Release Notes

Crea release su GitHub con changelog:

```bash
git tag v2.0.0
git push origin v2.0.0
```

## 🔧 Troubleshooting Pubblicazione

### GitHub Actions Fallisce

1. Controlla i secrets nelle repository settings
2. Verifica i permessi del token
3. Controlla i log delle actions

### Docker Build Fallisce

1. Verifica il Dockerfile
2. Controlla le dipendenze in requirements.txt
3. Assicurati che il context sia corretto

### HACS Rifiuta il Repository

1. Verifica la struttura HACS
2. Controlla che il repository sia public
3. Assicurati che i file richiesti siano presenti

## 📈 Monitoraggio Post-Pubblicazione

### Analytics

- Monitora le stelle e fork su GitHub
- Traccia i download delle immagini Docker
- Monitora le installazioni HACS

### Feedback

- Crea issues template per bug reports
- Aggiungi discussion forum per domande
- Rispondi prontamente alle issue

## 🔄 Aggiornamenti

### Versioning

Usa semantic versioning:

- `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: Nuove funzionalità
- `PATCH`: Bug fixes

### Release Process

1. Aggiorna versione in `src/core/config.py`
2. Aggiorna changelog
3. Crea nuovo tag
4. GitHub Actions pubblicherà automaticamente

## 🎉 Successo!

Una volta completati questi passaggi, HomeMind AI Assistant sarà:

- ✅ Disponibile su GitHub
- ✅ Deployabile via Docker
- ✅ Installabile da HACS
- ✅ Monitorabile e mantenibile
- ✅ Pronto per la community!

Congratulazioni per la pubblicazione! 🚀
