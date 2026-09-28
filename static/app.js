/* Original bytes go directly to object storage. No media transformation. */
const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || decodeURIComponent(document.cookie.split('; ').find(x => x.startsWith('csrftoken='))?.split('=')[1] || '');
async function postJSON(url, data = {}) {
  const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify(data)});
  const body = await response.json().catch(() => ({error: 'The request could not be completed. Please try again.'}));
  if (!response.ok) throw new Error(body.error || 'Request failed.');
  return body;
}
function announce(status, message, isError = false) {
  status.setAttribute('role', isError ? 'alert' : 'status');
  status.setAttribute('aria-live', isError ? 'assertive' : 'polite');
  status.style.color = isError ? '#a1352d' : '';
  status.textContent = message;
}
function uploadOriginal(permission, file, progress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(permission.method, permission.url);
    Object.entries(permission.headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = event => {if (event.lengthComputable) progress.value = Math.round(event.loaded / event.total * 100);};
    xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error('Storage rejected the upload. Please retry with a new upload permission.'));
    xhr.onerror = () => reject(new Error('Upload connection interrupted. Please try again.'));
    xhr.onabort = () => reject(new Error('Upload cancelled.'));
    xhr.send(file);
  });
}
document.querySelectorAll('.upload-form').forEach(uploadForm => {
  const input = uploadForm.querySelector('.upload-files');
  const status = uploadForm.querySelector('.upload-status');
  const maxFiles = Number(uploadForm.dataset.maxFiles || 0);
  const existingFiles = Number(uploadForm.dataset.existingFiles || 0);
  const exceedsFileLimit = () => maxFiles && existingFiles + input.files.length > maxFiles;
  input.addEventListener('change', () => {
    if (exceedsFileLimit()) announce(status, `Maximum ${maxFiles} inspiration uploads.`, true);
    else if (status.getAttribute('role') === 'alert') announce(status, '');
  });
  uploadForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (exceedsFileLimit()) {
      announce(status, `Maximum ${maxFiles} inspiration uploads.`, true);
      return;
    }
    const button = uploadForm.querySelector('button');
    const progress = uploadForm.querySelector('.upload-progress');
    const files = [...input.files];
    const category = uploadForm.dataset.fixedCategory || uploadForm.querySelector('[name="category"]').value;
    button.disabled = true;
    try {
      for (const file of files) {
        announce(status, `Checking original: ${file.name}`);
        // Incremental hashing keeps memory bounded for large video files.
        const sha256 = await window.hashOriginal(file);
        const result = await postJSON(`/api/projects/${uploadForm.dataset.projectId}/uploads/`, {filename: file.name, size_bytes: file.size, content_type: file.type || 'application/octet-stream', category, sha256});
        progress.hidden = false; progress.value = 0;
        announce(status, `Uploading ${file.name}…`);
        await uploadOriginal(result.upload, file, progress);
        announce(status, `Verifying ${file.name}…`);
        await postJSON(`/api/files/${result.file_id}/complete/`);
      }
      announce(status, 'Originals uploaded and verified.');
      window.location.reload();
    } catch (error) { announce(status, error.message, true); }
    finally { button.disabled = false; }
  });
});
document.querySelectorAll('.download-button').forEach(button => button.addEventListener('click', async () => {
  const status = document.getElementById('download-status');
  button.disabled = true;
  try {
    announce(status, 'Preparing private download…');
    const result = await postJSON(`/api/files/${button.dataset.fileId}/download/`);
    const link = document.createElement('a'); link.href = result.url; link.rel = 'noreferrer'; link.download = ''; document.body.appendChild(link); link.click(); link.remove();
    announce(status, 'Download started. Your original quality is preserved.');
  } catch (error) {announce(status, error.message, true);}
  finally {button.disabled = false;}
}));

