"""Load and validate the independent FABLE Knowledge Pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATEGORIES = ("fish", "techniques", "ports", "activities")


class KnowledgePackError(ValueError):
    """Raised when a Knowledge Pack is present but internally inconsistent."""


@dataclass(frozen=True)
class KnowledgePack:
    version: int
    status: str
    ranking: dict[str, Any]
    fish: dict[str, dict[str, Any]]
    techniques: dict[str, dict[str, Any]]
    ports: dict[str, dict[str, Any]]
    activities: dict[str, dict[str, Any]]
    warnings: tuple[str, ...] = ()

    def public_catalog(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "counts": {
                "fish": len(self.fish),
                "techniques": len(self.techniques),
                "ports": len(self.ports),
                "activities": len(self.activities),
            },
            "ids": {
                "fish": sorted(self.fish),
                "techniques": sorted(self.techniques),
                "ports": sorted(self.ports),
                "activities": sorted(self.activities),
            },
            "warnings": list(self.warnings),
        }


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise KnowledgePackError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgePackError(f"{path} must contain a YAML mapping")
    return value


def _load_category(directory: Path, category: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.yaml")):
        record = _yaml(path)
        record_id = str(record.get("id") or path.stem).strip()
        if not record_id:
            raise KnowledgePackError(f"Missing id in {path}")
        if record_id != path.stem:
            raise KnowledgePackError(f"{path}: id '{record_id}' must match filename '{path.stem}'")
        if record_id in records:
            raise KnowledgePackError(f"Duplicate {category} id: {record_id}")
        records[record_id] = record
    return records


def _as_ids(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _validate(pack: KnowledgePack) -> list[str]:
    errors: list[str] = []
    for port_id, port in pack.ports.items():
        seasons = ((port.get("fishing") or {}).get("seasons") or {})
        if not isinstance(seasons, dict):
            errors.append(f"ports/{port_id}: fishing.seasons must be a mapping")
            continue
        for season, profile in seasons.items():
            if not isinstance(profile, dict):
                errors.append(f"ports/{port_id}: season {season} must be a mapping")
                continue
            for fish_id in _as_ids(profile.get("species")):
                if fish_id not in pack.fish:
                    errors.append(f"ports/{port_id}/{season}: unknown fish '{fish_id}'")
            for technique_id in _as_ids(profile.get("techniques")):
                if technique_id not in pack.techniques:
                    errors.append(f"ports/{port_id}/{season}: unknown technique '{technique_id}'")
    for activity_id, activity in pack.activities.items():
        for technique_id in _as_ids(activity.get("techniques")):
            if technique_id not in pack.techniques:
                errors.append(f"activities/{activity_id}: unknown technique '{technique_id}'")
    return errors


def load_knowledge_pack(root: Path, *, strict: bool = True) -> KnowledgePack | None:
    """Load ``knowledge/``. Return ``None`` when no manifest exists.

    The pack is deliberately separate from navigation safety rules. It may rank
    activities only after the existing Family GO engine has produced a window.
    """
    directory = root / "knowledge"
    manifest_path = directory / "manifest.yaml"
    if not manifest_path.exists():
        return None
    manifest = _yaml(manifest_path)
    try:
        version = int(manifest.get("version", 1))
    except (TypeError, ValueError) as exc:
        raise KnowledgePackError("knowledge/manifest.yaml: version must be an integer") from exc
    loaded = {category: _load_category(directory / category, category) for category in CATEGORIES}
    pack = KnowledgePack(
        version=version,
        status=str(manifest.get("status") or "initial_tunable"),
        ranking=dict(manifest.get("ranking") or {}),
        fish=loaded["fish"],
        techniques=loaded["techniques"],
        ports=loaded["ports"],
        activities=loaded["activities"],
    )
    errors = _validate(pack)
    if errors and strict:
        raise KnowledgePackError("Invalid FABLE Knowledge Pack: " + "; ".join(errors))
    if errors:
        return KnowledgePack(**{**pack.__dict__, "warnings": tuple(errors)})
    return pack
