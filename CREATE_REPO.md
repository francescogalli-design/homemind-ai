# 🚀 Creazione Repository GitHub - Guida Rapida

## 📋 Procedura Completa

### 1. Vai su GitHub e Crea il Repository

1. Apri [https://github.com/new](https://github.com/new)
2. **Repository name**: `homemind-ai`
3. **Description**: `Advanced AI-powered Home Assistant integration with proactive capabilities`
4. **Visibility**: Public (necessario per HACS)
5. **Non** aggiungere README, .gitignore o license (già presenti)
6. Clicca **Create repository**

### 2. Collega il Repository Locale

Dopo aver creato il repository su GitHub, esegui questi comandi:

```bash
# Sostituisci TUO_USERNAME con il tuo username GitHub
git remote add origin https://github.com/TUO_USERNAME/homemind-ai.git

# Push del codice su GitHub
git push -u origin main

# Push anche i tag
git push origin --tags
```

### 3. Verifica il Repository

Vai su `https://github.com/TUO_USERNAME/homemind-ai` e dovresti vedere tutti i file.

## 📁 Struttura del Repository

Dovresti vedere questa struttura:

```
homemind-ai/
├── .github/workflows/     # CI/CD automation
├── nginx/                 # Nginx configuration
├── scripts/              # Deployment scripts
├── src/                  # Source code
├── tests/                # Test suite
├── config/               # Configuration files
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── Dockerfile            # Docker image
├── Makefile              # Convenient commands
├── README.md             # Project documentation
├── INSTALL.md            # Installation guide
├── PUBLISH.md            # Publishing guide
├── LICENSE               # MIT License
├── docker-compose.yml    # Development deployment
├── docker-compose.prod.yml # Production deployment
└── requirements.txt      # Python dependencies
```

## 🐳 Setup Docker Hub (Opzionale)

Se vuoi pubblicare anche su Docker Hub:

1. Crea account su [Docker Hub](https://hub.docker.com)
2. Crea repository `homemind-ai`
3. Su GitHub vai in `Settings > Secrets and variables > Actions`
4. Aggiungi:
   - `DOCKER_USERNAME`: Il tuo username Docker Hub
   - `DOCKER_PASSWORD`: Il tuo access token

## 🔄 GitHub Actions

I workflow si attiveranno automaticamente dopo il push:

- **CI Tests**: Test automatici
- **Docker Build**: Build immagine Docker
- **Security Scan**: Scansione vulnerabilità

Controlla in `Actions` tab del repository.

## 📦 Primo Deploy

```bash
# Copia il repository
git clone https://github.com/TUO_USERNAME/homemind-ai.git
cd homemind-ai

# Configura l'ambiente
cp .env.example .env
nano .env  # Inserisci le tue API keys

# Deploy in sviluppo
make quick-start

# Oppure produzione
make quick-prod
```

## ✅ Checklist Pubblicazione

- [ ] Repository creato su GitHub
- [ ] Codice pushato correttamente
- [ ] GitHub Actions funzionanti
- [ ] README.md completo
- [ ] Tag v2.0.0 creato e pushato
- [ ] Licenza MIT presente
- [ ] .gitignore configurato

## 🔗 Link Utilili

- Repository: `https://github.com/TUO_USERNAME/homemind-ai`
- Issues: `https://github.com/TUO_USERNAME/homemind-ai/issues`
- Actions: `https://github.com/TUO_USERNAME/homemind-ai/actions`

Una volta completato questi passaggi, il progetto sarà completamente pubblicato! 🎉
