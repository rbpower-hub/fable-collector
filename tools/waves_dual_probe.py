#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
waves_dual_probe.py — Compare Hs/Tp entre Open-Meteo Marine, NOAA WW3 (ERDDAP) et Copernicus Marine (optionnel)

Usage:
  python waves_dual_probe.py --lat 36.9203 --lon 10.2846 --hours 48 --start "2025-09-15T00:00"
  # ou juste:
  python waves_dual_probe.py

Sorties:
  - prints: résumé des spreads
  - CSV: waves_probe.csv (time, hs_om, tp_om, hs_noaa, tp_noaa, hs_cmems?, tp_cmems?)
"""

import os, sys, math, json, argparse, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests

# ------- Config par défaut (Gammarth) -------
DEF_LAT, DEF_LON = 36.9203, 10.2846
DEF_TZ = "Africa/Tunis"

# NOAA WW3 ERDDAP (Global Best): variables Thgt (Hs m), Tper (Tp s)
# Réf: dataset griddap/NWW3_Global_Best (ERDDAP CoastWatch). Voir data.gov -> ERDDAP. 
ERDDAP_NWW3 = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NWW3_Global_Best.nc"

# -------- Helpers --------
def to_utc(d: dt.datetime) -> dt.datetime:
    if d.tzinfo is None:
        return d.replace(tzinfo=ZoneInfo(DEF_TZ)).astimezone(ZoneInfo("UTC"))
    return d.astimezone(ZoneInfo("UTC"))

def floor_hour(d: dt.datetime) -> dt.datetime:
    return d.replace(minute=0, second=0, microsecond=0)

def daterange_hours(t0: dt.datetime, hours: int) -> list[dt.datetime]:
    return [t0 + dt.timedelta(hours=i) for i in range(hours)]

def open_meteo_marine(lat: float, lon: float, start_local: dt.datetime, hours: int, tzname: str):
    """Retourne DataFrame time(naive UTC ISO), hs, tp à 1h."""
    tz = ZoneInfo(tzname)
    start = floor_hour(start_local)
    end   = start + dt.timedelta(hours=hours)
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": "wave_height,wave_period",
        "timezone": tzname,           # on demande les timestamps déjà en tz locale
        "timeformat": "iso8601",
        "wave_height_unit":"m",
        "start_date": start.date().isoformat(),
        "end_date":   end.date().isoformat(),
    }
    url = "https://marine-api.open-meteo.com/v1/marine"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    d = r.json()
    hh = d.get("hourly", {})
    times = hh.get("time", [])
    hs    = hh.get("wave_height", [])
    tp    = hh.get("wave_period", [])
    # Filtre exact sur [start, end) en tz locale puis convertit en UTC naïf pour l’axe commun
    out = []
    for t, a, b in zip(times, hs, tp):
        try:
            tl = dt.datetime.fromisoformat(t)       # horodaté en tz locale
            if tl.tzinfo is None:
                tl = tl.replace(tzinfo=tz)
        except Exception:
            continue
        if start <= tl < end:
            tu = tl.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            out.append((tu, float(a) if a is not None else None, float(b) if b is not None else None))
    df = pd.DataFrame(out, columns=["time_utc", "hs_om", "tp_om"]).set_index("time_utc")
    return df

def noaa_ww3(lat: float, lon: float, start_utc: dt.datetime, hours: int):
    """ERDDAP OPeNDAP via netCDF4: lit Thgt (m) et Tper (s) au plus proche point de grille, sur la fenêtre voulue."""
    try:
        from netCDF4 import Dataset, num2date, date2index
    except Exception as e:
        raise RuntimeError("netCDF4 est requis pour NOAA WW3 (pip install netCDF4)") from e

    ds = Dataset(ERDDAP_NWW3)
    latv = ds.variables["latitude"][:]
    lonv = ds.variables["longitude"][:]
    # Normalise lon au domaine de la grille (0..360 ou -180..180)
    glon = lon
    if lonv.min() >= 0 and lon < 0:      # grille 0..360
        glon = (lon + 360) % 360
    if lonv.max() > 180 and glon < 0:
        glon = (glon + 360) % 360
    # indices les plus proches
    ilat = int(np.abs(latv - lat).argmin())
    ilon = int(np.abs(lonv - glon).argmin())

    time = ds.variables["time"]
    t0u  = to_utc(start_utc).replace(tzinfo=None)
    t1u  = t0u + dt.timedelta(hours=hours)
    try:
        i0 = date2index(t0u, time, select="nearest")
        i1 = date2index(t1u, time, select="nearest")
    except Exception:
        # fallback: parcours linéaire
        tu_all = num2date(time[:], time.units)
        i0 = int(np.argmin(np.abs(np.array([abs((t - t0u).total_seconds()) for t in tu_all]))))
        i1 = int(np.argmin(np.abs(np.array([abs((t - t1u).total_seconds()) for t in tu_all]))))

    # fetch bornes correctes
    if i1 < i0: i0, i1 = i1, i0
    # Récupère uniquement le sous-ensemble
    Thgt = ds.variables.get("Thgt")
    Tper = ds.variables.get("Tper")
    if Thgt is None or Tper is None:
        raise RuntimeError("Variables 'Thgt' et/ou 'Tper' introuvables dans NWW3_Global_Best")

    hs = Thgt[i0:i1+1, ilat, ilon].filled(np.nan) if hasattr(Thgt, "filled") else Thgt[i0:i1+1, ilat, ilon]
    tp = Tper[i0:i1+1, ilat, ilon].filled(np.nan) if hasattr(Tper, "filled") else Tper[i0:i1+1, ilat, ilon]
    tu = pd.to_datetime(num2date(time[i0:i1+1], time.units)).tz_localize("UTC").tz_convert(None)  # UTC naive

    df = pd.DataFrame({"hs_noaa": hs, "tp_noaa": tp}, index=pd.Index(tu, name="time_utc"))
    ds.close()
    return df

def copernicus_medsea(lat: float, lon: float, start_utc: dt.datetime, hours: int, bbox_km=5.0):
    """
    Optionnel — nécessite `pip install copernicusmarine` et un compte.
    Télécharger un sous-ensemble autour (lat, lon) et extraire la série du point le plus proche.
    """
    try:
        import shutil, tempfile
        from netCDF4 import Dataset
        import numpy as np
        from copernicusmarine import subset
    except Exception:
        # pas installé / pas dispo → on renvoie None
        return None

    # Dataset par défaut (peut évoluer). Adapter si besoin via env CMEMS_DATASET_ID.
    dataset_id = os.getenv("CMEMS_DATASET_ID", "cmems_mod_med_wav_anfc_4.2km_PT1H-m")  # MEDSEA hourly forecast (indicatif)
    # Boîte de 0.1° ~ 10-12 km selon latitude ; ajustable.
    dlat = 0.1
    dlon = 0.1

    t0 = to_utc(start_utc)
    t1 = t0 + dt.timedelta(hours=hours)
    tmpdir = tempfile.mkdtemp(prefix="cmems_")
    try:
        subset(
            dataset_id=dataset_id,
            variables=["VHM0","VTPK"],  # Hs, Tp
            minimum_longitude=lon - dlon, maximum_longitude=lon + dlon,
            minimum_latitude=lat - dlat, maximum_latitude=lat + dlat,
            start_datetime=t0.isoformat().replace("+00:00","Z"),
            end_datetime=t1.isoformat().replace("+00:00","Z"),
            output_directory=tmpdir,
            output_filename="medsea.nc",
            force_download=True,
        )
        nc = os.path.join(tmpdir, "medsea.nc")
        if not os.path.exists(nc) or os.path.getsize(nc) == 0:
            return None

        ds = Dataset(nc)
        # Variables usuelles (peuvent varier). Adapter si nécessaire.
        vhs = ds.variables.get("VHM0")
        vtp = ds.variables.get("VTPK")
        vlat = ds.variables.get("latitude") or ds.variables.get("lat")
        vlon = ds.variables.get("longitude") or ds.variables.get("lon")
        vtime= ds.variables.get("time")
        if not (vhs and vtp and vlat and vlon and vtime):
            ds.close(); return None

        lats = vlat[:]; lons = vlon[:]
        ilat = int(np.abs(lats - lat).argmin())
        ilon = int(np.abs(lons - lon).argmin())

        from netCDF4 import num2date
        tu = pd.to_datetime(num2date(vtime[:], vtime.units)).tz_localize("UTC").tz_convert(None)
        hs = vhs[:, ilat, ilon].filled(np.nan) if hasattr(vhs, "filled") else vhs[:, ilat, ilon]
        tp = vtp[:, ilat, ilon].filled(np.nan) if hasattr(vtp, "filled") else vtp[:, ilat, ilon]
        df = pd.DataFrame({"hs_cmems": hs, "tp_cmems": tp}, index=pd.Index(tu, name="time_utc"))
        ds.close()
        return df
    finally:
        try: shutil.rmtree(tmpdir)
        except Exception: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=DEF_LAT)
    ap.add_argument("--lon", type=float, default=DEF_LON)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--start", type=str, default="")
    ap.add_argument("--tz", type=str, default=DEF_TZ)
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    start_local = dt.datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    if args.start:
        try:
            start_local = dt.datetime.fromisoformat(args.start)
            if start_local.tzinfo is None:
                start_local = start_local.replace(tzinfo=tz)
            else:
                start_local = start_local.astimezone(tz)
        except Exception as e:
            print("⚠️ start invalide, utilisation de maintenant:", e, file=sys.stderr)

    # 1) Open-Meteo Marine
    df_om = open_meteo_marine(args.lat, args.lon, start_local, args.hours, args.tz)

    # 2) NOAA WW3 (UTC)
    df_noaa = noaa_ww3(args.lat, args.lon, to_utc(start_local), args.hours)

    # 3) Copernicus (optionnel)
    df_cmems = copernicus_medsea(args.lat, args.lon, to_utc(start_local), args.hours)

    # Alignement
    df = df_om.join(df_noaa, how="outer")
    if df_cmems is not None:
        df = df.join(df_cmems, how="outer")

    # Tri + filtre à la fenêtre exacte
    t0u = to_utc(start_local).replace(tzinfo=None)
    t1u = t0u + dt.timedelta(hours=args.hours)
    df = df[(df.index >= t0u) & (df.index < t1u)].sort_index()

    # Résumé des spreads (2 sources minis)
    avail_hs = [c for c in df.columns if c.startswith("hs_")]
    avail_tp = [c for c in df.columns if c.startswith("tp_")]

    def spread_row(row, cols):
        vals = [row[c] for c in cols if pd.notna(row.get(c))]
        if len(vals) < 2: return np.nan
        return float(np.nanmax(vals) - np.nanmin(vals))

    df["hs_spread"] = df.apply(lambda r: spread_row(r, avail_hs), axis=1)
    df["tp_spread"] = df.apply(lambda r: spread_row(r, avail_tp), axis=1)

    # Petites métriques
    hs_mean_spread = float(np.nanmean(df["hs_spread"])) if np.isfinite(df["hs_spread"]).any() else np.nan
    tp_mean_spread = float(np.nanmean(df["tp_spread"])) if np.isfinite(df["tp_spread"]).any() else np.nan
    pct_hs_ok = float(np.mean(df["hs_spread"] <= 0.2)) * 100 if "hs_spread" in df and df["hs_spread"].notna().any() else 0.0
    pct_tp_ok = float(np.mean(df["tp_spread"] <= 1.0)) * 100 if "tp_spread" in df and df["tp_spread"].notna().any() else 0.0

    # Export CSV
    out_csv = "waves_probe.csv"
    df.reset_index().rename(columns={"time_utc":"time"}).to_csv(out_csv, index=False)
    print(f"💾 Écrit {out_csv} ({len(df)} lignes)")

    # Rapport console
    def present_sources():
        s = ["Open-Meteo Marine (hs_om, tp_om)"]
        if "hs_noaa" in df: s.append("NOAA WW3 (hs_noaa, tp_noaa)")
        if "hs_cmems" in df: s.append("Copernicus MEDSEA (hs_cmems, tp_cmems)")
        return ", ".join(s)

    print("Sources utilisées:", present_sources())
    print(f"ΔHs moyen ~ {hs_mean_spread:.2f} m | ΔTp moyen ~ {tp_mean_spread:.2f} s")
    print(f"% d'heures avec |ΔHs|≤0.20 m: {pct_hs_ok:.0f}%  |  |ΔTp|≤1.0 s: {pct_tp_ok:.0f}%")

    # Petite règle “High waves-only” indicative (pour aider à viser HIGH une fois les vents à 2 modèles)
    enough_models = (df[avail_hs].notna().sum(axis=1) >= 2).mean() > 0.8
    waves_tight   = (pct_hs_ok >= 80.0 and pct_tp_ok >= 80.0)
    print(f"→ Indice vagues resserrées: {'OK' if (enough_models and waves_tight) else 'à confirmer'}")

if __name__ == "__main__":
    sys.exit(main())
