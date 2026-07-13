"""Directional one-way offshore crossing windows.

This module is intentionally separate from Family day-trip detection. A validated
one-way crossing never implies that the vessel must return to its home port on the
same day. Positioning to or from the relay port remains a separate operational
plan.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import asdict
from typing import Any

from .window_detect import route_transit_profile
from .window_models import Site, Thresholds
from .window_policy import (
    all_in_operating_light,
    blocker,
    compute_confidence,
    hour_ok_for_phase,
    min_confidence,
)


def _direction_windows(
    origin: Site,
    destination: Site,
    th: Thresholds,
    *,
    direction: str,
    crossing_hours: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return strict one-way transit windows and the best first blocker."""
    count = min(len(origin.times), len(destination.times))
    windows: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None

    for start in range(0, max(0, count - crossing_hours + 1)):
        end = start + crossing_hours
        failure = None
        validated = 0
        for index in range(start, end):
            ok_origin, origin_detail = hour_ok_for_phase(origin, index, "transit", th, "family")
            if not ok_origin:
                failure = blocker(origin, index, "departure", "transit", origin_detail)
                break
            ok_destination, destination_detail = hour_ok_for_phase(
                destination,
                index,
                "transit",
                th,
                "family",
            )
            if not ok_destination:
                failure = blocker(destination, index, "arrival", "transit", destination_detail)
                break
            validated += 1

        if failure:
            candidate = {"validated_hours": validated, "blocker": failure}
            if first_failure is None or validated > int(first_failure.get("validated_hours", -1)):
                first_failure = candidate
            continue

        daylight = all_in_operating_light(origin.times[start:end], origin, th) and all_in_operating_light(
            destination.times[start:end],
            destination,
            th,
        )
        confidence = min_confidence([
            compute_confidence(origin, start, end - 1, th),
            compute_confidence(destination, start, end - 1, th),
        ])
        windows.append({
            "start": origin.times[start].isoformat(),
            "end": (origin.times[end - 1] + dt.timedelta(hours=1)).isoformat(),
            "hours": crossing_hours,
            "confidence": confidence,
            "category": "family" if daylight else "off_hours",
            "family_tier": "family",
            "reason": "valid_OFFSHORE_ONE_WAY_rules",
            "trip_mode": "one_way_multi_day",
            "direction": direction,
            "origin_slug": f"{origin.slug}.json",
            "origin_name": origin.name,
            "destination_slug": f"{destination.slug}.json",
            "destination_name": destination.name,
            "same_day_round_trip_required": False,
            "return_window_required": False,
            "caution_fr": (
                "Traversée offshore beta : vérifier carburant, communications, formalités, "
                "équipement de sécurité et météo marine officielle avant départ."
            ),
            "caution_en": (
                "Beta offshore crossing: verify fuel, communications, formalities, safety equipment "
                "and official marine forecasts before departure."
            ),
        })
    return windows, first_failure


def detect_directional_crossings(
    relay: Site,
    offshore_destination: Site,
    th: Thresholds,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Evaluate relay↔offshore destination as two independent one-way trips."""
    minimum, maximum = route_transit_profile(relay, offshore_destination)
    crossing_hours = max(1, math.ceil(maximum))

    outbound, outbound_failure = _direction_windows(
        relay,
        offshore_destination,
        th,
        direction="outbound",
        crossing_hours=crossing_hours,
    )
    inbound, inbound_failure = _direction_windows(
        offshore_destination,
        relay,
        th,
        direction="return",
        crossing_hours=crossing_hours,
    )
    windows = outbound + inbound

    if windows:
        diagnostics = {
            "status": "available",
            "trip_mode": "one_way_multi_day",
            "same_day_round_trip_required": False,
            "outbound_windows": len(outbound),
            "return_windows": len(inbound),
            "required_crossing_hours": crossing_hours,
            "summary_fr": (
                "Fenêtres offshore aller simple publiées séparément pour l’aller et le retour. "
                "Aucun retour à Gammarth le même jour n’est exigé."
            ),
            "summary_en": (
                "One-way offshore windows are published separately for outbound and return trips. "
                "No same-day return to Gammarth is required."
            ),
        }
    else:
        failure = outbound_failure or inbound_failure or {}
        diagnostics = {
            "status": "blocked",
            "trip_mode": "one_way_multi_day",
            "same_day_round_trip_required": False,
            "outbound_windows": 0,
            "return_windows": 0,
            "required_crossing_hours": crossing_hours,
            "summary_fr": "Aucune fenêtre offshore aller simple validée dans l’horizon météo.",
            "summary_en": "No validated one-way offshore crossing in the forecast horizon.",
            "first_blocker": failure.get("blocker"),
            "near_miss": {
                "validated_hours": int(failure.get("validated_hours", 0)),
                "required_hours": crossing_hours,
                "tier_attempted": "family",
            },
        }

    profile = {
        "trip_mode": "one_way_multi_day",
        "same_day_round_trip_required": False,
        "relay_slug": f"{relay.slug}.json",
        "relay_name": relay.name,
        "offshore_slug": f"{offshore_destination.slug}.json",
        "offshore_name": offshore_destination.name,
        "crossing_distance_nm": round(
            ((minimum * float((offshore_destination.transit_speed_kts or {"max": 24})["max"]))),
            1,
        ),
        "transit_hours": {"fast": round(minimum, 2), "conservative": round(maximum, 2)},
        "crossing_hours_evaluated": crossing_hours,
        "directions": ["outbound", "return"],
        "positioning_note_fr": (
            "Le pré-positionnement Gammarth↔Kélibia est une étape séparée et n’impose pas "
            "un aller-retour complet dans la même journée."
        ),
        "positioning_note_en": (
            "Gammarth↔Kelibia positioning is a separate step and does not require a complete "
            "same-day round trip."
        ),
    }
    return windows, diagnostics, profile


def public_metrics(blocker_record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compatibility helper for callers that need JSON-safe blocker metrics."""
    if not blocker_record:
        return None
    result = dict(blocker_record)
    metrics = result.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        result["metrics"] = asdict(metrics)
    return result
