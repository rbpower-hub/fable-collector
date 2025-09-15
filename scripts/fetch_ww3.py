#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_ww3.py — Récupère Hs/Tp WW3 (ERDDAP) pour un spot FABLE.
Sortie: public/ww3-<slug>.json  { meta, hourly:{time,hs,tp} }

Stratégie:
1) Essaye PacIOOS ww3_global (vars: Thgt,Tper ; depth=0.0)
2) Si NaN partout autour du point (rayon 6°), bascule sur NOAA NWW3_Global_Best (vars: htsgws,tp ; pas de depth)
3) Explore les cellules voisines (spirale 0.5°) et s’arrête à la 1ère avec des valeurs.
"""

import argparse, csv, io, json, sys, urllib.parse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pathlib

# ---------------------------
# Fournisseurs (ERDDAPs)
# ---------------------------

PROVIDERS = {
    # PacIOOS (Hawaï) — NOTE: Méditerranée observée NaN → handled via fallback
    "pacioos": {
        "base": "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csv",
        # selection: [time][depth=0][lat][lon]
        "sel_tpl": "[({t0}):1:({t1})][(0.0)][({lat})][({lon})]",
        # variables
        "vars_tpl": "Thgt{sel},Tper{sel}",
        "needs_depth": True,
    },
    # NOAA CoastWatch ERDDAP — global WW3 Best Time Series
    "noaa": {
        "base": "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NWW3_Global_Best.csv",
        # selection: [time][lat][lon]
        "sel_tpl": "[({t0}):1:({t1})][({lat})][({lon})]",
        "vars_tpl": "htsgws{sel},tp{sel}",
        "needs_depth": False,
    },
}

DEFAULT_PROVIDER_ORDER = ("pacioos", "noaa")

# ---------------------------
# Helpers grille / coordonnées
# ---------------------------

def round_grid_half(v: float) -> float:
    """Accroche à la grille 0.5°."""
    return round(v * 2.0) / 2.0

def to_east_lon(lon_deg: float) -> float:
    """Convertit en [0 .. 360) degrees_east."""
    lon_e = lon_deg % 360.0
    if lon_e < 0:
        lon_e += 360.0
    return lon_e

# ---------------------------
# Lecture JSON spot & fenêtre
# ---------------------------

def load_spot_json(path_or_url: str) -> dict:
    if path_or_url.startswith(("http://", "https://")):
        with urlopen(path_or_url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    return json.loads(open(path_or_url, "r", encoding="utf-8").read())

def window_from_spot(d: dict):
    tz_name = (d.get("meta") or {}).get("tz") or "Africa/Tunis"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        print(f"[warn] TZ '{tz_name}' introuvable, fallback UTC", file=sys.stderr)
        tz = timezone.utc

    win = (d.get("meta") or {}).get("window") or {}
    t0s, t1s = win.get("start_local"), win.get("end_local")
    if not (t0s and t1s):
        raise SystemExit("Ce spot JSON ne contient pas meta.window.start_local/end_local")

    def parse_local(iso: str, tzobj):
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")) if "T" in iso else datetime.fromisoformat(iso + "T00:00")
        if t.tzinfo is None:
            t = t.replace(tzinfo=tzobj)
        else:
            t = t.astimezone(tzobj)
        return t

    t0 = parse_local(t0s, tz)
    t1 = parse_local(t1s, tz)
    return t0.astimezone(timezone.utc), t1.astimezone(timezone.utc)

# ---------------------------
# Construction URL griddap
# ---------------------------

def build_url(provider: str, t0z: datetime, t1z: datetime, lat: float, lon_e: float) -> str:
    """Construit l'URL ERDDAP griddap pour le provider donné."""
    cfg = PROVIDERS[provider]
    latg = round_grid_half(lat)
    long = round_grid_half(lon_e)
    t0s = t0z.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    t1s = t1z.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sel = cfg["sel_tpl"].format(t0=t0s, t1=t1s, lat=latg, lon=long)
    q = cfg["vars_tpl"].format(sel=sel)
    return cfg["base"] + "?" + urllib.parse.quote(q, safe=",:[]()=")

# ---------------------------
# Récup CSV et parsing
# ---------------------------

def fetch_csv(url: str):
    try:
        with urlopen(url, timeout=35) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise SystemExit(f"HTTP {e.code} from ERDDAP\nURL: {url}\n--- server said ---\n{body[:800]}")
    except URLError as e:
        raise SystemExit(f"Network error contacting ERDDAP: {e}")

    buf = io.StringIO(raw)
    rdr = csv.reader(buf)
    rows = list(rdr)

    # CSV ERDDAP: 2 lignes d’en-tête puis data
    if len(rows) <= 2:
        return []

    data = rows[2:]
    out = []
    for row in data:
        if not row or not row[0]:
            continue
        t = row[0]
        # Par sécurité, on prend les 2 dernières colonnes comme (Hs, Tp)
        hs_s = row[-2] if len(row) >= 2 else ""
        tp_s = row[-1] if len(row) >= 1 else ""
        try:
            hs = float(hs_s) if hs_s not in ("", "NaN", "nan", "NA") else None
        except Exception:
            hs = None
        try:
            tp = float(tp_s) if tp_s not in ("", "NaN", "nan", "NA") else None
        except Exception:
            tp = None
        out.append((t, hs, tp))
    return out

