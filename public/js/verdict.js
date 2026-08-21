import {
  freshnessState,
  navigationVerdictForDay,
} from './navigation-verdicts.js';
import {tunisNavigationDateKey} from './navigation-windows.js';

function futureNavigationDays(windows, today) {
  const keys = (windows?.windows || []).flatMap((destination) => (
    destination?.windows || []
  )).map((item) => tunisNavigationDateKey(item?.start))
    .filter((key) => key && key > today);
  return [...new Set(keys)].sort();
}

function blockerArgs(spot) {
  const diagnostics = spot?.diagnostics || {};
  return {
    reason_fr: diagnostics.summary_fr || diagnostics.first_blocker?.reason_fr || '',
    reason_en: diagnostics.summary_en || diagnostics.first_blocker?.reason_en || '',
  };
}

export function computeVerdict({windows, status, rules = {}, now = new Date()}) {
  const current = now instanceof Date ? now : new Date(now);
  const today = tunisNavigationDateKey(current);
  const todayVerdict = navigationVerdictForDay({
    windows,
    status,
    rules,
    now: current,
    selectedDay: today,
  });

  if (todayVerdict.state === 'STALE') {
    return {
      state: 'STALE',
      spot: null,
      window: null,
      message_key: 'stale',
      args: todayVerdict.args,
    };
  }
  if (todayVerdict.state === 'NO_DATA') {
    return {state:'NO_DATA', spot:null, window:null, message_key:'no_data', args:{}};
  }
  if (['GO_FAMILY', 'GO_PRUDENT'].includes(todayVerdict.state)) {
    return {
      state: 'GO_TODAY',
      spot: todayVerdict.spot,
      window: todayVerdict.window,
      message_key: 'go_today',
      args: todayVerdict.args,
    };
  }

  for (const selectedDay of futureNavigationDays(windows, today)) {
    const futureVerdict = navigationVerdictForDay({
      windows,
      status,
      rules,
      now: current,
      selectedDay,
    });
    if (!['GO_FAMILY', 'GO_PRUDENT'].includes(futureVerdict.state)) continue;
    return {
      state: 'GO_SOON',
      spot: futureVerdict.spot,
      window: futureVerdict.window,
      message_key: 'go_soon',
      args: futureVerdict.args,
    };
  }

  const spot = todayVerdict.blocker || null;
  return {
    state: 'NO_GO',
    spot,
    window: null,
    message_key: 'no_go',
    args: todayVerdict.state === 'NO_GO' ? todayVerdict.args : blockerArgs(spot),
  };
}

export {freshnessState, navigationVerdictForDay};

if (typeof window !== 'undefined') {
  window.FABLEVerdict = Object.assign(window.FABLEVerdict || {}, {
    computeVerdict,
    freshnessState,
    navigationVerdictForDay,
  });
}
