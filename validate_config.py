from __future__ import annotations
import json, sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent

def load_yaml(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"[YAML] Failed to read {p}: {e}")

def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"[JSON] Failed to read {p}: {e}")

def validate(doc_path: Path, schema_path: Path) -> int:
    doc, schema = load_yaml(doc_path), load_json(schema_path)
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(doc), key=lambda e: (list(e.path), e.message))
    if errs:
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            print(f"[SCHEMA] {doc_path}:{loc}: {e.message}")
        return 2
    print(f"[OK] {doc_path} ✓")
    return 0

if __name__ == "__main__":
    rc = 0
    rc |= validate(ROOT/"sites.yaml", ROOT/"schemas/sites.schema.json")
    rc |= validate(ROOT/"rules.yaml", ROOT/"schemas/rules.schema.json")
    sys.exit(rc)
