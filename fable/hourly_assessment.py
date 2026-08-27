"""Publish engine-owned, single-hour condition assessments for chart clients.

These records deliberately describe one hour of conditions.  They are not
navigation-window decisions: duration, departure/return and route checks still
belong to the window detector.
"""

from __future__ import annotations

from typing import Any

from .util import angle_in_ranges
from .window_models import HourMetrics, Site, Thresholds, worst_metrics_at_hour
from .window_policy import (
    blocking_wave_scenario,
    compute_confidence,
    hard_reasons,
    hour_ok_for_phase,
    in_operating_light,
    reason_text,
    standard_wave_reasons,
    watch_hour_assessment,
)


def _round(value: Any, digits: int = 2) -> float | None:
    return round(float(value), digits) if isinstance(value, (int, float)) else None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _display_wind_scenario(metrics: HourMetrics, th: Thresholds) -> dict[str, Any] | None:
    """Choose one physically paired wind/gust scenario for the main chart."""
    if not metrics.wind_scenarios:
        return None

    def risk(scenario: dict[str, Any]) -> tuple[float, float, float]:
        speed = float(scenario["speed"])
        gust = float(scenario["gust"])
        delta = float(scenario["gust_delta"])
        return (
            max(gust / th.gust_no_go_min, speed / th.wind_no_go_min, delta / th.squall_delta),
            gust,
            speed,
        )

    return max(metrics.wind_scenarios, key=risk)


def _display_wave_scenario(
    metrics: HourMetrics,
    reasons: list[str],
    th: Thresholds,
) -> dict[str, Any] | None:
    blocking = blocking_wave_scenario(metrics, reasons, th)
    if blocking:
        return blocking
    valid = [scenario for scenario in metrics.wave_scenarios if scenario.get("tp") is not None]
    return max(valid, key=lambda scenario: (scenario["hs"], -scenario["tp"])) if valid else None


def _cause(code: str, metrics: HourMetrics, hard_codes: set[str], th: Thresholds) -> dict[str, Any]:
    wave = blocking_wave_scenario(metrics, [code], th)
    pair = {"hs": wave["hs"], "tp": wave.get("tp")} if wave else None
    reason_fr, reason_en = reason_text(code, metrics, pair)
    return {
        "code": code,
        "severity": "hard_veto" if code in hard_codes else "family_limit",
        "reason_fr": reason_fr,
        "reason_en": reason_en,
        "source": wave.get("source") if wave else None,
        "wave_pair": pair,
    }


def _all_transit_family_reasons(metrics: HourMetrics, th: Thresholds) -> list[str]:
    """Collect hard vetoes and softer Family failures without short-circuiting."""
    reasons = hard_reasons(metrics, th)
    if metrics.max_speed is not None and metrics.any_onshore and metrics.max_speed > th.onshore_max_ok:
        reasons.append(f"onshore>{int(th.onshore_max_ok)}")
    if metrics.max_speed is not None and metrics.max_speed >= th.wind_family_max:
        reasons.append(f"vent>={int(th.wind_family_max)}")
    reasons.extend(standard_wave_reasons(metrics, th, sheltered=False))
    return _unique(reasons)


def assess_hour(site: Site, index: int, th: Thresholds) -> dict[str, Any]:
    """Return one conservative transit-phase assessment for a destination hour."""
    metrics = worst_metrics_at_hour(site, index)
    hard_codes = set(hard_reasons(metrics, th))
    family_ok, family = hour_ok_for_phase(site, index, "transit", th, "family")
    prudent_ok, prudent = hour_ok_for_phase(site, index, "transit", th, "prudent")
    watch_ok, watch = watch_hour_assessment(site, index, "transit", th)

    if family_ok:
        state = "family"
        outcome_codes: list[str] = []
    elif th.prudent_enabled and prudent_ok:
        state = "prudent"
        outcome_codes = list(family.get("reasons") or [])
    elif th.watch_enabled and watch_ok and watch.get("margins"):
        state = "watch"
        outcome_codes = list(family.get("reasons") or [])
    else:
        state = "no_go"
        outcome_codes = _unique(
            _all_transit_family_reasons(metrics, th) + list(watch.get("reasons") or [])
        )

    display_wind = _display_wind_scenario(metrics, th)
    display_wave = _display_wave_scenario(metrics, outcome_codes, th)
    display_direction = _round(display_wind.get("direction"), 1) if display_wind else None

    return {
        "time": site.times[index].isoformat(),
        "scope": "single_hour_conditions",
        "phase": "transit",
        "condition_state": state,
        "is_window_decision": False,
        "hard_veto": bool(hard_codes),
        "operating_light": in_operating_light(site, site.times[index], th),
        "confidence": compute_confidence(site, index, index, th),
        "reasons": [_cause(code, metrics, hard_codes, th) for code in outcome_codes],
        "margins": list(watch.get("margins") or []) if state == "watch" else [],
        "metrics": {
            "wind": {
                "max_speed_kmh": _round(metrics.max_speed),
                "max_gust_kmh": _round(metrics.max_gust),
                "model_spread_kmh": _round(metrics.spread_speed),
                "model_count": metrics.n_models,
                "display_source": display_wind.get("source") if display_wind else None,
                "display_speed_kmh": _round(display_wind.get("speed")) if display_wind else None,
                "display_gust_kmh": _round(display_wind.get("gust")) if display_wind else None,
                "display_gust_delta_kmh": _round(display_wind.get("gust_delta")) if display_wind else None,
                "display_direction_deg": display_direction,
                "display_onshore": (
                    angle_in_ranges(float(display_direction), site.onshore_sectors)
                    if display_direction is not None
                    else None
                ),
            },
            "wave": {
                "hs_spread_m": _round(metrics.hs_spread, 3),
                "source_count": metrics.n_wave_sources,
                "display_source": display_wave.get("source") if display_wave else None,
                "display_hs_m": _round(display_wave.get("hs"), 3) if display_wave else None,
                "display_tp_s": _round(display_wave.get("tp"), 2) if display_wave else None,
            },
            "visibility_min_km": _round(metrics.min_vis),
            "weather_codes": list(metrics.codes),
        },
    }


def build_hourly_assessment(site: Site, th: Thresholds) -> list[dict[str, Any]]:
    return [assess_hour(site, index, th) for index in range(len(site.times))]
