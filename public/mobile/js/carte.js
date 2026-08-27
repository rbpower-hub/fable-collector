/**
 * Ecran Carte : corridor Leaflet restyle.
 *
 * Reutilise les modules geometriques deja publies (public/js/map.js et
 * public/js/corridor.js) plutot que d'en refaire une copie.
 */

import { distanceKm } from '../../js/map.js';
import { pathDistanceKm, pointAlongPath } from '../../js/corridor.js';
import { durationHours, hourLabel, num } from './format.js';
import { card, h, icon, stateBadge, tile } from './ui.js';

const KM_PER_NM = 1.852;

let map = null;
let corridorLayer = null;
let spotsLayer = null;

function siteLatLng(site) {
  const lat = Number(site.map_lat ?? site.lat);
  const lon = Number(site.map_lon ?? site.lon);
  return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}

function routePlan(destSite, sites, homeSlug) {
  const origin = sites.find((site) => site.slug === (destSite.route_origin || homeSlug));
  if (!origin || origin.slug === destSite.slug) return null;
  const points = [
    { lat: Number(origin.map_lat ?? origin.lat), lon: Number(origin.map_lon ?? origin.lon), name: origin.name },
    ...(destSite.route_points ?? []).map((point) => ({
      lat: Number(point.lat), lon: Number(point.lon ?? point.lng), name: point.name ?? null,
    })),
    { lat: Number(destSite.map_lat ?? destSite.lat), lon: Number(destSite.map_lon ?? destSite.lon), name: destSite.name },
  ].filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon));
  if (points.length < 2) return null;
  const km = points.length > 2 ? pathDistanceKm(points) : distanceKm(points[0], points[1]);
  const speed = destSite.transit_speed_kts ?? {};
  const nm = km / KM_PER_NM;
  const minSpeed = Number(speed.min) || 16;
  const maxSpeed = Number(speed.max) || 24;
  return {
    origin,
    dest: destSite,
    points,
    km,
    nm,
    transitMin: nm / maxSpeed,
    transitMax: nm / minSpeed,
    speed: { min: minSpeed, max: maxSpeed },
  };
}

function onshoreWedge(site) {
  const sectors = site.onshore_sectors ?? [];
  const center = siteLatLng(site);
  if (!center || !sectors.length) return [];
  const radiusKm = 3;
  const wedges = [];
  for (const sector of sectors) {
    const [start, end] = sector.map(Number);
    if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
    const span = ((end - start) + 360) % 360 || 360;
    const ring = [center];
    const steps = Math.max(4, Math.round(span / 10));
    for (let i = 0; i <= steps; i += 1) {
      const angle = (start + (span * i) / steps) * Math.PI / 180;
      const dLat = (radiusKm / 111) * Math.cos(angle);
      const dLon = (radiusKm / (111 * Math.cos(center[0] * Math.PI / 180))) * Math.sin(angle);
      ring.push([center[0] + dLat, center[1] + dLon]);
    }
    wedges.push(ring);
  }
  return wedges;
}

function stateColor(state) {
  return { go: '#0ca30c', prudent: '#fab219', nogo: '#d03b3b' }[state] ?? '#6d829b';
}

