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
    if (history.length > 1 && document.referrer.startsWith(location.origin)) history.back();
    else location.assign('/dashboard/');
  });
});
