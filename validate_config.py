# validate_config.py
from __future__ import annotations
import json, sys, yaml
from jsonschema import validate, Draft202012Validator
from pathlib import Path

def _load_yaml(p: Path): 
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def check(doc_path: str, schema_path: str):
    doc = _load_yaml(Path(doc_path))
    schema = _load_json(Path(schema_path))
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(doc), key=lambda e: e.path)
    if errs:
        for e in errs:
            loc = "/".join([str(p) for p in e.path]) or "<root>"
            print(f"[SCHEMA] {doc_path}:{loc}: {e.message}")
        sys.exit(2)
    print(f"[OK] {doc_path} validated against {schema_path}")

if __name__ == "__main__":
    base = Path(__file__).parent
    check(base/"sites.yaml",  base/"schemas/sites.schema.json")
    check(base/"rules.yaml",  base/"schemas/rules.schema.json")
