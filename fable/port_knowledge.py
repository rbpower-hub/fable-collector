"""Generate public route, transit and shelter knowledge from validated config.

Distances are computed from configured coordinates and route points. Shelter
entries remain pending until field validation; the generator never invents GPS
positions or activates shelter bonuses on its own.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .config import load_sites
from .knowledge import load_knowledge_pack

_VALIDATED_ROUTE_STATUSES = {"validated", "field_validated", "official_validated"}
_MULTI_DAY_ROUTE_KINDS = {"long_trip_one_way", "offshore_one_way_beta"}


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    d_lat = lat2 - lat1
    d_lon = math.radians(float(b["lon"]) - float(a["lon"]))
    value = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def _route_distance_km(origin: dict[str, Any], destination: dict[str, Any]) -> float:
    points = [{"lat": origin["lat"], "lon": origin["lon"]}]
    points.extend(
        {"lat": point["lat"], "lon": point["lon"]}
        for point in destination.get("route_points") or []
    )
    points.append({"lat": destination["lat"], "lon": destination["lon"]})
    return sum(_distance_km(points[index - 1], points[index]) for index in range(1, len(points)))


def _navigation_profile(port: dict[str, Any] | None) -> dict[str, Any]:
    navigation = (port or {}).get("navigation") or {}
    return navigation if isinstance(navigation, dict) else {}


def _route_is_validated(status: Any) -> bool:
    return str(status or "").strip().lower() in _VALIDATED_ROUTE_STATUSES


def _shelter_summary(shelters: Any) -> dict[str, Any]:
    records = shelters if isinstance(shelters, list) else []
    validated = [item for item in records if isinstance(item, dict) and item.get("validation_status") == "validated"]
    pending = [item for item in records if isinstance(item, dict) and item.get("validation_status") != "validated"]
    return {
        "total": len(records),
        "validated": len(validated),
        "pending": len(pending),
        "bonus_enabled": bool(validated),
        "message_fr": (
            "Abri validé disponible."
            if validated
            else "Aucun abri terrain validé — seuils standards appliqués."
        ),
        "message_en": (
            "Validated shelter available."
            if validated
            else "No field-validated shelter — standard thresholds apply."
        ),
    }


def build_port_knowledge(root: Path, out_dir: Path) -> dict[str, Any]:
    sites_cfg = load_sites(root / "sites.yaml")
    pack = load_knowledge_pack(root, strict=True)
    ports = pack.ports if pack else {}
    sites = {site["slug"]: site for site in sites_cfg.sites}
    home = sites[sites_cfg.home]
    records = []

    for site in sites_cfg.sites:
        origin_slug = site.get("route_origin") or sites_cfg.home
        origin = sites.get(origin_slug) or home
        distance_km = _route_distance_km(origin, site)
        distance_nm = distance_km / 1.852
        speed = site.get("transit_speed_kts") or {"min": 16.0, "max": 24.0}
        fast = distance_nm / float(speed["max"]) if distance_nm else 0.0
        conservative = distance_nm / float(speed["min"]) if distance_nm else 0.0
        navigation = _navigation_profile(ports.get(site["slug"]))
        shelters = navigation.get("shelters") if isinstance(navigation.get("shelters"), list) else []
        field_observations = (
            navigation.get("field_observations")
            if isinstance(navigation.get("field_observations"), list)
            else []
        )
        shelter_summary = _shelter_summary(shelters)
        route_kind = str(site.get("route_kind") or "standard")
        multi_day = route_kind in _MULTI_DAY_ROUTE_KINDS
        route_validation_status = navigation.get("route_validation_status", "computed_from_config")
        route_validated = _route_is_validated(route_validation_status)
        display_eligible = route_validated or shelter_summary["validated"] > 0

        records.append({
            "port_id": site["slug"],
            "name": site["name"],
            "country": site.get("country"),
            "role": navigation.get("role") or ("home_port" if site["slug"] == sites_cfg.home else "destination"),
            "display_eligible": display_eligible,
            "route": {
                "origin_id": origin["slug"],
                "origin_name": origin["name"],
                "route_kind": route_kind,
                "trip_mode": "one_way_multi_day" if multi_day else "round_trip_day",
                "same_day_round_trip_required": not multi_day,
                "distance_km": round(distance_km, 1),
                "distance_nm": round(distance_nm, 1),
                "transit_hours": {
                    "fast": round(fast, 2),
                    "conservative": round(conservative, 2),
                },
                "speed_assumption_kts": speed,
                "validation_status": route_validation_status,
                "validated": route_validated,
                "note_fr": navigation.get("route_note_fr") or site.get("route_note"),
                "note_en": navigation.get("route_note_en"),
            },
            "field_observations": field_observations,
            "shelters": shelters,
            "shelter_summary": shelter_summary,
            "return_policy": navigation.get("return_policy") or {
                "mode": "independent" if multi_day else "same_window",
                "daylight_margin_min": 60,
                "weather_margin_min": 30,
            },
            "validation": navigation.get("validation") or {
                "local_validation_required": True,
                "coordinates_validated": False,
            },
        })

    output = {
        "version": 3,
        "status": "port_knowledge_tunable",
        "policy": {
            "shelter_bonus_requires_validated_record": True,
            "unvalidated_shelters_never_relax_thresholds": True,
            "field_observations_are_advisory": True,
            "offshore_one_way_supported": True,
            "long_trip_one_way_supported": True,
            "kelibia_same_day_round_trip_required": False,
            "pantelleria_same_day_round_trip_required": False,
            "ui_requires_validated_route_or_shelter": True,
        },
        "home_port": sites_cfg.home,
        "visible_ports_count": sum(1 for item in records if item["display_eligible"]),
        "ports": records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "port-knowledge.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def main() -> None:
    build_port_knowledge(Path("."), Path("public"))


if __name__ == "__main__":
    main()
