"""Notification Engine — notifiche intelligenti con dedup, aggregazione e presenza."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .const import (
    COOLDOWN_AWAY_DAY,
    COOLDOWN_AWAY_NIGHT,
    COOLDOWN_HOME_NIGHT,
    DEDUP_WINDOW,
    MAX_NOTIFICATIONS_PER_HOUR,
    THREAT_HIGH,
    THREAT_MEDIUM,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NotificationDecision:
    """Risultato della decisione di notifica."""
    should_notify: bool
    reason: str
    aggregated: bool = False


@dataclass
class NotificationState:
    """Stato interno del motore notifiche."""
    camera_cooldowns: dict[str, float] = field(default_factory=dict)
    event_fingerprints: dict[str, float] = field(default_factory=dict)
    hourly_log: list[tuple[float, str]] = field(default_factory=list)
    pending_digest: list[dict[str, Any]] = field(default_factory=list)
    silent_until: float = 0.0


class NotificationEngine:
    """
    Motore decisionale per notifiche intelligenti.

    Matrice:
    ┌────────┬─────────────────┬──────────────────┐
    │        │ Giorno          │ Notte            │
    ├────────┼─────────────────┼──────────────────┤
    │ Casa   │ MAI (solo log)  │ Solo HIGH        │
    │ Fuori  │ Solo HIGH       │ MEDIUM + HIGH    │
    └────────┴─────────────────┴──────────────────┘
    """

    def __init__(self) -> None:
        self._state = NotificationState()

    def evaluate(
        self,
        camera_entity: str,
        threat_level: str,
        is_home: bool,
        is_night: bool,
        analysis: dict[str, Any] | None = None,
    ) -> NotificationDecision:
        """Decide se inviare la notifica."""
        now = time.time()

        if now < self._state.silent_until:
            return NotificationDecision(
                should_notify=False,
                reason=f"silenzio globale ({int(self._state.silent_until - now)}s)",
            )

        if not self._passes_presence_filter(threat_level, is_home, is_night):
            reason = self._filter_reason(threat_level, is_home, is_night)
            _LOGGER.debug("Notifica soppressa: %s [%s]", camera_entity, reason)
            return NotificationDecision(should_notify=False, reason=reason)

        fp = self._fingerprint(camera_entity, threat_level)
        if fp in self._state.event_fingerprints:
            last_fp = self._state.event_fingerprints[fp]
            if (now - last_fp) < DEDUP_WINDOW:
                return NotificationDecision(
                    should_notify=False,
                    reason=f"duplicato ({int(now - last_fp)}s fa)",
                )

        cooldown = self._get_cooldown(is_home, is_night)
        last_cam = self._state.camera_cooldowns.get(camera_entity, 0)
        if (now - last_cam) < cooldown:
            return NotificationDecision(
                should_notify=False,
                reason=f"cooldown camera ({int(cooldown - (now - last_cam))}s)",
            )

        self._prune_hourly_log(now)
        if len(self._state.hourly_log) >= MAX_NOTIFICATIONS_PER_HOUR:
            if analysis:
                self._state.pending_digest.append(analysis)
            self._state.silent_until = now + 1800
            return NotificationDecision(
                should_notify=False,
                reason=f"rate limit ({MAX_NOTIFICATIONS_PER_HOUR}/ora), digest pendente",
                aggregated=True,
            )

        self._state.camera_cooldowns[camera_entity] = now
        self._state.event_fingerprints[fp] = now
        self._state.hourly_log.append((now, camera_entity))

        return NotificationDecision(should_notify=True, reason="approvata")

    def get_and_clear_digest(self) -> list[dict[str, Any]]:
        digest = self._state.pending_digest.copy()
        self._state.pending_digest.clear()
        return digest

    def force_reset(self) -> None:
        self._state = NotificationState()

    def cleanup_stale(self) -> None:
        now = time.time()
        self._state.event_fingerprints = {
            fp: ts for fp, ts in self._state.event_fingerprints.items()
            if (now - ts) < DEDUP_WINDOW
        }

    @staticmethod
    def _passes_presence_filter(threat_level: str, is_home: bool, is_night: bool) -> bool:
        if is_home and not is_night:
            return False
        if is_home and is_night:
            return threat_level == THREAT_HIGH
        if not is_home and not is_night:
            return threat_level == THREAT_HIGH
        return threat_level in (THREAT_MEDIUM, THREAT_HIGH)

    @staticmethod
    def _filter_reason(threat_level: str, is_home: bool, is_night: bool) -> str:
        stato = "casa" if is_home else "fuori"
        periodo = "notte" if is_night else "giorno"
        return f"{stato}+{periodo}: livello '{threat_level}' sotto soglia"

    @staticmethod
    def _get_cooldown(is_home: bool, is_night: bool) -> int:
        if not is_home and is_night:
            return COOLDOWN_AWAY_NIGHT
        if is_home and is_night:
            return COOLDOWN_HOME_NIGHT
        return COOLDOWN_AWAY_DAY

    @staticmethod
    def _fingerprint(camera_entity: str, threat_level: str) -> str:
        raw = f"{camera_entity}:{threat_level}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _prune_hourly_log(self, now: float) -> None:
        cutoff = now - 3600
        self._state.hourly_log = [
            (ts, cam) for ts, cam in self._state.hourly_log if ts > cutoff
        ]


def format_digest_message(events: list[dict[str, Any]]) -> str:
    """Formatta un messaggio digest aggregato."""
    if not events:
        return ""
    lines = [
        f"*Digest Sicurezza HomeMind AI*\n",
        f"_{len(events)} eventi aggregati:_\n",
    ]
    for ev in events[-5:]:
        emoji = "🔴" if ev.get("threat_level") == "high" else "🟠"
        cam = ev.get("camera", ev.get("camera_name", "?"))
        summary = ev.get("summary", "")[:80]
        lines.append(f"{emoji} {cam}: {summary}")
    if len(events) > 5:
        lines.append(f"\n_...e altri {len(events) - 5} eventi_")
    return "\n".join(lines)
