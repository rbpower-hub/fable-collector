"""Generate activity and fishing advice only inside validated Family GO windows."""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

from .knowledge import KnowledgePack, load_knowledge_pack


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _date(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None


PHASE_FR = {"transit": "traversée", "anchor": "au mouillage", "return": "retour"}
PHASE_EN = {"transit": "passage", "anchor": "at anchor", "return": "return leg"}


def _season(month: int) -> str:
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _indices(times: list[Any], start: dt.datetime, end: dt.datetime) -> list[int]:
    result = []
    for index, raw in enumerate(times):
        current = _date(raw)
        if current is None:
            continue
        if current.tzinfo is None and start.tzinfo is not None:
            current = current.replace(tzinfo=start.tzinfo)
        if start <= current < end:
            result.append(index)
    return result


def _values(hourly: dict[str, Any], key: str, indices: list[int]) -> list[float]:
    series = hourly.get(key)
    if not isinstance(series, list):
        return []
    result = []
    for index in indices:
        if index < len(series) and (value := _number(series[index])) is not None:
            result.append(value)
    return result


def _angle_in_sectors(angle: Any, sectors: Any) -> bool:
    value = _number(angle)
    if value is None or not isinstance(sectors, list):
        return False
    value %= 360
    for sector in sectors:
        if not isinstance(sector, (list, tuple)) or len(sector) < 2:
            continue
        low, high = _number(sector[0]), _number(sector[1])
        if low is None or high is None:
            continue
        low, high = low % 360, high % 360
        if (low <= value <= high) if low <= high else (value >= low or value <= high):
            return True
    return False


def _opposite_sectors(sectors: Any) -> list[list[float]]:
    """Secteur du vent de terre : l'onshore tourne de 180 degres.

    On ne prend pas `1 - onshore_share` : un vent parallele a la cote n'est ni
    onshore ni offshore, et la difference compte pour une petite embarcation.
    """
    result = []
    for sector in sectors if isinstance(sectors, list) else []:
        if not isinstance(sector, (list, tuple)) or len(sector) != 2:
            continue
        low, high = _number(sector[0]), _number(sector[1])
        if low is None or high is None:
            continue
        result.append([(low + 180) % 360, (high + 180) % 360])
    return result


def _metrics(spot: dict[str, Any], start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    hourly = spot.get("hourly") or {}
    indices = _indices(hourly.get("time") or [], start, end)
    wind = _values(hourly, "wind_speed_10m", indices)
    gusts = _values(hourly, "wind_gusts_10m", indices)
    hs = _values(hourly, "hs", indices) or _values(hourly, "wave_height", indices)
    tp = _values(hourly, "tp", indices) or _values(hourly, "wave_period", indices)
    visibility = _values(hourly, "visibility", indices)
    visibility = [value / 1000 if value > 50 else value for value in visibility]
    uv = _values(hourly, "uv_index", indices)
    apparent = _values(hourly, "apparent_temperature", indices)
    air = _values(hourly, "temperature_2m", indices)
    rain = _values(hourly, "precipitation", indices)
    sst = _values(hourly, "sea_surface_temperature", indices)

    # Part des heures ou le vent vient d'un secteur onshore du site : decisif
    # pour la clarte de l'eau et l'abri, jamais pour la securite.
    sectors = ((spot.get("meta") or {}).get("onshore_sectors")) or []
    offshore_sectors = _opposite_sectors(sectors)
    directions = _values(hourly, "wind_direction_10m", indices)
    onshore_hours = sum(1 for value in directions if _angle_in_sectors(value, sectors))
    offshore_hours = sum(1 for value in directions if _angle_in_sectors(value, offshore_sectors))
    onshore_share = round(onshore_hours / len(directions), 2) if directions else None
    offshore_share = round(offshore_hours / len(directions), 2) if directions else None

    return {
        "sample_hours": len(indices),
        "max_wind_kmh": round(max(wind), 1) if wind else None,
        "max_gust_kmh": round(max(gusts), 1) if gusts else None,
        "max_hs_m": round(max(hs), 2) if hs else None,
        "min_tp_s": round(min(tp), 1) if tp else None,
        "min_visibility_km": round(min(visibility), 1) if visibility else None,
        "max_uv_index": round(max(uv), 1) if uv else None,
        "max_apparent_temperature_c": round(max(apparent), 1) if apparent else None,
        "max_air_temperature_c": round(max(air), 1) if air else None,
        "total_precipitation_mm": round(sum(rain), 1) if rain else None,
        "sea_surface_temperature_c": round(sum(sst) / len(sst), 1) if sst else None,
        "onshore_share": onshore_share,
        "offshore_share": offshore_share,
    }


def _daily(spot: dict[str, Any], date: dt.date) -> dict[str, Any]:
    daily = spot.get("daily") or {}
    dates = [str(value)[:10] for value in daily.get("time") or []]
    try:
        index = dates.index(date.isoformat())
    except ValueError:
        return {}
    result = {}
    for key in ("sunrise", "sunset", "moonrise", "moonset", "moon_phase"):
        values = daily.get(key)
        if isinstance(values, list) and index < len(values):
            result[key] = values[index]
    return result


def _moon(phase: Any) -> dict[str, Any]:
    value = _number(phase)
    if value is None:
        return {"phase_fraction": None, "illumination_pct": None, "label_fr": None, "label_en": None}
    value %= 1
    illumination = round((1 - math.cos(2 * math.pi * value)) * 50)
    labels = [
        (0.03, "Nouvelle lune", "New moon"),
        (0.22, "Premier croissant", "Waxing crescent"),
        (0.28, "Premier quartier", "First quarter"),
        (0.47, "Lune gibbeuse croissante", "Waxing gibbous"),
        (0.53, "Pleine lune", "Full moon"),
        (0.72, "Lune gibbeuse décroissante", "Waning gibbous"),
        (0.78, "Dernier quartier", "Last quarter"),
        (0.97, "Dernier croissant", "Waning crescent"),
        (1.01, "Nouvelle lune", "New moon"),
    ]
    fr = en = None
    for limit, fr_label, en_label in labels:
        if value < limit:
            fr, en = fr_label, en_label
            break
    return {
        "phase_fraction": round(value, 3),
        "illumination_pct": illumination,
        "label_fr": fr,
        "label_en": en,
    }


def _aware(value: Any, reference: dt.datetime) -> dt.datetime | None:
    moment = _date(value)
    if moment is None:
        return None
    if moment.tzinfo is None and reference.tzinfo is not None:
        return moment.replace(tzinfo=reference.tzinfo)
    return moment


def _overlaps(start: dt.datetime, end: dt.datetime, low: dt.datetime, high: dt.datetime) -> bool:
    return start < high and low < end


def _window_periods(start: dt.datetime, end: dt.datetime, daily: dict[str, Any],
                    band_minutes: int = 90) -> list[str]:
    """Creneaux que la fenetre RECOUVRE, et non celui de son instant de depart.

    L'ancienne version classait sur le depart a deux heures pres : une fenetre
    15:00-19:00 couvrant un coucher a 18:54 sortait en `day` et perdait son
    bonus, tandis qu'une fenetre demarrant a 20:00, en pleine nuit, sortait en
    `sunset`.
    """
    band = dt.timedelta(minutes=band_minutes)
    sunrise = _aware(daily.get("sunrise"), start)
    sunset = _aware(daily.get("sunset"), start)
    periods: list[str] = []
    if sunrise and _overlaps(start, end, sunrise - band, sunrise + band):
        periods.append("sunrise")
    if sunset and _overlaps(start, end, sunset - band, sunset + band):
        periods.append("sunset")
    if sunrise and sunset and _overlaps(start, end, sunrise + band, sunset - band):
        periods.append("day")
    if sunrise and sunset and (start < sunrise - band or end > sunset + band):
        periods.append("night")
    if not periods:
        periods.append("day")
    return periods


def _daylight(daily: dict[str, Any], start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    """Part de la fenetre situee entre le lever et le coucher du soleil.

    Une fenetre hors horaires peut etre parfaite au sens meteo et courir en
    pleine nuit. Sans cette mesure, le moteur proposait une baignade familiale
    et du paddle a une heure du matin, avec 100/100.
    """
    sunrise = _aware(daily.get("sunrise"), start)
    sunset = _aware(daily.get("sunset"), start)
    if sunrise is None or sunset is None or end <= start:
        return {"available": False, "share": None, "sunrise": None, "sunset": None}
    low = max(start, sunrise)
    high = min(end, sunset)
    lit = max(0.0, (high - low).total_seconds())
    return {
        "available": True,
        "share": round(lit / (end - start).total_seconds(), 2),
        "sunrise": sunrise.strftime("%H:%M"),
        "sunset": sunset.strftime("%H:%M"),
    }


def _tide(spot: dict[str, Any], start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    """Marnage reel sur la fenetre, quand le niveau de la mer est publie.

    En Mediterranee tunisienne le marnage est faible : la phase lunaire est un
    proxy mediocre. Quand `sea_level_height_msl` est disponible on mesure le
    marnage au lieu de le deviner.
    """
    hourly = spot.get("hourly") or {}
    indices = _indices(hourly.get("time") or [], start, end)
    levels = _values(hourly, "sea_level_height_msl", indices)
    if len(levels) < 2:
        return {"available": False, "range_m": None, "trend": None}
    span = max(levels) - min(levels)
    delta = levels[-1] - levels[0]
    trend = "montante" if delta > 0.02 else "descendante" if delta < -0.02 else "etale"
    return {"available": True, "range_m": round(span, 3), "trend": trend}


def _moon_visible(daily: dict[str, Any], start: dt.datetime, end: dt.datetime) -> bool | None:
    """La lune est-elle au-dessus de l'horizon pendant la fenetre ?

    C'est la lumiere lunaire, pas la phase seule, qui compte pour les sorties
    nocturnes. moonrise / moonset etaient collectes sans jamais servir.
    """
    rise = _aware(daily.get("moonrise"), start)
    down = _aware(daily.get("moonset"), start)
    if rise is None and down is None:
        return None
    if rise is not None and down is not None:
        if rise <= down:
            return _overlaps(start, end, rise, down)
        return _overlaps(start, end, rise, end) or _overlaps(start, end, start, down)
    if rise is not None:
        return end > rise
    return start < down


def _label(record_id: str, records: dict[str, dict[str, Any]], language: str = "fr") -> str:
    record = records.get(record_id) or {}
    return str(record.get(f"label_{language}") or record.get("display_name") or record_id)


def _legacy_fishing(profile: dict[str, Any], season: str) -> dict[str, Any]:
    current = (profile.get("seasons") or {}).get(season) or {}
    return {
        "profile_confidence": profile.get("confidence"),
        "species": current.get("species") or [],
        "species_ids": [],
        "species_details": [],
        "techniques": current.get("techniques") or [],
        "technique_ids": [],
        "technique_details": [],
        "rigs": current.get("rigs") or [],
        "baits": current.get("baits") or [],
        "depths_m": current.get("depths_m") or profile.get("depths_m"),
        "preferred_periods": current.get("preferred_periods") or [],
        "habitats": profile.get("habitats") or [],
        "zones": profile.get("zones") or [],
        "intelligence_status": "legacy_profile",
    }


def _fish_detail(record_id: str, pack: KnowledgePack) -> dict[str, Any]:
    record = pack.fish.get(record_id) or {}
    return {
        "id": record_id,
        "label_fr": _label(record_id, pack.fish, "fr"),
        "label_en": _label(record_id, pack.fish, "en"),
        "status": record.get("status"),
        "taxonomy": record.get("taxonomy") or {},
        "habitats": record.get("habitats") or [],
        "depths_m": record.get("depths_m"),
        "preferred_periods": record.get("preferred_periods") or [],
        "targeting": record.get("targeting") or {},
        "validation": record.get("validation") or {},
    }


def _technique_detail(record_id: str, pack: KnowledgePack) -> dict[str, Any]:
    record = pack.techniques.get(record_id) or {}
    return {
        "id": record_id,
        "label_fr": _label(record_id, pack.techniques, "fr"),
        "label_en": _label(record_id, pack.techniques, "en"),
        "status": record.get("status"),
        "family": record.get("family"),
        "suitable_habitats": record.get("suitable_habitats") or [],
        "gear": record.get("gear") or {},
        "presentation": record.get("presentation") or [],
        "validation": record.get("validation") or {},
    }


def _knowledge_fishing(pack: KnowledgePack, slug: str, season: str) -> dict[str, Any]:
    port = pack.ports.get(slug) or {}
    current = (((port.get("fishing") or {}).get("seasons") or {}).get(season) or {})
    species_ids = [str(value) for value in current.get("species") or []]
    technique_ids = [str(value) for value in current.get("techniques") or []]
    species_details = [_fish_detail(record_id, pack) for record_id in species_ids]
    technique_details = [_technique_detail(record_id, pack) for record_id in technique_ids]
    return {
        "profile_confidence": port.get("confidence"),
        "species": [_label(record_id, pack.fish, "fr") for record_id in species_ids],
        "species_ids": species_ids,
        "species_details": species_details,
        "techniques": [_label(record_id, pack.techniques, "fr") for record_id in technique_ids],
        "technique_ids": technique_ids,
        "technique_details": technique_details,
        "rigs": current.get("rigs") or [],
        "baits": current.get("baits") or [],
        "depths_m": current.get("depths_m") or port.get("depths_m"),
        "preferred_periods": current.get("preferred_periods") or [],
        "habitats": port.get("habitats") or [],
        "zones": port.get("zones") or [],
        "intelligence_status": pack.status,
    }


def _nature(pack: KnowledgePack | None, slug: str, season: str) -> dict[str, Any]:
    """Contenu nature d'un port pour la saison en cours.

    Rien n'est produit ici quand le port ne declare pas de bloc `nature` : le
    pack ne contient que des observations sourcees, et une carte vide vaut
    mieux qu'un contenu invente pour remplir.
    """
    if pack is None:
        return {}
    port = pack.ports.get(slug) or {}
    nature = port.get("nature") or {}
    current = ((nature.get("seasons") or {}).get(season)) or {}
    if not current:
        return {}
    return {
        "status": nature.get("status"),
        "season": season,
        "headline_fr": current.get("headline_fr"),
        "headline_en": current.get("headline_en"),
        "detail_fr": current.get("detail_fr"),
        "detail_en": current.get("detail_en"),
        "look_for_fr": current.get("look_for_fr") or [],
        "notes_fr": nature.get("notes_fr"),
        "notes_en": nature.get("notes_en"),
        "sources": nature.get("sources") or [],
    }


def _fmt(value: Any, digits: int = 0, unit: str = "") -> str:
    number = _number(value)
    if number is None:
        return "—"
    text = f"{number:.{digits}f}".replace(".", ",")
    return f"{text}{unit}"


def advisories(metrics: dict[str, Any], context: dict[str, Any],
               limits: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Conseils de confort tires de donnees deja collectees.

    Ce sont des avertissements, jamais des blocages : la securite reste
    entierement du ressort du moteur de fenetres.
    """
    tuning = limits or {}
    uv_high = _number(tuning.get("uv_index_high")) or 7.0
    heat_high = _number(tuning.get("apparent_temperature_c_high")) or 38.0
    onshore_high = _number(tuning.get("onshore_share_high")) or 0.5
    offshore_high = _number(tuning.get("offshore_share_high")) or 0.5
    rain_min = _number(tuning.get("precipitation_mm")) or 0.5

    notes: list[dict[str, str]] = []
    uv = _number(metrics.get("max_uv_index"))
    if uv is not None and uv >= uv_high:
        notes.append({
            "id": "uv_high",
            "fr": f"Indice UV {_fmt(uv, 1)} sur la fenêtre : ombre, crème et tee-shirt pour les enfants.",
            "en": f"UV index {_fmt(uv, 1)} during the window: shade, sunscreen and a rash top for children.",
        })
    apparent = _number(metrics.get("max_apparent_temperature_c"))
    if apparent is not None and apparent >= heat_high:
        notes.append({
            "id": "heat",
            "fr": f"Ressenti jusqu’à {_fmt(apparent, 0, ' °C')} : eau à bord et pause à l’ombre.",
            "en": f"Feels like up to {_fmt(apparent, 0, ' °C')}: carry water and plan shade breaks.",
        })
    share = _number(metrics.get("onshore_share"))
    if share is not None and share >= onshore_high:
        notes.append({
            "id": "onshore",
            "fr": "Vent de mer sur la majorité de la fenêtre : eau plus trouble et clapot près du bord.",
            "en": "Onshore wind for most of the window: murkier water and chop close to shore.",
        })
    offshore = _number(metrics.get("offshore_share"))
    if offshore is not None and offshore >= offshore_high:
        # Les deux faces du vent de terre. Taire la derive serait trompeur :
        # c'est exactement la situation ou l'eau parait la plus engageante.
        notes.append({
            "id": "offshore",
            "fr": "Vent de terre : plan d’eau lissé et eau plus claire près du bord, "
                  "mais il pousse vers le large. Surveiller flotteurs, paddles et petites embarcations.",
            "en": "Offshore wind: flatter, clearer water near the shore, but it pushes seaward. "
                  "Keep an eye on floats, paddleboards and small craft.",
        })
    rain = _number(metrics.get("total_precipitation_mm"))
    if rain is not None and rain >= rain_min:
        notes.append({
            "id": "rain",
            "fr": f"Pluie attendue : {_fmt(rain, 1, ' mm')} cumulés sur la fenêtre.",
            "en": f"Rain expected: {_fmt(rain, 1, ' mm')} over the window.",
        })
    sst = _number(metrics.get("sea_surface_temperature_c"))
    if sst is not None:
        notes.append({
            "id": "sst",
            "fr": f"Eau à {_fmt(sst, 1, ' °C')}.",
            "en": f"Water at {_fmt(sst, 1, ' °C')}.",
        })
    tide = context.get("tide") or {}
    if tide.get("available") and _number(tide.get("range_m")) is not None:
        notes.append({
            "id": "tide",
            "fr": f"Marnage {_fmt(tide['range_m'], 2, ' m')} sur la fenêtre, marée {tide.get('trend')}.",
            "en": f"Tidal range {_fmt(tide['range_m'], 2, ' m')} over the window.",
        })
    return notes


def _lunar_or_tidal_bonus(context: dict[str, Any], ranking: dict[str, Any]) -> tuple[float, str, str]:
    """Bonus secondaire, jamais decisif pour la securite.

    Prefere le marnage mesure quand il est publie ; retombe sinon sur la phase
    lunaire, qui reste un proxy grossier sous ce climat de faible maree.
    """
    cap = float(ranking.get("lunar_max_bonus", 5))
    # Marnage donnant le bonus plein. Sous ce climat le marnage reste faible :
    # 0,25 m est deja une vive-eau marquee dans le golfe de Tunis.
    full = _number(ranking.get("tide_range_full_bonus_m")) or 0.25
    tide = context.get("tide") or {}
    span = _number(tide.get("range_m"))
    if tide.get("available") and span is not None:
        bonus = min(cap, cap * span / full) if full > 0 else 0.0
        return (
            round(bonus, 1),
            f"marnage mesuré {_fmt(span, 2, ' m')} ({tide.get('trend')})",
            f"measured tidal range {_fmt(span, 2, ' m')}",
        )
    moon = context.get("moon") or {}
    illumination = _number(moon.get("illumination_pct"))
    if illumination is None:
        return 0.0, "", ""
    bonus = min(cap, abs(illumination - 50) / 10)
    label = moon.get("label_fr") or "phase lunaire"
    detail_fr = f"{label.lower()}, illumination {_fmt(illumination, 0, ' %')}"
    if context.get("moon_visible") is False:
        detail_fr += ", lune sous l’horizon pendant la fenêtre"
    return round(bonus, 1), detail_fr, f"{moon.get('label_en') or 'moon phase'}, {_fmt(illumination, 0, '%')} lit"


def _score(
    activity_id: str,
    activity: dict[str, Any],
    metrics: dict[str, Any],
    fishing: dict[str, Any],
    context: dict[str, Any],
    ranking: dict[str, Any],
) -> dict[str, Any] | None:
    if activity.get("requires_fishing_profile") and not fishing.get("species"):
        return None
    allowed_techniques = {str(value) for value in activity.get("techniques") or []}
    available_techniques = set(fishing.get("technique_ids") or [])
    if allowed_techniques and available_techniques and not allowed_techniques.intersection(available_techniques):
        return None
    safety = activity.get("safety") or {}
    limits = (
        ("max_wind_kmh", "max_wind_kmh", 0, " km/h", "vent", "wind"),
        ("max_gust_kmh", "max_gust_kmh", 0, " km/h", "rafales", "gusts"),
        ("max_hs_m", "max_hs_m", 2, " m", "houle", "wave height"),
    )
    score = 100.0
    # Un depassement n'est plus jete : la carte doit pouvoir dire quelle limite
    # bloque et de combien, comme le fait deja le premier bloqueur d'un NO-GO.
    blockers: list[dict[str, Any]] = []
    margins = []
    for metric_key, limit_key, digits, unit, label, label_en in limits:
        value, limit = _number(metrics.get(metric_key)), _number(safety.get(limit_key))
        if value is None or limit is None:
            continue
        if value > limit:
            blockers.append({
                "metric": metric_key,
                "value": value,
                "limit": limit,
                "fr": f"{label} {_fmt(value, digits, unit)} pour une limite de {_fmt(limit, digits, unit)}",
                "en": f"{label_en} {_fmt(value, digits, unit)} against a {_fmt(limit, digits, unit)} limit",
                "over": value / limit if limit else float("inf"),
            })
        else:
            score -= max(0, value / limit - 0.55) * 25
            margins.append(f"{label} {_fmt(value, digits, unit)} pour une limite de {_fmt(limit, digits, unit)}")
    tp, tp_min = _number(metrics.get("min_tp_s")), _number(safety.get("min_tp_s"))
    visibility = _number(metrics.get("min_visibility_km"))
    visibility_min = _number(safety.get("min_visibility_km"))
    if tp is not None and tp_min is not None and tp < tp_min:
        blockers.append({
            "metric": "min_tp_s", "value": tp, "limit": tp_min,
            "fr": f"période de vague {_fmt(tp, 1, ' s')} pour un minimum de {_fmt(tp_min, 1, ' s')}",
            "en": f"wave period {_fmt(tp, 1, ' s')} against a {_fmt(tp_min, 1, ' s')} minimum",
            "over": (tp_min / tp) if tp else float("inf"),
        })
    if visibility is not None and visibility_min is not None and visibility < visibility_min:
        blockers.append({
            "metric": "min_visibility_km", "value": visibility, "limit": visibility_min,
            "fr": f"visibilité {_fmt(visibility, 0, ' km')} pour un minimum de {_fmt(visibility_min, 0, ' km')}",
            "en": f"visibility {_fmt(visibility, 0, ' km')} against a {_fmt(visibility_min, 0, ' km')} minimum",
            "over": (visibility_min / visibility) if visibility else float("inf"),
        })
    daylight = context.get("daylight") or {}
    share = _number(daylight.get("share"))
    if activity.get("requires_daylight") and daylight.get("available") and share is not None:
        needed = _number(activity.get("min_daylight_share")) or 0.5
        if share < needed:
            lit = f"jour de {daylight.get('sunrise')} à {daylight.get('sunset')}"
            blockers.append({
                "metric": "daylight_share", "value": share, "limit": needed,
                "fr": f"fenêtre de nuit ({_fmt(share * 100, 0, ' %')} de jour seulement, {lit})",
                "en": f"night-time window (only {_fmt(share * 100, 0, '%')} in daylight)",
                # Le manque de jour prime : c'est une condition d'existence de
                # l'activite, pas un depassement de seuil parmi d'autres.
                "over": float("inf"),
            })
    if blockers:
        # Le depassement le plus large en premier : c'est la contrainte qui
        # decide vraiment, les autres suivraient si on la levait.
        blockers.sort(key=lambda item: -item["over"])
        return {
            "blocked": True,
            "activity_id": activity_id,
            "icon": activity.get("icon", "🌊"),
            "label_fr": activity.get("label_fr", activity_id),
            "label_en": activity.get("label_en", activity_id),
            "reason_fr": blockers[0]["fr"],
            "reason_en": blockers[0]["en"],
            "blockers": blockers,
        }

    reasons_fr = ["fenêtre Family GO validée"]
    reasons_en = ["validated Family GO window"]
    if margins:
        reasons_fr.append(" · ".join(margins))
        reasons_en.append("conditions within the activity thresholds")

    periods = context.get("periods") or []
    preferred = [str(value) for value in fishing.get("preferred_periods") or []]
    matched = [value for value in periods if value in preferred]
    if matched:
        score += float(ranking.get("preferred_period_bonus", 7))
        names = {"sunrise": "lever du soleil", "sunset": "coucher du soleil", "day": "plein jour", "night": "nuit"}
        reasons_fr.append(f"la fenêtre couvre {names.get(matched[0], matched[0])}, favorable au profil de saison")
        reasons_en.append(f"window covers {matched[0]}, favourable for the seasonal profile")

    lunar_bonus = 0.0
    if activity.get("lunar_sensitive"):
        lunar_bonus, detail_fr, detail_en = _lunar_or_tidal_bonus(context, ranking)
        if detail_fr:
            score += lunar_bonus
            reasons_fr.append(detail_fr)
            reasons_en.append(detail_en)

    # Confort : penalise sans jamais bloquer, et seulement si l'activite le declare.
    comfort = activity.get("comfort") or {}
    caveats_fr, caveats_en = [], []
    for metric_key, limit_key, digits, unit, fr_label, en_label, as_share in (
        ("max_uv_index", "max_uv_index", 1, "", "indice UV", "UV index", False),
        ("max_apparent_temperature_c", "max_apparent_temperature_c", 0, " °C", "ressenti", "feels-like", False),
        ("onshore_share", "max_onshore_share", 0, "", "vent de mer", "onshore wind", True),
        ("offshore_share", "max_offshore_share", 0, "", "vent de terre", "offshore wind", True),
    ):
        value, limit = _number(metrics.get(metric_key)), _number(comfort.get(limit_key))
        if value is None or limit is None or value <= limit:
            continue
        score -= float(comfort.get("penalty", 8))
        if as_share:
            # « vent de mer sur 100 % de la fenetre » se lit ; « 1,00 » non.
            caveats_fr.append(
                f"{fr_label} sur {_fmt(value * 100, 0, ' %')} de la fenêtre "
                f"(confort visé : {_fmt(limit * 100, 0, ' %')})"
            )
            caveats_en.append(
                f"{en_label} over {_fmt(value * 100, 0, '%')} of the window "
                f"(comfort target: {_fmt(limit * 100, 0, '%')})"
            )
            continue
        caveats_fr.append(f"{fr_label} {_fmt(value, digits, unit)} au-dessus du confort visé ({_fmt(limit, digits, unit)})")
        caveats_en.append(f"{en_label} {_fmt(value, digits, unit)} above the comfort target")

    return {
        "activity_id": activity_id,
        "icon": activity.get("icon", "🌊"),
        "label_fr": activity.get("label_fr", activity_id),
        "label_en": activity.get("label_en", activity_id),
        "blocked": False,
        # Une activite tres tolerante marque mecaniquement un score eleve :
        # son seuil large rend le ratio valeur/limite petit. Sans ce rang,
        # l'observation nature passerait devant la peche un jour parfait.
        "tier": str(activity.get("tier") or "primary"),
        # `score` est borne pour l'affichage, `rank_score` ne l'est pas : deux
        # activites dont les bonus depassent 100 doivent rester departageables.
        "score": round(max(0.0, min(score, 100)), 1),
        "rank_score": round(score, 3),
        "why_fr": " · ".join(reasons_fr),
        "why_en": " · ".join(reasons_en),
        "caveats_fr": caveats_fr,
        "caveats_en": caveats_en,
        "lunar_bonus": round(lunar_bonus, 1),
        "periods": periods,
    }


def _sources(root: Path) -> tuple[KnowledgePack | None, dict[str, Any], dict[str, Any]]:
    pack = load_knowledge_pack(root, strict=True)
    if pack is not None:
        activity = {
            "status": pack.status,
            "ranking": pack.ranking,
            "advisories": pack.advisories,
            "activities": pack.activities,
        }
        return pack, activity, _yaml(root / "fishing_profiles.yaml")
    return None, _yaml(root / "activity_profiles.yaml"), _yaml(root / "fishing_profiles.yaml")



def _spread_by_day(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Repartit le plafond entre les jours au lieu de tronquer par date.

    Un simple `[:limit]` apres tri chronologique effacait en silence les jours
    suivants des qu'un jour portait assez de fenetres.
    """
    if limit <= 0 or len(items) <= limit:
        return items
    by_day: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_day.setdefault(str(item.get("start") or "")[:10], []).append(item)
    selected: list[dict[str, Any]] = []
    rank = 0
    while len(selected) < limit and any(rank < len(day) for day in by_day.values()):
        for day in by_day.values():
            if rank < len(day) and len(selected) < limit:
                selected.append(day[rank])
        rank += 1
    selected.sort(key=lambda item: str(item.get("start") or ""))
    return selected


def build_recommendations(root: Path, public: Path) -> dict[str, Any]:
    pack, activity_cfg, fishing_cfg = _sources(root)
    windows = _json(public / "windows.json")
    profiles = fishing_cfg.get("profiles") or {}
    activities = activity_cfg.get("activities") or {}
    ranking = activity_cfg.get("ranking") or {}
    advisory_limits = activity_cfg.get("advisories") or {}
    output = []
    no_go = []
    no_activity: list[dict[str, Any]] = []
    for destination in windows.get("windows") or []:
        filename = str(destination.get("dest_slug") or "")
        slug = filename.removesuffix(".json")
        destination_windows = destination.get("windows") or []
        if not destination_windows:
            # Le moteur connait deja le premier bloqueur : le repeter ici evite
            # d'afficher sept fois "aucune fenetre validee" sans dire pourquoi.
            diagnostics = destination.get("diagnostics") or {}
            blocker = diagnostics.get("first_blocker") or {}
            detail_fr = str(blocker.get("reason_fr") or "").strip()
            detail_en = str(blocker.get("reason_en") or "").strip()
            where = str(blocker.get("location_name") or "").strip()
            phase = str(blocker.get("phase") or "").strip()
            # Le lieu n'est cite que s'il differe de la destination : sur un
            # trajet direct, « a El Haouaria » pour El Haouaria n'apprend rien.
            if where and where == str(destination.get("dest_name") or "").strip():
                where = ""
            suffix_fr = ""
            suffix_en = ""
            if detail_fr:
                suffix_fr = f" Premier blocage : {detail_fr}"
                if where:
                    suffix_fr += f", à {where}"
                if phase:
                    suffix_fr += f" ({PHASE_FR.get(phase, phase)})"
                suffix_fr += "."
            if detail_en:
                suffix_en = f" First blocker: {detail_en}"
                if where:
                    suffix_en += f", at {where}"
                if phase:
                    suffix_en += f" ({PHASE_EN.get(phase, phase)})"
                suffix_en += "."
            no_go.append(
                {
                    "dest_slug": filename,
                    "dest_name": destination.get("dest_name"),
                    "required_hours": destination.get("required_hours"),
                    "reason_fr": "Aucune fenêtre Family GO validée." + suffix_fr,
                    "reason_en": "No validated Family GO window." + suffix_en,
                    "blocker": {
                        "location_name": blocker.get("location_name"),
                        "phase": blocker.get("phase"),
                        "time": blocker.get("time"),
                        "reasons": blocker.get("reasons") or [],
                        "reason_fr": blocker.get("reason_fr"),
                        "reason_en": blocker.get("reason_en"),
                    } if blocker else None,
                }
            )
            continue
        spot = _json(public / filename)
        profile = profiles.get(slug) or {}
        for window in destination_windows:
            start, end = _date(window.get("start")), _date(window.get("end"))
            if start is None or end is None:
                continue
            season = _season(start.month)
            metrics = _metrics(spot, start, end)
            daily = _daily(spot, start.date())
            moon = _moon(daily.get("moon_phase"))
            if pack and slug in pack.ports:
                fishing = _knowledge_fishing(pack, slug, season)
            else:
                fishing = _legacy_fishing(profile, season)
            nature = _nature(pack, slug, season)
            context = {
                "periods": _window_periods(start, end, daily),
                "tide": _tide(spot, start, end),
                "daylight": _daylight(daily, start, end),
                "moon": moon,
                "moon_visible": _moon_visible(daily, start, end),
            }
            window_advice = advisories(metrics, context, advisory_limits)
            ranked = []
            rejected = []
            for activity_id, activity in activities.items():
                if not isinstance(activity, dict):
                    continue
                item = _score(str(activity_id), activity, metrics, fishing, context, ranking)
                if not item:
                    continue
                (rejected if item.get("blocked") else ranked).append(item)
            # Tri sur le score non ecrete : deux activites a 100 a l'affichage
            # peuvent avoir 107 et 102 en interne, l'ordre doit le refleter.
            ranked.sort(key=lambda item: (
                0 if item["tier"] == "primary" else 1,
                -item["rank_score"],
                item["activity_id"],
            ))
            ranked = ranked[: int(ranking.get("max_per_window", 3))]
            # Les activites principales ecartees, dans l'ordre du depassement le
            # plus faible : c'est ce qui manquait le moins pour sortir.
            blocked_primary = []
            if not any(item["tier"] == "primary" for item in ranked) and rejected:
                rejected.sort(key=lambda item: item["blockers"][0]["over"])
                blocked_primary = [
                    {
                        "activity_id": item["activity_id"],
                        "icon": item["icon"],
                        "label_fr": item["label_fr"],
                        "label_en": item["label_en"],
                        "reason_fr": item["reason_fr"],
                        "reason_en": item["reason_en"],
                    }
                    for item in rejected[:2]
                ]
            if not ranked and rejected:
                # Fenetre Family GO ou aucune activite ne tient : on publie la
                # contrainte la plus proche d'etre satisfaite, c'est celle qui
                # explique le mieux pourquoi la journee est vide.
                no_activity.append(
                    {
                        "dest_slug": filename,
                        "dest_name": destination.get("dest_name")
                        or spot.get("meta", {}).get("name")
                        or slug,
                        "start": window.get("start"),
                        "end": window.get("end"),
                        "category": window.get("category"),
                        "closest": blocked_primary,
                        "advisories": window_advice,
                    }
                )
            if ranked:
                output.append(
                    {
                        "dest_slug": filename,
                        "dest_name": destination.get("dest_name")
                        or spot.get("meta", {}).get("name")
                        or slug,
                        "start": window.get("start"),
                        "end": window.get("end"),
                        "hours": window.get("hours"),
                        "confidence": window.get("confidence"),
                        "category": window.get("category"),
                        "season": season,
                        "metrics": metrics,
                        "astronomy": {
                            "sunrise": daily.get("sunrise"),
                            "sunset": daily.get("sunset"),
                            "moonrise": daily.get("moonrise"),
                            "moonset": daily.get("moonset"),
                            "moon_above_horizon": context["moon_visible"],
                            **moon,
                        },
                        "tide": context["tide"],
                        "daylight": context["daylight"],
                        "periods": context["periods"],
                        "advisories": window_advice,
                        "fishing": fishing,
                        "nature": nature,
                        "blocked_primary": blocked_primary,
                        "activities": ranked,
                        "method_note_fr": (
                            "Classement uniquement dans une fenêtre Family GO. "
                            "Les réglages de matériel sont indicatifs ; la lune ne neutralise jamais un NO-GO."
                        ),
                        "method_note_en": (
                            "Ranking only inside a Family GO window. Gear ranges are indicative; "
                            "the moon never overrides a NO-GO."
                        ),
                    }
                )
    output.sort(
        key=lambda item: (
            str(item.get("start") or ""),
            -(item.get("activities") or [{}])[0].get("rank_score", 0),
        )
    )
    output = _spread_by_day(output, int(ranking.get("max_total", 5)))
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "version": 3 if pack and pack.version >= 2 else (2 if pack else 1),
        "source_windows_generated_at": windows.get("generated_at"),
        "safety_policy": "recommendations_only_inside_validated_family_go_windows",
        "profile_status": activity_cfg.get("status", "initial_tunable"),
        "knowledge_pack": pack.public_catalog() if pack else None,
        "recommendations": output,
        "no_go": no_go,
        "no_activity": no_activity,
    }
    public.mkdir(parents=True, exist_ok=True)
    (public / "recommendations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if pack:
        (public / "knowledge.json").write_text(
            json.dumps(pack.public_catalog(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    repository = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    build_recommendations(repository, repository / "public")
