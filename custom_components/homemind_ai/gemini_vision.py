"""Gemini Vision — analisi immagini camera per HomeMind AI."""
from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def analyze_camera_image(
    session: aiohttp.ClientSession,
    api_key: str,
    image_bytes: bytes,
    camera_name: str,
    model: str = "gemini-2.0-flash",
) -> dict[str, Any]:
    """
    Invia uno snapshot camera a Gemini Vision e analizza la sicurezza.

    Returns:
        dict con threat_level, description, summary, threat_detected
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        f"Analizza questa immagine della telecamera '{camera_name}' "
        "per la sicurezza domestica. Rispondi SOLO in italiano.\n\n"
        "Descrivi:\n"
        "1. Cosa vedi (persone, animali, veicoli, oggetti insoliti)\n"
        "2. C'è qualcosa di sospetto o insolito?\n"
        "3. Livello di rischio: NESSUNO, BASSO, MEDIO o ALTO\n\n"
        "Formato risposta:\n"
        "DESCRIZIONE: [descrizione]\n"
        "INSOLITO: [sì/no — cosa]\n"
        "RISCHIO: [NESSUNO/BASSO/MEDIO/ALTO]\n"
        "RIEPILOGO: [una frase breve]"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": prompt},
                ]
            }
        ]
    }

    url = GEMINI_API_URL.format(model=model)
    params = {"key": api_key}

    try:
        async with session.post(url, json=payload, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.error("Gemini Vision errore HTTP %s: %s", resp.status, body[:200])
                return _error_result(camera_name, f"HTTP {resp.status}")

            data = await resp.json()
            raw_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )

    except Exception as exc:
        _LOGGER.error("Gemini Vision eccezione: %s", exc)
        return _error_result(camera_name, str(exc))

    return _parse_response(raw_text, camera_name)


def _parse_response(raw: str, camera_name: str) -> dict[str, Any]:
    """Parsea la risposta strutturata di Gemini."""
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
