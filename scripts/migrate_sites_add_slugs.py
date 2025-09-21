from __future__ import annotations
import re, sys
from pathlib import Path
import yaml

try:
    from unidecode import unidecode  # optional but nice for accents
except Exception:
    unidecode = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sites.yaml"

SLUG_RE = re.compile(r"[^a-z0-9-]+")

def slugify(name: str) -> str:
    s = name.strip().lower()
    if unidecode:
        s = unidecode(s)
    s = s.replace("&", " and ")
    s = re.sub(r"\s+", "-", s)
    s = SLUG_RE.sub("", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "site"

def main():
    data = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    seen = set()
    for i, row in enumerate(data):
        if "slug" not in row or not str(row["slug"]).strip():
            base = slugify(row.get("name", f"site-{i}"))
            slug = base
            k = 2
            # ensure uniqueness
            while slug in seen:
                slug = f"{base}-{k}"
                k += 1
            row["slug"] = slug
        seen.add(row["slug"])
    out = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    SRC.write_text(out, encoding="utf-8")
    print(f"[MIGRATE] Filled missing slugs. Total sites: {len(data)}")

if __name__ == "__main__":
    main()
