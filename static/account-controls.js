document.querySelectorAll('input[type="password"]').forEach(input => {
  const wrapper = document.createElement('div');
  wrapper.className = 'password-input';
  input.parentNode.insertBefore(wrapper, input);
  wrapper.appendChild(input);

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'password-toggle';
  toggle.setAttribute('aria-controls', input.id);
  toggle.setAttribute('aria-label', 'Show password');
  toggle.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.75"/></svg>';
  toggle.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    toggle.classList.toggle('is-visible', show);
    toggle.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} password`);
  });
  wrapper.appendChild(toggle);
});

document.querySelectorAll('.back-button').forEach(button => {
  button.addEventListener('click', () => {
    if (history.length > 1) history.back();
    else location.replace('/dashboard/');
  });
});

const AUTH_TRANSITION_KEY = 'brio-auth-transition';

// Authentication pages are deliberate history boundaries. A same-document guard
// absorbs Back/Forward without revisiting a credential POST or exposing an earlier
// signed-in page. Browser chrome cannot be disabled, so keeping the current safe URL
// is the standards-compliant equivalent.
if (document.body.classList.contains('auth-history-boundary')) {
  const safeUrl = window.location.href;
  const guardState = { brioAuthBoundary: true };
  history.replaceState(guardState, '', safeUrl);
  history.pushState(guardState, '', safeUrl);
  window.addEventListener('popstate', () => {
    history.pushState(guardState, '', safeUrl);
  });
  sessionStorage.removeItem(AUTH_TRANSITION_KEY);
}

document.querySelectorAll('[data-auth-entry]').forEach(form => {
  form.addEventListener('submit', () => {
    sessionStorage.setItem(AUTH_TRANSITION_KEY, 'sign-in');
  });
});
document.querySelectorAll('[data-auth-exit]').forEach(form => {
  form.addEventListener('submit', () => {
    sessionStorage.setItem(AUTH_TRANSITION_KEY, 'sign-out');
  });
});

// After a successful sign-in, absorb the single navigation that would otherwise
// reveal the credential page. Subsequent in-workspace history remains untouched.
if (document.body.classList.contains('workspace-page')
    && sessionStorage.getItem(AUTH_TRANSITION_KEY) === 'sign-in') {
  sessionStorage.removeItem(AUTH_TRANSITION_KEY);
  const workspaceUrl = window.location.href;
  const workspaceGuard = { brioSignedInBoundary: true };
  history.replaceState(workspaceGuard, '', workspaceUrl);
  history.pushState(workspaceGuard, '', workspaceUrl);
  window.addEventListener('popstate', () => {
    history.pushState(workspaceGuard, '', workspaceUrl);
  }, { once: true });
}
window.addEventListener('pageshow', event => {
  if (event.persisted) location.reload();
});
