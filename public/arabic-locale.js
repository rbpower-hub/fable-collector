/* FABLE Arabic locale — family-facing MSA with Tunisia time and RTL. */
(function () {
  const TUNIS_TZ = 'Africa/Tunis';
  const KEYS = [
    'appTitle','tabs.threeDays','tabs.activities','tabs.map','tabs.details','windows','warnings','radar','raw',
    'settings','close','modeExpert','modeFamily','verdict.STALE','verdict.NO_DATA','verdict.GO_TODAY',
    'verdict.GO_SOON','verdict.NO_GO','mapAction','reasonsAction','planning','longPlanner','today','tomorrow','afterTomorrow',
  ];
  const AR = {
    appTitle: '🧭 فابل: لوحة القيادة',
    tabs: {threeDays: '3 أيام', activities: 'الأنشطة', map: 'الخريطة', details: 'التفاصيل'},
    windows: '🪟 نوافذ الملاحة', warnings: '🚦 أسباب عدم الخروج', radar: '📡 رادار المواقع', raw: '📚 البيانات الخام',
    settings: 'الإعدادات', close: 'إغلاق', modeExpert: '🧰 وضع الخبير', modeFamily: '👨‍👩‍👧 وضع العائلة',
    verdict: {
      STALE: ['بيانات قديمة — لا تعتمد على هذه اللوحة', 'انتظر تحديثاً جديداً قبل التخطيط للخروج.', 'بيانات قديمة'],
      NO_DATA: ['البيانات غير متاحة — لا تعتمد على هذه اللوحة', 'تعذر تحميل ملف نوافذ السلامة.', 'لا توجد بيانات'],
      GO_TODAY: ['يمكن القيام بخروج عائلي اليوم', '', 'مناسب للعائلة'],
      GO_SOON: ['ليس اليوم — أقرب نافذة عائلية آمنة', '', 'نافذة قادمة'],
      NO_GO: ['لا توجد خرجة عائلية آمنة ضمن أفق التوقعات', 'لم يتم رصد نافذة عائلية آمنة ومكتملة.', 'غير مناسب'],
    },
    mapAction: 'عرض على الخريطة', reasonsAction: 'عرض الأسباب', planning: '📅 تخطيط عائلي لثلاثة أيام · توقيت تونس',
    longPlanner: '🧭 مخطط الرحلات الطويلة', today: 'اليوم', tomorrow: 'غداً', afterTomorrow: 'بعد غد',
    noWindow: 'لا توجد نافذة آمنة', outbound: 'الذهاب', return: 'العودة', noReturn: 'لا توجد نافذة عودة آمنة خلال 72 ساعة',
    reliability: {high: '●●● · موثوقية ممتازة', medium: '●●○ · موثوقية جيدة', low: '●○○ · موثوقية محدودة — يجب التأكد مجدداً قبل الانطلاق'},
    models: (count) => `✓ توافق ${count} نماذج جوية`, marineMissing: '⚠️ بيانات الأمواج غير متاحة — النوافذ غير مؤكدة',
    staleBanner: (date) => `⚠️ البيانات تعود إلى ${date}. لم تعد اللوحة موثوقة — لا تنطلق اعتماداً عليها.`,
    statusOk: 'الحالة: سليمة', statusStale: 'الحالة: بيانات قديمة',
    nextRefresh: (seconds) => `التحديث التالي خلال ${seconds} ثانية.`,
  };

  let statusPayload = null;
  let scheduled = false;

  const get = (path) => path.split('.').reduce((value, key) => value?.[key], AR);
  const setText = (node, value) => { if (node && value != null && node.textContent !== value) node.textContent = value; };
  const isArabic = () => localStorage.getItem('lang') === 'ar';

  function validateDictionary() {
    KEYS.forEach((key) => { if (get(key) == null) console.warn(`[FABLE i18n] missing ar key: ${key}`); });
  }

  function formatDate(value, options = {}) {
    const date = value instanceof Date ? value : new Date(value || '');
    if (!Number.isFinite(date.getTime())) return '—';
    return date.toLocaleString('ar-TN', {timeZone: TUNIS_TZ, hour12: false, ...options});
  }

  function installStyles() {
    if (document.getElementById('fable-arabic-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-arabic-styles';
    style.textContent = `
      html[dir="rtl"] body{font-family:Tahoma,"Segoe UI",Arial,sans-serif;text-align:right}
      html[dir="rtl"] .leaflet-container,html[dir="rtl"] .leaflet-control{direction:ltr;text-align:left}
      html[dir="rtl"] .app-header,html[dir="rtl"] .family-summary-main,html[dir="rtl"] .verdict-grid{direction:rtl}
      html[dir="rtl"] .family-board-nav,html[dir="rtl"] .hdr-tools{direction:rtl}
      html[dir="rtl"] .family-summary-actions,html[dir="rtl"] .verdict-actions{justify-content:flex-start}
      html[dir="rtl"] .window-line .title,html[dir="rtl"] .pk-title{justify-content:flex-start}
      html[dir="rtl"] .conditions .line{border-left:1px solid var(--br);border-right:4px solid var(--warn)}
      html[dir="rtl"] .conditions .line.bad{border-right-color:var(--bad)}
    `;
    document.head.appendChild(style);
  }

  function ensureArabicButton() {
    const toggle = document.getElementById('langToggle');
    if (!toggle) return;
    let button = toggle.querySelector('[data-lang="ar"]');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.dataset.lang = 'ar';
      button.textContent = 'ع';
      button.setAttribute('aria-pressed', 'false');
      toggle.appendChild(button);
    }
    if (!toggle.dataset.arBound) {
      toggle.dataset.arBound = '1';
      toggle.addEventListener('click', (event) => {
        const selected = event.target.closest('[data-lang]')?.dataset.lang;
        if (!selected) return;
        localStorage.setItem('lang', selected);
        document.documentElement.lang = selected === 'ar' ? 'ar' : selected;
        document.documentElement.dir = selected === 'ar' ? 'rtl' : 'ltr';
        toggle.querySelectorAll('[data-lang]').forEach((item) => {
          item.classList.toggle('active', item.dataset.lang === selected);
          item.setAttribute('aria-pressed', item.dataset.lang === selected ? 'true' : 'false');
        });
        window.dispatchEvent(new CustomEvent('fable:languagechange', {detail: {language: selected}}));
        setTimeout(apply, 0);
      }, true);
    }
  }

  function ArabicReason(raw) {
    const value = String(raw || '').toLowerCase();
    const number = String(raw || '').match(/\d+(?:[.,]\d+)?/)?.[0]?.replace(',', '.') || '';
    if (/orages?|thunder/.test(value)) return '⛈️ عواصف رعدية متوقعة — الخروج غير ممكن';
    if (/vis\s*</.test(value)) return '🌫️ الرؤية غير كافية';
    if (/rafales?|gust/.test(value)) return `💨 هبّات رياح قوية جداً${number ? ` (${number} كم/س)` : ''}`;
    if (/squall|grains|instable/.test(value)) return '💨 رياح غير مستقرة مع احتمال هبّات مفاجئة';
    if (/onshore/.test(value)) return '🌊 رياح قوية باتجاه الساحل';
    if (/(^|\s)vent\s+\d|wind too/.test(value)) return `💨 الرياح قوية جداً${number ? ` (${number} كم/س)` : ''}`;
    if (/vagues?.*[≥>]|sea too|\bhs\b/.test(value)) return `🌊 البحر مضطرب${number ? ` (${number} م)` : ''}`;
    if (/\btp\b|short.*wave|vagues? courtes?/.test(value)) return '🌊 أمواج قصيرة وغير مريحة';
    if (/vagues_inconnues|houle.*indisponible|wave data.*missing/.test(value)) return '❓ بيانات الأمواج غير متوفرة';
    if (/aucune fenêtre|no .*slot/.test(value)) return '📅 لا توجد فترة نهارية آمنة وطويلة بما يكفي';
    return String(raw || 'السبب غير متوفر');
  }

  function translateStatic() {
    setText(document.querySelector('.app-header h1'), AR.appTitle);
    const tabs = {today: AR.tabs.threeDays, activities: AR.tabs.activities, map: AR.tabs.map, details: AR.tabs.details};
    Object.entries(tabs).forEach(([tab, label]) => {
      const button = document.querySelector(`[data-family-tab="${tab}"]`);
      setText(button?.querySelector('.family-tab-label'), label);
      if (button) button.dataset.short = label;
    });
    setText(document.querySelector('.card.wins h3 span'), AR.windows);
    setText(document.querySelector('.card.conditions h3 span'), AR.warnings);
    setText(document.querySelector('.card.radar h3 span'), AR.radar);
    setText(document.querySelector('#raw-links-list')?.closest('details')?.querySelector('summary'), AR.raw);
    setText(document.querySelector('#mobile-settings-sheet h2'), AR.settings);
    document.querySelectorAll('.mobile-sheet-close').forEach((button) => button.setAttribute('aria-label', AR.close));
    const modeButton = document.getElementById('viewToggleBtn');
    setText(modeButton, document.body.classList.contains('family-board-mode') ? AR.modeExpert : AR.modeFamily);
    const status = document.getElementById('hc');
    if (status) setText(status, status.classList.contains('ok') ? AR.statusOk : AR.statusStale);
  }

  function translateVerdict() {
    const hero = document.getElementById('family-verdict-hero');
    if (!hero) return;
    const state = hero.dataset.state || 'NO_GO';
    const values = AR.verdict[state] || AR.verdict.NO_GO;
    const title = hero.querySelector('h2');
    const detail = hero.querySelector('.verdict-detail');
    const badge = hero.querySelector('.verdict-badge');
    setText(title, values[0]);
    setText(badge, values[2]);
    if (['STALE','NO_DATA','NO_GO'].includes(state)) {
      const raw = detail?.dataset.rawReason || detail?.title || detail?.textContent || '';
      setText(detail, state === 'NO_GO' && raw ? ArabicReason(raw) : values[1]);
    } else if (detail) {
      const spot = detail.dataset.arSpot || detail.textContent.split('·')[0].trim();
      detail.dataset.arSpot = spot;
      const start = hero.dataset.start;
      const end = hero.dataset.end;
      const period = state === 'GO_TODAY'
        ? `${formatDate(start, {hour:'2-digit',minute:'2-digit'})} ← ${formatDate(end, {hour:'2-digit',minute:'2-digit'})}`
        : `${formatDate(start, {weekday:'long',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})} ← ${formatDate(end, {hour:'2-digit',minute:'2-digit'})}`;
      setText(detail, `${spot} · ${period}`);
    }
    const reliability = hero.querySelector('.verdict-confidence');
    if (reliability) {
      const dots = reliability.textContent.match(/[●○]{3}/)?.[0] || '●○○';
      const key = dots === '●●●' ? 'high' : dots === '●●○' ? 'medium' : 'low';
      setText(reliability, AR.reliability[key]);
    }
    hero.querySelectorAll('[data-verdict-action="map"]').forEach((button) => setText(button, AR.mapAction));
    hero.querySelectorAll('[data-verdict-action="reasons"]').forEach((button) => setText(button, AR.reasonsAction));
  }

  function translatePlanning() {
    const headings = document.querySelectorAll('.family-planning-head h3');
    if (headings[0]) setText(headings[0], AR.planning);
    if (headings[1]) setText(headings[1], AR.longPlanner);
    const labels = [AR.today, AR.tomorrow, AR.afterTomorrow];
    document.querySelectorAll('.family-day').forEach((card, index) => {
      setText(card.querySelector('.family-day-title'), labels[index] || AR.afterTomorrow);
      setText(card.querySelector('.family-day-date'), formatDate(new Date(Date.now() + index * 86400000), {day:'2-digit',month:'short'}));
      const empty = card.querySelector('.family-day-empty');
      if (empty) setText(empty, AR.noWindow);
      const count = card.querySelector('.family-day-count');
      if (count) {
        const numbers = count.textContent.match(/\d+/g) || ['0','0'];
        setText(count, `${numbers[0]} خيارات عائلية · ${numbers[1] || 0} رحلات طويلة`);
      }
      const state = card.querySelector('.family-day-state');
      if (state?.textContent === 'TRAVEL') setText(state, 'رحلة');
    });
    document.querySelectorAll('.trip-leg b').forEach((label) => {
      setText(label, /Retour|Return/i.test(label.textContent) ? AR.return : AR.outbound);
    });
    document.querySelectorAll('.trip-leg.missing').forEach((row) => {
      const label = row.querySelector('b')?.textContent || AR.return;
      setText(row, `${label} ${AR.noReturn}`);
    });
  }

  function translateFamilyDetails() {
    document.querySelectorAll('.family-reliability').forEach((node) => {
      const dots = node.textContent.match(/[●○]{3}/)?.[0] || '●○○';
      setText(node, dots === '●●●' ? AR.reliability.high : dots === '●●○' ? AR.reliability.medium : AR.reliability.low);
    });
    document.querySelectorAll('.family-model-agreement').forEach((node) => {
      const count = node.textContent.match(/\d+/)?.[0] || '2';
      setText(node, AR.models(count));
    });
    document.querySelectorAll('.family-marine-warning').forEach((node) => setText(node, AR.marineMissing));
    document.querySelectorAll('#reasons .line').forEach((line) => {
      const friendly = line.querySelector('.friendly-reason');
      const raw = line.dataset.rawReason || line.title || friendly?.textContent;
      if (friendly && raw) setText(friendly, ArabicReason(raw));
    });
    document.querySelectorAll('.stale-data-banner').forEach((banner) => {
      const date = statusPayload?.generated_at ? formatDate(statusPayload.generated_at, {weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—';
      setText(banner, AR.staleBanner(date));
    });
  }

  function apply() {
    ensureArabicButton();
    const selected = localStorage.getItem('lang') || 'fr';
    document.documentElement.lang = selected;
    document.documentElement.dir = selected === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('#langToggle [data-lang]').forEach((item) => {
      item.classList.toggle('active', item.dataset.lang === selected);
      item.setAttribute('aria-pressed', item.dataset.lang === selected ? 'true' : 'false');
    });
    if (!isArabic()) return;
    translateStatic();
    translateVerdict();
    translatePlanning();
    translateFamilyDetails();
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; apply(); });
  }

  async function refreshStatus() {
    try {
      const response = await fetch('status.json', {cache:'no-store'});
      statusPayload = response.ok ? await response.json() : null;
    } catch {
      statusPayload = null;
    }
    apply();
  }

  function start() {
    validateDictionary();
    installStyles();
    ensureArabicButton();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {subtree:true,childList:true});
    refreshStatus();
    setInterval(refreshStatus, 10 * 60 * 1000);
    apply();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
