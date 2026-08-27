/**
 * Seuils de decision, reconstitues depuis ce que le collecteur publie.
 *
 * ATTENTION : deux schemas coexistent.
 *   - Le moteur (fable.window_models.Thresholds.from_rules) lit le schema
 *     PLAT de rules.yaml : wind.family_max_kmh, tp_matrix.transit.*,
 *     overrides.*, sea.*. C'est ce schema que chaque spot republie dans
 *     meta.rules, avec son digest.
 *   - rules.normalized.json est un schema v2 IMBRIQUE, que from_rules ne sait
 *     pas lire : lui passer ce fichier ferait silencieusement retomber tous
 *     les seuils sur les valeurs par defaut du code.
 *
 * meta.rules est donc la source prioritaire, mais il ne publie pas prudent,
 * combined.short_steep ni adaptive_window : ceux-la ne se trouvent que dans
 * rules.normalized.json. On fusionne les deux, dans cet ordre, et on ne
 * retombe sur une valeur en dur que si aucun des deux fichiers ne la porte.
 * Ces valeurs de repli reprennent celles de Thresholds.from_rules.
 */

const FALLBACK = {
  windFamilyMax: 20,
  windNoGoMin: 25,
  onshoreMaxOk: 22,
  gustNoGoMin: 30,
  squallDelta: 17,
  hsFamilyMax: 0.5,
  hsNoGoMin: 0.8,
  tpMinAtLt04: 3.2,
  tpMinAt0405: 4.5,
  visMinKm: 5,
  shortSteep1Hs: 0.5,
  shortSteep1Tp: 6.0,
  shortSteep2Hs: 0.6,
  shortSteep2Tp: 5.0,
  anchorHsEaseMax: 0.35,
  anchorTpFamily: 3.2,
  anchorGustAllow: 34,
  anchorSustainedAllow: 32,
  prudentEnabled: true,
  prudentWindMax: 22,
  prudentGustMax: 28,
  prudentHsMax: 0.4,
  prudentTpMin: 3.5,
  familyStartHour: 8,
  familyEndHour: 21,
  windowMinHours: 4,
  windowMaxHours: 6,
  absoluteMinHours: 3,
  thunderCodes: [95, 96, 99],
};

function dig(source, path) {
  return path.split('.').reduce((acc, key) => (acc && typeof acc === 'object' ? acc[key] : undefined), source);
}

/** Premiere valeur numerique trouvee dans les sources, dans l'ordre. */
function pick(sources, fallback) {
  for (const [source, path] of sources) {
    const value = Number(dig(source, path));
    if (Number.isFinite(value)) return value;
  }
  return fallback;
}

/**
 * @param {object|null} flat meta.rules d'un spot (schema rules.yaml)
 * @param {object|null} normalized rules.normalized.json (schema v2)
 */
