/* FABLE Simple View — isolated, mobile-first decision prototype. */
(function () {
  const MODE_KEY = 'fable_board_mode';
  const SIMPLE_DEFAULT_KEY = 'fable_simple_default_v1';
  const SIMPLE_MODE = 'simple';
  const TUNIS_TZ = 'Africa/Tunis';
  const state = {
    windows: null,
    status: null,
    rules: {},
    forecast: {},
    recommendations: {},
    activeDay: 0,
    loading: true,
    error: '',
    verdictModule: null,
  };

  const esc = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character])
  );
  const lang = () => {
    const value = (localStorage.getItem('lang') || document.documentElement.lang || 'fr').toLowerCase();
    return value.startsWith('ar') ? 'ar' : value.startsWith('en') ? 'en' : 'fr';
  };
  const copy = () => lang() === 'ar' ? {
    enter:'الوضع المبسّط', exit:'وضع العائلة', decision:'القرار', possible:'يمكن الخروج',
    prudent:'خروج بحذر', watch:'تحت المراقبة', watchDetail:'الظروف قريبة من حدود العائلة. هذه ليست موافقة للخروج، ويجب التحقق من النشرة البحرية قبل القرار.', blocked:'لا يُنصح بالخروج', conditions:'ظروف غير ملائمة',
    why:'لماذا؟', hide:'إخفاء الأسباب', route:'فتح الخريطة', confidence:'الثقة', options:'الخيارات',
    updated:'آخر تحديث', days:'3 أيام', today:'اليوم', tomorrow:'غداً', noWindow:'لا توجد نافذة مؤكدة',
    details:'التفاصيل', map:'الخريطة', more:'المزيد', good:'مناسب', cautious:'بحذر', noGo:'غير مناسب',
    next:'أفضل نافذة عائلية', planning:'نظرة على ثلاثة أيام', fresh:'بيانات حديثة', unavailable:'غير متاح',
    timeline:'التوقعات حسب الساعة', trends:'الظروف أثناء النافذة', wind:'الرياح', wave:'الأمواج', returnBy:'العودة قبل',
    weather:'الطقس', temperature:'الحرارة', feelsLike:'المحسوسة حتى', uv:'الأشعة فوق البنفسجية', humidity:'الرطوبة', sky:'السماء', rain:'الأمطار', visibility:'أدنى رؤية', cloud:'السحب',
    clear:'صافية', partlyCloudy:'قليلة السحب', cloudy:'غائمة', fog:'ضباب', showers:'أمطار أو زخات', storm:'عاصفة رعدية', uvLow:'منخفض', uvModerate:'متوسط', uvHigh:'مرتفع', uvVeryHigh:'مرتفع جداً',
    loading:'جارٍ تحميل التوقعات…', missing:'التوقعات غير متاحة', stale:'البيانات قديمة — تحقّق من النشرة البحرية الرسمية.',
    threshold:'حد العائلة', from:'من', to:'إلى', stable:'مستقر', rising:'في ارتفاع', falling:'في انخفاض', trySimple:'جرّب الوضع المبسّط',
    activities:'أنشطة مقترحة', noActivities:'لا توجد أنشطة متوافقة مع نافذة عائلية مؤكدة.', activityNote:'اقتراح بعد قرار السلامة',
    marineMissing:'بيانات الأمواج غير متاحة — بعض الوجهات غير مؤكدة.',
    offHours:'نافذة خارج الأوقات العائلية متاحة', offHoursDetail:'لا توجد نافذة عائلية كاملة في هذا اليوم، لكن توجد فترة طقس ملائمة خارج الأوقات العائلية.',
    travelOnly:'فترة سفر بحري طويلة متاحة', travelOnlyDetail:'هذه نافذة ملاحة لمسافة طويلة وليست موافقة على خرجة عائلية محلية.',
    staleTitle:'بيانات قديمة — لا تخرج اعتماداً عليها', noDataTitle:'بيانات الملاحة غير متاحة',
    windows:'نوافذ الملاحة', viewWindows:'عرض النوافذ', horizon:'أفق 72 ساعة', offHoursSlot:'خارج الأوقات', longTripSlot:'رحلة طويلة',
    confidenceHigh:'مرتفعة', confidenceMedium:'متوسطة', confidenceLow:'محدودة', outbound:'ذهاب', return:'عودة', beta:'تجريبي', review:'تحقق مطلوب',
  } : lang() === 'en' ? {
    enter:'Simple View', exit:'Family View', decision:'Decision', possible:'OUTING POSSIBLE',
    prudent:'CAUTIOUS OUTING', watch:'WATCH', watchDetail:'Conditions are close to Family limits. This is not a GO; check the marine forecast before deciding.', blocked:'OUTING NOT ADVISED', conditions:'Unfavourable conditions',
    why:'Why?', hide:'Hide reasons', route:'Open map', confidence:'Confidence', options:'Options',
    updated:'Updated', days:'3 days', today:'Today', tomorrow:'Tomorrow', noWindow:'No validated window',
    details:'Details', map:'Map', more:'More', good:'Good', cautious:'Cautious', noGo:'NO-GO',
    next:'Best family window', planning:'Three-day overview', fresh:'Fresh data', unavailable:'Unavailable',
    timeline:'Hourly outlook', trends:'Conditions during the window', wind:'Wind', wave:'Wave', returnBy:'Return by',
    weather:'Weather', temperature:'Temperature', feelsLike:'Feels like up to', uv:'UV index', humidity:'Humidity', sky:'Sky', rain:'Rain', visibility:'Minimum visibility', cloud:'Cloud',
    clear:'Clear', partlyCloudy:'Partly cloudy', cloudy:'Cloudy', fog:'Fog', showers:'Rain or showers', storm:'Thunderstorm', uvLow:'Low', uvModerate:'Moderate', uvHigh:'High', uvVeryHigh:'Very high',
    loading:'Loading forecast…', missing:'Forecast unavailable', stale:'Data is out of date — check the official marine bulletin.',
    threshold:'Family limit', from:'from', to:'to', stable:'stable', rising:'rising', falling:'falling', trySimple:'Try Simple View',
    activities:'Suggested activities', noActivities:'No compatible activity in a validated Family window.', activityNote:'Suggestion after the safety decision',
    marineMissing:'Wave data unavailable — some destinations are not confirmed.',
    offHours:'Out-of-hours window available', offHoursDetail:'There is no complete family window on this day, but favourable weather exists outside family hours.',
    travelOnly:'Long-distance navigation slot available', travelOnlyDetail:'This is a long-distance navigation window, not a local family-outing approval.',
    staleTitle:'Stale data — do not depart on this basis', noDataTitle:'Navigation data unavailable',
    windows:'Navigation windows', viewWindows:'View windows', horizon:'72-hour horizon', offHoursSlot:'Out of hours', longTripSlot:'Long trip',
    confidenceHigh:'High', confidenceMedium:'Medium', confidenceLow:'Limited', outbound:'Outbound', return:'Return', beta:'Beta', review:'Review required',
  } : {
    enter:'Vue Simple', exit:'Vue Famille', decision:'Décision', possible:'SORTIE POSSIBLE',
    prudent:'SORTIE PRUDENTE', watch:'À SURVEILLER', watchDetail:'Conditions proches des seuils Family. Ce créneau n’est pas un GO : vérifiez la météo marine avant de décider.', blocked:'SORTIE DÉCONSEILLÉE', conditions:'Conditions défavorables',
    why:'Pourquoi ?', hide:'Masquer les raisons', route:'Ouvrir la carte', confidence:'Confiance', options:'Options',
    updated:'Mise à jour', days:'3 jours', today:'Aujourd’hui', tomorrow:'Demain', noWindow:'Aucune fenêtre validée',
    details:'Détails', map:'Carte', more:'Plus', good:'Bonne', cautious:'Prudente', noGo:'NO-GO',
    next:'Meilleure fenêtre familiale', planning:'Aperçu sur trois jours', fresh:'Données fraîches', unavailable:'Indisponible',
    timeline:'Frise horaire', trends:'Conditions pendant la fenêtre', wind:'Vent', wave:'Houle', returnBy:'Retour avant',
    weather:'Météo', temperature:'Température', feelsLike:'Ressenti jusqu’à', uv:'Indice UV', humidity:'Humidité', sky:'Ciel', rain:'Pluie', visibility:'Visibilité minimale', cloud:'Nuages',
    clear:'Dégagé', partlyCloudy:'Peu nuageux', cloudy:'Couvert', fog:'Brume ou brouillard', showers:'Pluie ou averses', storm:'Orage', uvLow:'Faible', uvModerate:'Modéré', uvHigh:'Élevé', uvVeryHigh:'Très élevé',
    loading:'Chargement des prévisions…', missing:'Prévisions indisponibles', stale:'Données périmées — vérifiez le bulletin maritime officiel.',
    threshold:'Limite famille', from:'de', to:'à', stable:'stable', rising:'en hausse', falling:'en baisse', trySimple:'Essayer la Vue Simple',
    activities:'Activités conseillées', noActivities:'Aucune activité compatible dans une fenêtre Famille validée.', activityNote:'Suggestion après la décision de sécurité',
    marineMissing:'Données de vagues indisponibles — certaines destinations ne sont pas confirmées.',
    offHours:'Fenêtre hors horaires disponible', offHoursDetail:'Aucune fenêtre familiale complète ce jour, mais un créneau météo favorable existe hors horaires familiaux.',
    travelOnly:'Créneau de navigation longue distance', travelOnlyDetail:'Ce créneau concerne une navigation longue distance, pas une validation de sortie familiale locale.',
    staleTitle:'Données périmées — ne pas partir sur cette base', noDataTitle:'Données de navigation indisponibles',
    windows:'Fenêtres de navigation', viewWindows:'Voir les fenêtres', horizon:'Horizon 72 h', offHoursSlot:'Hors horaires', longTripSlot:'Long trajet',
    confidenceHigh:'Élevée', confidenceMedium:'Moyenne', confidenceLow:'Limitée', outbound:'Aller', return:'Retour', beta:'Bêta', review:'Vérification requise',
  };

  function installStyles() {
    if (document.getElementById('fable-simple-view-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-simple-view-styles';
    style.textContent = `
      #simple-view{display:none}
      .simple-entry{white-space:nowrap}
      body.simple-board-mode{padding-bottom:86px}
      body.simple-board-mode #simple-view{display:block}
      body.simple-board-mode #family-board-nav,body.simple-board-mode #family-summary,
      body.simple-board-mode #dashboard-content,body.simple-board-mode footer{display:none!important}
      body.simple-board-mode #viewToggleBtn,body.simple-board-mode #simpleViewBtn{display:none!important}
      .simple-shell{max-width:760px;margin:0 auto;padding:4px 0 22px}
      .simple-hero{position:relative;overflow:hidden;padding:22px;border:1px solid var(--br);border-radius:24px;background:linear-gradient(145deg,color-mix(in srgb,var(--ok) 18%,var(--card)),var(--card) 62%);box-shadow:var(--shadow)}
      .simple-hero.prudent{background:linear-gradient(145deg,color-mix(in srgb,var(--warn) 19%,var(--card)),var(--card) 62%)}
      .simple-hero.watch{background:linear-gradient(145deg,color-mix(in srgb,#f59e0b 20%,var(--card)),var(--card) 62%);border-color:color-mix(in srgb,#f59e0b 58%,var(--br))}
      .simple-hero.off-hours{background:linear-gradient(145deg,color-mix(in srgb,#22d3ee 18%,var(--card)),var(--card) 62%);border-color:color-mix(in srgb,#22d3ee 55%,var(--br))}
      .simple-hero.travel{background:linear-gradient(145deg,color-mix(in srgb,#60a5fa 16%,var(--card)),var(--card) 62%);border-color:color-mix(in srgb,#60a5fa 50%,var(--br))}
      .simple-hero.blocked{background:linear-gradient(145deg,color-mix(in srgb,var(--bad) 13%,var(--card)),var(--card) 62%)}
      .simple-hero-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(180px,.5fr);gap:18px;align-items:center}
      .simple-verdict{display:flex;align-items:center;gap:10px;margin:0 0 4px;font-size:clamp(1.45rem,7vw,2.2rem);line-height:1.08}
      .simple-verdict-icon{display:grid;place-items:center;width:42px;height:42px;flex:0 0 42px;border-radius:14px;background:color-mix(in srgb,var(--ok) 25%,var(--pill-bg))}
      .simple-hero.prudent .simple-verdict-icon{background:color-mix(in srgb,var(--warn) 27%,var(--pill-bg))}
      .simple-hero.watch .simple-verdict-icon{background:color-mix(in srgb,#f59e0b 29%,var(--pill-bg))}
      .simple-hero.off-hours .simple-verdict-icon{background:color-mix(in srgb,#22d3ee 24%,var(--pill-bg))}
      .simple-hero.travel .simple-verdict-icon{background:color-mix(in srgb,#60a5fa 23%,var(--pill-bg))}
      .simple-hero.blocked .simple-verdict-icon{background:color-mix(in srgb,var(--bad) 20%,var(--pill-bg))}
      .simple-destination{margin:13px 0 3px;font-size:1.18rem;font-weight:900}.simple-window{color:var(--muted);font-weight:700}
      .simple-hero-detail{max-width:48ch;margin:10px 0 0;color:var(--muted);font-weight:650;line-height:1.45}
      .simple-confidence{display:grid;place-items:center;align-content:center;min-height:172px;border-inline-start:1px solid var(--br)}
      .simple-confidence-ring{--score:0;display:grid;place-items:center;width:124px;height:124px;border-radius:50%;background:radial-gradient(circle at center,var(--card) 57%,transparent 59%),conic-gradient(var(--accent) calc(var(--score)*1%),color-mix(in srgb,var(--muted) 20%,transparent) 0);box-shadow:inset 0 0 22px #0004}
      .simple-confidence-ring span{display:block;text-align:center;color:var(--muted);font-size:.68rem}.simple-confidence-ring strong{display:block;margin-top:2px;color:var(--fg);font-size:1.75rem;line-height:1}.simple-confidence-word{margin-top:8px;color:var(--accent);font-size:.72rem;font-weight:900;text-transform:uppercase}
      .simple-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:18px}
      .simple-action{min-height:48px;border:1px solid var(--br);border-radius:14px;background:var(--pill-bg);color:var(--fg);font-weight:900;cursor:pointer}
      .simple-action:focus-visible,.simple-day:focus-visible,.simple-nav-action:focus-visible,.simple-entry:focus-visible,.simple-window-card:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
      .simple-action.primary{border-color:transparent;background:var(--accent);color:#041019}
      [data-theme="nautical"] .simple-action.primary{color:#fff}
      .simple-reasons{margin-top:12px;padding:14px;border:1px solid color-mix(in srgb,var(--bad) 40%,var(--br));border-radius:14px;background:var(--pill-bg)}
      .simple-reasons[hidden]{display:none}.simple-reasons p{margin:0;line-height:1.45}.simple-reasons small{display:block;margin-top:8px;color:var(--muted)}
      .simple-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:12px 0}
      .simple-metric{min-width:0;padding:12px;border:1px solid var(--br);border-radius:16px;background:var(--card)}
      .simple-metric span{display:block;color:var(--muted);font-size:.72rem}.simple-metric strong{display:block;margin-top:4px;font-size:.95rem;overflow:hidden;text-overflow:ellipsis}
      .simple-panel{margin-top:12px;padding:17px;border:1px solid var(--br);border-radius:20px;background:var(--card);box-shadow:var(--shadow)}
      .simple-panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.simple-panel h2{margin:0;font-size:1rem}.simple-panel-note{color:var(--muted);font-size:.76rem}
      .simple-day-context{--selection-color:var(--bad);position:relative;margin-top:4px}.simple-day-context.good{--selection-color:var(--ok)}.simple-day-context.prudent,.simple-day-context.stale{--selection-color:var(--warn)}.simple-day-context.watch{--selection-color:#f59e0b}.simple-day-context.off-hours{--selection-color:#22d3ee}.simple-day-context.travel{--selection-color:#60a5fa}.simple-day-context.loading,.simple-day-context.unavailable{--selection-color:var(--muted)}
      .simple-day-selector{position:relative;z-index:2;margin:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}.simple-day-selector .simple-panel-head{margin:0 2px 10px}
      .simple-selected-day-content{position:relative;z-index:1;margin-top:14px;padding:12px;border:2px solid var(--selection-color);border-radius:20px;background:color-mix(in srgb,var(--selection-color) 5%,var(--card));box-shadow:var(--shadow)}.simple-selected-day-content>.simple-hero{margin-top:0}
      .simple-days{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
      .simple-day{--day-color:var(--bad);position:relative;width:100%;display:flex;flex-direction:column;align-items:stretch;gap:7px;min-width:0;min-height:116px;padding:10px;border:1px solid var(--br);border-top:4px solid var(--day-color);border-radius:15px;background:var(--pill-bg);color:var(--fg);text-align:start;cursor:pointer}
      .simple-day.good{--day-color:var(--ok)}.simple-day.prudent,.simple-day.stale{--day-color:var(--warn)}.simple-day.watch{--day-color:#f59e0b}.simple-day.off-hours{--day-color:#22d3ee}.simple-day.travel{--day-color:#60a5fa}.simple-day.loading,.simple-day.unavailable{--day-color:var(--muted)}
      .simple-day[aria-selected="true"]{z-index:3;border-color:var(--day-color);border-end-start-radius:7px;border-end-end-radius:7px;background:color-mix(in srgb,var(--day-color) 12%,var(--card));box-shadow:0 0 0 2px color-mix(in srgb,var(--day-color) 26%,transparent),var(--shadow)}
      .simple-day[aria-selected="true"]::after{content:'';position:absolute;inset-inline:14px;bottom:-17px;height:17px;border-inline:2px solid var(--day-color);background:color-mix(in srgb,var(--day-color) 5%,var(--card));pointer-events:none}
      .simple-day-heading{display:flex;align-items:baseline;justify-content:space-between;gap:5px;min-width:0}.simple-day-title{font-weight:900;overflow:hidden;text-overflow:ellipsis}.simple-day-calendar{flex:0 0 auto;color:var(--muted);font-size:.64rem}
      .simple-day-state{color:var(--day-color);font-size:.75rem;font-weight:950;line-height:1.15}.simple-day-date{display:block;min-height:2.3em;color:var(--muted);font-size:.68rem;line-height:1.15}
      .simple-day-track{height:7px;margin-top:auto;overflow:hidden;border-radius:999px;background:color-mix(in srgb,var(--muted) 18%,transparent)}
      .simple-day-segment{height:100%;border-radius:inherit;background:var(--day-color)}.simple-day.blocked .simple-day-segment{width:100%!important;background:color-mix(in srgb,var(--bad) 35%,transparent)}
      .simple-data-state{margin:12px 0;padding:12px 14px;border:1px solid var(--br);border-radius:14px;background:var(--pill-bg);font-weight:800}.simple-data-state.stale,.simple-data-state.error{border-color:color-mix(in srgb,var(--warn) 55%,var(--br))}
      .simple-data-state.marine{border-color:color-mix(in srgb,var(--warn) 65%,var(--br));background:color-mix(in srgb,var(--warn) 10%,var(--card))}
      .simple-timeline{display:grid;grid-template-columns:repeat(17,1fr);gap:2px;margin-top:10px}.simple-hour{height:22px;border-radius:5px;background:color-mix(in srgb,var(--bad) 35%,var(--pill-bg))}.simple-hour.good{background:var(--ok)}.simple-hour.prudent{background:var(--warn)}.simple-hour.watch{background:#f59e0b}
      .simple-hour.off-hours{background:#22d3ee}.simple-hour.travel{background:#60a5fa}
      .simple-axis{display:flex;justify-content:space-between;margin-top:5px;color:var(--muted);font-size:.68rem}.simple-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;color:var(--muted);font-size:.72rem}.simple-key::before{content:'';display:inline-block;width:9px;height:9px;margin-right:5px;border-radius:3px;background:var(--bad)}.simple-key.good::before{background:var(--ok)}.simple-key.prudent::before{background:var(--warn)}
      .simple-key.watch::before{background:#f59e0b}.simple-key.off-hours::before{background:#22d3ee}.simple-key.travel::before{background:#60a5fa}
      .simple-condition-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.simple-condition{min-width:0;padding:14px;border-radius:16px;background:var(--pill-bg)}.simple-condition.return{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:12px}.simple-condition-label{display:block;color:var(--muted);font-size:.76rem}.simple-condition-value{display:block;margin-top:4px;font-size:1.18rem}.simple-condition-range{margin-left:6px;color:var(--muted);font-size:.72rem;font-weight:600}.simple-chart{margin:10px 0 0}.simple-spark{display:block;width:100%;height:88px;overflow:visible}.simple-spark .grid{stroke:color-mix(in srgb,var(--muted) 22%,transparent);stroke-width:1}.simple-spark .safe-zone{fill:color-mix(in srgb,var(--ok) 10%,transparent)}.simple-spark .threshold{stroke:var(--warn);stroke-width:1.5;stroke-dasharray:4 3}.simple-spark .area{fill:color-mix(in srgb,var(--accent) 13%,transparent)}.simple-spark .line{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.simple-spark .point{fill:var(--card);stroke:var(--accent);stroke-width:2;vector-effect:non-scaling-stroke}.simple-condition.wave .simple-spark .area{fill:color-mix(in srgb,var(--ok) 13%,transparent)}.simple-condition.wave .simple-spark .line,.simple-condition.wave .simple-spark .point{stroke:var(--ok)}.simple-chart-axis{display:flex;justify-content:space-between;margin-top:4px;color:var(--muted);font-size:.65rem}.simple-chart-threshold{margin-top:7px;color:var(--muted);font-size:.68rem}.simple-chart-threshold::before{content:'';display:inline-block;width:15px;margin-right:5px;border-top:2px dashed var(--warn);vertical-align:middle}html[dir="rtl"] .simple-chart-threshold::before{margin-right:0;margin-left:5px}
      .simple-weather-grid{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.simple-weather-item{min-width:0;padding:11px 12px;border:1px solid var(--br);border-radius:14px;background:color-mix(in srgb,var(--card) 55%,var(--pill-bg))}.simple-weather-label{display:block;color:var(--muted);font-size:.72rem}.simple-weather-value{display:block;margin-top:4px;font-size:.98rem}.simple-weather-detail{display:block;margin-top:3px;color:var(--muted);font-size:.68rem;line-height:1.3}
      .simple-activities{display:grid;gap:8px}.simple-activity{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;padding:12px;border:1px solid var(--br);border-radius:14px;background:var(--pill-bg)}.simple-activity-icon{font-size:1.35rem}.simple-activity strong{display:block}.simple-activity small{display:block;margin-top:3px;color:var(--muted);line-height:1.35}.simple-activity-score{padding:3px 7px;border-radius:999px;background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok);font-size:.72rem;font-weight:900}.simple-empty{color:var(--muted);line-height:1.45}
      .simple-navigation{display:grid;gap:8px}.simple-window-card{width:100%;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:11px;min-height:68px;padding:12px;border:1px solid var(--br);border-radius:15px;background:var(--pill-bg);color:var(--fg);text-align:start;cursor:pointer}.simple-window-card:hover{border-color:var(--accent)}.simple-window-badge{padding:4px 8px;border-radius:999px;background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok);font-size:.68rem;font-weight:900;text-transform:uppercase}.simple-window-badge.prudent{background:color-mix(in srgb,var(--warn) 17%,transparent);color:var(--warn)}.simple-window-badge.watch{background:color-mix(in srgb,#f59e0b 18%,transparent);color:#f59e0b}.simple-window-badge.off-hours{background:color-mix(in srgb,#22d3ee 16%,transparent);color:#22d3ee}.simple-window-badge.travel{background:color-mix(in srgb,#60a5fa 16%,transparent);color:#60a5fa}.simple-window-main strong,.simple-window-main small{display:block}.simple-window-main small{margin-top:4px;color:var(--muted)}.simple-window-arrow{font-size:1.4rem;color:var(--muted)}
      html[dir="rtl"] .simple-shell{direction:rtl;text-align:right}html[dir="rtl"] .simple-day{text-align:right}html[dir="rtl"] .simple-key::before{margin-right:0;margin-left:5px}
      .simple-bottom-nav{position:fixed;z-index:1100;left:max(10px,env(safe-area-inset-left));right:max(10px,env(safe-area-inset-right));bottom:max(10px,env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(4,1fr);max-width:560px;margin:auto;padding:7px;border:1px solid var(--br);border-radius:18px;background:color-mix(in srgb,var(--card) 94%,transparent);box-shadow:0 12px 35px #0007;backdrop-filter:blur(14px)}
      .simple-nav-action{min-height:48px;border:0;border-radius:12px;background:transparent;color:var(--muted);font-size:.7rem;font-weight:800;cursor:pointer}.simple-nav-action span{display:block;font-size:1.15rem;margin-bottom:2px}.simple-nav-action.active{background:color-mix(in srgb,var(--accent) 18%,var(--pill-bg));color:var(--fg)}
      @media(max-width:640px){.simple-hero-grid{grid-template-columns:minmax(0,1fr) 104px;gap:10px;align-items:start}.simple-confidence{min-height:0;padding-top:2px;border-inline-start:0;align-self:start}.simple-confidence-ring{width:92px;height:92px}.simple-confidence-ring strong{font-size:1.35rem}.simple-confidence-word{margin-top:6px;font-size:.62rem}.simple-verdict{font-size:clamp(1.3rem,7vw,1.9rem)}.simple-window-card{grid-template-columns:1fr auto}.simple-window-badge{grid-column:1/-1;justify-self:start}}
      @media(max-width:520px){.simple-shell{padding-top:2px}.simple-hero{padding:18px;border-radius:18px}.simple-selected-day-content{padding:9px;border-radius:18px}.simple-metrics{grid-template-columns:1fr 1fr}.simple-metric:last-child{grid-column:1/-1}.simple-condition-grid{grid-template-columns:1fr}.simple-condition.return{grid-column:auto}.simple-day{min-height:112px;padding:8px}.simple-day-heading{display:block}.simple-day-calendar{display:block;margin-top:2px}.simple-entry{font-size:0}.simple-entry::after{content:'✨';font-size:1rem}}
      @media(max-width:350px){.simple-hero-grid{grid-template-columns:minmax(0,1fr) 80px;gap:7px}.simple-confidence-ring{width:74px;height:74px}.simple-confidence-ring strong{font-size:1.12rem}.simple-confidence-ring span{font-size:.58rem}.simple-confidence-word{font-size:.54rem}.simple-actions{grid-template-columns:1fr}.simple-days{gap:5px}.simple-day{min-height:108px;padding:7px 6px}.simple-day[aria-selected="true"]::after{inset-inline:8px}.simple-day-title{font-size:.76rem}.simple-day-state{font-size:.66rem}.simple-day-date{font-size:.61rem}.simple-bottom-nav{left:4px;right:4px;padding:5px}.simple-nav-action{font-size:.64rem}.simple-panel{padding:13px}.simple-selected-day-content{padding:7px}.simple-weather-grid{grid-template-columns:1fr}}
      @media(min-width:521px) and (max-width:900px){.simple-shell{max-width:680px}.simple-hero{padding:24px}}
      @media(min-width:901px){body.simple-board-mode{padding-bottom:24px}.simple-bottom-nav{position:sticky;bottom:12px;margin-top:14px}}
      @media(prefers-reduced-motion:reduce){.simple-action,.simple-day,.simple-nav-action{scroll-behavior:auto}*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
      @media(forced-colors:active){.simple-hour{border:1px solid CanvasText}.simple-hour.good{background:Highlight}.simple-hour.prudent{background:Canvas}.simple-key::before{border:1px solid CanvasText}.simple-day[aria-selected="true"]{outline:3px solid Highlight}}
    `;
    document.head.appendChild(style);
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleTimeString(lang() === 'ar' ? 'ar-TN' : lang() === 'en' ? 'en-GB' : 'fr-FR', {timeZone:TUNIS_TZ,hour:'2-digit',minute:'2-digit',hour12:false});
  }
  function dateKey(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-CA', {timeZone:TUNIS_TZ,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date)
      .reduce((result, part) => ({...result, [part.type]:part.value}), {});
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  function dayKey(offset) {
    const now = new Date();
    return dateKey(new Date(now.getTime() + offset * 86400000));
  }
  function dayLabel(key, index) {
    const c = copy();
    if (index === 0) return c.today;
    if (index === 1) return c.tomorrow;
    return new Date(`${key}T12:00:00Z`).toLocaleDateString(lang() === 'ar' ? 'ar-TN' : lang() === 'en' ? 'en-GB' : 'fr-FR', {weekday:'long',timeZone:'UTC'});
  }
  function shortDate(key) {
    return new Date(`${key}T12:00:00Z`).toLocaleDateString(
      lang() === 'ar' ? 'ar-TN' : lang() === 'en' ? 'en-GB' : 'fr-FR',
      {day:'numeric',month:'short',timeZone:'UTC'},
    );
  }
  function verdictForDay(offset = state.activeDay) {
    if (!state.verdictModule) return null;
    return state.verdictModule.navigationVerdictForDay({
      windows:state.windows,
      status:state.status,
      rules:state.rules,
      selectedDay:dayKey(offset),
      now:new Date(),
    });
  }
  function bestForDay(offset = state.activeDay) {
    return verdictForDay(offset)?.row || null;
  }
  function confidenceScore(best) {
    const raw = Number(best?.windowItem?.confidence_score ?? best?.destination?.confidence_score);
    if (Number.isFinite(raw)) return Math.max(0, Math.min(100, Math.round(raw)));
    const label = String(best?.windowItem?.confidence || best?.destination?.confidence || '').toLowerCase();
    return label === 'high' ? 86 : label === 'medium' ? 64 : label === 'low' ? 38 : 0;
  }
  function confidenceWord(score) {
    const c = copy();
    return score >= 75 ? c.confidenceHigh : score >= 50 ? c.confidenceMedium : c.confidenceLow;
  }
  function selectedDayOffset(key) {
    return [0, 1, 2].find((offset) => dayKey(offset) === key) ?? 0;
  }
  function tunisHour(value) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return -1;
    return Number(new Intl.DateTimeFormat('en-GB', {
      timeZone:TUNIS_TZ,
      hour:'2-digit',
      hourCycle:'h23',
    }).format(date));
  }
  function blockerText(blocked) {
    const diagnostics = blocked?.diagnostics || {};
    if (lang() === 'ar') return copy().conditions;
    return lang() === 'en'
      ? diagnostics.summary_en || diagnostics.first_blocker?.reason_en
      : diagnostics.summary_fr || diagnostics.first_blocker?.reason_fr;
  }
  function hasMarineDataError(data) {
    return (data?.windows || []).some((destination) => {
      const diagnostics = destination?.diagnostics || {};
      const values = [
        diagnostics.summary_fr, diagnostics.summary_en,
        diagnostics.first_blocker?.reason_fr, diagnostics.first_blocker?.reason_en,
        ...(diagnostics.first_blocker?.reasons || []),
      ].filter(Boolean).join(' ').toLowerCase();
      return /marine_error|données de vagues|wave data|houle.*indisponible/.test(values);
    });
  }
  function freshness(generatedAt) {
    const c = copy();
    const minutes = Math.max(0, Math.round((Date.now() - new Date(generatedAt).getTime()) / 60000));
    return Number.isFinite(minutes) ? `${minutes} min` : c.unavailable;
  }
  function hourlyTone(rows, key, hour) {
    const match = rows.find(({windowItem}) => {
      if (dateKey(windowItem.start) !== key) return false;
      const startHour = tunisHour(windowItem.start);
      const endHour = tunisHour(windowItem.end);
      return endHour <= startHour
        ? hour >= startHour || hour < endHour
        : hour >= startHour && hour < endHour;
    });
    if (!match) return 'blocked';
    const tripMode = String(match.windowItem.trip_mode || match.destination.trip_mode || '');
    const routeKind = String(match.windowItem.route_kind || match.destination.route_kind || '');
    if (tripMode === 'one_way_multi_day' || ['long_trip_one_way', 'offshore_one_way_beta'].includes(routeKind)) return 'travel';
    if (String(match.category || match.windowItem.category || '').toLowerCase() === 'off_hours') return 'off-hours';
    if (String(match.category || match.windowItem.category || '').toLowerCase() === 'watch') return 'watch';
    return (match.windowItem.family_tier || match.destination.family_tier) === 'prudent' ? 'prudent' : 'good';
  }
  function renderTimeline(rows, counts = {}) {
    const c = copy(); const key = dayKey(state.activeDay);
    const hours = Array.from({length:17}, (_, index) => index + 5);
    const offHoursKey = counts.offHours ? `<span class="simple-key off-hours">${esc(c.offHoursSlot)}</span>` : '';
    const watchKey = counts.watch ? `<span class="simple-key watch">${esc(c.watch)}</span>` : '';
    const travelKey = counts.longTrip ? `<span class="simple-key travel">${esc(c.longTripSlot)}</span>` : '';
    return `<section id="simple-timeline" class="simple-panel"><div class="simple-panel-head"><h2>🕒 ${esc(c.timeline)}</h2><span class="simple-panel-note">05–21 h</span></div><div class="simple-timeline" role="img" aria-label="${esc(c.timeline)} — ${esc(dayLabel(key,state.activeDay))}">${hours.map((hour) => `<span class="simple-hour ${hourlyTone(rows,key,hour)}" title="${String(hour).padStart(2,'0')}:00"></span>`).join('')}</div><div class="simple-axis"><span>05 h</span><span>13 h</span><span>21 h</span></div><div class="simple-legend"><span class="simple-key good">GO</span><span class="simple-key prudent">${esc(c.cautious)}</span>${watchKey}${offHoursKey}${travelKey}<span class="simple-key">${esc(c.noGo)}</span></div></section>`;
  }
  function seriesForWindow(best, key) {
    const hourly = state.forecast?.hourly || {}; const times = hourly.time || [];
    const start = best ? new Date(best.windowItem.start).getTime() : new Date(`${key}T05:00:00`).getTime();
    const end = best ? new Date(best.windowItem.end).getTime() : new Date(`${key}T21:00:00`).getTime();
    const indexes = times.map((value,index) => ({index,time:new Date(value).getTime()})).filter(({time}) => time >= start && time <= end).map(({index}) => index);
    const values = (name) => indexes.map((index) => hourly[name]?.[index])
      .filter((value) => value !== null && value !== undefined && value !== '')
      .map(Number).filter(Number.isFinite);
    return {
      wind:values('wind_speed_10m'), wave:values('hs'), rain:values('precipitation'),
      temperature:values('temperature_2m'), apparent:values('apparent_temperature'),
      humidity:values('relative_humidity_2m'), cloud:values('cloud_cover'), uv:values('uv_index'),
      visibility:values('visibility'),
      weatherCodes:indexes.map((index) => hourly.weather_code?.[index])
        .filter((value) => value !== null && value !== undefined && value !== '')
        .map(Number).filter(Number.isFinite),
      indexes,
    };
  }
  function trend(values) {
    if (values.length < 2) return copy().stable;
    const delta = values.at(-1) - values[0];
    const tolerance = Math.max(...values, 1) * .08;
    return Math.abs(delta) <= tolerance ? copy().stable : delta > 0 ? copy().rising : copy().falling;
  }
  function chart(values, {unit, threshold, start, end}) {
    if (!values.length) return '';
    const c = copy(); const width = 240; const height = 82; const top = 8; const bottom = 70;
    const min = Math.min(0, ...values); const max = Math.max(threshold, ...values, 1); const span = max - min || 1;
    const y = (value) => bottom - (value - min) / span * (bottom - top);
    const points = values.map((value,index) => `${values.length === 1 ? width/2 : index * width/(values.length-1)},${y(value)}`);
    const line = points.join(' '); const area = `0,${bottom} ${line} ${width},${bottom}`; const thresholdY = y(threshold);
    const label = `${c.from} ${Math.min(...values).toFixed(unit === 'm' ? 2 : 0)} ${unit} ${c.to} ${Math.max(...values).toFixed(unit === 'm' ? 2 : 0)} ${unit}, ${trend(values)}. ${c.threshold} ${threshold} ${unit}.`;
    return `<figure class="simple-chart" role="img" aria-label="${esc(label)}"><svg class="simple-spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true"><rect class="safe-zone" x="0" y="${thresholdY}" width="${width}" height="${bottom-thresholdY}"></rect><line class="grid" x1="0" y1="${top}" x2="${width}" y2="${top}"></line><line class="grid" x1="0" y1="${bottom}" x2="${width}" y2="${bottom}"></line><line class="threshold" x1="0" y1="${thresholdY}" x2="${width}" y2="${thresholdY}"></line><polygon class="area" points="${area}"></polygon><polyline class="line" points="${line}"></polyline>${points.map((point) => `<circle class="point" cx="${point.split(',')[0]}" cy="${point.split(',')[1]}" r="2.5"></circle>`).join('')}</svg><div class="simple-chart-axis"><span>${esc(start)}</span><span>${esc(end)}</span></div><figcaption class="simple-chart-threshold">${esc(c.threshold)} ${threshold} ${esc(unit)} · ${esc(trend(values))}</figcaption></figure>`;
  }
  function uvLevel(value) {
    const c = copy();
    return value >= 8 ? c.uvVeryHigh : value >= 6 ? c.uvHigh : value >= 3 ? c.uvModerate : c.uvLow;
  }
  function weatherDescription(codes) {
    const c = copy();
    if (codes.some((code) => code >= 95)) return c.storm;
    if (codes.some((code) => (code >= 51 && code <= 67) || (code >= 80 && code <= 82))) return c.showers;
    if (codes.some((code) => code === 45 || code === 48)) return c.fog;
    if (codes.some((code) => code >= 3)) return c.cloudy;
    if (codes.some((code) => code === 1 || code === 2)) return c.partlyCloudy;
    return c.clear;
  }
  function renderConditions(best) {
    const c = copy(); const data = seriesForWindow(best, dayKey(state.activeDay));
    const maxWind = data.wind.length ? Math.max(...data.wind) : null;
    const maxWave = data.wave.length ? Math.max(...data.wave) : null;
    const windLimit = Number(state.forecast?.meta?.rules?.wind?.family_max_kmh || 22);
    const waveLimit = Number(state.forecast?.meta?.rules?.sea?.family_max_hs_m || .5);
    const start = best ? formatTime(best.windowItem.start) : '05:00'; const end = best ? formatTime(best.windowItem.end) : '21:00';
    const range = (values, digits, unit) => values.length ? `${Math.min(...values).toFixed(digits)}–${Math.max(...values).toFixed(digits)} ${unit}` : '—';
    const weatherItems = [];
    const item = (icon, label, value, detail = '') => `<div class="simple-weather-item"><span class="simple-weather-label">${icon} ${esc(label)}</span><strong class="simple-weather-value">${esc(value)}</strong>${detail ? `<small class="simple-weather-detail">${esc(detail)}</small>` : ''}</div>`;
    if (data.temperature.length) {
      const feelsLike = data.apparent.length ? `${c.feelsLike} ${Math.max(...data.apparent).toFixed(0)} °C` : '';
      weatherItems.push(item('🌡️', c.temperature, range(data.temperature,0,'°C'), feelsLike));
    }
    if (data.uv.length) {
      const maxUv = Math.max(...data.uv);
      weatherItems.push(item('☀️', c.uv, maxUv.toFixed(1), uvLevel(maxUv)));
    }
    if (data.weatherCodes.length || data.cloud.length || data.humidity.length) {
      const skyDetail = [
        data.cloud.length ? `${c.cloud} ${Math.round(data.cloud.reduce((sum,value) => sum + value,0) / data.cloud.length)} %` : '',
        data.humidity.length ? `${c.humidity} ${range(data.humidity,0,'%')}` : '',
      ].filter(Boolean).join(' · ');
      weatherItems.push(item('🌤️', c.sky, weatherDescription(data.weatherCodes), skyDetail));
    }
    if (data.rain.length || data.visibility.length) {
      const rainTotal = data.rain.length ? `${data.rain.reduce((sum,value) => sum + value,0).toFixed(1)} mm` : '—';
      const visibility = data.visibility.length ? `${c.visibility} ${(Math.min(...data.visibility) / 1000).toFixed(1)} km` : '';
      weatherItems.push(item('🌧️', c.rain, rainTotal, visibility));
    }
    const weather = weatherItems.length ? `<div class="simple-weather-grid" aria-label="${esc(c.weather)}">${weatherItems.join('')}</div>` : '';
    return `<section id="simple-conditions" class="simple-panel"><div class="simple-panel-head"><h2>〽️ ${esc(c.trends)}</h2></div><div class="simple-condition-grid"><div class="simple-condition"><span class="simple-condition-label">${esc(c.wind)}</span><strong class="simple-condition-value">${maxWind === null ? '—' : `${maxWind.toFixed(0)} km/h`}<small class="simple-condition-range">${esc(range(data.wind,0,'km/h'))}</small></strong>${chart(data.wind,{unit:'km/h',threshold:windLimit,start,end})}</div><div class="simple-condition wave"><span class="simple-condition-label">${esc(c.wave)}</span><strong class="simple-condition-value">${maxWave === null ? '—' : `${maxWave.toFixed(2)} m`}<small class="simple-condition-range">${esc(range(data.wave,2,'m'))}</small></strong>${chart(data.wave,{unit:'m',threshold:waveLimit,start,end})}</div>${weather}<div class="simple-condition return"><span class="simple-condition-label">${esc(c.returnBy)}</span><strong class="simple-condition-value">${best ? formatTime(best.windowItem.end) : '—'}</strong></div></div></section>`;
  }
  function renderActivities(best) {
    const c = copy();
    const records = (state.recommendations?.recommendations || []).filter((record) => (
      best && String(best.windowItem?.category || '').toLowerCase() === 'family' &&
      String(record.category || 'family').toLowerCase() === 'family' &&
      record.dest_slug === best.destination.dest_slug &&
      record.start === best.windowItem.start && record.end === best.windowItem.end
    ));
    const activities = records.flatMap((record) => record.activities || []).sort((a,b) => Number(b.score || 0) - Number(a.score || 0)).slice(0,3);
    const content = activities.length ? activities.map((item) => {
      const label = lang() === 'en' ? item.label_en : item.label_fr;
      const why = lang() === 'en' ? item.why_en : item.why_fr;
      return `<article class="simple-activity"><span class="simple-activity-icon" aria-hidden="true">${esc(item.icon || '🌊')}</span><div><strong>${esc(label || c.activities)}</strong><small>${esc(why || c.activityNote)}</small></div><span class="simple-activity-score">${Math.round(Number(item.score || 0))}/100</span></article>`;
    }).join('') : `<div class="simple-empty">${esc(c.noActivities)}</div>`;
    return `<section id="simple-activities" class="simple-panel"><div class="simple-panel-head"><h2>🌊 ${esc(c.activities)}</h2><span class="simple-panel-note">${esc(c.activityNote)}</span></div><div class="simple-activities">${content}</div></section>`;
  }
  function renderNavigation(result) {
    const c = copy();
    const rows = result?.rows || [];
    const content = rows.length ? rows.slice(0, 5).map((row, index) => {
      const item = row.windowItem;
      const destination = row.destination;
      const tripMode = String(item.trip_mode || destination.trip_mode || '');
      const routeKind = String(item.route_kind || destination.route_kind || '');
      const longTrip = tripMode === 'one_way_multi_day' || ['long_trip_one_way', 'offshore_one_way_beta'].includes(routeKind);
      const offHours = String(row.category || item.category || '').toLowerCase() === 'off_hours';
      const watch = String(row.category || item.category || '').toLowerCase() === 'watch';
      const prudent = String(item.family_tier || destination.family_tier || '').toLowerCase() === 'prudent';
      const tone = longTrip ? 'travel' : offHours ? 'off-hours' : watch ? 'watch' : prudent ? 'prudent' : '';
      const label = longTrip ? c.longTripSlot : offHours ? c.offHoursSlot : watch ? c.review : prudent ? c.cautious : 'FAMILY GO';
      const origin = item.origin_name || '';
      const target = item.destination_name || destination.dest_name || destination.dest_slug || '—';
      const name = longTrip && origin ? `${origin} → ${target}` : target;
      const duration = Math.max(0, (new Date(item.end) - new Date(item.start)) / 3600000);
      const direction = item.direction === 'outbound' ? c.outbound : item.direction === 'return' ? c.return : '';
      const beta = item.beta || destination.beta ? c.beta : '';
      const details = [direction, beta, `${formatTime(item.start)} → ${formatTime(item.end)} · ${duration.toFixed(duration % 1 ? 1 : 0)} h`].filter(Boolean).join(' · ');
      return `<button class="simple-window-card" data-simple-action="map-window" data-simple-window-index="${index}" type="button"><span class="simple-window-badge ${tone}">${esc(label)}</span><span class="simple-window-main"><strong>${esc(name)}</strong><small>${esc(details)}</small></span><span class="simple-window-arrow" aria-hidden="true">›</span></button>`;
    }).join('') : `<div class="simple-empty">${esc(c.noWindow)}</div>`;
    return `<section id="simple-navigation" class="simple-panel"><div class="simple-panel-head"><h2>🧭 ${esc(c.windows)} <span class="simple-panel-note">(${esc(dayLabel(dayKey(state.activeDay),state.activeDay))})</span></h2><span class="simple-panel-note">${rows.length}</span></div><div class="simple-navigation">${content}</div></section>`;
  }
  function toneForState(value) {
    return {
      GO_FAMILY:'good', GO_PRUDENT:'prudent', WATCH:'watch', OFF_HOURS:'off-hours', TRAVEL_ONLY:'travel',
      STALE:'stale', NO_DATA:'unavailable', NO_GO:'blocked',
    }[value] || 'loading';
  }
  function renderDays() {
    const c = copy();
    return [0, 1, 2].map((index) => {
      const key = dayKey(index);
      const result = verdictForDay(index);
      const best = result?.row || null;
      const startHour = best ? tunisHour(best.windowItem.start) : 0;
      const duration = best ? Math.max(1, (new Date(best.windowItem.end) - new Date(best.windowItem.start)) / 3600000) : 0;
      const width = Math.min(100, Math.max(12, duration / 16 * 100));
      const offset = Math.min(88, Math.max(0, (startHour - 5) / 16 * 100));
      const tone = toneForState(result?.state);
      const label = {
        GO_FAMILY:c.good, GO_PRUDENT:c.cautious, WATCH:c.watch, OFF_HOURS:c.offHoursSlot, TRAVEL_ONLY:c.longTripSlot,
        STALE:c.unavailable, NO_DATA:c.unavailable,
      }[result?.state] || (result?.state === 'NO_GO' ? c.noGo : c.loading);
      const counts = result?.counts || {};
      const countText = `${counts.total || 0} ${c.options}`;
      const windowText = best ? `${formatTime(best.windowItem.start)}–${formatTime(best.windowItem.end)} · ${countText}` : countText;
      const selected = index === state.activeDay;
      return `<button id="simple-day-tab-${index}" class="simple-day ${tone}" data-simple-day="${index}" type="button" role="tab" aria-selected="${selected}" aria-controls="simple-selected-day-content" tabindex="${selected ? 0 : -1}"${selected ? ' aria-current="date"' : ''}><span class="simple-day-heading"><span class="simple-day-title">${esc(dayLabel(key,index))}</span><time class="simple-day-calendar" datetime="${esc(key)}">${esc(shortDate(key))}</time></span><strong class="simple-day-state">${esc(label)}</strong><span class="simple-day-date">${esc(windowText)}</span><span class="simple-day-track" aria-hidden="true"><span class="simple-day-segment" style="width:${width}%;margin-left:${best ? offset : 0}%"></span></span></button>`;
    }).join('');
  }

  function render() {
    const root = document.getElementById('simple-view');
    if (!root) return;
    const c = copy();
    const result = verdictForDay();
    const selectedTone = toneForState(result?.state);
    const best = result?.row || null;
    const presentation = {
      GO_FAMILY:{tone:'good', title:c.possible, icon:'✓', detail:''},
      GO_PRUDENT:{tone:'prudent', title:c.prudent, icon:'⚠️', detail:''},
      WATCH:{tone:'watch', title:c.watch, icon:'◐', detail:c.watchDetail},
      OFF_HOURS:{tone:'off-hours', title:c.offHours, icon:'🕒', detail:c.offHoursDetail},
      TRAVEL_ONLY:{tone:'travel', title:c.travelOnly, icon:'🧭', detail:c.travelOnlyDetail},
      STALE:{tone:'blocked', title:c.staleTitle, icon:'⚠️', detail:c.stale},
      NO_DATA:{tone:'blocked', title:c.noDataTitle, icon:'⛔', detail:c.missing},
      NO_GO:{tone:'blocked', title:c.blocked, icon:'⛔', detail:c.conditions},
    }[result?.state] || {tone:'blocked', title:c.loading, icon:'⏳', detail:''};
    const blocked = result?.blocker || result?.spot || null;
    const destination = best ? best.destination.dest_name || best.destination.dest_slug : c.conditions;
    const windowText = best ? `${formatTime(best.windowItem.start)}–${formatTime(best.windowItem.end)}` : c.noWindow;
    const confidence = best ? best.windowItem.confidence || best.destination.confidence || '—' : '—';
    const score = confidenceScore(best);
    const generatedAt = state.windows?.generated_at || state.status?.generated_at;
    const reason = blockerText(blocked) || presentation.detail || c.conditions;
    const dataState = state.loading ? `<div class="simple-data-state" role="status">⏳ ${esc(c.loading)}</div>` : state.error ? `<div class="simple-data-state error" role="alert">⚠️ ${esc(c.missing)}</div>` : result?.state === 'STALE' ? `<div class="simple-data-state stale" role="alert">⚠️ ${esc(c.stale)}</div>` : '';
    const marineState = hasMarineDataError(state.windows) ? `<div class="simple-data-state marine" role="alert">🌊 ${esc(c.marineMissing)}</div>` : '';
    root.innerHTML = `<div class="simple-shell">${dataState}${marineState}<div class="simple-day-context ${selectedTone}" data-selected-tone="${selectedTone}">
      <section id="simple-three-days" class="simple-panel simple-day-selector"><div class="simple-panel-head"><h2>📅 ${esc(c.planning)}</h2><span class="simple-panel-note">${esc(c.horizon)}</span></div><div class="simple-days" role="tablist" aria-label="${esc(c.planning)}">${renderDays()}</div></section>
      <div id="simple-selected-day-content" class="simple-selected-day-content" role="tabpanel" aria-labelledby="simple-day-tab-${state.activeDay}" tabindex="0">
      <section id="simple-decision" class="simple-hero ${presentation.tone}" data-verdict-state="${esc(result?.state || 'LOADING')}" aria-live="polite">
        <div class="simple-hero-grid"><div><h1 class="simple-verdict"><span class="simple-verdict-icon" aria-hidden="true">${presentation.icon}</span>${esc(presentation.title)}</h1>
        ${best ? `<div class="simple-destination">📍 ${esc(destination)}</div><div class="simple-window">${esc(windowText)}</div>` : ''}
        ${presentation.detail ? `<p class="simple-hero-detail">${esc(presentation.detail)}</p>` : ''}
        <div class="simple-actions">${result?.rows?.length ? `<button class="simple-action primary" data-simple-action="windows" type="button">${esc(c.viewWindows)} →</button><button class="simple-action" data-simple-action="map" type="button">🗺️ ${esc(c.map)}</button>` : `<button class="simple-action primary" aria-expanded="false" aria-controls="simple-reasons" data-simple-action="reasons" type="button">${esc(c.why)}</button><button class="simple-action" data-simple-action="map" type="button">🗺️ ${esc(c.map)}</button>`}</div>
        <div id="simple-reasons" class="simple-reasons" hidden><p>⚠️ <strong>${esc(reason)}</strong></p><small>${esc(c.details)} : ${esc(blocked?.dest_name || blocked?.dest_slug || '—')}</small></div></div>
        <aside class="simple-confidence" aria-label="${esc(c.confidence)} ${score}%"><div class="simple-confidence-ring" style="--score:${score}"><div><span>${esc(c.confidence)}</span><strong>${score}%</strong></div></div><div class="simple-confidence-word">${esc(confidenceWord(score))}</div></aside></div>
      </section>
      <section class="simple-metrics" aria-label="${esc(c.details)}"><div class="simple-metric"><span>◎ ${esc(c.confidence)}</span><strong>${esc(confidence)}</strong></div><div class="simple-metric"><span>▦ ${esc(c.options)}</span><strong>${result?.state === 'WATCH' ? result?.counts?.watch || 0 : result?.counts?.family || 0}</strong></div><div class="simple-metric"><span>● ${esc(c.updated)}</span><strong>${esc(freshness(generatedAt))}</strong></div></section>
      ${renderTimeline(result?.rows || [], result?.counts || {})}
      ${renderNavigation(result)}${renderConditions(best)}${renderActivities(best)}
      </div>
      </div>
    </div><nav class="simple-bottom-nav" aria-label="${esc(c.enter)}"><button class="simple-nav-action active" data-simple-action="decision" type="button"><span>🏠</span>${esc(c.decision)}</button><button class="simple-nav-action" data-simple-action="days" type="button"><span>📅</span>${esc(c.days)}</button><button class="simple-nav-action" data-simple-action="map" type="button"><span>🗺️</span>${esc(c.map)}</button><button class="simple-nav-action" data-simple-action="details" type="button"><span>•••</span>${esc(c.more)}</button></nav>`;
  }

  function setMode(mode, persist = true) {
    const simple = mode === SIMPLE_MODE;
    document.body.classList.toggle('simple-board-mode', simple);
    if (simple) {
      document.body.classList.remove('family-board-mode', 'expert-board-mode', 'simplified-view');
      if (persist) localStorage.setItem(MODE_KEY, SIMPLE_MODE);
      render();
      window.scrollTo({top:0,behavior:'smooth'});
    } else {
      document.body.classList.remove('simple-board-mode');
      if (persist) localStorage.setItem(MODE_KEY, 'family');
      document.getElementById('viewToggleBtn')?.click();
      if (!persist) localStorage.setItem(MODE_KEY, SIMPLE_MODE);
    }
  }
  async function loadForecast(best) {
    const slug = best?.destination?.dest_slug;
    if (!slug) { state.forecast = {}; return; }
    try {
      const response = await fetch(slug,{cache:'no-store'});
      state.forecast = response.ok ? await response.json() : {};
      if (!response.ok) state.error = 'forecast-unavailable';
    } catch { state.forecast = {}; state.error = 'forecast-network'; }
  }
  function openFamilyTab(tab) {
    const selectedKey = dayKey(state.activeDay);
    localStorage.setItem('fable_selected_day', selectedKey);
    window.FABLEDaySelection?.setSelectedDay?.(selectedKey, {persist:true, announce:false});
    setMode('family', false);
    setTimeout(() => document.querySelector(`[data-family-tab="${tab}"]`)?.click(), 120);
  }
  function openSelectedMap(best = bestForDay()) {
    const slug = best?.destination?.dest_slug;
    openFamilyTab('map');
    setTimeout(() => {
      const line = Array.from(document.querySelectorAll('.window-line')).find((item) => (
        item.dataset.slug === slug
        && item.dataset.start === best?.windowItem?.start
        && item.dataset.end === best?.windowItem?.end
        && (!best?.windowItem?.direction || item.dataset.direction === best.windowItem.direction)
      ));
      line?.click();
      if (slug) setTimeout(() => window.panToFile?.(slug), 120);
    }, 320);
  }
  async function refresh() {
    state.loading = true; state.error = ''; render();
    try {
      state.verdictModule ||= await import('./js/verdict.js');
      const [windowsResponse, statusResponse, recommendationsResponse, rulesResponse] = await Promise.all([
        fetch('windows.json',{cache:'no-store'}),
        fetch('status.json',{cache:'no-store'}),
        fetch('recommendations.json',{cache:'no-store'}).catch(() => null),
        fetch('rules.normalized.json',{cache:'no-store'}).catch(() => null),
      ]);
      state.windows = windowsResponse.ok ? await windowsResponse.json() : null;
      state.status = statusResponse.ok ? await statusResponse.json() : null;
      state.recommendations = recommendationsResponse?.ok ? await recommendationsResponse.json() : {};
      state.rules = rulesResponse?.ok ? await rulesResponse.json() : {};
      if (!windowsResponse.ok || !statusResponse.ok) state.error = 'published-data-unavailable';
      await loadForecast(bestForDay());
    } catch { state.windows = null; state.status = null; state.forecast = {}; state.recommendations = {}; state.rules = {}; state.error = 'network'; }
    state.loading = false;
    render();
  }
  function build() {
    installStyles();
    const headerTools = document.querySelector('.hdr-tools');
    const dashboard = document.getElementById('dashboard-content');
    if (!headerTools || !dashboard) return;
    if (!document.getElementById('simpleViewBtn')) {
      const button = document.createElement('button');
      button.id = 'simpleViewBtn'; button.type = 'button'; button.className = 'btn simple-entry';
      button.textContent = `✨ ${copy().trySimple}`;
      button.addEventListener('click', () => setMode(SIMPLE_MODE));
      headerTools.insertBefore(button, document.getElementById('viewToggleBtn'));
      document.dispatchEvent(new CustomEvent('fable:simple-view-ready'));
    }
    if (!document.getElementById('simple-view')) {
      const view = document.createElement('main'); view.id = 'simple-view';
      dashboard.insertAdjacentElement('beforebegin', view);
      view.addEventListener('click', (event) => {
        const action = event.target.closest('[data-simple-action]')?.dataset.simpleAction;
        if (action === 'reasons') {
          const panel = document.getElementById('simple-reasons'); const button = event.target.closest('button');
          panel.hidden = !panel.hidden; button.setAttribute('aria-expanded', String(!panel.hidden)); button.textContent = panel.hidden ? copy().why : copy().hide;
        }
        if (action === 'windows') document.getElementById('simple-navigation')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (action === 'details') document.getElementById('simple-conditions')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (action === 'map') openSelectedMap();
        if (action === 'map-window') {
          const index = Number(event.target.closest('[data-simple-window-index]')?.dataset.simpleWindowIndex);
          const row = verdictForDay()?.rows?.[index] || null;
          openSelectedMap(row);
        }
        if (action === 'days') document.getElementById('simple-three-days')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (action === 'decision') document.getElementById('simple-decision')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (['decision', 'days', 'details'].includes(action)) {
          view.querySelectorAll('.simple-nav-action').forEach((button) => button.classList.toggle('active', button.dataset.simpleAction === action));
        }
        const dayButton = event.target.closest('[data-simple-day]');
        const day = dayButton?.dataset.simpleDay;
        if (day !== undefined) {
          state.activeDay = Number(day);
          const selectedKey = dayKey(state.activeDay);
          localStorage.setItem('fable_selected_day', selectedKey);
          window.FABLEDaySelection?.setSelectedDay?.(selectedKey, {persist:true, announce:true});
          state.loading = true; render();
          loadForecast(bestForDay()).finally(() => {
            state.loading = false; render();
            document.querySelector(`[data-simple-day="${day}"]`)?.focus();
          });
        }
      });
      view.addEventListener('keydown', (event) => {
        const tab = event.target.closest('[data-simple-day][role="tab"]');
        if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const current = Number(tab.dataset.simpleDay);
        const rtl = document.documentElement.dir === 'rtl';
        const step = event.key === 'ArrowRight' ? (rtl ? -1 : 1) : (rtl ? 1 : -1);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (current + step + 3) % 3;
        view.querySelector(`[data-simple-day="${next}"]`)?.click();
      });
    }
    state.activeDay = selectedDayOffset(localStorage.getItem('fable_selected_day') || dayKey(0));
    refresh();
    let savedMode = localStorage.getItem(MODE_KEY);
    if (!localStorage.getItem(SIMPLE_DEFAULT_KEY)) {
      localStorage.setItem(SIMPLE_DEFAULT_KEY, '1');
      localStorage.setItem(MODE_KEY, SIMPLE_MODE);
      savedMode = SIMPLE_MODE;
    }
    if (!savedMode || savedMode === SIMPLE_MODE) setTimeout(() => setMode(SIMPLE_MODE, false), 0);
    document.addEventListener('fable:dashboard-updated', refresh);
    const updateLanguage = () => setTimeout(() => { document.getElementById('simpleViewBtn').textContent = `✨ ${copy().trySimple}`; render(); }, 0);
    document.getElementById('langToggle')?.addEventListener('click', updateLanguage);
    window.addEventListener('fable:languagechange', updateLanguage);
    window.addEventListener('fable:day-selected', (event) => {
      const offset = selectedDayOffset(event.detail?.dateKey || '');
      if (offset === state.activeDay) return;
      state.activeDay = offset;
      state.loading = true;
      render();
      loadForecast(bestForDay()).finally(() => { state.loading = false; render(); });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build, {once:true}); else build();
})();
