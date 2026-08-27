/** Formatage francais partage par les trois vues. */

const DAY_NAMES = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
const DAY_SHORT = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];

export function num(value, digits = 0) {
  if (!Number.isFinite(value)) return '—';
  return value.toFixed(digits).replace('.', ',');
}

/** Les horodatages du collecteur sont deja en heure locale du site. */
export function parseLocal(stamp) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(stamp ?? ''));
  if (!match) return null;
  const [, y, mo, d, h, mi] = match.map(Number);
  return new Date(y, mo - 1, d, h, mi);
}

export function hourLabel(stamp) {
  const match = /T(\d{2}):(\d{2})/.exec(String(stamp ?? ''));
  return match ? `${match[1]}:${match[2]}` : '—';
}

export function dayKey(stamp) {
  return String(stamp ?? '').slice(0, 10);
}

export function dayShort(stamp) {
  const date = parseLocal(stamp);
  if (!date) return '—';
  return `${DAY_SHORT[date.getDay()]} ${String(date.getDate()).padStart(2, '0')}`;
}

export function dayLong(stamp) {
  const date = parseLocal(stamp);
  if (!date) return '—';
  return `${DAY_NAMES[date.getDay()]} ${date.getDate()}`;
}

export function durationHours(hours) {
  if (!Number.isFinite(hours)) return '—';
  const whole = Math.floor(hours);
  const minutes = Math.round((hours - whole) * 60);
  if (!minutes) return `${whole} h`;
  return `${whole} h ${String(minutes).padStart(2, '0')}`;
}

export function relativeAge(stamp, now = new Date()) {
  const date = parseLocal(stamp);
  if (!date) return '—';
  const minutes = Math.round((now.getTime() - date.getTime()) / 60000);
  if (minutes < 0) return 'à l’instant';
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return `il y a ${Math.floor(hours / 24)} j`;
}

const REASON_LABELS = new Map([
  ['orages', 'orage détecté'],
  ['squalls', 'risque de grain'],
  ['short_steep', 'mer courte et creuse'],
  ['short_steep_hard', 'mer courte et creuse, veto'],
  ['vent_inconnu', 'données de vent manquantes'],
  ['vagues_inconnues', 'données de vagues manquantes'],
  ['prudent_onshore', 'vent onshore incompatible avec le GO prudent'],
]);

/** Traduit un code de raison du moteur en une phrase lisible. */
export function reasonText(code, metrics) {
  if (code && typeof code === 'object') return code.reason_fr ?? code.code ?? 'raison non précisée';
  if (REASON_LABELS.has(code)) return REASON_LABELS.get(code);
  let match = /^rafales>=?([\d.]+)/.exec(code);
  if (match) return `rafales ${num(metrics?.maxGust, 0)} km/h, seuil ${num(Number(match[1]), 0)} km/h`;
  match = /^vent>=?([\d.]+)/.exec(code);
  if (match) return `vent ${num(metrics?.maxSpeed, 0)} km/h, seuil ${num(Number(match[1]), 0)} km/h`;
  match = /^onshore>([\d.]+)/.exec(code);
  if (match) return `vent onshore ${num(metrics?.maxSpeed, 0)} km/h, seuil ${num(Number(match[1]), 0)} km/h`;
  match = /^Hs>=?([\d.]+)/.exec(code);
  if (match) return `houle ${num(metrics?.hs, 2)} m, seuil ${num(Number(match[1]), 2)} m`;
  match = /^Tp<([\d.]+)/.exec(code);
  if (match) return `période trop courte, minimum ${num(Number(match[1]), 1)} s`;
  match = /^vis<([\d.]+)/.exec(code);
  if (match) return `visibilité ${num(metrics?.minVis, 1)} km, minimum ${match[1]} km`;
  return code;
}

export function firstReasonText(reasons, metrics) {
  if (!reasons?.length) return 'dans les limites famille';
  return reasonText(reasons[0], metrics);
}
