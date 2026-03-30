"""Costruisce il contesto real-time della casa per le query AI."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_SYSTEM_IGNORE_NAMES = ("cpu", "gpu", "processor", "system board", "zigbee", "zwave", "bluetooth")


def build_home_context(hass: HomeAssistant, cameras: list[str] | None = None) -> str:
    """
    Costruisce una stringa di contesto con lo stato attuale della casa.
    Usata come sistema di input per le query AI.
    """
    now = datetime.now()
    lines: list[str] = [
        f"🏠 STATO CASA — {now.strftime('%A %d/%m/%Y %H:%M')}",
        "",
    ]

    # --- Persone ---
    person_ids = hass.states.async_entity_ids("person")
    if person_ids:
        home_people = []
        away_people = []
        for eid in person_ids:
            state = hass.states.get(eid)
            if not state:
                continue
            name = state.attributes.get("friendly_name") or eid.replace("person.", "").replace("_", " ").title()
            if state.state in ("home", "Home", "casa"):
                home_people.append(name)
            else:
                away_people.append(name)
        if home_people:
            lines.append(f"👥 IN CASA: {', '.join(home_people)}")
        if away_people:
            lines.append(f"🚶 FUORI: {', '.join(away_people)}")
        if not home_people and not away_people:
            lines.append("👥 PERSONE: nessuna entità person configurata")
        lines.append("")

    # --- Allarme ---
    alarm_ids = hass.states.async_entity_ids("alarm_control_panel")
    if alarm_ids:
        lines.append("🔒 ALLARME:")
        for eid in alarm_ids:
            state = hass.states.get(eid)
            if state:
                name = state.attributes.get("friendly_name") or eid
                lines.append(f"  {name}: {state.state}")
        lines.append("")

    # --- Luci ---
    light_ids = hass.states.async_entity_ids("light")
    lights_on: list[str] = []
    lights_off_count = 0
    for eid in light_ids:
        state = hass.states.get(eid)
        if not state:
            continue
        name = state.attributes.get("friendly_name") or eid.replace("light.", "").replace("_", " ").title()
        if state.state == "on":
            brightness = state.attributes.get("brightness")
            pct = f" {int(brightness / 255 * 100)}%" if brightness else ""
            lights_on.append(f"  💡 {name}: accesa{pct}")
        else:
            lights_off_count += 1
    if lights_on or lights_off_count:
        lines.append(f"💡 LUCI ({len(lights_on)} accese / {lights_off_count} spente):")
        lines.extend(lights_on[:12])
        lines.append("")

    # --- Temperature ---
    temp_lines: list[str] = []
    for eid in hass.states.async_entity_ids("sensor"):
        state = hass.states.get(eid)
        if not state:
            continue
        if state.attributes.get("device_class") != "temperature":
            continue
        name = state.attributes.get("friendly_name") or eid
        name_lower = name.lower()
        if any(skip in name_lower for skip in _SYSTEM_IGNORE_NAMES):
            continue
        unit = state.attributes.get("unit_of_measurement", "°C")
        try:
            val = round(float(state.state), 1)
            temp_lines.append(f"  🌡️ {name}: {val}{unit}")
        except (ValueError, TypeError):
            pass
    if temp_lines:
        lines.append("🌡️ TEMPERATURE:")
        lines.extend(temp_lines[:8])
        lines.append("")

    # --- Clima / HVAC ---
    climate_ids = hass.states.async_entity_ids("climate")
    if climate_ids:
        lines.append("❄️ CLIMA/RISCALDAMENTO:")
        for eid in climate_ids[:6]:
            state = hass.states.get(eid)
            if not state:
                continue
            name = state.attributes.get("friendly_name") or eid
            cur = state.attributes.get("current_temperature")
            setpt = state.attributes.get("temperature")
            detail = ""
            if cur is not None:
                detail = f" (attuale {cur}°C"
                if setpt is not None:
                    detail += f", set {setpt}°C"
                detail += ")"
            lines.append(f"  {name}: {state.state}{detail}")
        lines.append("")

    # --- Tapparelle / Cover ---
    cover_ids = hass.states.async_entity_ids("cover")
    if cover_ids:
        lines.append("🪟 TAPPARELLE/COVER:")
        for eid in cover_ids[:10]:
            state = hass.states.get(eid)
            if not state:
                continue
            name = state.attributes.get("friendly_name") or eid.replace("cover.", "").replace("_", " ").title()
            pos = state.attributes.get("current_position")
            pos_str = f" ({pos}%)" if pos is not None else ""
            lines.append(f"  {name}: {state.state}{pos_str}")
        lines.append("")

    # --- Switch rilevanti ---
    switch_ids = hass.states.async_entity_ids("switch")
    switch_lines: list[str] = []
    _skip_switch = ("zigbee", "zwave", "update", "restart", "debug", "firmware")
    for eid in switch_ids:
        state = hass.states.get(eid)
        if not state:
            continue
        name = state.attributes.get("friendly_name") or eid
        if any(s in name.lower() for s in _skip_switch):
            continue
        icon = "🔌" if state.state == "on" else "⭕"
        switch_lines.append(f"  {icon} {name}: {state.state}")
    if switch_lines:
        lines.append("🔌 SWITCH:")
        lines.extend(switch_lines[:10])
        lines.append("")

    # --- Porte e Finestre ---
    door_lines: list[str] = []
    for eid in hass.states.async_entity_ids("binary_sensor"):
        state = hass.states.get(eid)
        if not state:
            continue
        dc = state.attributes.get("device_class", "")
        if dc in ("door", "window", "garage_door"):
            name = state.attributes.get("friendly_name") or eid
            icon = "🚪" if dc in ("door", "garage_door") else "🪟"
            status = "APERTO ⚠️" if state.state == "on" else "chiuso"
            door_lines.append(f"  {icon} {name}: {status}")
    if door_lines:
        lines.append("🚪 PORTE E FINESTRE:")
        lines.extend(door_lines[:8])
        lines.append("")

    # --- Movimento attivo ---
    motion_active: list[str] = []
    for eid in hass.states.async_entity_ids("binary_sensor"):
        state = hass.states.get(eid)
        if not state or state.state != "on":
            continue
        dc = state.attributes.get("device_class", "")
        if dc in ("motion", "occupancy", "vibration"):
            name = state.attributes.get("friendly_name") or eid
            motion_active.append(f"  🔴 {name}")
    if motion_active:
        lines.append("⚠️ MOVIMENTO RILEVATO ORA:")
        lines.extend(motion_active[:6])
        lines.append("")

    # --- Telecamere configurate ---
    cam_ids = cameras or hass.states.async_entity_ids("camera")
    if cam_ids:
        cam_names: list[str] = []
        for eid in cam_ids:
            state = hass.states.get(eid)
            name = state.attributes.get("friendly_name") or eid if state else eid
            cam_names.append(name)
        lines.append(f"📷 TELECAMERE: {', '.join(cam_names)}")
        lines.append("")

    # --- Aree HA (se disponibili) ---
    try:
        area_registry = hass.helpers.area_registry.async_get(hass)
        areas = list(area_registry.areas.values())
        if areas:
            area_names = [a.name for a in areas[:10]]
            lines.append(f"🏘️ ZONE/AREE: {', '.join(area_names)}")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)
