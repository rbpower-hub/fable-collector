/* reasons-debug.js — FABLE "first failing reason" helper */
window.FABLE = window.FABLE || {};
(function(NS){

  const RULES = {
    family_hours_local: { start_h: 8, end_h: 21 },
    wind: {
      family_max_kmh: 20,
      expert_max_kmh: 24,
      nogo_min_kmh: 25,
      expert_nogo_min_kmh: 27,
      onshore_degrade_kmh: 22
    },
    sea: {
      family_max_hs_m: 0.5,
      expert_max_hs_m: 0.7,
      nogo_min_hs_m: 0.8
    },
    corridor: { outMin: 1, anchorMin: 1, backMin: 1 }
  };

  const SHORE_BEARING = {
    "gammarth-port.json":  60,
    "sidi-bou-said.json":  80,
    "ghar-el-melh.json":   90,
    "ras-fartass.json":   110,
    "el-haouaria.json":   140
  };

  function isOnshore(dirDeg, shorelineDeg){
    if(typeof dirDeg!=='number' || typeof shorelineDeg!=='number') return false;
    const d = Math.abs(((dirDeg - shorelineDeg + 540) % 360) - 180);
    return d < 60;
  }

  function minutesLocal(iso, tz){
    try{
      const d = new Date(iso);
      const s = d.toLocaleTimeString('fr-FR', { timeZone: tz||Intl.DateTimeFormat().resolvedOptions().timeZone, hour:'2-digit', minute:'2-digit', hour12:false });
      const [hh,mm] = s.split(':').map(n=>parseInt(n,10)||0);
      return hh*60+mm;
    }catch(e){ return null; }
  }

  function firstFailForWindow(cls, series, tz, shorelineDeg){
    const windCap   = (cls==="family") ? RULES.wind.family_max_kmh : RULES.wind.expert_max_kmh;
    const windHard  = (cls==="family") ? RULES.wind.nogo_min_kmh : RULES.wind.expert_nogo_min_kmh;
    const hsCap     = (cls==="family") ? RULES.sea.family_max_hs_m : RULES.sea.expert_max_hs_m;
    const hsHard    = RULES.sea.nogo_min_hs_m;

    const startM = RULES.family_hours_local.start_h*60;
    const endM   = RULES.family_hours_local.end_h*60;

    const segHours = Math.ceil(RULES.corridor.outMin + RULES.corridor.anchorMin + RULES.corridor.backMin);
    const N = series.time.length;

    for(let i=0;i+segHours<=N;i++){
      let allDay = true;
      for(let k=0;k<segHours;k++){
        const mm = minutesLocal(series.time[i+k], tz);
        if(mm==null || mm < startM || mm > endM){ allDay=false; break; }
      }
      if(!allDay) continue;

      for(let k=0;k<segHours;k++){
        const t  = series.time[i+k];
        const ws = series.wind[i+k];
        const wd = series.wind_dir ? series.wind_dir[i+k] : null;
        const hs = series.hs ? series.hs[i+k] : null;

        if(typeof ws==='number' && ws >= windHard) return `vent ${ws} ≥ ${windHard} km/h à ${t}`;
        if(typeof hs==='number' && hs >= hsHard)   return `vagues ${hs.toFixed(2)} ≥ ${hsHard} m à ${t}`;

        if(typeof ws==='number' && ws > windCap){
          if(cls==='family' && typeof wd==='number' && isOnshore(wd, shorelineDeg) && ws >= RULES.wind.onshore_degrade_kmh){
            return `vent onshore ${ws} ≥ ${RULES.wind.onshore_degrade_kmh} km/h à ${t}`;
          }
          return `vent ${ws} > ${windCap} km/h à ${t}`;
        }
        if(typeof hs==='number' && hs > hsCap) return `vagues ${hs.toFixed(2)} > ${hsCap} m à ${t}`;
      }
      return null;
    }
    return `aucune fenêtre de ${segHours}h dans ${RULES.family_hours_local.start_h}:00-${RULES.family_hours_local.end_h}:00`;
  }

  function toSeries(data){
    const h = (data && data.hourly) || {};
    return {
      time: h.time || [],
      wind: h.wind_speed_10m || h.wind_speed || [],
      wind_dir: h.wind_direction_10m || h.wind_direction || null,
      hs: h.hs || h.wave_height || null,
    };
  }

  async function loadSpot(path){
    try{ const r=await fetch(path,{cache:'no-store'}); if(!r.ok) throw 0; return await r.json(); }
    catch(e){ return null; }
  }

  NS.debugReasons = async function(paths){
    const defaults = ["gammarth-port.json","sidi-bou-said.json","ghar-el-melh.json","ras-fartass.json","el-haouaria.json"];
    const list = (paths && paths.length) ? paths : defaults;
    const rows = [];
    for(const p of list){
      const spot = await loadSpot(p);
      if(!spot){ rows.push({spot:p, family:"erreur de lecture", expert:""}); continue; }
      const tz = (spot.meta && spot.meta.tz) || null;
      const series = toSeries(spot);
      const shore = SHORE_BEARING[p] ?? null;

      const famFail = firstFailForWindow("family", series, tz, shore);
      const expFail = firstFailForWindow("expert", series, tz, shore);
      rows.push({
        spot: (spot.meta && spot.meta.name) ? `${spot.meta.name} (${p})` : p,
        family: famFail ? `✗ ${famFail}` : "✓ fenêtre possible",
        expert: expFail ? `✗ ${expFail}` : "✓ fenêtre possible"
      });
    }
    console.table(rows);
    return rows;
  };

})(window.FABLE);
