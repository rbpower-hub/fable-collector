/* FABLE field validation journal — local-first, exportable, no automatic rule changes. */
(function () {
  const STORAGE_KEY = 'fable_field_logs_v1';
  const TUNIS_TZ = 'Africa/Tunis';
  const state = { sites: [], windows: null, status: null, snapshot: null, records: [] };

  const $ = (id) => document.getElementById(id);
  const numberOrNull = (value) => value === '' || value == null ? null : Number(value);
  const nowLocalInput = () => {
    const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
    return date.toISOString().slice(0, 16);
  };
  const asIso = (value) => value ? new Date(value).toISOString() : null;
  const safeText = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function themeFromBoard() {
    const theme = localStorage.getItem('theme');
    document.documentElement.dataset.theme = theme === 'dark' ? 'dark' : 'nautical';
  }

  async function loadJson(path) {
    try {
      const response = await fetch(path, {cache: 'no-store'});
      return response.ok ? await response.json() : null;
    } catch {
      return null;
    }
  }

  function loadRecords() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      state.records = Array.isArray(parsed) ? parsed : [];
    } catch {
      state.records = [];
    }
  }

  function saveRecords() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.records));
  }

  function destinationItem(path) {
    return (state.windows?.windows || []).find((item) => String(item.dest_slug || '') === String(path || '')) || null;
  }

  function selectedForecastWindow(destination, plannedAt) {
    const target = new Date(plannedAt || '').getTime();
    const windows = Array.isArray(destination?.windows) ? destination.windows : [];
    if (!windows.length || !Number.isFinite(target)) return null;
    return windows
      .map((item) => {
        const start = new Date(item.start || '').getTime();
        const end = new Date(item.end || '').getTime();
        const within = Number.isFinite(start) && Number.isFinite(end) && target >= start && target <= end;
        const distance = within ? 0 : Math.min(Math.abs(target - start), Math.abs(target - end));
        return {item, distance};
      })
      .sort((a, b) => a.distance - b.distance)[0]?.item || null;
  }

  function decisionFor(destination, windowItem) {
    if (!state.windows) return 'NO_DATA';
    if (!destination) return 'NO_DATA';
    if (!windowItem) return 'NO_GO';
    if (String(windowItem.family_tier || '').toLowerCase() === 'prudent') return 'PRUDENT_GO';
    if (String(windowItem.category || '').toLowerCase() === 'family') return 'FAMILY_GO';
    return 'OTHER_WINDOW';
  }

  function decisionLabel(value) {
    return {
      FAMILY_GO: 'FAMILY GO', PRUDENT_GO: 'GO PRUDENT', NO_GO: 'NO-GO',
      NO_DATA: 'DONNÉES ABSENTES', OTHER_WINDOW: 'FENÊTRE NON FAMILIALE',
    }[value] || value;
  }

  function buildSnapshot() {
    const path = $('destination').value;
    const site = state.sites.find((item) => item.path === path) || null;
    const plannedAt = $('planned-at').value;
    const destination = destinationItem(path);
    const windowItem = selectedForecastWindow(destination, plannedAt);
    const decision = decisionFor(destination, windowItem);
    state.snapshot = {
      captured_at: new Date().toISOString(),
      forecast_generated_at: state.windows?.generated_at || state.status?.generated_at || null,
      destination_path: path,
      destination_name: destination?.dest_name || site?.name || path,
      route_kind: destination?.route_kind || site?.route_kind || 'standard',
      trip_mode: destination?.trip_mode || windowItem?.trip_mode || 'round_trip_same_day',
      planned_at: asIso(plannedAt),
      decision,
      window: windowItem ? {
        start: windowItem.start || null,
        end: windowItem.end || null,
        family_tier: windowItem.family_tier || null,
        confidence: windowItem.confidence || null,
        confidence_score: numberOrNull(windowItem.confidence_score),
        models: Array.isArray(windowItem.models) ? windowItem.models : [],
        spreads: windowItem.spreads || null,
      } : null,
      diagnostics: destination?.diagnostics || null,
    };
    renderSnapshot();
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '—';
    return date.toLocaleString('fr-TN', {timeZone: TUNIS_TZ, dateStyle: 'medium', timeStyle: 'short'});
  }

  function renderSnapshot() {
    const box = $('snapshot');
    const snapshot = state.snapshot;
    if (!snapshot) {
      box.innerHTML = '<strong>Prévision indisponible</strong><span class="muted">Le journal peut être enregistré, mais la comparaison sera incomplète.</span>';
      return;
    }
    const confidence = snapshot.window?.confidence ? ` · confiance ${safeText(snapshot.window.confidence)}` : '';
    const period = snapshot.window ? ` · ${formatDate(snapshot.window.start)} → ${formatDate(snapshot.window.end)}` : '';
    box.innerHTML = `<strong>${safeText(decisionLabel(snapshot.decision))} · ${safeText(snapshot.destination_name)}</strong><span>${safeText(formatDate(snapshot.planned_at))}${period}${confidence}</span><span class="muted">Prévision générée : ${safeText(formatDate(snapshot.forecast_generated_at))}</span>`;
  }

  function classify(record) {
    const decision = record.forecast?.decision;
    const performed = record.observation_type === 'outing';
    const shore = record.observation_type === 'shore';
    const comfort = Number(record.actual?.comfort || 0);
    const problem = Boolean(record.actual?.early_return || record.actual?.incident || comfort && comfort <= 2);
    const positive = performed && comfort >= 4 && !record.actual?.early_return && !record.actual?.incident;
    const benignShore = shore && ['calm', 'slight'].includes(record.actual?.observed_sea) && !record.actual?.incident;

    if (['FAMILY_GO', 'PRUDENT_GO'].includes(decision) && positive) return 'confirmed_go';
    if (['FAMILY_GO', 'PRUDENT_GO'].includes(decision) && performed && problem) return 'false_go';
    if (decision === 'NO_GO' && benignShore) return 'conservative_observation';
    if (decision === 'NO_GO' && record.observation_type === 'cancelled') return 'no_go_respected';
    return 'inconclusive';
  }

  function classificationLabel(value) {
    return {
      confirmed_go: 'GO confirmé', false_go: 'GO à revoir',
      conservative_observation: 'Observation conservatrice', no_go_respected: 'NO-GO respecté',
      inconclusive: 'Non concluant',
    }[value] || value;
  }

  function classificationClass(value) {
    if (value === 'confirmed_go' || value === 'no_go_respected') return 'good';
    if (value === 'false_go') return 'bad';
    return 'warn';
  }

  function formRecord() {
    const record = {
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      schema_version: 1,
      saved_at: new Date().toISOString(),
      forecast: JSON.parse(JSON.stringify(state.snapshot || {})),
      observation_type: $('observation-type').value,
      crew: { adults: Number($('adults').value), children: Number($('children').value) },
      actual: {
        start: asIso($('actual-start').value), end: asIso($('actual-end').value),
        comfort: numberOrNull($('comfort').value), observed_sea: $('observed-sea').value,
        wind_kmh: numberOrNull($('wind').value), gust_kmh: numberOrNull($('gust').value),
        wave_height_m: numberOrNull($('wave-height').value), wave_period_s: numberOrNull($('wave-period').value),
        early_return: $('early-return').checked, wet_ride: $('wet-ride').checked,
        incident: $('incident').checked, notes: $('notes').value.trim(),
      },
    };
    record.classification = classify(record);
    return record;
  }

  function validateRecord(record) {
    if (!record.forecast?.destination_path) return 'Choisir une destination.';
    if (!record.forecast?.planned_at) return 'Renseigner la date prévue.';
    if (record.observation_type === 'outing' && !record.actual.comfort) return 'Évaluer le confort familial pour une sortie effectuée.';
    if (record.observation_type !== 'outing' && record.actual.early_return) return 'Un retour anticipé suppose une sortie effectuée.';
    return null;
  }

  function routeStats() {
    const map = new Map();
    state.records.forEach((record) => {
      const key = record.forecast?.destination_name || record.forecast?.destination_path || 'Inconnue';
      const item = map.get(key) || {count: 0, review: 0};
      item.count += 1;
      if (record.classification === 'false_go') item.review += 1;
      map.set(key, item);
    });
    return [...map.entries()].sort((a, b) => b[1].count - a[1].count);
  }

  function renderSummary() {
    $('stat-total').textContent = state.records.length;
    $('stat-confirmed').textContent = state.records.filter((item) => item.classification === 'confirmed_go').length;
    $('stat-false-go').textContent = state.records.filter((item) => item.classification === 'false_go').length;
    $('stat-conservative').textContent = state.records.filter((item) => item.classification === 'conservative_observation').length;
    const tbody = $('route-summary');
    const rows = routeStats();
    tbody.innerHTML = rows.length ? rows.map(([name, stats]) => `<tr><td>${safeText(name)}</td><td>${stats.count}</td><td>${stats.review}</td></tr>`).join('') : '<tr><td colspan="3" class="muted">Aucune donnée</td></tr>';
  }

  function renderRecords() {
    const root = $('records');
    const records = [...state.records].sort((a, b) => String(b.saved_at).localeCompare(String(a.saved_at))).slice(0, 12);
    if (!records.length) {
      root.innerHTML = '<div class="empty">Le journal est vide. Enregistrez une première sortie ou une observation depuis le port.</div>';
      return;
    }
    root.innerHTML = records.map((record) => {
      const title = record.forecast?.destination_name || record.forecast?.destination_path || 'Destination inconnue';
      const comfort = record.actual?.comfort ? ` · confort ${record.actual.comfort}/5` : '';
      const decision = decisionLabel(record.forecast?.decision || 'NO_DATA');
      return `<article class="record"><div class="record-head"><strong>${safeText(title)}</strong><span class="tag ${classificationClass(record.classification)}">${safeText(classificationLabel(record.classification))}</span></div><div>${safeText(formatDate(record.forecast?.planned_at))} · ${safeText(decision)}${safeText(comfort)}</div><div class="muted">${safeText(record.actual?.notes || record.observation_type)}</div><div class="actions"><button type="button" data-delete-id="${safeText(record.id)}" class="danger">Supprimer</button></div></article>`;
    }).join('');
  }

  function renderAll() {
    renderSummary();
    renderRecords();
  }

  function download(filename, text, type) {
    const blob = new Blob([text], {type});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function csvValue(value) {
    const text = value == null ? '' : String(value);
    return `"${text.replaceAll('"', '""')}"`;
  }

  function exportCsv() {
    const headers = ['id','saved_at','destination','planned_at','decision','classification','observation_type','adults','children','comfort','observed_sea','wind_kmh','gust_kmh','wave_height_m','wave_period_s','early_return','wet_ride','incident','notes'];
    const rows = state.records.map((record) => [
      record.id, record.saved_at, record.forecast?.destination_name, record.forecast?.planned_at,
      record.forecast?.decision, record.classification, record.observation_type,
      record.crew?.adults, record.crew?.children, record.actual?.comfort, record.actual?.observed_sea,
      record.actual?.wind_kmh, record.actual?.gust_kmh, record.actual?.wave_height_m, record.actual?.wave_period_s,
      record.actual?.early_return, record.actual?.wet_ride, record.actual?.incident, record.actual?.notes,
    ]);
    download(`fable-field-log-${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows].map((row) => row.map(csvValue).join(',')).join('\n'), 'text/csv;charset=utf-8');
  }

  async function refreshForecast() {
    const [sitesData, windowsData, statusData] = await Promise.all([
      loadJson('sites.normalized.json'), loadJson('windows.json'), loadJson('status.json'),
    ]);
    state.sites = Array.isArray(sitesData?.sites) ? sitesData.sites.filter((site) => site.windows_enabled !== false) : [];
    state.windows = windowsData;
    state.status = statusData;
    const select = $('destination');
    const previous = select.value;
    select.innerHTML = state.sites.map((site) => `<option value="${safeText(site.path)}">${safeText(site.name)}</option>`).join('');
    if (state.sites.some((site) => site.path === previous)) select.value = previous;
    buildSnapshot();
  }

  function bind() {
    $('planned-at').value = nowLocalInput();
    $('destination').addEventListener('change', buildSnapshot);
    $('planned-at').addEventListener('change', buildSnapshot);
    $('refresh-snapshot').addEventListener('click', refreshForecast);
    $('field-form').addEventListener('submit', (event) => {
      event.preventDefault();
      buildSnapshot();
      const record = formRecord();
      const error = validateRecord(record);
      if (error) { alert(error); return; }
      state.records.push(record);
      saveRecords(); renderAll();
      alert('Observation enregistrée localement. Pensez à exporter régulièrement le journal.');
    });
    $('field-form').addEventListener('reset', () => setTimeout(() => {
      $('planned-at').value = nowLocalInput();
      $('adults').value = '2'; $('children').value = '0'; buildSnapshot();
    }, 0));
    $('records').addEventListener('click', (event) => {
      const id = event.target.closest('[data-delete-id]')?.dataset.deleteId;
      if (!id || !confirm('Supprimer cette observation ?')) return;
      state.records = state.records.filter((item) => item.id !== id);
      saveRecords(); renderAll();
    });
    $('export-json').addEventListener('click', () => download(`fable-field-log-${new Date().toISOString().slice(0,10)}.json`, JSON.stringify({schema_version:1, exported_at:new Date().toISOString(), records:state.records}, null, 2), 'application/json'));
    $('export-csv').addEventListener('click', exportCsv);
    $('import-file').addEventListener('change', async (event) => {
      const file = event.target.files?.[0]; if (!file) return;
      try {
        const parsed = JSON.parse(await file.text());
        const imported = Array.isArray(parsed) ? parsed : parsed.records;
        if (!Array.isArray(imported)) throw new Error('Format invalide');
        const byId = new Map(state.records.map((item) => [item.id, item]));
        imported.forEach((item) => { if (item?.id) byId.set(item.id, item); });
        state.records = [...byId.values()]; saveRecords(); renderAll();
      } catch { alert('Le fichier JSON ne correspond pas au journal FABLE.'); }
      event.target.value = '';
    });
    $('clear-all').addEventListener('click', () => {
      if (!state.records.length || !confirm('Effacer définitivement toutes les observations locales ?')) return;
      state.records = []; saveRecords(); renderAll();
    });
  }

  async function start() {
    themeFromBoard(); loadRecords(); bind(); renderAll(); await refreshForecast();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
