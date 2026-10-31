 const btn = document.getElementById('userMenuBtn');
  const panel = document.getElementById('userMenuPanel');

  function closeMenu() {
    panel.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
  }

  if (btn && panel) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      panel.hidden = !panel.hidden;
      btn.setAttribute('aria-expanded', String(!panel.hidden));
    });
    document.addEventListener('click', function (e) {
      if (!panel.contains(e.target)) closeMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeMenu();
    });
  }