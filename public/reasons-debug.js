/* reasons-debug.js — FABLE "first failing reason" helper */
window.FABLE = window.FABLE || {};
(function(NS){

  // ⚙️ Thresholds aligned with reader + rules.normalized.json
  const RULES = {
    family_hours_local: { start_h: 8, end_h: 21 }, // end exclusive
    wind: { family_max_kmh: 20, nogo_min_kmh: 25, onshore_degrade_kmh: 22 },
    sea:  { family_max_hs_m: 0.5, nogo_min_hs_m: 0.8 },
    overrides: {
      gusts_hard_nogo_kmh: 30,
      squall_delta_kmh: 17,
      thunder_wmo: [95,96,99],
      visibility_km_min: 5
    },
    corridor: { minHours: 4 }
  };

  // Same onshore sectors as in reader.py
  function onshoreRanges(slugOrFile){
    const s = String(slugOrFile||'').replace('.json','').toLowerCase();
    if (['gammarth-port','gammarth'].includes(s)) return [[30,150]];
    if (['sidi-bou-said','sidibousaid','sidi-bou'].includes(s)) return [[30,150]];
    if (['ghar-el-melh','ghar el melh','gharemelh','ghar-elmelh'].includes(s)) return [[10,130]];
    if (['el-haouaria','haouaria','el haouaria'].includes(s)) return [[330,360],[0,70]];
    if (['ras-fartass','rasfartass','ras fartass'].includes(s)) return [[330,360],[0,70]];
    if (['korbous'].includes(s)) return [[30,150]];
    if (['kelibia','kélibia'].includes(s)) return [[330,360],[0,70]];
    return [[20,160]];
  }
  function angleInRanges(a, ranges){
    for(const [lo,hi] of ranges){
      if (lo <= hi) { if (a >= lo && a <= hi) return true; }
      else { if (a >= lo || a <= hi) return true; } // wrap
    }
    return false;
  }

  // Local minutes for hour-window checks
  function minutesLocal(iso, tz){
    try{
      const d = new Date(iso);
      const s = d.toLocaleTimeString('fr-FR', {
        timeZone: tz || Intl.DateTimeFormat().resolvedOptions().timeZone,
        hour:'2-digit', minute:'2-digit', hour12:false
      });
      const [hh,mm] = s.split(':').map(n=>parseInt(n,10)||0);
      return hh*60+mm;
    }catch{ return null; }
  }

  // Normalize visibility to km (accept meters or km)
  const visToKm = v => (v==null ? null : (v>50? v/1000 : v));

  // Extract series we need
  function toSeries(data){
    const h = (data && data.hourly) || {};
    return {
      time:      h.time || [],
      wind:      h.wind_speed_10m || h.wind_speed || [],
      gusts:     h.wind_gusts_10m || h.wind_gusts || null,
      wind_dir:  h.wind_direction_10m || h.wind_direction || null,
      hs:        h.hs || h.wave_height || null,
      wcode:     h.weather_code || null,
      vis_km:    Array.isArray(h.visibility) ? h.visibility.map(visToKm) : null,
    };
  }

  // First failing reason for a Family window of RULES.corridor.minHours strictly within family hours
  function firstFailForWindow(_cls, series, tz, slugOrFile){
    const windCap  = RULES.wind.family_max_kmh;
    const windHard = RULES.wind.nogo_min_kmh;
    const hsCap    = RULES.sea.family_max_hs_m;
    const hsHard   = RULES.sea.nogo_min_hs_m;

    const startM = RULES.family_hours_local.start_h*60; // 08:00
    const endM   = RULES.family_hours_local.end_h*60;   // 21:00 (exclusive)

    const segHours = RULES.corridor.minHours; // 4h minimum
    const N = (series.time||[]).length;
    const ranges = onshoreRanges(slugOrFile);

    for(let i=0;i+segHours<=N;i++){
      // all timestamps must be within [08:00, 21:00)
      let allDay = true;
      for(let k=0;k<segHours;k++){
        const mm = minutesLocal(series.time[i+k], tz);
        if(mm==null || mm < startM || mm >= endM){ allDay=false; break; }
      }
      if(!allDay) continue;

      // scan the segment and return the first failure
      for(let k=0;k<segHours;k++){
        const t  = series.time[i+k];
        const ws = series.wind?.[i+k];
        const gu = series.gusts?.[i+k];
        const wd = series.wind_dir?.[i+k];
        const hs = series.hs?.[i+k];
        const wc = series.wcode?.[i+k];
        const vk = series.vis_km?.[i+k];

        // hard no-go first (align reader.py)
        if (wc!=null && RULES.overrides.thunder_wmo.includes(Number(wc))) {
          return `orages (code ${wc}) à ${t}`;
        }
        if (vk!=null && vk < RULES.overrides.visibility_km_min) {
          return `vis<${RULES.overrides.visibility_km_min}km à ${t}`;
        }
        if (typeof gu==='number' && gu >= RULES.overrides.gusts_hard_nogo_kmh) {
          return `rafales≥${RULES.overrides.gusts_hard_nogo_kmh} km/h à ${t}`;
        }
        if (typeof ws==='number' && typeof gu==='number' &&
            (gu - ws) >= RULES.overrides.squall_delta_kmh) {
          return `squalls Δ≥${RULES.overrides.squall_delta_kmh} à ${t}`;
        }

        if (typeof ws==='number' && ws >= windHard) return `vent ${ws} ≥ ${windHard} km/h à ${t}`;
        if (typeof hs==='number' && hs >= hsHard)   return `vagues ${hs.toFixed(2)} ≥ ${hsHard} m à ${t}`;

        // family caps (include onshore downgrade)
        if (typeof ws==='number' && ws > windCap){
          if (typeof wd==='number' && angleInRanges(wd, ranges) && ws >= RULES.wind.onshore_degrade_kmh){
            return `vent onshore ${ws} ≥ ${RULES.wind.onshore_degrade_kmh} km/h à ${t}`;
          }
          return `vent ${ws} > ${windCap} km/h à ${t}`;
        }
        if (typeof hs==='number' && hs > hsCap) return `vagues ${hs.toFixed(2)} > ${hsCap} m à ${t}`;
      }
      // If we reach here, this 4h segment is acceptable for Family → success
      return null;
    }

    return `aucune fenêtre de ${segHours}h dans ${RULES.family_hours_local.start_h}:00-${RULES.family_hours_local.end_h}:00`;
  }

  async function loadSpot(path){
    try{ const r=await fetch(path,{cache:'no-store'}); if(!r.ok) throw 0; return await r.json(); }
    catch{ return null; }
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

      const famFail = firstFailForWindow("family", series, tz, spot.meta?.slug || p);

      rows.push({
        spot: (spot.meta && spot.meta.name) ? `${spot.meta.name} (${p})` : p,
        family: famFail ? `✗ ${famFail}` : "✓ fenêtre possible",
        expert: "— non évalué (backend famille uniquement)"
      });
    }
    console.table(rows);
    return rows;
  };

})(window.FABLE);
