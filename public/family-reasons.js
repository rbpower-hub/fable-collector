/* FABLE family reasons — friendly copy layered over expert diagnostics. */
(function () {
  let formatter = null;
  let scheduled = false;

  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';

  async function ensureFormatter() {
    formatter ||= await import('./js/reasons-i18n.js');
    return formatter;
  }

  function rawReason(line) {
    const reason = line.querySelector('.reason');
    return String(line.dataset.rawReason || line.getAttribute('title') || reason?.textContent || '').trim();
  }

  function applyReasonLine(line) {
    const original = line.querySelector('.reason:not(.friendly-reason)');
    if (!original) return;
    const raw = rawReason(line);
    if (!raw) return;
    line.dataset.rawReason = raw;
    line.title = raw;
    original.classList.add('expert-only');
    let friendly = line.querySelector('.friendly-reason');
    if (!friendly) {
      friendly = document.createElement('div');
      friendly.className = 'reason friendly-reason family-only';
      original.insertAdjacentElement('afterend', friendly);
    }
    const text = formatter.friendlyReason(raw, language());
    if (friendly.textContent !== text) friendly.textContent = text;
  }

  function applyTooltip() {
    const tooltip = document.getElementById('tooltip');
    if (!tooltip || getComputedStyle(tooltip).display === 'none') return;
    const familyRow = Array.from(tooltip.querySelectorAll('.row')).find((row) => /^\s*Family\s*:/i.test(row.textContent || ''));
    if (!familyRow) return;
    const raw = String(familyRow.dataset.rawReason || familyRow.textContent.replace(/^\s*Family\s*:\s*/i, '')).trim();
    familyRow.dataset.rawReason = raw;
    familyRow.title = raw;
    if (document.body.classList.contains('family-board-mode')) {
      familyRow.textContent = `Family: ${formatter.friendlyReason(raw, language())}`;
    }
  }

  function applyVerdict() {
    const hero = document.getElementById('family-verdict-hero');
    if (!hero || hero.dataset.state !== 'NO_GO') return;
    const detail = hero.querySelector('.verdict-detail');
    if (!detail) return;
    const raw = String(detail.dataset.rawReason || detail.textContent || '').trim();
    if (!raw) return;
    detail.dataset.rawReason = raw;
    detail.title = raw;
    const text = formatter.friendlyReason(raw, language());
    if (detail.textContent !== text) detail.textContent = text;
  }

  function apply() {
    document.querySelectorAll('#reasons .line').forEach(applyReasonLine);
    applyTooltip();
    applyVerdict();
  }

  function scheduleApply() {
    if (scheduled || !formatter) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      apply();
    });
  }

  async function start() {
    formatter = await ensureFormatter();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {subtree: true, childList: true});
    document.getElementById('langToggle')?.addEventListener('click', () => setTimeout(apply, 0));
    apply();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
