# 🧠 HomeMind AI

Sicurezza proattiva per Home Assistant — powered by **Gemini Vision**.

HomeMind AI monitora le telecamere di casa, usa Gemini Vision per analizzare cosa succede, e ti invia notifiche Telegram immediate quando rileva qualcosa di sospetto. Ogni mattina ricevi un riepilogo della notte.

## ✨ Funzionalità

- **Monitoraggio notturno** — finestra configurabile (default 22:00→06:00)
- **Gemini Vision** — analisi AI delle immagini: persone, veicoli, attività sospette
- **Notifiche Telegram** — alert immediati con foto + analisi in italiano
- **Report mattutino** — riepilogo giornaliero generato da AI
- **Trigger su movimento** — analisi automatica al rilevamento movimento
- **Servizi HA** — `analyze_camera`, `generate_report`, `clear_alerts`
- **5 sensori HA** — stato, night mode, alert count, ultimo alert, ultimo report
- **Configurabile da UI** — nessun YAML richiesto

## 📦 Installazione via HACS

1. Apri HACS → Integrazioni → Menu (⋮) → **Repository personalizzati**
2. Aggiungi `https://github.com/francescogalli-design/homemind-ai` come **Integrazione**
3. Cerca **HomeMind AI** e clicca Scarica
4. Riavvia Home Assistant
5. Vai in **Impostazioni → Dispositivi e Servizi → Aggiungi integrazione** → cerca HomeMind AI

## ⚙️ Configurazione

Il wizard ti guida in 1 step:

| Campo | Descrizione |
|-------|-------------|
| Gemini API Key | Da [aistudio.google.com](https://aistudio.google.com) |
| Modello Gemini | `gemini-2.0-flash` (consigliato) |
| Telegram Bot Token | Da [@BotFather](https://t.me/botfather) (opzionale) |
| Telegram Chat ID | Da [@userinfobot](https://t.me/userinfobot) (opzionale) |
| Inizio notte | Ora attivazione monitoraggio (default: 22) |
| Fine notte | Ora disattivazione monitoraggio (default: 6) |
| Ora report mattutino | (default: 7) |

## 📡 Sensori

| Entity | Descrizione |
|--------|-------------|
| `sensor.homemind_ai_status` | `online` / `error` |
| `sensor.homemind_night_mode` | `active` / `inactive` |
| `sensor.homemind_alerts_tonight` | Numero alert della notte |
| `sensor.homemind_last_alert` | Descrizione ultimo alert |
| `sensor.homemind_last_report` | Testo ultimo report mattutino |

## 🔧 Servizi

```yaml
# Analizza una camera on-demand
service: homemind_ai.analyze_camera
data:
  entity_id: camera.ingresso

# Genera report manualmente
service: homemind_ai.generate_report

# Svuota la coda degli alert
service: homemind_ai.clear_alerts
```

## 🤖 Automazione esempio

```yaml
automation:
  alias: "HomeMind — Allerta Alta Priorità"
  trigger:
    platform: event
    event_type: homemind_ai_alert
    event_data:
      priority: high
  action:
    - service: notify.mobile_app_il_mio_telefono
      data:
        title: "🚨 Allerta Sicurezza"
        message: "{{ trigger.event.data.description }}"
        data:
          image: "{{ trigger.event.data.snapshot_url }}"
```

## 📄 Licenza

MIT License
