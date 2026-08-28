const TUNIS_TZ = 'Africa/Tunis';

const TEXT = {
  fr: {
    title:'Vent et mer sur 72 h', curves:'Courbes', table:'Tableau', all:'72 h',
    wind:'Vent', gust:'Rafales', wave:'Houle Hs', family:'Dans les limites',
    prudent:'Prudence', watch:'À surveiller', noGo:'NO-GO', night:'Nuit',
    time:'Heure', state:'État', reason:'Cause principale', source:'Source',
    quality:'Qualité', period:'Tp', modelSpread:'Écart modèles vent', noReason:'Dans les limites Family pour cette heure.',
    hourlyWarning:'Une heure favorable ne valide pas une sortie complète.',
    loading:'Chargement du graphique…', unavailable:'Données horaires indisponibles.',
    destination:'Destination', windLimit:'Limite vent Family', gustLimit:'Veto rafales',
    waveLimit:'Limite houle Family', selectHint:'Touchez ou glissez pour lire une heure.',
  },
  en: {
    title:'Wind and sea over 72 h', curves:'Charts', table:'Table', all:'72 h',
    wind:'Wind', gust:'Gusts', wave:'Wave Hs', family:'Within limits',
    prudent:'Caution', watch:'Watch', noGo:'NO-GO', night:'Night',
    time:'Time', state:'State', reason:'Main cause', source:'Source',
    quality:'Quality', period:'Tp', modelSpread:'Wind model spread', noReason:'Within Family limits for this hour.',
    hourlyWarning:'A favourable hour does not validate a complete outing.',
    loading:'Loading chart…', unavailable:'Hourly data unavailable.',
    destination:'Destination', windLimit:'Family wind limit', gustLimit:'Gust veto',
    waveLimit:'Family wave limit', selectHint:'Tap or drag to inspect an hour.',
  },
  ar: {
    title:'الرياح والبحر خلال 72 ساعة', curves:'منحنيات', table:'جدول', all:'72 س',
    wind:'الرياح', gust:'الهبات', wave:'ارتفاع الموج', family:'ضمن الحدود',
    prudent:'حذر', watch:'تحت المراقبة', noGo:'غير مناسب', night:'ليل',
    time:'الساعة', state:'الحالة', reason:'السبب الرئيسي', source:'المصدر',
    quality:'الجودة', period:'Tp', modelSpread:'فرق نماذج الرياح', noReason:'ضمن حدود العائلة لهذه الساعة.',
    hourlyWarning:'ساعة ملائمة لا تعني أن الرحلة الكاملة صالحة.',
    loading:'جارٍ تحميل الرسم…', unavailable:'البيانات الساعية غير متاحة.',
    destination:'الوجهة', windLimit:'حد رياح العائلة', gustLimit:'حد منع الهبات',
    waveLimit:'حد موج العائلة', selectHint:'المس أو اسحب لقراءة ساعة.',
  },
};

const esc = (value) => String(value ?? '').replace(
  /[&<>"']/g,
  (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]),
);
const text = (language) => TEXT[language] || TEXT.fr;
const finite = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
const number = (value) => finite(value) ? Number(value) : null;

export function tunisDateKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone:TUNIS_TZ, year:'numeric', month:'2-digit', day:'2-digit',
  }).formatToParts(date).reduce((result, part) => ({...result, [part.type]:part.value}), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function hourLabel(value, language, withDay = false) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '—';
  return date.toLocaleString(language === 'ar' ? 'ar-TN' : language === 'en' ? 'en-GB' : 'fr-FR', {
    timeZone:TUNIS_TZ,
    weekday:withDay ? 'short' : undefined,
    hour:'2-digit', minute:'2-digit', hour12:false,
  });
}

function dayChipLabel(key, language) {
  return new Date(`${key}T12:00:00Z`).toLocaleDateString(
    language === 'ar' ? 'ar-TN' : language === 'en' ? 'en-GB' : 'fr-FR',
    {weekday:'short', day:'numeric', timeZone:'UTC'},
  );
}

