"""Provider HA Gemini — usa l'integrazione google_generative_ai_conversation già configurata in HA."""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Il dominio dell'integrazione ufficiale HA Google Generative AI
_HA_GEMINI_DOMAIN = "google_generative_ai_conversation"
_HA_GEMINI_SERVICE = "generate_content"


async def test_ha_gemini(hass) -> tuple[bool, str]:
    """
    Verifica che l'integrazione google_generative_ai_conversation sia attiva
    e che il servizio generate_content sia disponibile.
    """
    if not hass.services.has_service(_HA_GEMINI_DOMAIN, _HA_GEMINI_SERVICE):
        # Controlla se l'integrazione è caricata ma il servizio non esiste
        if _HA_GEMINI_DOMAIN in hass.config.components:
            return (
                False,
                f"Integrazione '{_HA_GEMINI_DOMAIN}' trovata ma servizio "
                f"'{_HA_GEMINI_SERVICE}' non disponibile. "
                f"Aggiorna Home Assistant alla versione 2024.6 o superiore.",
            )
        return (
            False,
            f"Integrazione '{_HA_GEMINI_DOMAIN}' non trovata. "
            f"Aggiungi 'Google Generative AI Conversation' in Impostazioni → "
            f"Dispositivi e servizi → Aggiungi integrazione.",
        )

    # Test rapido con prompt minimale
    try:
        result = await hass.services.async_call(
            _HA_GEMINI_DOMAIN,
            _HA_GEMINI_SERVICE,
            {"prompt": "Test. Rispondi solo: ok"},
            blocking=True,
            return_response=True,
        )
        text = result.get("text", "") if result else ""
        if text:
            return True, f"Online — tramite integrazione HA ({_HA_GEMINI_DOMAIN})"
        # Se non c'è testo ma nessuna eccezione, consideriamo OK
        return True, f"Online — tramite integrazione HA ({_HA_GEMINI_DOMAIN})"
    except Exception as exc:
        err = str(exc)
        if "API_KEY" in err.upper() or "api key" in err.lower():
            return False, f"Chiave API non valida nell'integrazione HA Gemini: {err}"
        if "quota" in err.lower() or "429" in err:
            return False, f"Limite API superato: {err}"
        return False, f"Errore test integrazione HA Gemini: {err}"


async def ask_ha_gemini(hass, question: str, home_context: str) -> str:
    """
    Query testuale tramite l'integrazione HA Gemini.
    Nessuna chiamata HTTP diretta — usa hass.services.
    """
    system = (
        "Sei HomeMind AI, l'assistente intelligente della casa smart. "
        "Hai accesso allo stato completo della casa in tempo reale. "
        "Rispondi SEMPRE in italiano, in modo conciso e diretto. "
        "NON inventare stati o valori che non sono nel contesto. "
        "Se un dato non è disponibile, dillo chiaramente."
    )

    full_prompt = (
        f"{system}\n\n"
        f"--- CONTESTO CASA (aggiornato ora) ---\n"
        f"{home_context}\n\n"
        f"--- DOMANDA ---\n{question}"
    )

    try:
        result = await hass.services.async_call(
            _HA_GEMINI_DOMAIN,
            _HA_GEMINI_SERVICE,
            {"prompt": full_prompt},
            blocking=True,
            return_response=True,
        )
        text = (result or {}).get("text", "").strip()
        return text or "Nessuna risposta ricevuta da Gemini."
    except Exception as exc:
        _LOGGER.error("HA Gemini text errore: %s", exc)
        return f"Errore Gemini: {exc}"