# ---------------------------
# Recherche auto d’une cellule marine
# ---------------------------

def build_offsets_halfdeg(max_radius_deg: float = 6.0):
    """Spirale d’offsets à 0.5°, jusqu’à max_radius_deg."""
    out = [(0.0, 0.0)]
    steps_max = int(round(max_radius_deg / 0.5))
    for r_steps in range(1, steps_max + 1):
        r = r_steps * 0.5
        rng = [i * 0.5 for i in range(-r_steps, r_steps + 1)]
        # bord haut et bas (dlat = ±r)
        for dx in rng:
            out.append((+r, dx))
            out.append((-r, dx))
        # bord gauche/droite (dlon = ±r) sans redoubler les coins
        for dy in rng[1:-1]:
            out.append((dy, +r))
            out.append((dy, -r))
    return out

OFFSETS_05 = build_offsets_halfdeg(6.0)  # jusqu'à ±6°

def try_cell(provider, t0z, t1z, lat, lon_e):
    url = build_url(provider, t0z, t1z, lat, lon_e)
    print(f"[{provider}] ERDDAP URL:", url)
    rows = fetch_csv(url)
    has_value = any((h is not None or p is not None) for _, h, p in rows)
    return has_value, rows, url

# ---------------------------
# main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-spot", help="Chemin local d’un JSON spot (public/<slug>.json)")
    ap.add_argument("--from-url",  help="URL publique d’un JSON spot (Pages)")
    ap.add_argument("--slug", help="Slug pour la sortie (si pas from-spot/url)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--tz", default="Africa/Tunis")
    ap.add_argument("--provider", choices=list(PROVIDERS.keys()), help="Forcer un provider")
    args = ap.parse_args()

    if args.from_spot or args.from_url:
        d = load_spot_json(args.from_spot or args.from_url)
        name = (d.get("meta") or {}).get("name") or args.slug or "spot"
        slug = (d.get("meta") or {}).get("slug") or (args.slug or "spot")
        lat  = float((d.get("meta") or {}).get("lat"))
        lon  = float((d.get("meta") or {}).get("lon"))
        t0z, t1z = window_from_spot(d)
    else:
        if not (args.slug and args.lat is not None and args.lon is not None):
            sys.exit("Spécifie --from-spot/--from-url ou bien --slug --lat --lon")
        name, slug, lat, lon = args.slug, args.slug, args.lat, args.lon
        try:
            tz = ZoneInfo(args.tz)
        except ZoneInfoNotFoundError:
            print(f"[warn] TZ '{args.tz}' introuvable, fallback UTC", file=sys.stderr)
            tz = timezone.utc
        now_loc = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
        t0z = now_loc.astimezone(timezone.utc)
        t1z = (now_loc + timedelta(hours=args.hours)).astimezone(timezone.utc)

    # Recherche automatique d'une cellule marine voisine + fallback de provider
    lon_e = to_east_lon(lon)

    provider_order = (args.provider,) if args.provider else DEFAULT_PROVIDER_ORDER
    best_rows = None
    meta_used = {
        "provider": None,
        "url": None,
        "lat_used": None,
        "lon_e_used": None,
    }

    for prov in provider_order:
        for dlat, dlon in OFFSETS_05:
            lat_try = round_grid_half(lat + dlat)
            lon_try = round_grid_half((lon_e + dlon) % 360.0)
            ok, rows, url = try_cell(prov, t0z, t1z, lat_try, lon_try)
            if rows:
                if ok:
                    best_rows = rows
                    meta_used.update({"provider": prov, "url": url, "lat_used": lat_try, "lon_e_used": lon_try})
                    break
                # garde au cas où aucune cellule n'ait de valeurs sur ce provider
                if best_rows is None:
                    best_rows = rows
                    meta_used.update({"provider": prov, "url": url, "lat_used": lat_try, "lon_e_used": lon_try})
        if best_rows and any((h is not None or p is not None) for _, h, p in best_rows):
            break
        else:
            # reset pour tenter provider suivant si rien d'exploitable
            best_rows = None

    if best_rows is None:
        sys.exit("Aucune ligne renvoyée par ERDDAP (fenêtre temporelle hors couverture ?).")

    if not any((h is not None or p is not None) for _, h, p in best_rows):
        sys.exit("Aucune cellule avec données non-NaN trouvée (même après bascule provider et rayon 6°). Essaie une autre fenêtre ou vérifie la connectivité ERDDAP.")

    times, hs, tp = [], [], []
    for t, h, p in best_rows:
        times.append(t)
        hs.append(h)
        tp.append(p)

    out = {
        "meta": {
            "sources_tried": list(provider_order),
            "source_used": meta_used["provider"],
            "erddap_url": meta_used["url"],
            "name": name, "slug": slug,
            "request": {"lat": lat, "lon": lon, "lon_east": lon_e},
            "grid": "0.5deg",
            "grid_used": {"lat": meta_used["lat_used"], "lon_east": meta_used["lon_e_used"], "step_deg": 0.5},
            "queried": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "time_window_utc": {"start": times[0], "end": times[-1], "points": len(times)}
        },
        "hourly": {"time": times, "hs": hs, "tp": tp}
    }

    pathlib.Path("public").mkdir(exist_ok=True)
    target = f"public/ww3-{slug}.json"
    open(target, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    print("✔ écrit", target, f"({len(times)} points)")

if __name__ == "__main__":
    main()