export function recordsForRange(payload, range) {
  const hours = Array.isArray(payload?.hours) ? payload.hours : [];
  return range && range !== '72h' ? hours.filter((record) => tunisDateKey(record.time) === range) : hours;
}

export function mainReason(record, language = 'fr') {
  const reasons = Array.isArray(record?.reasons) ? record.reasons : [];
  const reason = reasons.find((item) => item.severity === 'hard_veto') || reasons[0];
  return reason?.[`reason_${language === 'en' ? 'en' : 'fr'}`] || text(language).noReason;
}

function stateLabel(state, language) {
  const c = text(language);
  return {family:c.family, prudent:c.prudent, watch:c.watch, no_go:c.noGo}[state] || c.noGo;
}

function confidenceLabel(value, language) {
  const labels = {
    fr:{High:'Élevée',Medium:'Moyenne',Low:'Limitée'},
    en:{High:'High',Medium:'Medium',Low:'Limited'},
    ar:{High:'مرتفعة',Medium:'متوسطة',Low:'محدودة'},
  };
  return labels[language]?.[value] || labels.fr[value] || '—';
}

function metric(record, group, name) {
  return number(record?.metrics?.[group]?.[name]);
}

function points(records, accessor, x, y) {
  return records.map((record, index) => {
    const value = accessor(record);
    return value === null ? null : `${x(index).toFixed(2)},${y(value).toFixed(2)}`;
  });
}

function pathFromPoints(values) {
  let drawing = false;
  return values.map((point) => {
    if (!point) { drawing = false; return ''; }
    const command = drawing ? 'L' : 'M';
    drawing = true;
    return `${command}${point}`;
  }).filter(Boolean).join(' ');
}

function ribbonPath(windPoints, gustPoints) {
  const paired = windPoints.map((wind, index) => ({wind, gust:gustPoints[index]})).filter((item) => item.wind && item.gust);
  if (paired.length < 2) return '';
  return `M${paired.map((item) => item.gust).join(' L')} L${paired.reverse().map((item) => item.wind).join(' L')} Z`;
}