async def analyze_camera_image_ha_gemini(
    hass,
    image_bytes: bytes,
    camera_name: str,
) -> dict[str, Any]:
    """
    Analizza uno snapshot camera tramite l'integrazione HA Gemini (Vision).
    Salva l'immagine in un file temporaneo nella directory config di HA,
    la passa al servizio generate_content, poi la cancella.
    """
    # Usa la cartella /config/tmp (sempre accessibile in HA)
    tmp_dir = hass.config.path("tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"homemind_snap_{camera_name.replace(' ', '_')}.jpg")

    try:
        # Scrivi snapshot su disco (operazione sincrona rapida)
        with open(tmp_path, "wb") as f:
            f.write(image_bytes)
    except Exception as exc:
        _LOGGER.error("Impossibile salvare snapshot temporaneo: %s", exc)
        return _error_result(camera_name, f"Errore salvataggio snapshot: {exc}")

    prompt = (
        f"Analizza questa immagine della telecamera '{camera_name}' "
        "per la sicurezza domestica. Rispondi SOLO in italiano.\n\n"
        "Descrivi:\n"
        "1. Cosa vedi (persone, animali, veicoli, oggetti insoliti)\n"
        "2. C'è qualcosa di sospetto o insolito?\n"
        "3. Livello di rischio: NESSUNO, BASSO, MEDIO o ALTO\n\n"
        "Formato risposta OBBLIGATORIO:\n"
        "DESCRIZIONE: [descrizione]\n"
        "INSOLITO: [sì/no — cosa]\n"
        "RISCHIO: [NESSUNO/BASSO/MEDIO/ALTO]\n"
        "RIEPILOGO: [una frase breve]"
    )

    raw_text = ""
    try:
        result = await hass.services.async_call(
            _HA_GEMINI_DOMAIN,
            _HA_GEMINI_SERVICE,
            {"prompt": prompt, "filenames": [tmp_path]},
            blocking=True,
            return_response=True,
        )
        raw_text = (result or {}).get("text", "").strip()
    except Exception as exc:
        _LOGGER.error("HA Gemini Vision errore su %s: %s", camera_name, exc)
        return _error_result(camera_name, str(exc))
    finally:
        # Cancella sempre il file temporaneo
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not raw_text:
        return _error_result(camera_name, "Nessuna risposta da Gemini Vision")

    return _parse_response(raw_text, camera_name)


async def ask_ha_gemini_security(
    hass,
    camera_name: str,
    scene_description: str,
    home_context: str,
) -> str:
    """Valutazione sicurezza contestuale tramite integrazione HA Gemini."""
    prompt = (
        f"--- CONTESTO CASA ---\n{home_context}\n\n"
        f"--- ANALISI SICUREZZA ---\n"
        f"Telecamera: {camera_name}\n"
        f"Rilevamento: {scene_description}\n\n"
        f"Considerando il contesto della casa (chi è presente, ora del giorno, "
        f"stato allarme, porte/finestre), questo evento è davvero sospetto? "
        f"Rispondi in italiano con: VALUTAZIONE (normale/attenzione/allarme), "
        f"MOTIVAZIONE (1-2 frasi), AZIONE CONSIGLIATA."
    )

    try:
        result = await hass.services.async_call(
            _HA_GEMINI_DOMAIN,
            _HA_GEMINI_SERVICE,
            {"prompt": prompt},
            blocking=True,
            return_response=True,
        )
        return (result or {}).get("text", "").strip()
    except Exception as exc:
        _LOGGER.debug("HA Gemini security errore: %s", exc)
        return ""


def _parse_response(raw: str, camera_name: str) -> dict[str, Any]:
    """Parsea risposta strutturata."""
    result: dict[str, Any] = {
        "camera": camera_name,
        "description": "",
        "unusual": "",
        "threat_level": "none",
        "threat_detected": False,
        "summary": "",
        "raw_response": raw,
    }
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("DESCRIZIONE:"):
            result["description"] = line.replace("DESCRIZIONE:", "").strip()
        elif line.startswith("INSOLITO:"):
            result["unusual"] = line.replace("INSOLITO:", "").strip()
        elif line.startswith("RISCHIO:"):
            level = line.replace("RISCHIO:", "").strip().upper()
            if "ALTO" in level:
                result["threat_level"] = "high"
                result["threat_detected"] = True
            elif "MEDIO" in level:
                result["threat_level"] = "medium"
                result["threat_detected"] = True
            elif "BASSO" in level:
                result["threat_level"] = "low"
        elif line.startswith("RIEPILOGO:"):
            result["summary"] = line.replace("RIEPILOGO:", "").strip()

    if not result["description"]:
        result["description"] = raw
        result["summary"] = raw[:150]
    return result


def _error_result(camera_name: str, error: str) -> dict[str, Any]:
    return {
        "camera": camera_name,
        "description": "Errore nell'analisi.",
        "unusual": "",
        "threat_level": "none",
        "threat_detected": False,
        "summary": f"Errore: {error}",
        "error": error,
    }
