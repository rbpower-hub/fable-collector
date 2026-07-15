import {distanceKm} from './map.js';

export function pathDistanceKm(points) {
  if (!Array.isArray(points) || points.length < 2) return 0;
  return points.slice(1).reduce((total, point, index) => total + distanceKm(points[index], point), 0);
}

export function pointAlongPath(points, ratio = 0.5) {
  if (!Array.isArray(points) || !points.length) return [0, 0];
  if (points.length === 1) return [points[0].lat, Number(points[0].lon ?? points[0].lng)];
  const total = pathDistanceKm(points);
  if (total <= 0) return [points[0].lat, Number(points[0].lon ?? points[0].lng)];
  const target = total * Math.min(1, Math.max(0, ratio));
  let walked = 0;
  for (let index = 1; index < points.length; index += 1) {
    const segment = distanceKm(points[index - 1], points[index]);
    if (walked + segment >= target) {
      const part = (target - walked) / (segment || 1);
      const start = points[index - 1];
      const end = points[index];
      const startLon = Number(start.lon ?? start.lng);
      const endLon = Number(end.lon ?? end.lng);
      return [start.lat + (end.lat - start.lat) * part, startLon + (endLon - startLon) * part];
    }
    walked += segment;
  }
  const last = points.at(-1);
  return [last.lat, Number(last.lon ?? last.lng)];
}

if (typeof window !== 'undefined') {
  window.FABLEModules = Object.assign(window.FABLEModules || {}, {pathDistanceKm, pointAlongPath});
}