function chartSvg(records, rules, cursor, language) {
  const c = text(language);
  const width = 620; const height = 286; const left = 42; const right = 12;
  const plotWidth = width - left - right; const count = Math.max(records.length, 1);
  const x = (index) => left + (count === 1 ? plotWidth / 2 : index * plotWidth / (count - 1));
  const windValues = records.flatMap((record) => [
    metric(record,'wind','display_speed_kmh'), metric(record,'wind','display_gust_kmh'),
  ]).filter((value) => value !== null);
  const waveValues = records.map((record) => metric(record,'wave','display_hs_m')).filter((value) => value !== null);
  const thresholds = rules?.family?.thresholds || {};
  const windFamily = Number(thresholds?.wind?.family_max_kmh ?? rules?.wind?.family_max_kmh ?? 22);
  const gustVeto = Number(thresholds?.gusts?.no_go_min_kmh ?? rules?.overrides?.gusts_hard_nogo_kmh ?? 30);
  const waveFamily = Number(thresholds?.waves?.hs_family_max_m ?? rules?.sea?.family_max_hs_m ?? .5);
  const windMax = Math.max(40, gustVeto + 5, ...windValues); const waveMax = Math.max(.6, waveFamily, ...waveValues);
  const windTop = 42; const windBottom = 169; const waveTop = 202; const waveBottom = 258;
  const windY = (value) => windBottom - Math.max(0,value) / windMax * (windBottom-windTop);
  const waveY = (value) => waveBottom - Math.max(0,value) / waveMax * (waveBottom-waveTop);
  const windPoints = points(records, (record) => metric(record,'wind','display_speed_kmh'), x, windY);
  const gustPoints = points(records, (record) => metric(record,'wind','display_gust_kmh'), x, windY);
  const wavePoints = points(records, (record) => metric(record,'wave','display_hs_m'), x, waveY);
  const selected = Math.max(0, Math.min(records.length - 1, cursor));
  const selectedX = x(selected);
  const segmentWidth = plotWidth / count + .5;
  const stateRects = records.map((record,index) => `<rect class="hourly-state ${esc(record.condition_state)}" x="${(left + index*plotWidth/count).toFixed(2)}" y="12" width="${segmentWidth.toFixed(2)}" height="11" fill="url(#hourly-${esc(record.condition_state)})"><title>${esc(hourLabel(record.time,language,true))} · ${esc(stateLabel(record.condition_state,language))}</title></rect>`).join('');
  const nightRects = records.map((record,index) => record.operating_light === false ? `<rect class="hourly-night" x="${(left + index*plotWidth/count).toFixed(2)}" y="30" width="${segmentWidth.toFixed(2)}" height="${waveBottom-30}"></rect>` : '').join('');
  const axisIndexes = [...new Set([0, Math.floor((count-1)/3), Math.floor(2*(count-1)/3), count-1])];
  const xLabels = axisIndexes.map((index) => `<text x="${x(index)}" y="280" text-anchor="${index===0?'start':index===count-1?'end':'middle'}">${esc(hourLabel(records[index]?.time,language,records.length>24))}</text>`).join('');
  const grid = [0,.5,1].map((ratio) => {
    const y = windBottom - ratio*(windBottom-windTop);
    return `<line class="hourly-grid" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"></line><text x="${left-7}" y="${y+3}" text-anchor="end">${Math.round(ratio*windMax)}</text>`;
  }).join('');
  const selectedRecord = records[selected];
  const aria = selectedRecord ? `${c.title}. ${hourLabel(selectedRecord.time,language,true)}. ${stateLabel(selectedRecord.condition_state,language)}. ${mainReason(selectedRecord,language)}` : c.unavailable;
  return `<svg class="hourly-chart-svg" viewBox="0 0 ${width} ${height}" role="img" tabindex="0" data-hour-count="${records.length}" aria-label="${esc(aria)}">
    <defs>
      <pattern id="hourly-family" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#07932b"></rect></pattern>
      <pattern id="hourly-prudent" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#9a6b00"></rect><rect width="3" height="8" fill="#fbbf24"></rect></pattern>
      <pattern id="hourly-watch" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#7c4a03"></rect><circle cx="2" cy="2" r="1.5" fill="#f59e0b"></circle><circle cx="6" cy="6" r="1.5" fill="#f59e0b"></circle></pattern>
      <pattern id="hourly-no_go" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(135)"><rect width="8" height="8" fill="#6f1d25"></rect><rect width="3" height="8" fill="#ef4444"></rect></pattern>
      <linearGradient id="hourly-ribbon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f97316" stop-opacity=".28"></stop><stop offset="1" stop-color="#f97316" stop-opacity=".04"></stop></linearGradient>
    </defs>
    ${stateRects}${nightRects}${grid}
    <line class="hourly-threshold wind" x1="${left}" y1="${windY(windFamily)}" x2="${width-right}" y2="${windY(windFamily)}"><title>${esc(c.windLimit)} ${windFamily} km/h</title></line>
    <line class="hourly-threshold gust" x1="${left}" y1="${windY(gustVeto)}" x2="${width-right}" y2="${windY(gustVeto)}"><title>${esc(c.gustLimit)} ${gustVeto} km/h</title></line>
    <path class="hourly-ribbon" d="${ribbonPath(windPoints,gustPoints)}"></path>
    <path class="hourly-line wind" d="${pathFromPoints(windPoints)}"></path>
    <path class="hourly-line gust" d="${pathFromPoints(gustPoints)}"></path>
    <line class="hourly-grid" x1="${left}" y1="${waveBottom}" x2="${width-right}" y2="${waveBottom}"></line>
    <line class="hourly-threshold wave" x1="${left}" y1="${waveY(waveFamily)}" x2="${width-right}" y2="${waveY(waveFamily)}"><title>${esc(c.waveLimit)} ${waveFamily} m</title></line>
    <path class="hourly-line wave" d="${pathFromPoints(wavePoints)}"></path>
    <text x="${left-7}" y="${waveTop+3}" text-anchor="end">${waveMax.toFixed(1)}</text><text x="${left-7}" y="${waveBottom+3}" text-anchor="end">0</text>
    <line class="hourly-cursor" x1="${selectedX}" y1="8" x2="${selectedX}" y2="${waveBottom}"></line>
    <circle class="hourly-cursor-point wind" cx="${selectedX}" cy="${windY(metric(selectedRecord,'wind','display_speed_kmh') || 0)}" r="4"></circle>
    <circle class="hourly-cursor-point gust" cx="${selectedX}" cy="${windY(metric(selectedRecord,'wind','display_gust_kmh') || 0)}" r="4"></circle>
    <circle class="hourly-cursor-point wave" cx="${selectedX}" cy="${waveY(metric(selectedRecord,'wave','display_hs_m') || 0)}" r="4"></circle>
    ${xLabels}
  </svg>`;
}

