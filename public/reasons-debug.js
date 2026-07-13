/* Backend-first Family GO diagnostics and window annotations. */
window.FABLE = window.FABLE || {};

(function (NS) {
  let sites = new Map();
  let cachedWindows = null;
  let cachedAt = 0;

  async function loadJSON(path) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      return await response.json();
    } catch {
      return null;
    }
  }

  function applySites(normalized) {
    if (!normalized || !Array.isArray(normalized.sites)) return;
    sites = new Map();
    normalized.sites.forEach((site) => {
      const path = String(site?.path || `${site?.slug || ""}.json`);
      if (!path) return;
      const record = {
        path,
        name: String(site?.name || path),
        windows_enabled: site?.windows_enabled !== false,
      };
      sites.set(path.toLowerCase(), record);
      sites.set(path.replace(/\.json$/i, "").toLowerCase(), record);
    });
  }

  NS.configure = function configure(options = {}) {
    applySites(options.sitesNormalized);
  };

  async function getWindows(force = false) {
    const now = Date.now();
    if (!force && cachedWindows && now - cachedAt < 60_000) return cachedWindows;
    cachedWindows = await loadJSON("windows.json");
    cachedAt = now;
    return cachedWindows;
  }

  function siteRecord(path) {
    const key = String(path || "").toLowerCase();
    return sites.get(key) || sites.get(key.replace(/\.json$/i, "")) || {
      path,
      name: String(path || "").replace(/\.json$/i, ""),
      windows_enabled: true,
    };
  }

  function destinationMap(data) {
    return new Map(
      (data?.windows || []).map((item) => [String(item?.dest_slug || "").toLowerCase(), item])
    );
  }

  function formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("fr-FR", {
      weekday: "long",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  function diagnosticLine(destination) {
    const windows = Array.isArray(destination?.windows) ? destination.windows : [];
    const offshore = destination?.trip_mode === "one_way_multi_day";
    if (windows.length) {
      if (offshore) {
        const outbound = windows.filter((item) => item?.direction === "outbound").length;
        const inbound = windows.filter((item) => item?.direction === "return").length;
        return `✓ navigation offshore · ${outbound} aller · ${inbound} retour · aucun A/R le même jour`;
      }
      const prudent = windows.filter((item) => item?.family_tier === "prudent").length;
      const standard = windows.length - prudent;
      if (prudent && !standard) {
        return `⚠ FAMILY GO prudent disponible (${prudent} fenêtre${prudent > 1 ? "s" : ""})`;
      }
      if (prudent) {
        return `✓ fenêtre possible · ${standard} standard · ${prudent} prudente${prudent > 1 ? "s" : ""}`;
      }
      return "✓ fenêtre Family GO possible";
    }

    const diagnostics = destination?.diagnostics || {};
    const blocker = diagnostics?.first_blocker || {};
    const nearMiss = diagnostics?.near_miss || {};
    const fallback = offshore
      ? "Aucune fenêtre offshore aller simple validée."
      : "Aucune fenêtre Family GO validée.";
    let message = String(diagnostics?.summary_fr || fallback);
    if (blocker?.time) message += ` · ${formatTime(blocker.time)}`;
    if (
      Number.isFinite(Number(nearMiss?.validated_hours)) &&
      Number.isFinite(Number(nearMiss?.required_hours)) &&
      Number(nearMiss.required_hours) > 0
    ) {
      message += ` · proche: ${nearMiss.validated_hours}/${nearMiss.required_hours} h validées`;
    }
    return `✗ ${message}`;
  }

  NS.debugReasons = async function debugReasons(paths, options = {}) {
    NS.configure(options);
    const data = options.windowsData || await getWindows(true);
    const byDestination = destinationMap(data);
    const requested = new Set(
      Array.isArray(paths) && paths.length
        ? paths
        : Array.from(new Set(Array.from(sites.values()).map((item) => item.path)))
    );
    (data?.windows || []).forEach((destination) => {
      if (destination?.trip_mode === "one_way_multi_day" && destination?.dest_slug) {
        requested.add(destination.dest_slug);
      }
    });
    const rows = [];

    requested.forEach((path) => {
      const record = siteRecord(path);
      if (record.windows_enabled === false) return;
      const destination = byDestination.get(String(path).toLowerCase());
      if (!destination) {
        rows.push({
          spot: `${record.name} (${record.path})`,
          family: "✗ diagnostic backend indisponible",
          note: "windows.json ne contient pas cette destination",
        });
        return;
      }
      const offshore = destination?.trip_mode === "one_way_multi_day";
      rows.push({
        spot: `${destination.dest_name || record.name} (${destination.dest_slug || record.path})`,
        family: diagnosticLine(destination),
        note: offshore
          ? "Navigation offshore directionnelle — l’aller et le retour sont indépendants."
          : "Diagnostic publié par le moteur Python — aucune réévaluation simplifiée dans le navigateur.",
        diagnostics: destination.diagnostics || null,
      });
    });
    console.table(rows);
    return rows;
  };

  function installStyles() {
    if (document.getElementById("fable-window-extension-styles")) return;
    const style = document.createElement("style");
    style.id = "fable-window-extension-styles";
    style.textContent = `
      .window-line.family-prudent {
        border-color: var(--warn) !important;
        background: rgb(from var(--warn) r g b / .08);
      }
      .window-line.family-prudent .go {
        background: var(--warn) !important;
        color: #160f04 !important;
      }
      .window-line.offshore-one-way {
        border-color: var(--accent, #4ba3ff) !important;
        background: rgb(75 163 255 / .08);
      }
      .window-line.offshore-one-way .go {
        background: transparent !important;
        border: 1px solid var(--accent, #4ba3ff) !important;
        color: var(--accent, #4ba3ff) !important;
      }
      .prudent-note, .offshore-note {
        margin-top: 6px;
        font-size: .84rem;
        line-height: 1.35;
      }
      .prudent-note { color: var(--warn); }
      .offshore-note { color: var(--muted); }
    `;
    document.head.appendChild(style);
  }

  function annotateRenderedWindows(data) {
    installStyles();
    const byKey = new Map();
    (data?.windows || []).forEach((destination) => {
      (destination?.windows || []).forEach((item) => {
        const key = [destination.dest_slug || "", item.start || "", item.end || ""].join("|");
        byKey.set(key, { ...item, destination_trip_mode: destination.trip_mode });
      });
    });

    document.querySelectorAll(".window-line[data-slug]").forEach((node) => {
      const key = [node.dataset.slug || "", node.dataset.start || "", node.dataset.end || ""].join("|");
      const item = byKey.get(key);
      if (!item) return;
      const badge = node.querySelector(".go");

      if (item.trip_mode === "one_way_multi_day" || item.destination_trip_mode === "one_way_multi_day") {
        node.classList.add("offshore-one-way");
        const direction = item.direction === "return" ? "RETOUR" : "ALLER";
        if (badge) badge.textContent = `OFFSHORE ${direction}`;
        if (!node.querySelector(".offshore-note")) {
          const note = document.createElement("div");
          note.className = "offshore-note";
          note.textContent = item.caution_fr
            || "Traversée aller simple : aucun retour à Gammarth le même jour n’est exigé.";
          node.appendChild(note);
        }
        return;
      }

      if (item.family_tier !== "prudent") return;
      node.classList.add("family-prudent");
      if (badge) badge.textContent = "FAMILY GO PRUDENT";
      if (!node.querySelector(".prudent-note")) {
        const note = document.createElement("div");
        note.className = "prudent-note";
        note.textContent = item.caution_fr
          || "Confort réduit : surveiller le renforcement et prévoir un retour anticipé.";
        node.appendChild(note);
      }
    });
  }

  async function refreshAnnotations() {
    const data = await getWindows(true);
    if (data) annotateRenderedWindows(data);
  }

  function observeBoard() {
    const target = document.getElementById("wins");
    if (!target) return;
    const observer = new MutationObserver(() => {
      if (cachedWindows) annotateRenderedWindows(cachedWindows);
      else refreshAnnotations();
    });
    observer.observe(target, { childList: true, subtree: true });
    refreshAnnotations();
    setInterval(refreshAnnotations, 10 * 60 * 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observeBoard, { once: true });
  } else {
    observeBoard();
  }
})(window.FABLE);
