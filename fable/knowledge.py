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
    schema: dict[str, Any]
    policy: dict[str, Any]
    ranking: dict[str, Any]
    fish: dict[str, dict[str, Any]]
    techniques: dict[str, dict[str, Any]]
    ports: dict[str, dict[str, Any]]
    activities: dict[str, dict[str, Any]]
    warnings: tuple[str, ...] = ()

    def public_catalog(self) -> dict[str, Any]:
        taxonomic_pending = sum(
            1
            for record in self.fish.values()
            if bool((record.get("validation") or {}).get("taxonomic_validation_required"))
        )
        regulatory_checks = sum(
            1
            for record in self.fish.values()
            if bool((record.get("validation") or {}).get("regulatory_check_required"))
        )
        return {
            "version": self.version,
            "status": self.status,
            "schema": self.schema,
            "policy": self.policy,
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
            "validation_summary": {
                "fish_with_targeting": sum(1 for record in self.fish.values() if record.get("targeting")),
                "taxonomic_validation_required": taxonomic_pending,
                "regulatory_check_required": regulatory_checks,
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


def _validate_numeric_pair(owner: str, field: str, value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list) or len(value) != 2:
        errors.append(f"{owner}: {field} must be a two-value list")
        return
    try:
        low, high = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        errors.append(f"{owner}: {field} must contain numeric values")
        return
    if low < 0 or high < low:
        errors.append(f"{owner}: {field} must be ordered and non-negative")


def _validate_hook_sizes(owner: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{owner}: hook_sizes must be a mapping")
        return
    system = str(value.get("system") or "")
    sizes = value.get("range")
    if system == "not_applicable":
        if sizes not in ([], None):
            errors.append(f"{owner}: not_applicable hook_sizes must have an empty range")
        return
    if not system:
        errors.append(f"{owner}: hook_sizes.system is required")
    if not isinstance(sizes, list) or len(sizes) != 2 or not all(str(item).strip() for item in sizes):
        errors.append(f"{owner}: hook_sizes.range must contain two non-empty values")


def _validate_targeting(pack: KnowledgePack, errors: list[str]) -> None:
    for fish_id, fish in pack.fish.items():
        owner = f"fish/{fish_id}"
        targeting = fish.get("targeting")
        if not isinstance(targeting, dict):
            errors.append(f"{owner}: targeting must be a mapping")
            continue
        technique_ids = _as_ids(targeting.get("technique_ids"))
        if not technique_ids:
            errors.append(f"{owner}: targeting.technique_ids must not be empty")
        for technique_id in technique_ids:
            if technique_id not in pack.techniques:
                errors.append(f"{owner}: unknown targeting technique '{technique_id}'")
        tackle = targeting.get("terminal_tackle")
        if not isinstance(tackle, dict):
            errors.append(f"{owner}: targeting.terminal_tackle must be a mapping")
        else:
            _validate_hook_sizes(owner, tackle.get("hook_sizes"), errors)
            _validate_numeric_pair(owner, "leader_mm", tackle.get("leader_mm"), errors)
            _validate_numeric_pair(owner, "sinker_g", tackle.get("sinker_g"), errors)
        validation = fish.get("validation")
        if not isinstance(validation, dict):
            errors.append(f"{owner}: validation must be a mapping")
        elif not bool(validation.get("local_validation_required")):
            errors.append(f"{owner}: local_validation_required must remain true")

    for technique_id, technique in pack.techniques.items():
        owner = f"techniques/{technique_id}"
        gear = technique.get("gear")
        if not isinstance(gear, dict):
            errors.append(f"{owner}: gear must be a mapping")
            continue
        _validate_hook_sizes(owner, gear.get("hook_sizes"), errors)
        for field in ("leader_mm", "sinker_g", "lure_weight_g", "lure_length_cm", "jighead_g"):
            _validate_numeric_pair(owner, field, gear.get(field), errors)


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
    if pack.version >= 2:
        _validate_targeting(pack, errors)
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
        schema=dict(manifest.get("schema") or {}),
        policy=dict(manifest.get("policy") or {}),
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
