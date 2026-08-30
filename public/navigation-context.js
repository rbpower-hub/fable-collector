/* Contexte de navigation partage entre les vues Simplifiee, Family et Expert.

   Ce module ne calcule aucun verdict. Il ne connait ni seuil ni regle meteo :
   `windows.json` reste la seule source autorisee pour valider l'existence d'une
   fenetre. Son role se limite a conserver une identite coherente
   jour + port + fenetre entre les composants et les rafraichissements. */
(function (root) {
  const DAY_STORAGE_KEY = 'fable_selected_day';
  const PORT_STORAGE_KEY = 'fable_selected_port';
  // La vue Mobile historique utilise `fable_selected_window` pour l'etat de
  // son accordeon. Une cle dediee evite qu'elle ecrase l'identite metier.
  const WINDOW_STORAGE_KEY = 'fable_navigation_window_v1';
  const TUNIS_TZ = 'Africa/Tunis';
  const EVENT_NAME = 'fable:navigation-context-changed';

  const storageGet = (storage, key) => {
    try { return storage?.getItem?.(key) || ''; } catch { return ''; }
  };
  const storageSet = (storage, key, value) => {
    try {
      if (value) storage?.setItem?.(key, value);
      else storage?.removeItem?.(key);
    } catch { /* storage indisponible : le contexte memoire reste utilisable */ }
  };

  function tunisDateKey(value) {
    const date = value instanceof Date ? value : new Date(value || '');
    if (!Number.isFinite(date.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone:TUNIS_TZ, year:'numeric', month:'2-digit', day:'2-digit',
    }).formatToParts(date).reduce((result, part) => {
      if (part.type !== 'literal') result[part.type] = part.value;
      return result;
    }, {});
    return `${parts.year}-${parts.month}-${parts.day}`;
  }

  function planningDays(now = new Date(), count = 3) {
    const first = tunisDateKey(now);
    if (!first) return [];
    const [year, month, day] = first.split('-').map(Number);
    return Array.from({length:count}, (_, index) => (
      new Date(Date.UTC(year, month - 1, day + index, 12)).toISOString().slice(0, 10)
    ));
  }

  const normalizePort = (value) => String(value || '').trim();
  function normalizeWindow(value) {
    if (!value || typeof value !== 'object') return null;
    const slug = normalizePort(value.slug || value.file || value.dest_slug);
    const start = String(value.start || '');
    const end = String(value.end || '');
    const startTime = new Date(start).getTime();
    const endTime = new Date(end).getTime();
    if (!slug || !Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime <= startTime) return null;
    return {slug, start, end, direction:String(value.direction || '')};
  }
  const windowIdentity = (value) => {
    const item = normalizeWindow(value);
    return item ? [item.slug, item.start, item.end, item.direction].join('|') : '';
  };

  function storedWindow() {
    const raw = storageGet(root.sessionStorage, WINDOW_STORAGE_KEY);
    if (!raw) return null;
    try { return normalizeWindow(JSON.parse(raw)); } catch { return null; }
  }

  const initialWindow = storedWindow();
  let state = {
    day:initialWindow
      ? tunisDateKey(initialWindow.start)
      : storageGet(root.localStorage, DAY_STORAGE_KEY),
    port:initialWindow?.slug
      || normalizePort(storageGet(root.localStorage, PORT_STORAGE_KEY)),
    window:initialWindow,
  };

  function snapshot() {
    return {
      day:state.day,
      port:state.port,
      window:state.window ? {...state.window} : null,
    };
  }

  function persist() {
    storageSet(root.localStorage, DAY_STORAGE_KEY, state.day);
    storageSet(root.localStorage, PORT_STORAGE_KEY, state.port);
    storageSet(
      root.sessionStorage,
      WINDOW_STORAGE_KEY,
      state.window ? JSON.stringify(state.window) : '',
    );
  }

  function publish(previous, source) {
    const current = snapshot();
    const changes = Object.keys(current).filter((key) => (
      key === 'window'
        ? windowIdentity(previous.window) !== windowIdentity(current.window)
        : previous[key] !== current[key]
    ));
    if (!changes.length) return current;
    root.dispatchEvent?.(new root.CustomEvent(EVENT_NAME, {
      detail:{context:current, previous, changes, source},
    }));
    return current;
  }

  function replace(next, {source = 'unknown', persistState = true} = {}) {
    const previous = snapshot();
    state = {
      day:String(next.day || ''),
      port:normalizePort(next.port),
      window:normalizeWindow(next.window),
    };
    if (persistState) persist();
    return publish(previous, source);
  }

  function setDay(day, options = {}) {
    const nextDay = String(day || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(nextDay)) return snapshot();
    const keepWindow = state.window && tunisDateKey(state.window.start) === nextDay;
    return replace({...state, day:nextDay, window:keepWindow ? state.window : null}, options);
  }

  function setPort(port, options = {}) {
    const nextPort = normalizePort(port);
    const keepWindow = state.window && state.window.slug === nextPort;
    return replace({...state, port:nextPort, window:keepWindow ? state.window : null}, options);
  }

  function selectWindow(value, options = {}) {
    const selected = normalizeWindow(value);
    if (!selected) return snapshot();
    return replace({
      day:tunisDateKey(selected.start) || state.day,
      port:selected.slug,
      window:selected,
    }, options);
  }

  function clearWindow(options = {}) {
    return replace({...state, window:null}, options);
  }

  function candidateWindows(destination) {
    const containers = [
      destination,
      destination?.long_trip_one_way,
      destination?.offshore_one_way_beta,
      destination?.offshore,
    ].filter(Boolean);
    return [
      ...(destination?.windows || []),
      ...(destination?.watch_windows || []),
      ...containers.flatMap((container) => [
        ...(container?.outbound || []).map((item) => ({...item, direction:item.direction || 'outbound'})),
        ...(container?.outbound_windows || []).map((item) => ({...item, direction:item.direction || 'outbound'})),
        ...(container?.return || []).map((item) => ({...item, direction:item.direction || 'return'})),
        ...(container?.returns || []).map((item) => ({...item, direction:item.direction || 'return'})),
        ...(container?.return_windows || []).map((item) => ({...item, direction:item.direction || 'return'})),
      ]),
    ];
  }

  function reconcile(windowsData, {
    now = new Date(), validDays = planningDays(now), defaultDay = validDays[0] || '',
    source = 'windows-refresh',
  } = {}) {
    const day = validDays.includes(state.day) ? state.day : defaultDay;
    const destinations = Array.isArray(windowsData?.windows) ? windowsData.windows : null;
    let port = state.port;
    let selected = state.window;

    if (destinations) {
      if (port && !destinations.some((item) => String(item?.dest_slug || '') === port)) port = '';
      if (selected) {
        const destination = destinations.find((item) => String(item?.dest_slug || '') === selected.slug);
        const identities = (destination ? candidateWindows(destination) : []).map((item) => (
          windowIdentity({slug:selected.slug, ...item})
        ));
        if (tunisDateKey(selected.start) !== day || !identities.includes(windowIdentity(selected))) selected = null;
      }
    } else {
      // Sans windows.json exploitable, aucune fenetre ne reste presentee comme
      // valide. Le port peut rester selectionne : c'est une identite, pas un GO.
      selected = null;
    }
    return replace({day, port, window:selected}, {source});
  }

  const api = {
    get:snapshot,
    setDay,
    setPort,
    selectWindow,
    clearWindow,
    reconcile,
    tunisDateKey,
    planningDays,
    windowIdentity,
    eventName:EVENT_NAME,
  };
  root.FABLENavigationContext = Object.assign(root.FABLENavigationContext || {}, api);

  // Pont temporaire avec le tableau Expert existant. Les nouveaux composants
  // ecrivent directement dans le contexte ; cet evenement reste accepte pour
  // les anciens liens de ports pendant la migration.
  root.addEventListener?.('fable:spot-selected', (event) => {
    setPort(event.detail?.file || '', {source:'legacy-spot-event'});
  });
  root.addEventListener?.('storage', (event) => {
    if (![DAY_STORAGE_KEY, PORT_STORAGE_KEY].includes(event.key)) return;
    if (event.key === DAY_STORAGE_KEY) {
      setDay(String(event.newValue || ''), {source:'storage', persistState:false});
    } else {
      setPort(event.newValue || '', {source:'storage', persistState:false});
    }
  });
})(window);
