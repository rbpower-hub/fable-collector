export const TUNIS_TZ = 'Africa/Tunis';
export const LOCALES = {fr: 'fr-FR', en: 'en-GB', ar: 'ar-TN'};

export function localeFor(language = 'fr') {
  return LOCALES[language] || LOCALES.fr;
}

export function formatTunis(value, language = 'fr', options = {}) {
  const date = value instanceof Date ? value : new Date(value || '');
  if (!Number.isFinite(date.getTime())) return '';
  return date.toLocaleString(localeFor(language), {timeZone: TUNIS_TZ, hour12: false, ...options});
}

if (typeof window !== 'undefined') {
  window.FABLEModules = Object.assign(window.FABLEModules || {}, {TUNIS_TZ, LOCALES, localeFor, formatTunis});
}
