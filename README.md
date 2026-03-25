# 🧠 HomeMind AI Assistant - Versione Migliorata

Un assistente AI avanzato per Home Assistant con capacità proattive e integrazione Telegram.

## 🚀 Caratteristiche Migliorate

### 🤖 AI Proattiva Avanzata
- **Predizione comportamentale**: Impara le tue routine e anticipa azioni
- **Context awareness**: Capisce il contesto domestico in tempo reale
- **Multi-provider intelligente**: 7 provider AI con routing dinamico basato sul tipo di richiesta
- **Memory system**: Memoria persistente a lungo termine con embeddings

### 📱 Telegram Potenziato
- **Comandi vocali avanzati**: Trascrizione e comprensione semantica
- **Notifiche proattive**: Solo quando servono davvero, basate su contesto
- **Conversazioni naturali**: Chat contestuale con memoria della conversazione
- **Quick actions**: Bottoni rapidi per azioni comuni

### 🏠 Home Assistant Integration
- **Real-time monitoring**: WebSocket per stato istantaneo
- **Automazioni intelligenti**: Create e modificate via linguaggio naturale
- **Energy optimization**: Gestione intelligente di consumi e produzione solare
- **Security management**: Allarmi con riconoscimento pattern

### 🎨 Interfaccia Web Moderna
- **Dashboard React**: Interfaccia responsive e reattiva
- **Real-time updates**: Stato live di tutti i dispositivi
- **Configuration wizard**: Setup guidato per nuove funzionalità
- **Analytics dashboard**: Grafici e statistiche avanzate

## 📁 Struttura Progetto

```
homemind-ai/
├── src/
│   ├── core/                 # Core system
│   │   ├── ai_engine.py     # AI multi-provider
│   │   ├── memory_system.py # Memoria persistente
│   │   └── context_manager.py # Gestione contesto
│   ├── integrations/         # Integrazioni esterne
│   │   ├── telegram/         # Bot Telegram
│   │   ├── homeassistant/    # Client HA
│   │   └── voice/           # Voce e TTS
│   ├── analytics/            # Analisi e predizioni
│   │   ├── energy_analyzer.py
│   │   ├── behavior_predictor.py
│   │   └── routine_detector.py
│   ├── web/                 # Interfaccia web
│   │   ├── api/            # API FastAPI
│   │   └── frontend/       # React dashboard
│   └── plugins/             # Sistema plugin
├── config/                  # Configurazioni
├── tests/                   # Test suite
└── docs/                    # Documentazione
```

## 🛠️ Installazione

### Prerequisiti
- Home Assistant 2024.1+
- Python 3.11+
- Docker o ambiente virtuale

### Setup Rapido
```bash
# Clona il repository
git clone https://github.com/tu-username/homemind-ai.git
cd homemind-ai

# Installa dipendenze
pip install -r requirements.txt

# Configura le API keys
cp config/config.example.yaml config/config.yaml
# Edit config.yaml con le tue keys

# Avvia il servizio
python src/main.py
```

## 📖 Documentazione

- [Setup completo](docs/setup.md)
- [Configurazione AI](docs/ai-config.md)
- [API Reference](docs/api.md)
- [Sviluppo Plugin](docs/plugins.md)

## 🤝 Contributi

Benvenuti! Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per dettagli.

## 📄 Licenza

MIT License - vedi [LICENSE](LICENSE) per dettagli.
