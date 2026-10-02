(() => {
  const statusNodes = [...document.querySelectorAll('[data-availability-status]')];
  if (!statusNodes.length) return;

  const endpoint = statusNodes[0].dataset.availabilityEndpoint;
  let refreshing = false;

  const render = state => {
    statusNodes.forEach(node => {
      node.classList.toggle('is-available', state.status === 'available');
      node.classList.toggle('is-unavailable', state.status === 'unavailable');
      node.textContent = `${state.icon} ${state.summary}`;
    });
    document.querySelectorAll('[data-active-project-count]').forEach(node => {
      node.textContent = String(state.active_count);
    });
  };

  const refresh = async () => {
    if (refreshing || document.hidden) return;
    refreshing = true;
    try {
      const response = await fetch(endpoint, {
        credentials: 'same-origin',
        headers: {'Accept': 'application/json'},
        cache: 'no-store',
      });
      if (response.ok) render(await response.json());
    } finally {
      refreshing = false;
    }
  };

  window.setInterval(refresh, 5000);
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('focus', refresh);
  refresh();
})();
