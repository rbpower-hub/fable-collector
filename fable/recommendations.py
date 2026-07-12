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


def _metrics(spot: dict[str, Any], start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    hourly = spot.get("hourly") or {}
    indices = _indices(hourly.get("time") or [], start, end)
    wind = _values(hourly, "wind_speed_10m", indices)
    gusts = _values(hourly, "wind_gusts_10m", indices)
    hs = _values(hourly, "hs", indices) or _values(hourly, "wave_height", indices)
    tp = _values(hourly, "tp", indices) or _values(hourly, "wave_period", indices)
    visibility = _values(hourly, "visibility", indices)
    visibility = [value / 1000 if value > 50 else value for value in visibility]
    return {
        "sample_hours": len(indices),
        "max_wind_kmh": round(max(wind), 1) if wind else None,
        "max_gust_kmh": round(max(gusts), 1) if gusts else None,
        "max_hs_m": round(max(hs), 2) if hs else None,
        "min_tp_s": round(min(tp), 1) if tp else None,
        "min_visibility_km": round(min(visibility), 1) if visibility else None,
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


def _period(start: dt.datetime, daily: dict[str, Any]) -> str:
    for key, name in (("sunrise", "sunrise"), ("sunset", "sunset")):
        target = _date(daily.get(key))
        if target is None:
            continue
        if target.tzinfo is None and start.tzinfo is not None:
            target = target.replace(tzinfo=start.tzinfo)
        if abs((start - target).total_seconds()) <= 7200:
            return name
    return "day"


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


def _score(
    activity_id: str,
    activity: dict[str, Any],
    metrics: dict[str, Any],
    fishing: dict[str, Any],
    period: str,
    moon: dict[str, Any],
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
        ("max_wind_kmh", "max_wind_kmh"),
        ("max_gust_kmh", "max_gust_kmh"),
        ("max_hs_m", "max_hs_m"),
    )
    score = 100.0
    blockers = []
    for metric_key, limit_key in limits:
        value, limit = _number(metrics.get(metric_key)), _number(safety.get(limit_key))
        if value is None or limit is None:
            continue
        if value > limit:
            blockers.append(f"{metric_key}>{limit}")
        else:
            score -= max(0, value / limit - 0.55) * 25
    tp, tp_min = _number(metrics.get("min_tp_s")), _number(safety.get("min_tp_s"))
    visibility = _number(metrics.get("min_visibility_km"))
    visibility_min = _number(safety.get("min_visibility_km"))
    if tp is not None and tp_min is not None and tp < tp_min:
        blockers.append(f"min_tp_s<{tp_min}")
    if visibility is not None and visibility_min is not None and visibility < visibility_min:
        blockers.append(f"visibility<{visibility_min}")
    if blockers:
        return None
    reasons_fr = ["fenêtre Family GO validée", "conditions compatibles avec les seuils de l’activité"]
    reasons_en = ["validated Family GO window", "conditions match the activity thresholds"]
    if period in fishing.get("preferred_periods", []):
        score += float(ranking.get("preferred_period_bonus", 7))
        reasons_fr.append("horaire favorable au profil saisonnier")
        reasons_en.append("favourable seasonal timing")
    lunar_bonus = 0.0
    if activity.get("lunar_sensitive") and moon.get("illumination_pct") is not None:
        illumination = float(moon["illumination_pct"])
        lunar_bonus = min(float(ranking.get("lunar_max_bonus", 5)), abs(illumination - 50) / 10)
        score += lunar_bonus
        reasons_fr.append("signal lunaire secondaire")
        reasons_en.append("secondary lunar signal")
    return {
        "activity_id": activity_id,
        "icon": activity.get("icon", "🌊"),
        "label_fr": activity.get("label_fr", activity_id),
        "label_en": activity.get("label_en", activity_id),
        "score": round(min(score, 100), 1),
        "why_fr": " · ".join(reasons_fr),
        "why_en": " · ".join(reasons_en),
        "lunar_bonus": round(lunar_bonus, 1),
    }


def _sources(root: Path) -> tuple[KnowledgePack | None, dict[str, Any], dict[str, Any]]:
    pack = load_knowledge_pack(root, strict=True)
    if pack is not None:
        activity = {"status": pack.status, "ranking": pack.ranking, "activities": pack.activities}
        return pack, activity, _yaml(root / "fishing_profiles.yaml")
    return None, _yaml(root / "activity_profiles.yaml"), _yaml(root / "fishing_profiles.yaml")


def build_recommendations(root: Path, public: Path) -> dict[str, Any]:
    pack, activity_cfg, fishing_cfg = _sources(root)
    windows = _json(public / "windows.json")
    profiles = fishing_cfg.get("profiles") or {}
    activities = activity_cfg.get("activities") or {}
    ranking = activity_cfg.get("ranking") or {}
    output = []
    no_go = []
    for destination in windows.get("windows") or []:
        filename = str(destination.get("dest_slug") or "")
        slug = filename.removesuffix(".json")
        destination_windows = destination.get("windows") or []
        if not destination_windows:
            no_go.append(
                {
                    "dest_slug": filename,
                    "dest_name": destination.get("dest_name"),
                    "reason_fr": "Aucune fenêtre Family GO validée.",
                    "reason_en": "No validated Family GO window.",
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
            ranked = []
            for activity_id, activity in activities.items():
                if not isinstance(activity, dict):
                    continue
                item = _score(
                    str(activity_id),
                    activity,
                    metrics,
                    fishing,
                    _period(start, daily),
                    moon,
                    ranking,
                )
                if item:
                    ranked.append(item)
            ranked.sort(key=lambda item: (-item["score"], item["activity_id"]))
            ranked = ranked[: int(ranking.get("max_per_window", 3))]
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
                            **moon,
                        },
                        "fishing": fishing,
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
            -(item.get("activities") or [{}])[0].get("score", 0),
        )
    )
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "version": 3 if pack and pack.version >= 2 else (2 if pack else 1),
        "source_windows_generated_at": windows.get("generated_at"),
        "safety_policy": "recommendations_only_inside_validated_family_go_windows",
        "profile_status": activity_cfg.get("status", "initial_tunable"),
        "knowledge_pack": pack.public_catalog() if pack else None,
        "recommendations": output[: int(ranking.get("max_total", 5))],
        "no_go": no_go,
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
