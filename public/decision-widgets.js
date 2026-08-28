(function decisionWidgets(global) {
  const esc = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]),
  );

  const COPY = {
    fr: {
      duration:'Durée famille continue', wind:'Vent soutenu max', gust:'Rafales max',
      wave:'Houle Hs max', visibility:'Visibilité min', ok:'OK', exceeded:'DÉPASSÉ',
      insufficient:'INSUFFISANT', unavailable:'Détail des contrôles indisponible.',
    },
    en: {
      duration:'Continuous family duration', wind:'Maximum sustained wind', gust:'Maximum gusts',
      wave:'Maximum wave Hs', visibility:'Minimum visibility', ok:'OK', exceeded:'EXCEEDED',
      insufficient:'INSUFFICIENT', unavailable:'Check details unavailable.',
    },
    ar: {
      duration:'مدة الخروج العائلي المتواصلة', wind:'أقصى رياح مستمرة', gust:'أقصى هبات',
      wave:'أقصى ارتفاع للموج', visibility:'أدنى مدى للرؤية', ok:'مناسب', exceeded:'تجاوز',
      insufficient:'غير كافٍ', unavailable:'تفاصيل الفحوصات غير متاحة.',
    },
  };

  const number = (value) => {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const pick = (...values) => values.map(number).find((value) => value !== null) ?? null;
  const language = (value) => String(value || 'fr').toLowerCase().startsWith('en')
    ? 'en' : String(value || '').toLowerCase().startsWith('ar') ? 'ar' : 'fr';

  function thresholds(rules = {}) {
    const family = rules.family?.thresholds || {};
    return {
      duration: pick(rules.family?.window_hours?.min, rules.window_hours?.min, 4),
      wind: pick(family.wind?.family_max_kmh, rules.wind?.family_max_kmh, 22),
      gust: pick(family.gusts?.no_go_min_kmh, rules.overrides?.gusts_hard_nogo_kmh, 30),
      wave: pick(family.waves?.hs_family_max_m, rules.sea?.family_max_hs_m, 0.5),
      visibility: pick(family.visibility_km_min, rules.overrides?.visibility_km_min, 5),
    };
  }

  function metric(metrics, ...keys) {
    return pick(...keys.map((key) => metrics?.[key]));
  }

  function checks(destination = {}, rules = {}, lang = 'fr') {
    destination = destination || {};
    const copy = COPY[language(lang)];
    const diagnostics = destination.diagnostics || {};
    const blocker = diagnostics.first_blocker || {};
    const metrics = blocker.metrics || {};
    const limits = thresholds(rules);
    const result = [];
    const pushMax = (key, label, value, limit, unit, digits = 0) => {
      if (value === null || limit === null) return;
      result.push({
        key, label, value, limit, unit, digits, kind:'max', passed:value < limit,
        ratio:Math.min(1, Math.max(0.04, value / Math.max(limit, 0.001))),
        status:value < limit ? copy.ok : copy.exceeded,
      });
    };
    const pushMin = (key, label, value, limit, unit, digits = 0) => {
      if (value === null || limit === null) return;
      result.push({
        key, label, value, limit, unit, digits, kind:'min', passed:value >= limit,
        ratio:Math.min(1, Math.max(0.04, value / Math.max(limit, 0.001))),
        status:value >= limit ? copy.ok : copy.insufficient,
      });
    };

    const validated = pick(
      diagnostics.near_miss?.validated_hours,
      diagnostics.validated_hours,
      blocker.stage === 'duration' ? 0 : null,
    );
    pushMin('duration', copy.duration, validated, pick(destination.required_hours, limits.duration), 'h');
    pushMax('gust', copy.gust, metric(metrics, 'gust_kmh', 'max_gust_kmh'), limits.gust, 'km/h', 1);
    pushMax('wind', copy.wind, metric(metrics, 'wind_kmh', 'max_wind_kmh'), limits.wind, 'km/h', 1);
    pushMax('wave', copy.wave, metric(metrics, 'hs_m', 'max_hs_m'), limits.wave, 'm', 2);
    let visibility = metric(metrics, 'visibility_km', 'min_visibility_km', 'visibility');
    if (visibility !== null && visibility > 100) visibility /= 1000;
    pushMin('visibility', copy.visibility, visibility, limits.visibility, 'km', 1);
    return result;
  }

  function formatValue(value, digits, unit) {
    const formatted = Number(value).toLocaleString('fr-FR', {
      minimumFractionDigits:digits,
      maximumFractionDigits:digits,
    });
    return `${formatted} ${unit}`;
  }

  function checksHtml(destination = {}, rules = {}, lang = 'fr') {
    destination = destination || {};
    const copy = COPY[language(lang)];
    const rows = checks(destination, rules, lang);
    if (!rows.length) return `<p class="decision-checks-empty">${esc(copy.unavailable)}</p>`;
    return `<div class="decision-checks">${rows.map((row) => {
      const relation = row.kind === 'max' ? '<' : '≥';
      return `<div class="decision-check ${row.passed ? 'ok' : 'blocked'}" data-check="${esc(row.key)}">
        <div class="decision-check-head"><span>${esc(row.label)} · ${esc(relation)} ${esc(formatValue(row.limit,row.digits,row.unit))}</span><strong>${esc(formatValue(row.value,row.digits,row.unit))}</strong><b>${esc(row.status)}</b></div>
        <div class="decision-check-track" aria-hidden="true"><i style="width:${(row.ratio * 100).toFixed(0)}%"></i></div>
      </div>`;
    }).join('')}</div>`;
  }

  function confidenceBarsHtml(level, label = '') {
    const normalized = ['high','medium','low','limited'].includes(String(level).toLowerCase())
      ? String(level).toLowerCase() : 'low';
    return `<span class="quality-bars" aria-hidden="true"><i></i><i></i><i></i></span>${label ? `<span class="quality-label">${esc(label)}</span>` : ''}`;
  }

  global.FABLEDecisionWidgets = Object.freeze({checks, checksHtml, confidenceBarsHtml});
}(window));
