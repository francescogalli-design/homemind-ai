# 🏠 HomeMind AI Assistant - HACS Integration

## 📦 Installazione Tramite HACS

### Prerequisiti
- Home Assistant 2024.1+
- HACS installato

### Installazione

1. **Aggiungi Repository Personalizzato**:
   - Vai su **HACS > Integrations**
   - Clicca i 3 puntini → **Custom repositories**
   - Aggiungi:
     ```
     Repository: francescogalli-design/homemind-ai
     Category: Integration
     ```

2. **Installa l'Integrazione**:
   - Cerca "HomeMind AI Assistant" in HACS
   - Clicca **Install**
   - Riavvia Home Assistant

3. **Configura**:
   - Vai su **Settings > Devices & Services > Integrations**
   - Clicca **+ Add Integration**
   - Cerca "HomeMind AI Assistant"
   - Configura con:
     - API URL: `http://localhost:8080` (default)
     - Telegram Bot Token (opzionale)
     - Telegram Chat ID (opzionale)

### Setup Servizio Esterno

L'integrazione richiede il servizio HomeMind AI in esecuzione:

```bash
git clone https://github.com/francescogalli-design/homemind-ai-service.git
cd homemind-ai-service
cp .env.example .env
# Configura le tue API keys nel file .env
docker-compose up -d
```

### Utilizzo

#### Servizio Chat
```yaml
service: homemind_ai.chat
data:
  message: "Accendi la luce del salotto"
  user_id: "user1"
```

#### Sensori Disponibili
- `sensor.homemind_ai_status`: Stato del sistema
- `sensor.homemind_ai_active_conversations`: Conversazioni attive

### Funzionalità
- ✅ Chat AI multi-provider
- ✅ Notifiche proattive
- ✅ Integrazione Telegram
- ✅ Monitoraggio energetico
- ✅ Memoria persistente
- ✅ Dashboard web

### Supporto
- Issues: [GitHub Issues](https://github.com/francescogalli-design/homemind-ai/issues)
- Repository servizio: [homemind-ai-service](https://github.com/francescogalli-design/homemind-ai-service)
