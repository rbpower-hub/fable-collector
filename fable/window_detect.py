"""Window detection, adaptive duration, composite routing and publication."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from pathlib import Path
from typing import Any

from .config import load_rules, window_bounds
from .util import slugify
from .window_models import Site, Thresholds, load_site
from .window_policy import (
    all_in_operating_light,
    compute_confidence,
    confidence_details,
    evaluate_window,
    hour_ok_for_phase,
    min_confidence,
)

log = logging.getLogger("fable.windows")

NON_SPOT_FILES = {
    "index.json",
    "index.spots.json",
    "windows.json",
    "catalog.json",
    "status.json",
    "rules.normalized.json",
    "sites.normalized.json",
    "config.normalized.json",
    "recommendations.json",
    "knowledge.json",
}


def _window_record(
    home: Site,
    dest: Site,
    start: int,
    end: int,
    tier: str,
    evaluation: dict[str, Any],
    th: Thresholds,
) -> dict[str, Any]:
    category = "family" if evaluation["daylight"] else "off_hours"
    record = {
        "start": dest.times[start].isoformat(),
        "end": (dest.times[end - 1] + dt.timedelta(hours=1)).isoformat(),
        "hours": end - start,
        "confidence": evaluation["confidence"],
        "confidence_details": confidence_details(dest, start, end),
        "category": category,
        "family_tier": tier,
        "reason": (
            "valid_FAMILY_PRUDENT_rules"
            if tier == "prudent"
            else "valid_FAMILY_rules" + ("" if category == "family" else "_outside_daylight")
        ),
    }
    if tier == "prudent":
        _, standard = evaluate_window(home, dest, start, end, th, "family")
        blocker = standard.get("blocker") or {}
        record["cautions"] = blocker.get("reasons") or ["comfort_margin_reduced"]
        record["caution_fr"] = (
            "Confort réduit : fenêtre acceptée uniquement avec les limites prudentes, "
            "retour anticipé recommandé si les conditions se renforcent."
        )
        record["caution_en"] = (
            "Reduced comfort: accepted only under prudent limits; return early if conditions strengthen."
        )
    return record


def _summary(dest: Site, failure: dict[str, Any] | None, min_h: int) -> dict[str, Any]:
    blocker = (failure or {}).get("blocker")
    summary_fr = "Aucune fenêtre Family GO validée."
    summary_en = "No validated Family GO window."
    if blocker:
        stage_fr = {
            "departure": "départ",
            "destination": "destination",
            "return": "retour",
            "confidence": "confiance",
            "daylight": "lumière",
            "data": "données",
        }
        stage_en = {
            "departure": "departure",
            "destination": "destination",
            "return": "return",
            "confidence": "confidence",
            "daylight": "daylight",
            "data": "data",
        }
        stage = str(blocker.get("stage") or "destination")
        name = blocker.get("location_name") or dest.name
        summary_fr = (
            f"{stage_fr.get(stage, stage).capitalize()} bloqué à {name} : "
            f"{blocker.get('reason_fr') or 'condition défavorable'}."
        )
        summary_en = (
            f"{stage_en.get(stage, stage).capitalize()} blocked at {name}: "
            f"{blocker.get('reason_en') or 'unfavourable condition'}."
        )
    return {
        "status": "blocked",
        "first_blocker": blocker,
        "near_miss": {
            "validated_hours": int((failure or {}).get("validated_hours", 0)),
            "required_hours": min_h,
            "tier_attempted": (failure or {}).get("tier_attempted"),
        },
        "summary_fr": summary_fr,
        "summary_en": summary_en,
    }


def detect_windows_detailed(
    home: Site,
    dest: Site,
    min_h: int,
    max_h: int,
    th: Thresholds,
    *,
    allow_prudent: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    count = min(len(dest.times), len(home.times))
    windows = []
    best_failure = None
    standard_count = 0
    prudent_count = 0
    index = 0

    while index < count:
        selected = None
        for tier in ("family", "prudent"):
            if tier == "prudent" and (not allow_prudent or not th.prudent_enabled):
                continue
            for length in range(max_h, min_h - 1, -1):
                end = index + length
                ok, evaluation = evaluate_window(home, dest, index, end, th, tier)
                if ok:
                    selected = (end, tier, evaluation)
                    break
                candidate = {
                    "validated_hours": int(evaluation.get("validated_hours", 0)),
                    "required_hours": min_h,
                    "tier_attempted": tier,
                    "blocker": evaluation.get("blocker"),
                }
                if best_failure is None or candidate["validated_hours"] > best_failure["validated_hours"]:
                    best_failure = candidate
            if selected:
                break

        if selected:
            end, tier, evaluation = selected
            windows.append(_window_record(home, dest, index, end, tier, evaluation, th))
            if tier == "prudent":
                prudent_count += 1
            else:
                standard_count += 1
            index = end
        else:
            index += 1

    if windows:
        diagnostics = {
            "status": "available",
            "standard_windows": standard_count,
            "prudent_windows": prudent_count,
            "required_hours": min_h,
        }
    else:
        diagnostics = _summary(dest, best_failure, min_h)
    return windows, diagnostics


def detect_windows(home: Site, dest: Site, min_h: int, max_h: int, th: Thresholds) -> list[dict[str, Any]]:
    """Backward-compatible strict detector used by existing tests and callers."""
    return detect_windows_detailed(home, dest, min_h, max_h, th, allow_prudent=False)[0]


def _distance_km(a: dict[str, float], b: dict[str, float]) -> float:
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    d_lat = lat2 - lat1
    d_lon = math.radians(float(b["lon"]) - float(a["lon"]))
    value = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def route_distance_km(origin: Site, dest: Site) -> float:
    points = [{"lat": origin.lat, "lon": origin.lon}]
    points.extend({"lat": point["lat"], "lon": point["lon"]} for point in dest.route_points)
    points.append({"lat": dest.lat, "lon": dest.lon})
    return sum(_distance_km(points[index - 1], points[index]) for index in range(1, len(points)))


def route_transit_profile(origin: Site, dest: Site) -> tuple[float, float]:
    speed = dest.transit_speed_kts or {"min": 16.0, "max": 24.0}
    distance_nm = route_distance_km(origin, dest) / 1.852
    return distance_nm / float(speed["max"]), distance_nm / float(speed["min"])


def adaptive_min_hours(home: Site, dest: Site, configured_min: int, th: Thresholds) -> int:
    if not th.adaptive_enabled:
        return configured_min
    _, slow_hours = route_transit_profile(home, dest)
    required = math.ceil(2 * slow_hours + th.adaptive_zone_min_h)
    return max(th.adaptive_absolute_min_h, required)


def _route_site_key(point: dict[str, Any], sites: dict[str, Site]) -> str | None:
    slug = point.get("slug")
    if slug and f"{slug}.json" in sites:
        return f"{slug}.json"
    name = point.get("name")
    if name and f"{slugify(name)}.json" in sites:
        return f"{slugify(name)}.json"
    lat, lon = point.get("lat"), point.get("lon")
    if lat is None or lon is None:
        return None
    for filename, site in sites.items():
        if abs(site.lat - float(lat)) < 0.02 and abs(site.lon - float(lon)) < 0.02:
            return filename
    return None


def route_checkpoints(origin: Site, dest: Site, sites: dict[str, Site]) -> list[Site]:
    checkpoints = [origin]
    for point in dest.route_points:
        key = _route_site_key(point, sites)
        if key and all(current.path != sites[key].path for current in checkpoints):
            checkpoints.append(sites[key])
    if all(current.path != dest.path for current in checkpoints):
        checkpoints.append(dest)
    return checkpoints


def detect_transfer_windows(
    origin: Site,
    dest: Site,
    checkpoints: list[Site],
    th: Thresholds,
) -> list[dict[str, Any]]:
    if not checkpoints:
        return []
    minimum, maximum = route_transit_profile(origin, dest)
    span = max(1, math.ceil(maximum))
    count = min(len(site.times) for site in checkpoints)
    windows = []
    for start in range(0, max(0, count - span + 1)):
        end = start + span
        confidences = []
        valid = True
        for site in checkpoints:
            for index in range(start, end):
                ok, _ = hour_ok_for_phase(site, index, "transit", th, "family")
                if not ok:
                    valid = False
                    break
            if not valid:
                break
            confidences.append(compute_confidence(site, start, end - 1, th))
        if valid:
            start_dt = origin.times[start]
            windows.append({
                "start": start_dt.isoformat(),
                "arrival_earliest": (start_dt + dt.timedelta(hours=minimum)).isoformat(),
                "arrival_latest": (start_dt + dt.timedelta(hours=maximum)).isoformat(),
                "hours": {"min": round(minimum, 2), "max": round(maximum, 2)},
                "confidence": min_confidence(confidences),
                "category": (
                    "family"
                    if all_in_operating_light(origin.times[start:end], origin, th)
                    else "off_hours"
                ),
                "family_tier": "family",
                "checkpoints": [site.slug for site in checkpoints],
            })
    return windows


def combine_composite_windows(
    home: Site,
    relay: Site,
    dest: Site,
    transfer_windows: list[dict[str, Any]],
    offshore_windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for offshore in offshore_windows:
        start = dt.datetime.fromisoformat(offshore["start"])
        eligible = [
            transfer
            for transfer in transfer_windows
            if dt.datetime.fromisoformat(transfer["arrival_latest"]) <= start
        ]
        if not eligible:
            continue
        transfer = max(eligible, key=lambda item: item["arrival_latest"])
        arrival = dt.datetime.fromisoformat(transfer["arrival_latest"])
        staging = max(0.0, (start - arrival).total_seconds() / 3600)
        output.append({
            **offshore,
            "confidence": min_confidence([
                offshore.get("confidence", "Low"),
                transfer.get("confidence", "Low"),
            ]),
            "category": (
                "family"
                if offshore.get("category") == "family" and transfer.get("category") == "family"
                else "off_hours"
            ),
            "reason": "valid_composite_beta",
            "composite": {
                "transfer_origin": f"{home.slug}.json",
                "route_origin": f"{relay.slug}.json",
                "transfer_start": transfer["start"],
                "transfer_arrival_earliest": transfer["arrival_earliest"],
                "transfer_arrival_latest": transfer["arrival_latest"],
                "transfer_hours": transfer["hours"],
                "transfer_confidence": transfer["confidence"],
                "transfer_category": transfer["category"],
                "offshore_start": offshore["start"],
                "offshore_end": offshore["end"],
                "offshore_hours": offshore.get("hours"),
                "offshore_confidence": offshore.get("confidence", "Low"),
                "offshore_category": offshore.get("category"),
                "staging_hours": round(staging, 2),
            },
        })
    return output


def composite_diagnostics(
    dest: Site,
    transfers: list[dict[str, Any]],
    offshore: list[dict[str, Any]],
    combined: list[dict[str, Any]],
) -> dict[str, Any]:
    if combined:
        return {"status": "available", "standard_windows": len(combined), "prudent_windows": 0}
    if not transfers:
        fr, en, stage = (
            "Étape de transfert vers le port relais non validée.",
            "Transfer stage to the relay port is not validated.",
            "transfer",
        )
    elif not offshore:
        fr, en, stage = (
            "Fenêtre offshore depuis le port relais non validée.",
            "Offshore window from the relay port is not validated.",
            "offshore",
        )
    else:
        fr, en, stage = (
            "Les fenêtres de transfert et offshore ne s’alignent pas.",
            "Transfer and offshore windows do not align.",
            "alignment",
        )
    return {
        "status": "blocked",
        "summary_fr": fr,
        "summary_en": en,
        "first_blocker": {
            "stage": stage,
            "location_slug": f"{dest.slug}.json",
            "location_name": dest.name,
            "phase": "composite",
            "time": None,
            "reasons": [stage],
            "reason_fr": fr,
            "reason_en": en,
            "metrics": {},
            "tier": "family",
        },
        "near_miss": {"validated_hours": 0, "required_hours": None, "tier_attempted": "family"},
    }


def _load_sites(from_dir: Path) -> dict[str, Site]:
    sites = {}
    candidates = sorted(
        path
        for path in from_dir.glob("*.json")
        if path.name not in NON_SPOT_FILES and not path.name.startswith("_debug-")
    )
    for path in candidates:
        try:
            site = load_site(path)
        except Exception as exc:  # noqa: BLE001
            log.warning("skipped (unreadable) %s: %s", path.name, exc)
            continue
        if site is not None:
            sites[path.name] = site
    return sites


def _home_slug(from_dir: Path, sites: dict[str, Site], requested: str | None) -> str:
    if requested and requested in sites:
        return requested
    if not requested:
        try:
            from .config import load_sites

            candidate = f"{load_sites(from_dir.parent / 'sites.yaml').home}.json"
            if candidate in sites:
                return candidate
        except Exception:  # noqa: BLE001
            pass
    matching = [name for name in sites if "gammarth" in name]
    return matching[0] if matching else sorted(sites)[0]


def run_reader(
    from_dir: Path,
    out_dir: Path,
    home_slug: str | None,
    min_h: int | None = None,
    max_h: int | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = rules or load_rules()
    th = Thresholds.from_rules(rules)
    configured_min, configured_max = window_bounds(rules)
    min_h = min_h if min_h is not None else configured_min
    max_h = min(max_h if max_h is not None else configured_max, 6)
    sites = _load_sites(from_dir)
    if not sites:
        raise SystemExit(f"No valid spot JSON found in {from_dir}")
    home_slug = _home_slug(from_dir, sites, home_slug)
    home = sites[home_slug]

    output = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "version": 3,
        "home_slug": home_slug,
        "window_hours": {
            "configured_min": min_h,
            "absolute_min": th.adaptive_absolute_min_h,
            "max": max_h,
            "adaptive": th.adaptive_enabled,
        },
        "policy": {
            "hard_vetoes_unchanged": True,
            "prudent_enabled": th.prudent_enabled,
            "daylight_enabled": th.daylight_enabled,
            "shelter_tolerance_requires_configured_radius": True,
        },
        "rules_digest": None,
        "windows": [],
    }
    try:
        from .config import rules_digest

        output["rules_digest"] = rules_digest(rules)
    except Exception:  # noqa: BLE001
        pass

    for filename, destination in sites.items():
        if filename != home_slug and not destination.windows_enabled:
            continue
        required = adaptive_min_hours(home, destination, min_h, th)
        if required > max_h:
            windows = []
            diagnostics = {
                "status": "blocked",
                "summary_fr": (
                    f"Trajet trop long pour une fenêtre maximale de {max_h} h : "
                    f"{required} h nécessaires avec le temps minimal sur zone."
                ),
                "summary_en": (
                    f"Route is too long for the {max_h} h maximum window: "
                    f"{required} h are required including minimum time on site."
                ),
                "first_blocker": {
                    "stage": "duration",
                    "location_slug": filename,
                    "location_name": destination.name,
                    "phase": "route",
                    "time": None,
                    "reasons": ["route_duration"],
                    "reason_fr": "durée minimale supérieure à la fenêtre maximale",
                    "reason_en": "minimum duration exceeds the maximum window",
                    "metrics": {"required_hours": required, "maximum_hours": max_h},
                    "tier": "family",
                },
                "near_miss": {"validated_hours": 0, "required_hours": required},
            }
        elif filename != home_slug and destination.route_origin:
            relay = sites.get(f"{destination.route_origin}.json")
            if relay is None:
                windows = []
                diagnostics = {
                    "status": "blocked",
                    "summary_fr": "Port relais introuvable dans la configuration.",
                    "summary_en": "Relay port is missing from configuration.",
                    "first_blocker": None,
                    "near_miss": {"validated_hours": 0, "required_hours": required},
                }
            else:
                transfers = detect_transfer_windows(home, relay, route_checkpoints(home, relay, sites), th)
                offshore_required = adaptive_min_hours(relay, destination, min_h, th)
                offshore, _ = detect_windows_detailed(
                    relay,
                    destination,
                    offshore_required,
                    max_h,
                    th,
                    allow_prudent=False,
                )
                windows = combine_composite_windows(home, relay, destination, transfers, offshore)
                diagnostics = composite_diagnostics(destination, transfers, offshore, windows)
        else:
            windows, diagnostics = detect_windows_detailed(
                home,
                destination,
                required,
                max_h,
                th,
                allow_prudent=th.prudent_enabled,
            )
        output["windows"].append({
            "dest_slug": filename,
            "dest_name": destination.name,
            "required_hours": required,
            "windows": windows,
            "diagnostics": diagnostics,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "windows.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output