function spotMarker(latlng, color, isHome) {
  const size = isHome ? 15 : 11;
  return L.marker(latlng, {
    icon: L.divIcon({
      className: '',
      html: `<span class="fb-spot-marker" style="display:block;width:${size}px;height:${size}px;background:${color}"></span>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    }),
    keyboard: false,
  });
}

function blockerFor(windows, destPath) {
  const entry = (windows?.windows ?? []).find((item) => item.dest_slug === destPath);
  if (!entry) return null;
  const diagnostics = entry.diagnostics ?? {};
  return {
    status: diagnostics.status ?? null,
    requiredHours: entry.required_hours ?? null,
    hasWindow: Boolean((entry.windows ?? []).length),
    first: diagnostics.first_blocker ?? null,
  };
}

export function renderCarte(host, ctx) {
  const {
    sites, homeSlug, verdicts, windows, destSlug, onDest,
  } = ctx;
  host.textContent = '';

  const home = sites.find((site) => site.slug === homeSlug) ?? sites[0];
  const destinations = sites.filter((site) => site.slug !== home.slug);
  const dest = destinations.find((site) => site.slug === destSlug) ?? destinations[0] ?? null;
  const plan = dest ? routePlan(dest, sites, home.slug) : null;
  const blocker = dest ? blockerFor(windows, dest.path) : null;

  const destState = dest ? (verdicts.get(dest.slug) ?? 'nogo') : 'nogo';
  const blocked = Boolean(blocker && blocker.status === 'blocked');

  host.append(h('div', { class: 'fb-topbar', style: 'padding-left:0;padding-right:0' }, [
    h('div', { class: 'fb-topbar__meta' }, [
      h('span', {
        class: 'fb-topbar__title',
        style: 'font-size:16px',
        text: dest ? `${home.name.split(' (')[0]} → ${dest.name}` : home.name,
      }),
      h('span', { class: 'fb-topbar__sub', text: plan ? `Corridor · ${num(plan.km, 1)} km` : 'Spots' }),
    ]),
    blocked
      ? h('span', { class: 'fb-badge fb-badge--nogo' }, [icon('block', { size: 13, width: 2.2 }), h('span', { text: 'BLOQUÉ' })])
      : stateBadge(destState),
  ]));

  // Selecteur de destination
  const chipRow = h('div', { class: 'fb-chip-row', style: 'flex-wrap:wrap' });
  for (const site of destinations) {
    chipRow.append(h('button', {
      type: 'button',
      class: 'fb-chip',
      style: 'flex:0 1 auto;padding:0 10px',
      'aria-pressed': String(dest && site.slug === dest.slug),
      text: site.name,
      onClick: () => onDest?.(site.slug),
    }));
  }
  host.append(chipRow);

  // Conteneur carte
  const mapWrap = h('div', { class: 'fb-map-wrap' }, [h('div', { id: 'fb-map' })]);
  const summary = h('div', { class: 'fb-map-overlay' });
  mapWrap.append(summary);
  host.append(mapWrap);

  const blockerText = blocker?.first
    ? `Premier bloqueur à ${blocker.first.location_name}, phase ${blocker.first.phase}, `
      + `${hourLabel(blocker.first.time)} : ${blocker.first.reason_fr ?? (blocker.first.reasons ?? []).join(', ')}.`
    : plan
      ? `Corridor indicatif. ${blocker?.hasWindow ? 'Fenêtre validée par le moteur.' : 'Aucune fenêtre validée sur l’horizon.'}`
      : 'Sélectionnez une destination.';
  summary.append(
    icon(blocked ? 'warning' : 'compass', { size: 15, stroke: blocked ? 'var(--nogo)' : 'var(--accent)', width: 2 }),
    h('span', { text: blockerText }),
  );

  // Detail du corridor
  if (plan) {
    const noteText = dest.route_note;
    host.append(card(
      plan.points.length > 2 ? `Étape unique · ${plan.points.length - 2} waypoints au large` : 'Étape unique',
      dest.beta ? 'route beta' : null,
      [
        h('div', { class: 'fb-tiles', style: 'grid-template-columns:repeat(3,minmax(0,1fr))' }, [
          tile('DISTANCE', `${num(plan.km, 1)} km`, `${num(plan.nm, 1)} NM`),
          tile('TRANSIT', durationHours(plan.transitMin), `→ ${durationHours(plan.transitMax)}`),
          tile('VITESSE', `${num(plan.speed.min, 0)}–${num(plan.speed.max, 0)}`, 'nœuds'),
        ]),
        blocker?.requiredHours
          ? h('div', { class: 'fb-muted', text: `Fenêtre continue requise : ${blocker.requiredHours} h.` })
          : null,
        noteText ? h('div', { class: 'fb-muted', text: noteText }) : null,
      ],
    ));
  }

  // ---- Leaflet ----
  const container = mapWrap.querySelector('#fb-map');
  if (map) {
    map.remove();
    map = null;
  }
  map = L.map(container, { zoomControl: true, attributionControl: true });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
    noWrap: true,
    maxZoom: 18,
  }).addTo(map);
  corridorLayer = L.layerGroup().addTo(map);
  spotsLayer = L.layerGroup().addTo(map);

  for (const ring of onshoreWedge(home)) {
    L.polygon(ring, {
      color: '#fab219', weight: 1, dashArray: '3,3', fillColor: '#fab219', fillOpacity: 0.08, interactive: false,
    }).addTo(corridorLayer);
  }

  if (plan) {
    const latlngs = plan.points.map((point) => [point.lat, point.lon]);
    L.polyline(latlngs, {
      color: '#35c1e8', weight: 2.5, opacity: 0.95, dashArray: '6,6',
    }).addTo(corridorLayer);
    for (const point of plan.points.slice(1, -1)) {
      L.circleMarker([point.lat, point.lon], {
        radius: 3, color: '#35c1e8', fillColor: '#35c1e8', fillOpacity: 1, weight: 1.5,
      }).addTo(corridorLayer).bindTooltip(point.name ?? '', { direction: 'top', offset: [0, -4] });
    }
    const mid = pointAlongPath(plan.points);
    L.marker(mid, {
      interactive: false,
      icon: L.divIcon({
        className: '',
        html: `<div class="fb-transit-badge"><b>${durationHours(plan.transitMin)} → ${durationHours(plan.transitMax)}</b>`
          + `<span>${num(plan.km, 1)} km · ${num(plan.nm, 1)} NM</span></div>`,
        iconSize: [120, 34],
        iconAnchor: [60, 17],
      }),
    }).addTo(corridorLayer);
  }

  for (const site of sites) {
    const latlng = siteLatLng(site);
    if (!latlng) continue;
    const isHome = site.slug === home.slug;
    const color = isHome ? '#35c1e8' : stateColor(verdicts.get(site.slug));
    const marker = spotMarker(latlng, color, isHome).addTo(spotsLayer);
    marker.bindTooltip(site.name, { direction: 'top', offset: [0, -8] });
    if (!isHome) marker.on('click', () => onDest?.(site.slug));
    if (site.slug === dest?.slug && blocked) {
      L.circleMarker(latlng, {
        radius: 12, color: '#d03b3b', weight: 1.5, dashArray: '3,3', fill: false, interactive: false,
      }).addTo(spotsLayer);
    }
  }

  const bounds = plan
    ? L.latLngBounds(plan.points.map((point) => [point.lat, point.lon]))
    : L.latLngBounds(sites.map(siteLatLng).filter(Boolean));
  map.fitBounds(bounds, { padding: [30, 30] });
  // Le conteneur est cree juste avant : Leaflet doit remesurer apres le layout.
  window.setTimeout(() => map && map.invalidateSize({ pan: false }), 60);
}

export function destroyMap() {
  if (map) {
    map.remove();
    map = null;
  }
}