function selectedCard(record, language) {
  if (!record) return '';
  const c = text(language); const wind = record.metrics?.wind || {}; const wave = record.metrics?.wave || {};
  const value = (item, digits, unit) => finite(item) ? `${Number(item).toFixed(digits)} ${unit}` : '—';
  const sources = [wind.display_source, wave.display_source].filter(Boolean).join(' · ');
  const spread = finite(wind.model_spread_kmh) ? `${c.modelSpread} ${Number(wind.model_spread_kmh).toFixed(1)} km/h` : '';
  const reasons = (record.reasons || []).map((reason) => reason[`reason_${language === 'en' ? 'en' : 'fr'}`]).filter(Boolean);
  return `<div class="hourly-selected ${esc(record.condition_state)}" aria-live="polite">
    <time datetime="${esc(record.time)}">${esc(hourLabel(record.time,language,true))}</time>
    <span><small>${esc(c.wind)}</small><strong>${esc(value(wind.display_speed_kmh,0,'km/h'))}</strong></span>
    <span><small>${esc(c.gust)}</small><strong>${esc(value(wind.display_gust_kmh,0,'km/h'))}</strong></span>
    <span><small>${esc(c.wave)} · ${esc(c.period)}</small><strong>${esc(value(wave.display_hs_m,2,'m'))} · ${esc(value(wave.display_tp_s,1,'s'))}</strong></span>
    <b class="hourly-state-badge">${esc(stateLabel(record.condition_state,language))}</b>
  </div><div class="hourly-explanation ${esc(record.condition_state)}"><strong>${esc(mainReason(record,language))}</strong><span>${esc(c.quality)} : ${esc(confidenceLabel(record.confidence,language))}${spread ? ` · ${esc(spread)}` : ''}${sources ? ` · ${esc(c.source)} : ${esc(sources)}` : ''}</span>${reasons.length > 1 ? `<ul>${reasons.map((reason) => `<li>${esc(reason)}</li>`).join('')}</ul>` : ''}</div>`;
}

function tableView(records, language) {
  const c = text(language);
  return `<div class="hourly-table-wrap"><table class="hourly-table"><thead><tr><th>${esc(c.time)}</th><th>${esc(c.wind)}</th><th>${esc(c.gust)}</th><th>${esc(c.wave)}</th><th>${esc(c.state)}</th><th>${esc(c.reason)}</th></tr></thead><tbody>${records.map((record) => {
    const wind=record.metrics?.wind||{}; const wave=record.metrics?.wave||{};
    return `<tr class="${esc(record.condition_state)}"><td>${esc(hourLabel(record.time,language,true))}</td><td>${finite(wind.display_speed_kmh)?`${Number(wind.display_speed_kmh).toFixed(0)} km/h`:'—'}</td><td>${finite(wind.display_gust_kmh)?`${Number(wind.display_gust_kmh).toFixed(0)} km/h`:'—'}</td><td>${finite(wave.display_hs_m)?`${Number(wave.display_hs_m).toFixed(2)} m`:'—'}</td><td><span class="hourly-state-badge">${esc(stateLabel(record.condition_state,language))}</span></td><td>${esc(mainReason(record,language))}</td></tr>`;
  }).join('')}</tbody></table></div>`;
}

