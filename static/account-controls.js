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

(() => {
  const dialog = document.querySelector('[data-policy-dialog]');
  const checkbox = dialog?.querySelector('[data-policy-checkbox]');
  const button = dialog?.querySelector('[data-policy-continue]');
  const accepted = document.querySelector('[data-policy-accepted]');
  if (!dialog || !checkbox || !button || !accepted) return;
  checkbox.addEventListener('change', () => { button.disabled = !checkbox.checked; });
  button.addEventListener('click', () => {
    if (!checkbox.checked) return;
    accepted.value = 'yes';
    dialog.remove();
    document.querySelector('#client-registration-form input:not([type=hidden])')?.focus();
  });
})();

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

// After a successful sign-in, the first workspace entry becomes a boundary that Back
// never crosses, so the credential page is not revisited. The marker lives in the
// history entry, so the boundary still holds after visiting other workspace pages.
if (document.body.classList.contains('workspace-page')) {
  const workspaceGuard = { brioSignedInBoundary: true };
  if (sessionStorage.getItem(AUTH_TRANSITION_KEY) === 'sign-in') {
    sessionStorage.removeItem(AUTH_TRANSITION_KEY);
    history.replaceState(workspaceGuard, '', window.location.href);
    history.pushState(workspaceGuard, '', window.location.href);
  }
  if (history.state?.brioSignedInBoundary) {
    window.addEventListener('popstate', event => {
      if (event.state?.brioSignedInBoundary) history.pushState(workspaceGuard, '', window.location.href);
    });
  }
}
window.addEventListener('pageshow', event => {
  if (event.persisted) location.reload();
});
