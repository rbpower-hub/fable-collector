const TUNIS_TZ = 'Africa/Tunis';

const TRANSLATIONS = {
  fr: {
    thunder: '⛈️ Orages prévus — sortie impossible',
    visibility: '🌫️ Visibilité insuffisante',
    gusts: (value) => `💨 Rafales trop fortes${value ? ` (${value} km/h)` : ''}`,
    squalls: '💨 Vent instable (risque de grains)',
    onshore: '🌊 Vent vers la côte trop fort',
    wind: (value) => `💨 Vent trop fort${value ? ` (${value} km/h)` : ''}`,
    waves: (value) => `🌊 Mer trop agitée${value ? ` (${value} m)` : ''}`,
    shortWaves: '🌊 Vagues courtes et inconfortables',
    missingWaves: '❓ Données de vagues manquantes',
    duration: '📅 Pas de créneau assez long en journée',
  },
  en: {
    thunder: '⛈️ Thunderstorms forecast — no outing',
    visibility: '🌫️ Poor visibility',
    gusts: (value) => `💨 Gusts too strong${value ? ` (${value} km/h)` : ''}`,
    squalls: '💨 Unstable wind (squall risk)',
    onshore: '🌊 Onshore wind too strong',
    wind: (value) => `💨 Wind too strong${value ? ` (${value} km/h)` : ''}`,
    waves: (value) => `🌊 Sea too rough${value ? ` (${value} m)` : ''}`,
    shortWaves: '🌊 Short, uncomfortable waves',
    missingWaves: '❓ Wave data missing',
    duration: '📅 No long-enough daytime slot',
  },
};

function normalizedLocale(locale) {
  return String(locale || 'fr').toLowerCase().startsWith('en') ? 'en' : 'fr';
}

function cleanReason(raw) {
  return String(raw || '')
    .replace(/^[✗✓⚠🚫✅]\s*/u, '')
    .replace(/\s*\([^)]+\.json\)\s*$/i, '')
    .trim();
}

function extractTime(raw) {
  return String(raw || '').match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2}|Z)?/)?.[0] || '';
}

export function prettifyReasonDate(value, locale = 'fr') {
  const date = new Date(value || '');
  if (!Number.isFinite(date.getTime())) return String(value || '');
  const language = normalizedLocale(locale);
  const formatted = date.toLocaleString(language === 'en' ? 'en-GB' : 'fr-FR', {
    timeZone: TUNIS_TZ,
    weekday: 'long',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return formatted.replace(/^\p{L}/u, (letter) => letter.toUpperCase());
}

function numericValue(raw, unit) {
  const escapedUnit = unit === 'm' ? 'm' : 'km\\/h';
  const match = String(raw).match(new RegExp(`(\\d+(?:[.,]\\d+)?)\\s*${escapedUnit}`, 'i'));
  return match?.[1]?.replace(',', '.') || '';
}

export function friendlyReason(raw, locale = 'fr') {
  const language = normalizedLocale(locale);
  const text = TRANSLATIONS[language];
  const cleaned = cleanReason(raw);
  const lower = cleaned.toLowerCase();
  let phrase = '';

  if (/orages?\s*\(code\s*\d+\)|thunder/i.test(cleaned)) phrase = text.thunder;
  else if (/vis\s*<\s*\d+\s*km|visibility/i.test(cleaned)) phrase = text.visibility;
  else if (/rafales?.*[≥>]|gusts?.*(?:too|[≥>])/i.test(cleaned)) phrase = text.gusts(numericValue(cleaned, 'km/h'));
  else if (/squalls?\s*δ?\s*[≥>]|grains?|vent instable/i.test(cleaned)) phrase = text.squalls;
  else if (/vent onshore|onshore wind/i.test(cleaned)) phrase = text.onshore;
  else if (/(?:^|\s)vent\s+\d+.*[≥>]|wind\s+\d+.*[≥>]|wind too strong/i.test(cleaned)) phrase = text.wind(numericValue(cleaned, 'km/h'));
  else if (/vagues?.*[≥>]|sea too rough|hs\s*[≥>]/i.test(cleaned)) phrase = text.waves(numericValue(cleaned, 'm'));
  else if (/\btp\b.*<|short[ -]steep|vagues? courtes?/i.test(cleaned)) phrase = text.shortWaves;
  else if (/vagues_inconnues|houle.*indisponible|wave data.*missing|marine.*unavailable/i.test(cleaned)) phrase = text.missingWaves;
  else if (/aucune fenêtre de \d+\s*h|no .*long-enough|no window of \d+\s*h/i.test(cleaned)) phrase = text.duration;
  else phrase = cleaned.replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2}|Z)?/g, (iso) => prettifyReasonDate(iso, language));

  const timestamp = extractTime(cleaned);
  if (timestamp && !phrase.includes(prettifyReasonDate(timestamp, language))) {
    phrase = `${phrase} — ${prettifyReasonDate(timestamp, language)}`;
  }
  return phrase || cleaned || (language === 'en' ? 'Reason unavailable' : 'Raison indisponible');
}

if (typeof window !== 'undefined') {
  window.FABLEReasons = Object.assign(window.FABLEReasons || {}, {friendlyReason, prettifyReasonDate});
}