export function renderHourlyExplorer({payload, destinations = [], selectedSlug = '', rules = {}, mode = 'curves', range = '72h', cursorTime = '', language = 'fr', loading = false, error = ''}) {
  const c = text(language);
  if (loading) return `<section id="simple-hourly-explorer" class="simple-panel hourly-explorer"><div class="hourly-empty" role="status">${esc(c.loading)}</div></section>`;
  if (error || !Array.isArray(payload?.hours) || !payload.hours.length) return `<section id="simple-hourly-explorer" class="simple-panel hourly-explorer"><div class="hourly-empty" role="alert">${esc(c.unavailable)}</div></section>`;
  const dates = [...new Set(payload.hours.map((record) => tunisDateKey(record.time)).filter(Boolean))];
  const activeRange = range === '72h' || dates.includes(range) ? range : '72h';
  const records = recordsForRange(payload, activeRange);
  const cursorIndex = Math.max(0, cursorTime ? records.findIndex((record) => record.time === cursorTime) : 0);
  const selected = records[cursorIndex < 0 ? 0 : cursorIndex];
  const destinationOptions = destinations.map((item) => `<option value="${esc(item.dest_slug)}"${item.dest_slug===selectedSlug?' selected':''}>${esc(item.dest_name || item.dest_slug)}</option>`).join('');
  const chips = [`<button type="button" class="hourly-chip${activeRange==='72h'?' active':''}" data-hourly-range="72h">${esc(c.all)}</button>`, ...dates.map((key) => `<button type="button" class="hourly-chip${activeRange===key?' active':''}" data-hourly-range="${esc(key)}">${esc(dayChipLabel(key,language))}</button>`)].join('');
  const content = mode === 'table' ? tableView(records,language) : `${chartSvg(records,rules,Math.max(0,cursorIndex),language)}<p class="hourly-touch-hint">${esc(c.selectHint)}</p>`;
  return `<section id="simple-hourly-explorer" class="simple-panel hourly-explorer" data-hourly-range-current="${esc(activeRange)}">
    <div class="hourly-head"><div><label for="hourly-destination">${esc(c.destination)}</label><select id="hourly-destination" data-hourly-destination>${destinationOptions}</select></div><div class="hourly-view-toggle" role="group" aria-label="${esc(c.title)}"><button type="button" data-hourly-mode="curves" class="${mode==='curves'?'active':''}" aria-pressed="${mode==='curves'}">${esc(c.curves)}</button><button type="button" data-hourly-mode="table" class="${mode==='table'?'active':''}" aria-pressed="${mode==='table'}">${esc(c.table)}</button></div></div>
    <div class="hourly-title"><h2>${esc(c.title)}</h2><span>${esc(payload.dest_name || '')}${payload.rules_digest ? ` · rules ${esc(String(payload.rules_digest).slice(0,8))}` : ''}</span></div>
    <div class="hourly-chips" role="group" aria-label="${esc(c.title)}">${chips}</div>
    <div class="hourly-chart-stage" data-hourly-stage>${content}</div>
    <div class="hourly-legend"><span class="wind">${esc(c.wind)}</span><span class="gust">${esc(c.gust)}</span><span class="wave">${esc(c.wave)}</span><span class="family">${esc(c.family)}</span><span class="prudent">${esc(c.prudent)}</span><span class="watch">${esc(c.watch)}</span><span class="no_go">${esc(c.noGo)}</span><span class="night">${esc(c.night)}</span></div>
    ${selectedCard(selected,language)}<p class="hourly-safety-note">${esc(c.hourlyWarning)}</p>
  </section>`;
}