export function parseThresholds(flat, normalized) {
  const f = flat ?? {};
  const n = normalized ?? {};

  const thunder = dig(f, 'overrides.thunder_wmo') ?? dig(n, 'family.thunder_codes');

  return {
    digest: dig(f, 'digest') ?? null,

    windFamilyMax: pick([[f, 'wind.family_max_kmh'], [n, 'family.thresholds.wind.family_max_kmh']], FALLBACK.windFamilyMax),
    windNoGoMin: pick([[f, 'wind.nogo_min_kmh'], [n, 'family.thresholds.wind.no_go_min_kmh']], FALLBACK.windNoGoMin),
    onshoreMaxOk: pick([[f, 'wind.onshore_degrade_kmh'], [n, 'family.thresholds.wind.onshore_downgrade_kmh']], FALLBACK.onshoreMaxOk),

    gustNoGoMin: pick([[f, 'overrides.gusts_hard_nogo_kmh'], [n, 'family.thresholds.gusts.no_go_min_kmh']], FALLBACK.gustNoGoMin),
    squallDelta: pick([[f, 'overrides.squall_delta_kmh'], [n, 'family.thresholds.gusts.squall_delta_kmh']], FALLBACK.squallDelta),
    visMinKm: pick([[f, 'overrides.visibility_km_min'], [n, 'family.thresholds.visibility_km_min']], FALLBACK.visMinKm),

    hsFamilyMax: pick([[f, 'sea.family_max_hs_m'], [n, 'family.thresholds.waves.hs_family_max_m']], FALLBACK.hsFamilyMax),
    hsNoGoMin: pick([[f, 'sea.nogo_min_hs_m'], [n, 'family.thresholds.waves.hs_no_go_min_m']], FALLBACK.hsNoGoMin),

    tpMinAtLt04: pick(
      [[f, 'tp_matrix.transit.hs_lt_0_4_family_tp_s'], [n, 'family.thresholds.waves.tp_min_at_hs_lt_0_4_s']],
      FALLBACK.tpMinAtLt04,
    ),
    tpMinAt0405: pick(
      [[f, 'tp_matrix.transit.hs_0_4_0_5_family_tp_s'], [n, 'family.thresholds.waves.tp_min_at_hs_0_4_0_5_s']],
      FALLBACK.tpMinAt0405,
    ),

    shortSteep1Hs: pick([[f, 'combined.short_steep_downgrade.hs_min_m'], [n, 'family.combined.short_steep.downgrade.hs_min_m']], FALLBACK.shortSteep1Hs),
    shortSteep1Tp: pick([[f, 'combined.short_steep_downgrade.tp_max_s'], [n, 'family.combined.short_steep.downgrade.tp_max_s']], FALLBACK.shortSteep1Tp),
    shortSteep2Hs: pick([[f, 'combined.short_steep_hard_nogo.hs_min_m'], [n, 'family.combined.short_steep.hard_nogo.hs_min_m']], FALLBACK.shortSteep2Hs),
    shortSteep2Tp: pick([[f, 'combined.short_steep_hard_nogo.tp_max_s'], [n, 'family.combined.short_steep.hard_nogo.tp_max_s']], FALLBACK.shortSteep2Tp),

    anchorHsEaseMax: pick([[f, 'tp_matrix.anchor_sheltered.hs_max_m'], [n, 'family.anchor_sheltered.waves.hs_max_m']], FALLBACK.anchorHsEaseMax),
    anchorTpFamily: pick([[f, 'tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s'], [n, 'family.anchor_sheltered.waves.hs_le_0_35_family_tp_s']], FALLBACK.anchorTpFamily),
    anchorGustAllow: pick([[f, 'shelter.anchor_gusts_allow_up_to_kmh'], [n, 'family.shelter_bonus.anchor.gusts_allow_up_to_kmh']], FALLBACK.anchorGustAllow),
    anchorSustainedAllow: pick([[f, 'shelter.anchor_sustained_allow_up_to_kmh'], [n, 'family.shelter_bonus.anchor.sustained_allow_up_to_kmh']], FALLBACK.anchorSustainedAllow),

    prudentEnabled: (dig(f, 'prudent.enabled') ?? dig(n, 'prudent.enabled') ?? FALLBACK.prudentEnabled) !== false,
    prudentWindMax: pick([[f, 'prudent.wind_max_kmh'], [n, 'prudent.wind_max_kmh']], FALLBACK.prudentWindMax),
    prudentGustMax: pick([[f, 'prudent.gust_max_kmh'], [n, 'prudent.gust_max_kmh']], FALLBACK.prudentGustMax),
    prudentHsMax: pick([[f, 'prudent.hs_max_m'], [n, 'prudent.hs_max_m']], FALLBACK.prudentHsMax),
    prudentTpMin: pick([[f, 'prudent.tp_min_s'], [n, 'prudent.tp_min_s']], FALLBACK.prudentTpMin),

    familyStartHour: pick([[f, 'family_hours_local.start_h'], [n, 'family.hours_local.start']], FALLBACK.familyStartHour),
    familyEndHour: pick([[f, 'family_hours_local.end_h'], [n, 'family.hours_local.end']], FALLBACK.familyEndHour),
    windowMinHours: pick([[n, 'family.window_hours.min']], FALLBACK.windowMinHours),
    windowMaxHours: pick([[n, 'family.window_hours.max']], FALLBACK.windowMaxHours),
    absoluteMinHours: pick([[f, 'adaptive_window.absolute_min_hours'], [n, 'adaptive_window.absolute_min_hours']], FALLBACK.absoluteMinHours),

    thunderCodes: Array.isArray(thunder) && thunder.length ? thunder.map(Number) : FALLBACK.thunderCodes,
  };
}

export { FALLBACK as THRESHOLD_FALLBACK };
