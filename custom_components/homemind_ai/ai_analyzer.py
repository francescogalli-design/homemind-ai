"""AI image analysis via Ollama (local, free)."""

import base64
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

SECURITY_PROMPT = """Sei un sistema di sicurezza domestica. Analizza questa immagine da una telecamera di sorveglianza.
Rispondi SOLO con un oggetto JSON valido con esattamente questi campi:
{
  "important": true o false,
  "description": "descrizione breve in italiano (max 120 caratteri)",
  "priority": "high" o "medium" o "low",
  "tags": ["tag1", "tag2"]
}

Regole per "important: true":
- Persona presente nell'inquadratura
- Veicolo sconosciuto fermo
- Movimento sospetto o insolito
- Intrusione in area privata
- Oggetto abbandonato

Tag disponibili: person, vehicle, animal, object, movement, suspicious, delivery, unknown

Rispondi SOLO con il JSON, zero testo aggiuntivo."""


class OllamaAnalyzer:
    """Handles AI image analysis via Ollama vision models."""

    def __init__(self, ollama_url: str, model: str) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model

    async def analyze_image(self, image_bytes: bytes) -> dict | None:
        """Send image to Ollama and return structured analysis."""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": self.model,
            "prompt": SECURITY_PROMPT,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as response:
                    if response.status != 200:
                        _LOGGER.error("Ollama returned HTTP %s", response.status)
                        return None
                    data = await response.json()
                    raw = data.get("response", "{}")
                    try:
                        result = json.loads(raw)
                        # Sanitize fields
                        return {
                            "important": bool(result.get("important", False)),
                            "description": str(result.get("description", "Movimento rilevato"))[:120],
                            "priority": result.get("priority", "medium") if result.get("priority") in ("high", "medium", "low") else "medium",
                            "tags": result.get("tags", []) if isinstance(result.get("tags"), list) else [],
                        }
                    except (json.JSONDecodeError, ValueError):
                        _LOGGER.warning("Ollama returned non-JSON: %s", raw[:200])
                        return {
                            "important": True,
                            "description": raw[:120],
                            "priority": "medium",
                            "tags": ["unknown"],
                        }
        except aiohttp.ClientConnectorError:
            _LOGGER.error("Cannot connect to Ollama at %s", self.ollama_url)
            return None
        except Exception as err:
            _LOGGER.error("Ollama error: %s", err)
            return None

    async def generate_night_report(self, events: list[dict]) -> str:
        """Generate a concise morning report from the night's events."""
        if not events:
            return "Nessun evento rilevante stanotte. Tutto tranquillo! ✅"

        events_summary = "\n".join(
            f"- {e['time']}: {e['description']} [priorità: {e['priority']}]"
            for e in events
        )
        prompt = (
            f"Sei l'assistente AI di sicurezza domestica HomeMind.\n"
            f"Ecco gli eventi rilevati stanotte dalle telecamere:\n\n"
            f"{events_summary}\n\n"
            f"Genera un report breve (max 200 parole) in italiano, professionale e amichevole.\n"
            f"Includi: breve riepilogo, eventuali situazioni da approfondire, e un saluto.\n"
            f"Non usare markdown, scrivi in testo semplice."
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=90),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "Errore nella generazione del report.")
                    return "Errore nella generazione del report (HTTP error)."
        except Exception as err:
            _LOGGER.error("Report generation error: %s", err)
            return f"Report non disponibile: {err}"

    async def describe_scene(self, image_bytes: bytes, camera_name: str) -> str:
        """Describe what is currently visible in a camera scene (snapshot query)."""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            f"Stai guardando l'immagine della telecamera '{camera_name}'.\n"
            "Descrivi brevemente e in modo naturale quello che vedi: ambiente, persone, oggetti, "
            "stato della scena. Sii conciso (2-3 frasi max). Rispondi in italiano."
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "Nessuna descrizione disponibile.").strip()
                    return f"Errore HTTP {response.status} da Ollama."
        except aiohttp.ClientConnectorError:
            return "Ollama non raggiungibile."
        except Exception as err:
            _LOGGER.error("describe_scene error: %s", err)
            return f"Errore: {err}"

    async def check_connection(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ollama_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        model_available = any(self.model in m for m in models)
                        if not model_available:
                            _LOGGER.warning(
                                "Ollama is online but model '%s' not found. Available: %s",
                                self.model,
                                models,
                            )
                        return True
                    return False
        except Exception:
            return False