export function cursorTimeFromPointer(svg, clientX, payload, range) {
  const records = recordsForRange(payload, range);
  if (!records.length) return '';
  const box = svg.getBoundingClientRect();
  const plotLeft = box.left + box.width * (42/620); const plotRight = box.right - box.width * (12/620);
  const ratio = Math.max(0, Math.min(1, (clientX - plotLeft) / Math.max(1, plotRight-plotLeft)));
  return records[Math.round(ratio*(records.length-1))]?.time || '';
}

export function installHourlyChartStyles() {
  if (document.getElementById('fable-hourly-chart-styles')) return;
  const style=document.createElement('style'); style.id='fable-hourly-chart-styles';
  style.textContent=`
    .hourly-explorer{overflow:hidden;background:linear-gradient(145deg,color-mix(in srgb,#0f2848 38%,var(--card)),var(--card) 65%)}
    .hourly-head,.hourly-title{display:flex;align-items:end;justify-content:space-between;gap:12px}.hourly-head label{display:block;margin-bottom:4px;color:var(--muted);font-size:.66rem;font-weight:800;text-transform:uppercase}.hourly-head select{min-height:44px;max-width:210px;padding:8px 32px 8px 10px;border:1px solid var(--br);border-radius:12px;background:var(--pill-bg);color:var(--fg);font-weight:850}.hourly-view-toggle{display:flex;padding:3px;border:1px solid var(--br);border-radius:999px;background:#03070dcc}.hourly-view-toggle button{min-height:38px;padding:7px 13px;border:0;border-radius:999px;background:transparent;color:var(--muted);font-weight:850;cursor:pointer}.hourly-view-toggle button.active{background:#314665;color:#fff}.hourly-title{margin-top:14px}.hourly-title h2{font-size:1.05rem}.hourly-title span{color:var(--muted);font-size:.72rem}.hourly-chips{display:flex;gap:7px;margin:12px 0;overflow-x:auto;scrollbar-width:none}.hourly-chip{min-width:62px;min-height:42px;padding:7px 12px;border:1px solid var(--br);border-radius:11px;background:var(--pill-bg);color:var(--muted);font-weight:850;white-space:nowrap;cursor:pointer}.hourly-chip.active{border-color:#35c1e8;background:#12354a;color:#58d5f5;box-shadow:inset 0 0 0 1px #35c1e866}.hourly-chart-stage{min-height:250px}.hourly-chart-svg{display:block;width:100%;height:auto;max-height:330px;touch-action:none;user-select:none}.hourly-chart-svg text{fill:var(--muted);font:10px ui-monospace,SFMono-Regular,Consolas,monospace}.hourly-grid{stroke:#26374f;stroke-width:1}.hourly-night{fill:#03070d;opacity:.62}.hourly-threshold{stroke-width:1.3;stroke-dasharray:5 4}.hourly-threshold.wind,.hourly-threshold.wave{stroke:#d99c19}.hourly-threshold.gust{stroke:#e44952}.hourly-ribbon{fill:url(#hourly-ribbon)}.hourly-line{fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.hourly-line.wind{stroke:#3987e5}.hourly-line.gust{stroke:#d95926}.hourly-line.wave{stroke:#199e70}.hourly-cursor{stroke:#dbeafe;stroke-width:1.4;opacity:.72}.hourly-cursor-point{stroke:#07111f;stroke-width:2}.hourly-cursor-point.wind{fill:#3987e5}.hourly-cursor-point.gust{fill:#d95926}.hourly-cursor-point.wave{fill:#199e70}.hourly-touch-hint{margin:2px 0 0;color:var(--muted);font-size:.65rem;text-align:center}.hourly-legend{display:flex;flex-wrap:wrap;gap:8px 13px;margin-top:10px;color:var(--muted);font-size:.68rem}.hourly-legend span::before{content:'';display:inline-block;width:17px;height:8px;margin-inline-end:5px;border-radius:2px;vertical-align:middle}.hourly-legend .wind::before{height:2px;background:#3987e5}.hourly-legend .gust::before{height:2px;background:#d95926}.hourly-legend .wave::before{height:2px;background:#199e70}.hourly-legend .family::before{background:#07932b}.hourly-legend .prudent::before{background:repeating-linear-gradient(45deg,#fbbf24 0 3px,#7c5700 3px 6px)}.hourly-legend .watch::before{background:radial-gradient(circle,#f59e0b 0 1.5px,#6d4100 2px)}.hourly-legend .no_go::before{background:repeating-linear-gradient(135deg,#ef4444 0 3px,#6f1d25 3px 6px)}.hourly-legend .night::before{border:1px solid #26374f;background:#03070d}.hourly-selected{display:grid;grid-template-columns:1.2fr repeat(3,1fr) auto;align-items:center;gap:9px;margin-top:13px;padding:12px;border-radius:14px;background:color-mix(in srgb,var(--pill-bg) 90%,#0b223d)}.hourly-selected time{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.9rem;font-weight:900}.hourly-selected span small,.hourly-selected span strong{display:block}.hourly-selected span small{color:var(--muted);font-size:.58rem;text-transform:uppercase}.hourly-selected span strong{margin-top:2px;font-size:.82rem}.hourly-state-badge{display:inline-block;padding:4px 7px;border-radius:7px;background:#07932b22;color:#45d36b;font-size:.65rem;white-space:nowrap}.prudent .hourly-state-badge{background:#fbbf2422;color:#fbbf24}.watch .hourly-state-badge{background:#f59e0b22;color:#f59e0b}.no_go .hourly-state-badge{background:#ef444422;color:#ff646d}.hourly-explanation{display:grid;gap:4px;margin-top:8px;padding:10px 12px;border-inline-start:3px solid #07932b;border-radius:8px;background:#02071255}.hourly-explanation.prudent{border-color:#fbbf24}.hourly-explanation.watch{border-color:#f59e0b}.hourly-explanation.no_go{border-color:#ef4444}.hourly-explanation strong{font-size:.78rem}.hourly-explanation span,.hourly-explanation li{color:var(--muted);font-size:.68rem}.hourly-explanation ul{margin:4px 0 0;padding-inline-start:18px}.hourly-safety-note{margin:9px 0 0;color:var(--muted);font-size:.64rem}.hourly-table-wrap{max-height:390px;overflow:auto;border:1px solid var(--br);border-radius:12px}.hourly-table{width:100%;min-width:720px;border-collapse:collapse;font-size:.7rem}.hourly-table th{position:sticky;top:0;z-index:1;background:#0b1626;color:var(--muted);text-align:start}.hourly-table th,.hourly-table td{padding:9px;border-bottom:1px solid var(--br)}.hourly-table tr.no_go td:first-child{border-inline-start:3px solid #ef4444}.hourly-table tr.prudent td:first-child{border-inline-start:3px solid #fbbf24}.hourly-table tr.watch td:first-child{border-inline-start:3px dotted #f59e0b}.hourly-empty{padding:32px 12px;color:var(--muted);text-align:center}
    .hourly-view-toggle button:focus-visible,.hourly-chip:focus-visible,.hourly-head select:focus-visible,.hourly-chart-svg:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
    @media(max-width:520px){.hourly-explorer{padding:13px}.hourly-head{align-items:stretch}.hourly-head select{max-width:165px}.hourly-view-toggle button{padding:7px 9px}.hourly-selected{grid-template-columns:1fr 1fr 1fr}.hourly-selected time{grid-column:1/3}.hourly-selected .hourly-state-badge{justify-self:end}.hourly-selected span{min-width:0}.hourly-selected span strong{font-size:.74rem}.hourly-chart-svg{min-width:0}.hourly-legend{gap:7px 10px}}
    @media(forced-colors:active){.hourly-state{stroke:CanvasText}.hourly-line{stroke:CanvasText!important}.hourly-state-badge{border:1px solid CanvasText}}
  `;
  document.head.appendChild(style);
}
