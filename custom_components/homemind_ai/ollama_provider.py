"""Ollama provider — analisi immagini e query AI via Ollama locale (100% gratuito)."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Semaforo: una sola inferenza vision alla volta per non sovraccaricare
_VISION_SEMAPHORE = asyncio.Semaphore(1)

# Modelli con supporto vision consigliati
OLLAMA_VISION_MODELS_HINT = ["llava", "llava-phi3", "moondream", "moondream2", "bakllava", "llava:13b"]


async def test_ollama(
    session: aiohttp.ClientSession,
    host: str,
    model: str,
) -> tuple[bool, str]:
    """
    Verifica che Ollama sia raggiungibile e che il modello sia disponibile.
    Returns (ok, message).
    """
    host = host.rstrip("/")
    try:
        async with session.get(
            f"{host}/api/tags",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                return False, f"Ollama non raggiungibile (HTTP {resp.status}): {body[:100]}"

            data = await resp.json()
            available = [m.get("name", "") for m in data.get("models", [])]

            # Controlla se il modello (o una variante) è disponibile
            model_base = model.split(":")[0]
            model_match = any(
                m == model or m.startswith(model_base + ":") or m.startswith(model_base)
                for m in available
            )

            if not model_match and available:
                return (
                    False,
                    f"Modello '{model}' non trovato in Ollama. "
                    f"Modelli disponibili: {', '.join(available[:5])}. "
                    f"Esegui: ollama pull {model}",
                )
            if not available:
                return (
                    False,
                    f"Nessun modello installato in Ollama. "
                    f"Esegui: ollama pull {model}",
                )

            return True, f"Online — {model} ({len(available)} modelli disponibili)"

    except aiohttp.ClientConnectorError:
        return False, f"Impossibile connettersi a Ollama su {host}. Verifica che Ollama sia avviato."
    except Exception as exc:
        return False, f"Errore connessione Ollama: {exc}"


async def analyze_camera_image_ollama(
    session: aiohttp.ClientSession,
    host: str,
    model: str,
    image_bytes: bytes,
    camera_name: str,
) -> dict[str, Any]:
    """
    Analizza uno snapshot camera con Ollama Vision (es. llava).
    Usa la stessa struttura di risposta di Gemini Vision.
    """
    host = host.rstrip("/")
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        f"Telecamera sicurezza '{camera_name}'. Analizza SOLO eventi rilevanti.\n"
        "Se la scena è normale (nessuna persona, veicolo, animale o oggetto insolito): rispondi SOLO \"NESSUN EVENTO\"\n"
        "Se c'è un evento, rispondi con questo formato esatto:\n"
        "EVENTO: [cosa succede — max 1 riga]\n"
        "RISCHIO: [NESSUNO/BASSO/MEDIO/ALTO]\n"
        "NOTA: [perché è rilevante — max 1 riga]"
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }

    async with _VISION_SEMAPHORE:
        try:
            async with session.post(
                f"{host}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("Ollama Vision errore HTTP %s: %s", resp.status, body[:200])
                    return _error_result(camera_name, f"HTTP {resp.status}: {body[:100]}")

                data = await resp.json()
                raw_text = data.get("message", {}).get("content", "").strip()

        except asyncio.TimeoutError:
            _LOGGER.error("Ollama Vision timeout (90s) per %s", camera_name)
            return _error_result(camera_name, "Timeout 90s")
        except Exception as exc:
            _LOGGER.error("Ollama Vision eccezione: %s", exc)
            return _error_result(camera_name, str(exc))

    return _parse_response(raw_text, camera_name)


async def ask_ollama(
    session: aiohttp.ClientSession,
    host: str,
    model: str,
    question: str,
    home_context: str,
) -> str:
    """Query testuale a Ollama con contesto casa."""
    host = host.rstrip("/")

    system_prompt = (
        "Sei HomeMind AI, l'assistente intelligente della casa smart. "
        "Hai accesso allo stato completo della casa. "
        "Rispondi SEMPRE in italiano, in modo conciso e diretto. "
        "Usa il contesto fornito per rispondere con precisione. "
        "NON inventare stati o valori che non sono nel contesto."
    )

    full_prompt = (
        f"--- CONTESTO CASA (aggiornato ora) ---\n"
        f"{home_context}\n\n"
        f"--- DOMANDA ---\n{question}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512},
    }

    try:
        async with session.post(
            f"{host}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.error("Ollama text errore HTTP %s: %s", resp.status, body[:200])
                return f"Errore Ollama ({resp.status}). Verifica che il modello sia installato."

            data = await resp.json()
            return data.get("message", {}).get("content", "").strip() or "Nessuna risposta da Ollama."

    except Exception as exc:
        _LOGGER.error("Ollama text eccezione: %s", exc)
        return f"Errore di comunicazione con Ollama: {exc}"


async def ask_ollama_security(
    session: aiohttp.ClientSession,
    host: str,
    model: str,
    camera_name: str,
    scene_description: str,
    home_context: str,
) -> str:
    """Valutazione sicurezza contestuale con Ollama."""
    prompt = (
        f"--- CONTESTO CASA ---\n{home_context}\n\n"
        f"--- ANALISI SICUREZZA ---\n"
        f"Telecamera: {camera_name}\n"
        f"Rilevamento: {scene_description}\n\n"
        f"Considerando il contesto della casa (chi è presente, ora del giorno, "
        f"stato allarme, porte/finestre), questo evento è davvero sospetto? "
        f"Rispondi con: VALUTAZIONE (normale/attenzione/allarme), MOTIVAZIONE (1-2 frasi), "
        f"AZIONE CONSIGLIATA."
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 256},
    }

    try:
        async with session.post(
            f"{host}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("message", {}).get("content", "").strip()
    except Exception as exc:
        _LOGGER.debug("Ollama security errore: %s", exc)

    return ""


def _parse_response(raw: str, camera_name: str) -> dict[str, Any]:
    """Parsea risposta strutturata (formato evento)."""
    result: dict[str, Any] = {
        "camera": camera_name,
        "description": "",
        "unusual": "",
        "threat_level": "none",
        "threat_detected": False,
        "has_event": False,
        "summary": "",
        "raw_response": raw,
    }

    if "NESSUN EVENTO" in raw.upper():
        return result

    result["has_event"] = True
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("EVENTO:"):
            result["description"] = line.replace("EVENTO:", "").strip()
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
        elif line.startswith("NOTA:"):
            result["summary"] = line.replace("NOTA:", "").strip()

    if not result["description"]:
        result["description"] = raw
        result["summary"] = raw[:150]

    return result


async def check_plate_visible(
    session: aiohttp.ClientSession,
    host: str,
    model: str,
    image_bytes: bytes,
) -> bool:
    """
    Pre-validazione ALPR: verifica se c'è una targa leggibile nell'immagine.
    Restituisce True/False. Usato PRIMA di chiamare PlateRecognizer per
    risparmiare chiamate API a pagamento.
    """
    host = host.rstrip("/")
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Is there a visible and readable license plate in this image? Answer ONLY: YES or NO",
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 5},
    }

    async with _VISION_SEMAPHORE:
        try:
            async with session.post(
                f"{host}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Ollama plate-check fallito HTTP %s", resp.status)
                    return True  # in dubbio, procedi con PlateRecognizer

                data = await resp.json()
                answer = data.get("message", {}).get("content", "").strip().upper()

        except Exception as exc:
            _LOGGER.warning("Ollama plate-check eccezione: %s", exc)
            return True  # in dubbio, procedi

    return "YES" in answer or "SI" in answer or "SÌ" in answer


def _error_result(camera_name: str, error: str) -> dict[str, Any]:
    return {
        "camera": camera_name,
        "description": "Errore nell'analisi.",
        "unusual": "",
        "threat_level": "none",
        "threat_detected": False,
        "has_event": False,
        "summary": f"Errore: {error}",
        "error": error,
    }
