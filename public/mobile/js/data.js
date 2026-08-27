/** Chargement des JSON publies par le collecteur. Meme origine, un niveau au-dessus. */

const BASE = '../';
const cache = new Map();

async function getJson(path, { optional = false } = {}) {
  if (cache.has(path)) return cache.get(path);
  const promise = fetch(`${BASE}${path}`, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      return response.json();
    })
    .catch((error) => {
      if (optional) return null;
      throw error;
    });
  cache.set(path, promise);
  return promise;
}

export function clearCache() {
  cache.clear();
}

export async function loadCatalog() {
  const [index, rules, sites, windows, status] = await Promise.all([
    getJson('index.json'),
    getJson('rules.normalized.json'),
    getJson('sites.normalized.json'),
    getJson('windows.json', { optional: true }),
    getJson('status.json', { optional: true }),
  ]);

  const byPath = new Map();
  for (const site of sites?.sites ?? []) {
    byPath.set(site.path, site);
    byPath.set(site.slug, site);
  }

  const spots = (index?.spots ?? []).map((entry) => ({
    ...entry,
    config: byPath.get(entry.path) ?? byPath.get(entry.slug) ?? null,
    engine: (windows?.windows ?? []).find((candidate) => {
      const dest = String(candidate?.dest_slug ?? '').replace(/\.json$/, '');
      const path = String(entry.path ?? '').replace(/\.json$/, '');
      return dest === entry.slug || dest === path;
    }) ?? null,
  }));

  return {
    generatedAt: index?.generated_at ?? null,
    tz: index?.tz ?? sites?.tz ?? 'Africa/Tunis',
    collectorVersion: index?.collector_version ?? null,
    window: index?.window ?? null,
    homeSlug: index?.home ?? sites?.home ?? spots[0]?.slug ?? null,
    spots,
    rules,
    windows,
    status,
  };
}

export function loadSpot(path) {
  return getJson(path);
}

export function loadHourlyAssessment(reference) {
  const path = reference?.path;
  return path ? getJson(path, { optional: true }) : Promise.resolve(null);
}