const newOrderForm = document.querySelector('[data-new-order-form]');
if (newOrderForm) {
  const customFields = newOrderForm.querySelector('[data-custom-fields]');
  const wordingDirection = newOrderForm.querySelector('[data-wording-direction]');
  const fontName = newOrderForm.querySelector('[data-font-name]');
  const wordingCheckbox = newOrderForm.querySelector('#id_wants_wording');
  const fontSelection = newOrderForm.querySelector('#id_wording_direction');
  const songChoice = newOrderForm.querySelector('#id_song_choice');
  const songDetails = newOrderForm.querySelector('[data-song-details]');
  const estimate = newOrderForm.querySelector('#custom-estimate');
  let estimateRequest = 0;
  [...newOrderForm.querySelectorAll('[name="order_choice"]')]
    .find(field => field.value === newOrderForm.dataset.selectedChoice)?.click();
  const updateOrderFields = () => {
    const custom = newOrderForm.querySelector('[name="order_choice"]:checked')?.value === 'custom';
    customFields.hidden = !custom;
    customFields.querySelectorAll('input, select').forEach(field => field.disabled = !custom);
    const wording = custom && wordingCheckbox.checked;
    wordingDirection.hidden = !wording;
    wordingDirection.querySelectorAll('select').forEach(field => field.disabled = !wording);
    const ownFont = wording && fontSelection.value === 'own_font';
    fontName.hidden = !ownFont;
    fontName.querySelectorAll('input').forEach(field => field.disabled = !ownFont);
    const providesSong = ['provide', 'both'].includes(songChoice.value);
    songDetails.hidden = !providesSong;
    songDetails.querySelectorAll('textarea, input').forEach(field => field.disabled = !providesSong);
    if (custom) updateCustomEstimate();
  };
  const updateCustomEstimate = async () => {
    const requestNumber = ++estimateRequest;
    const duration = newOrderForm.querySelector('#id_reel_duration').value;
    if (!duration) {
      announce(estimate, 'Price estimate: choose a duration to calculate the configured amount.');
      return;
    }
    announce(estimate, 'Calculating the configured price…');
    try {
      const result = await postJSON('/api/custom-estimate/', {
        colour_grading: newOrderForm.querySelector('#id_colour_grading').checked,
        quality_enhancement: newOrderForm.querySelector('#id_quality_enhancement').checked,
        reel_duration: duration,
        wants_wording: wordingCheckbox.checked,
        wording_direction: wordingCheckbox.checked ? newOrderForm.querySelector('#id_wording_direction').value : '',
      });
      if (requestNumber !== estimateRequest) return;
      const breakdown = result.items.map(item => `${item.name}: ${item.display_amount}`).join(' · ');
      announce(estimate, `Configured estimate: ${result.display_total}. ${breakdown}`);
    } catch (error) {
      if (requestNumber === estimateRequest) announce(estimate, `Estimate unavailable: ${error.message}`);
    }
  };
  newOrderForm.addEventListener('change', updateOrderFields);
  const inspirationBox = newOrderForm.querySelector('.inspiration-upload-box');
  const inspirationInput = newOrderForm.querySelector('.brief-inspiration-files');
  const inspirationStatus = newOrderForm.querySelector('.brief-inspiration-status');
  const existingInspirationFiles = Number(inspirationBox.dataset.existingFiles || 0);
  const exceedsInspirationLimit = () => existingInspirationFiles + inspirationInput.files.length > 3;
  inspirationInput.addEventListener('change', () => {
    if (exceedsInspirationLimit()) announce(inspirationStatus, 'Max 3 uploads.', true);
    else if (inspirationStatus.getAttribute('role') === 'alert') announce(inspirationStatus, '');
  });
  newOrderForm.addEventListener('submit', async event => {
    const clipInput = newOrderForm.querySelector('.brief-upload-files');
    const clipFiles = [...clipInput.files];
    const inspirationFiles = [...inspirationInput.files];
    if (exceedsInspirationLimit()) {
      event.preventDefault();
      announce(inspirationStatus, 'Max 3 uploads.', true);
      return;
    }
    if (!clipFiles.length && !inspirationFiles.length) return;
    event.preventDefault();
    const button = newOrderForm.querySelector('[type="submit"]');
    const clipProgress = newOrderForm.querySelector('.brief-upload-progress');
    const clipStatus = newOrderForm.querySelector('.brief-upload-status');
    const inspirationProgress = newOrderForm.querySelector('.brief-inspiration-progress');
    button.disabled = true;
    try {
      announce(clipFiles.length ? clipStatus : inspirationStatus, 'Saving your creative brief…');
      const formData = new FormData(newOrderForm);
      formData.delete('clips');
      formData.delete('inspiration_files');
      const response = await fetch(newOrderForm.action || window.location.href, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: formData,
      });
      if (!response.ok) throw new Error('The creative brief could not be saved. Please try again.');
      if (!response.redirected) {
        document.open(); document.write(await response.text()); document.close();
        return;
      }
      const projectMatch = new URL(response.url).pathname.match(/^\/client\/projects\/([0-9a-f-]+)\/$/i);
      if (!projectMatch) throw new Error('The saved project could not be identified. Please upload your files from the project page.');
      const uploadFiles = async (files, category, progress, status) => {
        for (const file of files) {
          announce(status, `Checking original: ${file.name}`);
          const sha256 = await window.hashOriginal(file);
          const result = await postJSON(`/api/projects/${projectMatch[1]}/uploads/`, {
            filename: file.name, size_bytes: file.size,
            content_type: file.type || 'application/octet-stream', category, sha256,
          });
          progress.hidden = false; progress.value = 0;
          announce(status, `Uploading ${file.name}…`);
          await uploadOriginal(result.upload, file, progress);
          announce(status, `Verifying ${file.name}…`);
          await postJSON(`/api/files/${result.file_id}/complete/`);
        }
      };
      await uploadFiles(clipFiles, 'source', clipProgress, clipStatus);
      await uploadFiles(inspirationFiles, 'reference', inspirationProgress, inspirationStatus);
      window.location.assign(response.url);
    } catch (error) {
      announce(clipFiles.length ? clipStatus : inspirationStatus, error.message, true);
      button.disabled = false;
    }
  });
  updateOrderFields();
}
