"""Publication inventory & status: catalog.json, status.json, status.html, windows.md.

Key fix vs v1: build-time freshness was meaningless (files are always fresh
at build time, so the page kept saying OK while production was down for
months). v2 publishes `stale_after` and status.html evaluates freshness
CLIENT-SIDE against the visitor's clock; healthcheck.yml is the server-side
alerting layer.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import __version__

log = logging.getLogger("fable.status")

# Collection cadence promise (hourly) + scheduling leeway.
CADENCE_MIN = 60
LEEWAY_MIN = 35


def build_catalog(public: Path, tz: ZoneInfo) -> dict[str, Any]:
    files = []
    for p in sorted(public.glob("*.json")):
        if p.name in ("catalog.json",):
            continue
        st = p.stat()
        files.append({
            "path": p.name,
            "size": st.st_size,
            "modified": dt.datetime.fromtimestamp(st.st_mtime, tz).isoformat(),
        })
    catalog = {"generated_at": dt.datetime.now(tz).isoformat(), "files": files}
    (public / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog


def build_status(public: Path, tz: ZoneInfo, expected_spots: list[str] | None = None,
                 now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(tz)
    catalog = json.loads((public / "catalog.json").read_text(encoding="utf-8")) \
        if (public / "catalog.json").exists() else {"files": []}
    files = catalog.get("files", [])

    missing = []
    if expected_spots:
        present = {f["path"] for f in files}
        missing = [s for s in expected_spots if s not in present]

    status = {
        "generated_at": now.isoformat(),
        "collector_version": __version__,
        "cadence_minutes": CADENCE_MIN,
        "stale_after": (now + dt.timedelta(minutes=CADENCE_MIN + LEEWAY_MIN)).isoformat(),
        "expected_spots": expected_spots or [],
        "missing_spots": missing,
        "build_ok": not missing,
        "files": files,
    }
    (public / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


STATUS_HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fable-collector — status</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0b1020;color:#e8eef6;margin:2rem}}
 .card{{max-width:640px;margin:auto;background:#131a30;border-radius:12px;padding:1.5rem 2rem}}
 .ok{{color:#2dd4bf}}.ko{{color:#f87171}}.muted{{color:#9fb3c8;font-size:.9rem}}
 h1{{font-size:1.2rem}} table{{width:100%;border-collapse:collapse;font-size:.85rem}}
 td,th{{text-align:left;padding:.25rem .5rem;border-bottom:1px solid #24304f}}
</style></head><body><div class="card">
<h1>🧭 fable-collector — status</h1>
<p>Dernière collecte : <b>{generated_at}</b></p>
<p id="verdict">Évaluation de la fraîcheur…</p>
<p class="muted">Cadence promise : {cadence} min (+{leeway} min de tolérance).
La fraîcheur est évaluée par votre navigateur, pas au moment du build.</p>
<table><tr><th>Fichier</th><th>Taille</th></tr>{rows}</table>
<p class="muted">v{version} — <a style="color:#4cc9f0" href="status.json">status.json</a></p>
</div>
<script>
 var gen = new Date("{generated_at}");
 var limitMs = ({cadence} + {leeway}) * 60000;
 var age = Date.now() - gen.getTime();
 var v = document.getElementById('verdict');
 var mins = Math.round(age/60000);
 if (age <= limitMs) {{
   v.innerHTML = '<span class="ok">✅ FRAIS</span> — âge : ' + mins + ' min';
 }} else {{
   v.innerHTML = '<span class="ko">❌ OBSOLÈTE</span> — âge : ' + mins +
                 ' min (pipeline probablement arrêté, vérifier GitHub Actions)';
 }}
</script></body></html>
"""


def build_status_html(public: Path, status: dict[str, Any]) -> None:
    rows = "".join(
        f"<tr><td>{f['path']}</td><td>{f['size']:,} o</td></tr>"
        for f in status.get("files", []) if not f["path"].startswith("_debug-")
    )
    html = STATUS_HTML.format(
        generated_at=status["generated_at"],
        cadence=status.get("cadence_minutes", CADENCE_MIN),
        leeway=LEEWAY_MIN,
        rows=rows,
        version=status.get("collector_version", __version__),
    )
    (public / "status.html").write_text(html, encoding="utf-8")


def build_windows_md(public: Path, tz: ZoneInfo) -> None:
    d = json.loads((public / "windows.json").read_text(encoding="utf-8"))
    ts = dt.datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
    lines = ["# FABLE — Fenêtres Family GO", "", f"Horodatage : {ts} ({tz.key})", ""]
    any_win = False
    for w in d.get("windows", []):
        segs = w.get("windows", [])
        if not segs:
            continue
        any_win = True
        lines.append(f"## {w.get('dest_name','?')} ({w.get('dest_slug','?')})")
        for seg in segs:
            lines.append(
                f"- {seg['start']} → {seg['end']} ({seg['hours']} h, "
                f"{seg.get('category','?')}, confiance {seg.get('confidence','?')})"
            )
        lines.append("")
    if not any_win:
        lines.append("- Aucune fenêtre Family GO détectée dans l'horizon analysé.")
    (public / "windows.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def final_check(public: Path, expected_spots: list[str]) -> list[str]:
    """Return list of problems (empty = ready to deploy)."""
    problems = []
    for required in ["index.json", "catalog.json", "status.json", "status.html",
                     "windows.json", "windows.md", "index.html", "rules.normalized.json"]:
        p = public / required
        if not p.exists() or p.stat().st_size == 0:
            problems.append(f"missing or empty: {required}")
    for spot in expected_spots:
        p = public / spot
        if not p.exists() or p.stat().st_size == 0:
            problems.append(f"missing or empty spot: {spot}")
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            pts = len((d.get("hourly") or {}).get("time") or [])
            if pts < 24:
                problems.append(f"suspiciously few hourly points in {spot}: {pts}")
        except Exception as e:  # noqa: BLE001
            problems.append(f"unparsable spot {spot}: {e}")
    return problems
