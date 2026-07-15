/* Reload once when leaving Arabic so the native FR/EN renderer starts cleanly. */
(function () {
  let leavingArabic = false;
  document.addEventListener('pointerdown', (event) => {
    const target = event.target.closest('#langToggle [data-lang]');
    leavingArabic = localStorage.getItem('lang') === 'ar' && ['fr', 'en'].includes(target?.dataset.lang);
  }, true);
  document.addEventListener('click', (event) => {
    const target = event.target.closest('#langToggle [data-lang]');
    if (leavingArabic && target) setTimeout(() => window.location.reload(), 30);
    leavingArabic = false;
  }, true);
})();
