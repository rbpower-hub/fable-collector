/* FABLE Port Knowledge — validated routes and shelters only. */
(function () {
  async function loadJSON(path) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      return await response.json();
    } catch {
      return null;
    }
  }

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function routeLabel(port) {
    const route = port?.route || {};
    if (route.trip_mode === "one_way_multi_day") {
      return "Aller et retour évalués séparément · séjour multi-jours possible";
    }
    return "Aller–zone–retour dans la même fenêtre";
  }

  function isRouteValidated(port) {
    return port?.route?.validated === true;
  }

  function hasValidatedShelter(port) {
    return Number(port?.shelter_summary?.validated || 0) > 0;
  }

  function isDisplayEligible(port) {
    return port?.display_eligible === true || isRouteValidated(port) || hasValidatedShelter(port);
  }

  function renderPort(port) {
    const route = port?.route || {};
    const transit = route?.transit_hours || {};
    const shelter = port?.shelter_summary || {};
    const routeValidated = isRouteValidated(port);
    const shelterValidated = hasValidatedShelter(port);
    const offshore = route.trip_mode === "one_way_multi_day";
    const pills = [
      routeValidated ? `<span class="pk-pill">${offshore ? "ROUTE OFFSHORE VALIDÉE" : "ROUTE VALIDÉE"}</span>` : "",
      shelterValidated ? '<span class="pk-pill pk-shelter-pill">ABRI VALIDÉ</span>' : "",
    ].filter(Boolean).join("");
    const routeBlock = routeValidated ? `
      <div class="pk-meta">
        ${escapeHTML(route.origin_name)} → ${escapeHTML(port.name)} ·
        ${Number(route.distance_nm || 0).toFixed(1)} NM ·
        ${Number(transit.fast || 0).toFixed(1)}–${Number(transit.conservative || 0).toFixed(1)} h
      </div>
      <div class="pk-note">${escapeHTML(routeLabel(port))}</div>
      ${route.note_fr ? `<div class="pk-note">${escapeHTML(route.note_fr)}</div>` : ""}` : "";
    const shelterBlock = shelterValidated
      ? `<div class="pk-shelter">${escapeHTML(shelter.message_fr || "Abri validé disponible")}</div>`
      : "";
    return `
      <div class="pk-row${offshore && routeValidated ? " pk-offshore" : ""}">
        <div class="pk-title">
          <strong>${escapeHTML(port.name)}</strong>
          <span class="pk-pills">${pills}</span>
        </div>
        ${routeBlock}
        ${shelterBlock}
      </div>`;
  }

  function installStyles() {
    if (document.getElementById("fable-port-knowledge-styles")) return;
    const style = document.createElement("style");
    style.id = "fable-port-knowledge-styles";
    style.textContent = `
      .port-knowledge-card { margin-top: 16px; }
      .pk-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; }
      .pk-row { border:1px solid var(--br); border-radius:12px; padding:12px; background:var(--pill-bg); }
      .pk-row.pk-offshore { border-color:var(--warn); }
      .pk-title { display:flex; justify-content:space-between; gap:8px; align-items:center; }
      .pk-pills { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:5px; }
      .pk-pill { border:1px solid var(--br); border-radius:999px; padding:2px 7px; font-size:.72rem; font-weight:800; }
      .pk-shelter-pill { color:var(--ok); border-color:var(--ok); }
      .pk-meta { margin-top:7px; font-size:.9rem; }
      .pk-note, .pk-shelter { margin-top:5px; color:var(--muted); font-size:.84rem; line-height:1.35; }
      .pk-offshore .pk-pill { color:var(--warn); border-color:var(--warn); }
      .pk-offshore .pk-shelter-pill { color:var(--ok); border-color:var(--ok); }
    `;
    document.head.appendChild(style);
  }

  async function mount() {
    const data = await loadJSON("port-knowledge.json");
    if (!data || !Array.isArray(data.ports)) return;
    const visiblePorts = data.ports.filter(isDisplayEligible);
    if (!visiblePorts.length) return;
    if (document.getElementById("port-knowledge-card")) return;
    installStyles();
    const card = document.createElement("section");
    card.id = "port-knowledge-card";
    card.className = "card port-knowledge-card";
    card.innerHTML = `
      <h3><span>🧭 Routes & abris validés</span></h3>
      <div class="pk-grid">${visiblePorts.map(renderPort).join("")}</div>`;
    const dashboard = document.getElementById("dashboard-content");
    if (dashboard) dashboard.appendChild(card);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
