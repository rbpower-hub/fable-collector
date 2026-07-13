"""Separate offshore navigation windows from leisure activity recommendations.

A Kélibia↔Pantelleria crossing is a navigation operation, not a Family day-trip
activity window. This post-processor prevents swimming, anchoring or fishing
cards from being inferred during the crossing while preserving a compact
navigation-only summary for the dashboard and machine consumers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return value if isinstance(value, dict) else {}


def separate_offshore_recommendations(public: Path) -> dict[str, Any]:
    windows = _json(public / "windows.json")
    recommendations = _json(public / "recommendations.json")
    if not recommendations:
        return {}

    offshore_entries = {
        str(item.get("dest_slug") or ""): item
        for item in windows.get("windows") or []
        if item.get("trip_mode") == "one_way_multi_day"
    }
    offshore_slugs = set(offshore_entries)
    recommendations["recommendations"] = [
        item
        for item in recommendations.get("recommendations") or []
        if str(item.get("dest_slug") or "") not in offshore_slugs
    ]

    navigation_only = []
    for slug, destination in offshore_entries.items():
        for window in destination.get("windows") or []:
            navigation_only.append({
                "dest_slug": slug,
                "dest_name": destination.get("dest_name"),
                "start": window.get("start"),
                "end": window.get("end"),
                "hours": window.get("hours"),
                "confidence": window.get("confidence"),
                "category": window.get("category"),
                "trip_mode": "one_way_multi_day",
                "direction": window.get("direction"),
                "origin_slug": window.get("origin_slug"),
                "origin_name": window.get("origin_name"),
                "destination_slug": window.get("destination_slug"),
                "destination_name": window.get("destination_name"),
                "same_day_round_trip_required": False,
                "method_note_fr": (
                    "Fenêtre de navigation offshore uniquement. Aucune activité de baignade, "
                    "mouillage ou pêche n’est déduite pendant la traversée."
                ),
                "method_note_en": (
                    "Offshore navigation window only. No swimming, anchoring or fishing activity "
                    "is inferred during the crossing."
                ),
            })
    navigation_only.sort(key=lambda item: (str(item.get("start") or ""), str(item.get("direction") or "")))
    recommendations["navigation_only"] = navigation_only
    recommendations["offshore_activity_policy"] = "navigation_only_no_leisure_recommendations"
    recommendations["version"] = max(int(recommendations.get("version", 1)), 4)
    (public / "recommendations.json").write_text(
        json.dumps(recommendations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return recommendations


def main() -> None:
    separate_offshore_recommendations(Path("public"))


if __name__ == "__main__":
    main()
