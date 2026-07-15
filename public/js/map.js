const EARTH_RADIUS_KM = 6371;

export function distanceKm(a, b) {
  const latA = Number(a?.lat);
  const latB = Number(b?.lat);
  const lonA = Number(a?.lon ?? a?.lng);
  const lonB = Number(b?.lon ?? b?.lng);
  if (![latA, latB, lonA, lonB].every(Number.isFinite)) return 0;
  const rad = (degrees) => degrees * Math.PI / 180;
  const dLat = rad(latB - latA);
  const dLon = rad(lonB - lonA);
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(rad(latA)) * Math.cos(rad(latB)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(x));
}

export function pointInViewport(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
}

if (typeof window !== 'undefined') {
  window.FABLEModules = Object.assign(window.FABLEModules || {}, {distanceKm, pointInViewport});
}
