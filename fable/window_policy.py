"""Safety evaluation, confidence and backend diagnostic helpers."""

from __future__ import annotations

import datetime as dt
import statistics
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from .window_models import HourMetrics, Site, Thresholds, has_wind_range, worst_metrics_at_hour


def confidence_rank(value: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(value, 0)


def min_confidence(values: Sequence[str]) -> str:
    cleaned = [value for value in values if value]
    return min(cleaned, key=confidence_rank) if cleaned else "Low"


def compute_confidence(site: Site, start: int, end: int, th: Thresholds) -> str:
    spreads = []
    min_models = float("inf")
    min_wave_sources = float("inf")
    max_hs_spread = None
    for index in range(start, end + 1):
        metrics = worst_metrics_at_hour(site, index)
        if metrics.spread_speed is not None:
            spreads.append(metrics.spread_speed)
        min_models = min(min_models, metrics.n_models or 0)
        min_wave_sources = min(min_wave_sources, metrics.n_wave_sources or 0)
        if metrics.hs_spread is not None:
            max_hs_spread = (
                metrics.hs_spread
                if max_hs_spread is None
                else max(max_hs_spread, metrics.hs_spread)
            )
    if min_models < th.min_models_not_low:
        return "Low"
    average = statistics.mean(spreads) if spreads else None
    corroborated = (
        min_wave_sources >= th.min_wave_sources
        and max_hs_spread is not None
        and max_hs_spread < th.high_hs_spread_lt
    )
    if average is not None and average < th.high_wind_spread_lt and corroborated:
        return "High"
    if average is not None and average < th.medium_wind_spread_lt:
        return "Medium"
    return "Low"


def phases_for_window(length: int) -> list[str]:
    if length <= 1:
        return ["transit"] * max(length, 0)
    if length == 2:
        return ["transit", "transit"]
    return ["transit"] + ["anchor"] * (length - 2) + ["transit"]


def in_operating_light(site: Site, moment: dt.datetime, th: Thresholds) -> bool:
    local = (moment if moment.tzinfo else moment.replace(tzinfo=site.tz)).astimezone(site.tz)
    pair = site.daylight.get(local.date().isoformat()) if th.daylight_enabled else None
    if pair:
        start = pair[0] + dt.timedelta(minutes=th.daylight_after_sunrise_min)
        end = pair[1] - dt.timedelta(minutes=th.daylight_before_sunset_min)
        return start <= local < end
    return th.family_hour_start <= local.hour < th.family_hour_end


def all_in_operating_light(times: Sequence[dt.datetime], site: Site, th: Thresholds) -> bool:
    return all(in_operating_light(site, moment, th) for moment in times)


def shelter_validated(site: Site, metrics: HourMetrics) -> bool:
    return site.shelter_radius_km > 0 and metrics.any_onshore is False


def hard_reasons(metrics: HourMetrics, th: Thresholds) -> list[str]:
    reasons = []
    if metrics.max_speed is None or metrics.max_gust is None:
        reasons.append("vent_inconnu")
    if metrics.hs is None or metrics.tp is None:
        reasons.append("vagues_inconnues")
    if any(code in th.thunder_codes for code in metrics.codes):
        reasons.append("orages")
    if metrics.min_vis is not None and metrics.min_vis < th.vis_min_km:
        reasons.append(f"vis<{th.vis_min_km:g}km")
    if metrics.max_gust is not None and metrics.max_gust >= th.gust_no_go_min:
        reasons.append(f"rafales>={int(th.gust_no_go_min)}")
    if metrics.max_speed is not None and metrics.max_speed >= th.wind_no_go_min:
        reasons.append(f"vent>={int(th.wind_no_go_min)}")
    if metrics.max_gust is not None and metrics.min_speed is not None:
        if metrics.max_gust - metrics.min_speed >= th.squall_delta:
            reasons.append("squalls")
    if metrics.hs is not None and metrics.hs > th.hs_no_go_min:
        reasons.append(f"Hs>{th.hs_no_go_min}")
    if (
        metrics.hs is not None
        and metrics.tp is not None
        and metrics.hs >= th.short_steep_2_hs
        and metrics.tp <= th.short_steep_2_tp
    ):
        reasons.append("short_steep_hard")
    return reasons


def standard_wave_reasons(metrics: HourMetrics, th: Thresholds, sheltered: bool) -> list[str]:
    if metrics.hs is None or metrics.tp is None:
        return ["vagues_inconnues"]
    if sheltered and metrics.hs <= th.anchor_hs_ease_max:
        if metrics.tp >= th.anchor_tp_family:
            return []
        return [f"Tp<{th.anchor_tp_family}@Hs<={th.anchor_hs_ease_max}"]
    reasons = []
    if metrics.hs >= th.hs_family_max:
        reasons.append(f"Hs>={th.hs_family_max}")
    elif metrics.hs < 0.4 and metrics.tp < th.tp_min_at_lt04:
        reasons.append(f"Tp<{th.tp_min_at_lt04}@Hs<0.4")
    elif 0.4 <= metrics.hs < 0.5 and metrics.tp < th.tp_min_at_04_05:
        reasons.append(f"Tp<{th.tp_min_at_04_05}@Hs0.4-0.5")
    if metrics.hs >= th.short_steep_1_hs and metrics.tp <= th.short_steep_1_tp:
        reasons.append("short_steep")
    return reasons


def hour_ok_for_phase(
    site: Site,
    index: int,
    phase: str,
    th: Thresholds,
    tier: str = "family",
) -> tuple[bool, dict[str, Any]]:
    metrics = worst_metrics_at_hour(site, index)
    reasons = hard_reasons(metrics, th)
    sheltered = phase == "anchor" and shelter_validated(site, metrics)
    if not reasons and tier == "prudent":
        if metrics.any_onshore:
            reasons.append("prudent_onshore")
        if metrics.max_speed is not None and metrics.max_speed > th.prudent_wind_max:
            reasons.append(f"vent>{th.prudent_wind_max:g}@prudent")
        if metrics.max_gust is not None and metrics.max_gust >= th.prudent_gust_max:
            reasons.append(f"rafales>={th.prudent_gust_max:g}@prudent")
        if metrics.hs is not None and metrics.hs > th.prudent_hs_max:
            reasons.append(f"Hs>{th.prudent_hs_max:g}@prudent")
        if metrics.tp is not None and metrics.tp < th.prudent_tp_min:
            reasons.append(f"Tp<{th.prudent_tp_min:g}@prudent")
    elif not reasons:
        if metrics.max_speed is not None and metrics.any_onshore and metrics.max_speed > th.onshore_max_ok:
            reasons.append(f"onshore>{int(th.onshore_max_ok)}")
        if sheltered:
            if metrics.max_gust is not None and metrics.max_gust >= th.anchor_gust_allow:
                reasons.append(f"gusts>={int(th.anchor_gust_allow)}@anchor")
            if metrics.max_speed is not None and metrics.max_speed >= th.anchor_sustained_allow:
                reasons.append(f"vent>={int(th.anchor_sustained_allow)}@anchor")
        elif metrics.max_speed is not None and metrics.max_speed >= th.wind_family_max:
            reasons.append(f"vent>={int(th.wind_family_max)}")
        reasons.extend(standard_wave_reasons(metrics, th, sheltered))
    return not reasons, {
        "reasons": reasons,
        "metrics": metrics,
        "tier": tier,
        "shelter_validated": sheltered,
    }


def reason_text(code: str, metrics: HourMetrics | None = None) -> tuple[str, str]:
    fixed = {
        "orages": ("orage détecté", "thunderstorm detected"),
        "vent_inconnu": ("données de vent incomplètes", "incomplete wind data"),
        "vagues_inconnues": ("données de vagues ou de période incomplètes", "incomplete wave data"),
        "squalls": ("écart rafales/vent compatible avec une ligne de grains", "gust/wind spread indicates squalls"),
        "short_steep": ("mer courte et raide", "short and steep sea"),
        "short_steep_hard": ("mer courte et raide — veto dur", "short and steep sea — hard veto"),
        "prudent_onshore": ("vent onshore incompatible avec le GO prudent", "onshore wind incompatible with prudent GO"),
    }
    if code in fixed:
        return fixed[code]
    if code.startswith("vis<"):
        return f"visibilité inférieure à {code[4:]}", f"visibility below {code[4:]}"
    if code.startswith("rafales"):
        value = metrics.max_gust if metrics else None
        suffix = f" ({value:.0f} km/h)" if value is not None else ""
        return f"rafales trop fortes{suffix}", f"gusts too strong{suffix}"
    if code.startswith("vent") or code.startswith("onshore"):
        value = metrics.max_speed if metrics else None
        suffix = f" ({value:.0f} km/h)" if value is not None else ""
        return f"vent trop fort{suffix}", f"wind too strong{suffix}"
    if code.startswith("Hs"):
        value = metrics.hs if metrics else None
        suffix = f" ({value:.2f} m)" if value is not None else ""
        return f"hauteur de vague trop élevée{suffix}", f"wave height too high{suffix}"
    if code.startswith("Tp"):
        value = metrics.tp if metrics else None
        suffix = f" ({value:.1f} s)" if value is not None else ""
        return f"période de vague trop courte{suffix}", f"wave period too short{suffix}"
    return code.replace("_", " "), code.replace("_", " ")


def blocker(site: Site, index: int, stage: str, phase: str, detail: dict[str, Any]) -> dict[str, Any]:
    metrics = detail["metrics"]
    reasons = list(detail.get("reasons") or [])
    code = reasons[0] if reasons else "condition_inconnue"
    fr, en = reason_text(code, metrics)
    return {
        "stage": stage,
        "location_slug": f"{site.slug}.json",
        "location_name": site.name,
        "phase": phase,
        "time": site.times[index].isoformat() if index < len(site.times) else None,
        "reasons": reasons,
        "reason_fr": fr,
        "reason_en": en,
        "metrics": asdict(metrics),
        "tier": detail.get("tier"),
        "shelter_validated": bool(detail.get("shelter_validated", False)),
    }


def evaluate_window(
    home: Site,
    dest: Site,
    start: int,
    end: int,
    th: Thresholds,
    tier: str,
) -> tuple[bool, dict[str, Any]]:
    if end > min(len(home.times), len(dest.times)):
        return False, {
            "validated_hours": 0,
            "blocker": {
                "stage": "data",
                "location_slug": f"{dest.slug}.json",
                "location_name": dest.name,
                "phase": "window",
                "time": None,
                "reasons": ["forecast_horizon"],
                "reason_fr": "horizon météo insuffisant",
                "reason_en": "insufficient forecast horizon",
                "metrics": {},
                "tier": tier,
            },
        }
    if not has_wind_range(home, start, end - 1) or not has_wind_range(dest, start, end - 1):
        target = home if not has_wind_range(home, start, end - 1) else dest
        detail = hour_ok_for_phase(target, start, "transit", th, tier)[1]
        return False, {"validated_hours": 0, "blocker": blocker(target, start, "data", "transit", detail)}

    ok, detail = hour_ok_for_phase(home, start, "transit", th, tier)
    if not ok:
        return False, {"validated_hours": 0, "blocker": blocker(home, start, "departure", "transit", detail)}

    validated = 0
    phases = phases_for_window(end - start)
    for offset, index in enumerate(range(start, end)):
        phase = phases[offset]
        ok, detail = hour_ok_for_phase(dest, index, phase, th, tier)
        if not ok:
            return False, {
                "validated_hours": validated,
                "blocker": blocker(dest, index, "destination", phase, detail),
            }
        validated += 1

    ok, detail = hour_ok_for_phase(home, end - 1, "transit", th, tier)
    if not ok:
        return False, {
            "validated_hours": validated,
            "blocker": blocker(home, end - 1, "return", "transit", detail),
        }

    confidence = min_confidence([
        compute_confidence(home, start, end - 1, th),
        compute_confidence(dest, start, end - 1, th),
    ])
    daylight = all_in_operating_light(dest.times[start:end], dest, th)
    if tier == "prudent" and not daylight:
        return False, {
            "validated_hours": validated,
            "blocker": {
                "stage": "daylight",
                "location_slug": f"{dest.slug}.json",
                "location_name": dest.name,
                "phase": "window",
                "time": dest.times[start].isoformat(),
                "reasons": ["outside_daylight"],
                "reason_fr": "fenêtre en dehors de la plage de lumière sécurisée",
                "reason_en": "window outside the safe daylight range",
                "metrics": {},
                "tier": tier,
            },
        }
    if tier == "prudent" and confidence_rank(confidence) < confidence_rank(th.prudent_min_confidence):
        return False, {
            "validated_hours": validated,
            "blocker": {
                "stage": "confidence",
                "location_slug": f"{dest.slug}.json",
                "location_name": dest.name,
                "phase": "window",
                "time": dest.times[start].isoformat(),
                "reasons": ["confidence_too_low"],
                "reason_fr": f"confiance {confidence} insuffisante pour un GO prudent",
                "reason_en": f"{confidence} confidence is insufficient for a prudent GO",
                "metrics": {},
                "tier": tier,
            },
        }
    return True, {"validated_hours": validated, "confidence": confidence, "daylight": daylight}


def confidence_details(site: Site, start: int, end: int) -> dict[str, Any]:
    metrics = [worst_metrics_at_hour(site, index) for index in range(start, end)]
    spreads = [value.spread_speed for value in metrics if value.spread_speed is not None]
    hs_spreads = [value.hs_spread for value in metrics if value.hs_spread is not None]
    return {
        "min_wind_models_per_hour": min((value.n_models for value in metrics), default=0),
        "avg_wind_spread_kmh": round(statistics.mean(spreads), 2) if spreads else None,
        "min_wave_sources_per_hour": min((value.n_wave_sources for value in metrics), default=0),
        "max_hs_spread_m": round(max(hs_spreads), 3) if hs_spreads else None,
    }
