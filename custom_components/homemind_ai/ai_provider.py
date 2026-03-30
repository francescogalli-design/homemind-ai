"""Provider AI per query testuali con Gemini — HomeMind AI."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_SYSTEM_PROMPT = """\
Sei HomeMind AI, l'assistente intelligente integrato nella casa smart di questo utente.
Hai accesso allo stato completo e in tempo reale della casa.

REGOLE:
- Rispondi SEMPRE in italiano, in modo conciso e diretto.
- Usa il contesto fornito per rispondere con precisione.
- Se vedi qualcosa di insolito (movimento attivo, porte aperte, allarme attivo, tutti fuori) segnalalo proattivamente.
- Per domande sulle telecamere: rispondi in base al contesto; per analisi visiva suggerisci il comando /analizza.
- Per le azioni sui dispositivi: descrivi l'azione che eseguiresti e invita a usare i servizi HA.
- Sii sintetico: max 300 parole per risposta normale, max 150 per risposte semplici.
- NON inventare stati o valori che non sono nel contesto.
- Se il dato non è disponibile, dillo chiaramente.
"""


async def ask_gemini(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    question: str,
    home_context: str,
) -> str:
    """
    Invia una domanda a Gemini con il contesto completo della casa.

    Returns:
        Risposta testuale in italiano.
    """
    full_prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"--- CONTESTO CASA (aggiornato ora) ---\n"
        f"{home_context}\n\n"
        f"--- DOMANDA UTENTE ---\n"
        f"{question}"
    )

    payload = {
        "contents": [
            {
                "parts": [{"text": full_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
            "topP": 0.8,
        },
    }

    url = GEMINI_TEXT_URL.format(model=model)

    try:
        async with session.post(
            f"{url}?key={api_key}",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.error("Gemini text API errore HTTP %s: %s", resp.status, body[:300])
                return f"❌ Errore Gemini ({resp.status}). Riprova o controlla i log."

            data = await resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not text:
                # Check for safety blocks
                finish = data.get("candidates", [{}])[0].get("finishReason", "")
                if finish == "SAFETY":
                    return "⚠️ La risposta è stata bloccata dai filtri di sicurezza Gemini."
                return "⚠️ Nessuna risposta ricevuta da Gemini."

            return text

    except asyncio.TimeoutError:
        _LOGGER.warning("Gemini text: timeout dopo 30s")
        return "⏱️ Timeout: Gemini non ha risposto in 30 secondi."
    except Exception as exc:
        _LOGGER.error("Gemini text eccezione: %s", exc)
        return f"❌ Errore di comunicazione con Gemini: {exc}"


async def ask_gemini_security(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    camera_name: str,
    scene_description: str,
    home_context: str,
) -> str:
    """
    Valutazione approfondita sicurezza con contesto casa completo.
    Usata per escalation e correlazione cross-camera.
    """
    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"--- CONTESTO CASA ---\n{home_context}\n\n"
        f"--- ANALISI SICUREZZA ---\n"
        f"Telecamera: {camera_name}\n"
        f"Rilevamento: {scene_description}\n\n"
        f"Considerando il contesto completo della casa (chi è presente, ora del giorno, "
        f"stato allarme, porte/finestre, altri sensori attivi), questo evento è davvero sospetto? "
        f"Rispondi con: VALUTAZIONE (normale/attenzione/allarme), MOTIVAZIONE (1-2 frasi), "
        f"AZIONE CONSIGLIATA (cosa fare)."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
    }

    url = GEMINI_TEXT_URL.format(model=model)
    try:
        async with session.post(
            f"{url}?key={api_key}",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=25),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
    except Exception as exc:
        _LOGGER.debug("Gemini security context errore: %s", exc)

    return ""
