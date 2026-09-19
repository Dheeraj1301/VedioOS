document.querySelectorAll('input[type="password"]').forEach(input => {
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'password-toggle';
  toggle.setAttribute('aria-controls', input.id);
  toggle.setAttribute('aria-label', 'Show password');
  toggle.textContent = 'Show';
  toggle.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    toggle.textContent = show ? 'Hide' : 'Show';
    toggle.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} password`);
  });
  input.insertAdjacentElement('afterend', toggle);
});

document.querySelectorAll('.back-button').forEach(button => {
  button.addEventListener('click', () => {
    if (history.length > 1 && document.referrer.startsWith(location.origin)) history.back();
    else location.assign('/dashboard/');
  });
});
