/* Original bytes go directly to object storage. No media transformation. */
const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || decodeURIComponent(document.cookie.split('; ').find(x => x.startsWith('csrftoken='))?.split('=')[1] || '');
async function postJSON(url, data = {}) {
  const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify(data)});
  const body = await response.json().catch(() => ({error: 'The request could not be completed. Please try again.'}));
  if (!response.ok) throw new Error(body.error || 'Request failed.');
  return body;
}
async function getJSON(url) {
  const response = await fetch(url, {credentials: 'same-origin'});
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
        const completed = await postJSON(`/api/files/${result.file_id}/complete/`);
        if (completed.available_to_client) announce(status, `${file.name} saved as version ${completed.version} and shared with the client.`);
      }
      announce(status, category === 'draft' || category === 'final' ? 'Deliverables uploaded, verified, and shared with the client.' : 'Originals uploaded and verified.');
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

const editorSearchForm = document.querySelector('[data-editor-search-form]');
if (editorSearchForm) {
  const editorSearch = editorSearchForm.querySelector('[data-editor-search]');
  const editorSort = editorSearchForm.querySelector('[data-editor-sort]');
  let editorSearchTimer;
  editorSearch.addEventListener('input', () => {
    window.clearTimeout(editorSearchTimer);
    editorSearchTimer = window.setTimeout(() => editorSearchForm.submit(), 250);
  });
  editorSearchForm.querySelectorAll('[data-editor-sort-choice]').forEach(choice => {
    choice.addEventListener('change', () => {
      editorSort.value = choice.value;
      editorSearchForm.submit();
    });
  });
}

const newOrderForm = document.querySelector('[data-new-order-form]');
if (newOrderForm) {
  const customFields = newOrderForm.querySelector('[data-custom-fields]');
  const briefFields = newOrderForm.querySelector('[data-brief-fields]');
  const submitRow = newOrderForm.querySelector('[data-submit-row]');
  const submitButton = submitRow.querySelector('[type="submit"]');
  const submitStatus = submitRow.querySelector('.form-submit-status');
  const wordingDirection = newOrderForm.querySelector('[data-wording-direction]');
  const fontName = newOrderForm.querySelector('[data-font-name]');
  const fontInspiration = newOrderForm.querySelector('[data-font-inspiration]');
  const fontInspirationInput = newOrderForm.querySelector('.brief-font-inspiration-files');
  const fontInspirationStatus = newOrderForm.querySelector('.brief-font-inspiration-status');
  const wordingCheckbox = newOrderForm.querySelector('#id_wants_wording');
  const fontSelection = newOrderForm.querySelector('#id_wording_direction');
  const songChoice = newOrderForm.querySelector('#id_song_choice');
  const songDetails = newOrderForm.querySelector('[data-song-details]');
  const estimate = newOrderForm.querySelector('#custom-estimate');
  const pricingPeriodFields = [...newOrderForm.querySelectorAll('[name="pricing_period"]')];
  const pricingPeriodLabels = {per_reel: '/reel', monthly: '/month', yearly: '/year'};
  let estimateRequest = 0;
  const updatePlanPricing = () => {
    const period = pricingPeriodFields.find(field => field.checked)?.value || 'per_reel';
    const dataKey = period === 'per_reel' ? 'pricePerReel' : `price${period[0].toUpperCase()}${period.slice(1)}`;
    newOrderForm.querySelectorAll('[data-plan-card]').forEach(card => {
      const price = card.dataset[dataKey] || '';
      const available = card.dataset.planActive === 'true' && Boolean(price);
      const input = card.querySelector('[name="order_choice"]');
      card.classList.toggle('unavailable', !available);
      card.setAttribute('aria-disabled', String(!available));
      input.disabled = !available;
      if (!available && input.checked) input.checked = false;
      card.querySelector('[data-plan-price]').textContent = price || 'Coming soon';
      card.querySelector('[data-plan-period-label]').textContent = price ? pricingPeriodLabels[period] : '';
    });
  };
  updatePlanPricing();
  [...newOrderForm.querySelectorAll('[name="order_choice"]')]
    .find(field => field.value === newOrderForm.dataset.selectedChoice)?.click();
  const updateOrderFields = () => {
    const selectedChoice = newOrderForm.querySelector('[name="order_choice"]:checked')?.value || '';
    const custom = selectedChoice === 'custom';
    customFields.hidden = !custom;
    customFields.classList.toggle('is-hidden', !custom);
    customFields.querySelectorAll('input, select').forEach(field => field.disabled = !custom);
    briefFields.hidden = !custom;
    briefFields.classList.toggle('is-hidden', !custom);
    briefFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = !custom);
    submitRow.hidden = !selectedChoice;
    submitRow.classList.toggle('is-hidden', !selectedChoice);
    submitButton.disabled = !selectedChoice;
    const wording = custom && wordingCheckbox.checked;
    wordingDirection.hidden = !wording;
    wordingDirection.querySelectorAll('select').forEach(field => field.disabled = !wording);
    const ownFont = wording && fontSelection.value === 'own_font';
    fontName.hidden = !ownFont;
    fontName.querySelectorAll('input').forEach(field => field.disabled = !ownFont);
    const uploadsFontInspiration = wording && fontSelection.value === 'font_inspiration';
    fontInspiration.hidden = !uploadsFontInspiration;
    fontInspirationInput.disabled = !uploadsFontInspiration;
    if (!uploadsFontInspiration) {
      fontInspirationInput.value = '';
      announce(fontInspirationStatus, '');
    }
    const providesSong = ['provide', 'both'].includes(songChoice.value);
    songDetails.hidden = !providesSong;
    songDetails.querySelectorAll('textarea, input').forEach(field => field.disabled = !providesSong);
    if (custom) updateCustomEstimate();
  };
  const updateCustomEstimate = async () => {
    const requestNumber = ++estimateRequest;
    const duration = newOrderForm.querySelector('#id_reel_duration').value;
    if (!duration) {
      announce(estimate, 'Estimated price: choose a duration to calculate the configured amount.');
      return;
    }
    announce(estimate, 'Calculating the configured price…');
    try {
      const result = await postJSON('/api/quote/', {
        colour_grading: newOrderForm.querySelector('#id_colour_grading').checked,
        quality_enhancement: newOrderForm.querySelector('#id_quality_enhancement').checked,
        reel_duration: duration,
        wants_wording: wordingCheckbox.checked,
        wording_direction: wordingCheckbox.checked ? newOrderForm.querySelector('#id_wording_direction').value : '',
        song_choice: songChoice.value,
        overlays: newOrderForm.querySelector('#id_overlays').checked,
        beat_sync: newOrderForm.querySelector('#id_beat_sync').checked,
      });
      if (requestNumber !== estimateRequest) return;
      const breakdown = (result.breakdown || result.items)
        .map(item => `${item.name}: ${item.display_amount}`)
        .join(' · ');
      announce(estimate, `Estimated price: ${result.display_total}. ${breakdown}. Final pricing is confirmed before payment.`);
    } catch (error) {
      if (requestNumber === estimateRequest) announce(estimate, `Estimate unavailable: ${error.message}`);
    }
  };
  newOrderForm.addEventListener('change', event => {
    if (event.target.name === 'pricing_period') updatePlanPricing();
    updateOrderFields();
  });
  const inspirationBox = newOrderForm.querySelector('.inspiration-upload-box');
  const clipInput = newOrderForm.querySelector('.brief-upload-files');
  const clipStatus = newOrderForm.querySelector('.brief-upload-status');
  const inspirationInput = newOrderForm.querySelector('.brief-inspiration-files');
  const inspirationStatus = newOrderForm.querySelector('.brief-inspiration-status');
  const existingInspirationFiles = Number(inspirationBox.dataset.existingFiles || 0);
  const inspirationUploadLimit = 3;
  const uploadsEnabled = newOrderForm.dataset.uploadEnabled === 'true';
  const fileKey = file => `${file.name}:${file.size}:${file.lastModified}:${file.type}`;
  const syncFileInput = (input, files) => {
    try {
      const acceptedFiles = new DataTransfer();
      files.forEach(file => acceptedFiles.items.add(file));
      input.files = acceptedFiles.files;
    } catch (_error) {
      // Submission uses the internal queue when FileList replacement is unavailable.
      input.value = '';
    }
  };
  let selectedClipFiles = [];
  let selectedInspirationFiles = [];
  clipInput.addEventListener('change', () => {
    const knownFiles = new Set(selectedClipFiles.map(fileKey));
    for (const file of clipInput.files) {
      const key = fileKey(file);
      if (!knownFiles.has(key)) {
        selectedClipFiles.push(file);
        knownFiles.add(key);
      }
    }
    syncFileInput(clipInput, selectedClipFiles);
    if (!uploadsEnabled && selectedClipFiles.length) {
      announce(clipStatus, 'File uploads are temporarily unavailable. Your project has not been saved.', true);
    } else if (selectedClipFiles.length) {
      announce(clipStatus, `${selectedClipFiles.length} clip${selectedClipFiles.length === 1 ? '' : 's'} selected.`);
    }
  });
  inspirationInput.addEventListener('change', () => {
    const incomingFiles = [...inspirationInput.files];
    let remainingSlots = Math.max(
      0,
      inspirationUploadLimit - existingInspirationFiles - selectedInspirationFiles.length,
    );
    let rejected = false;
    for (const file of incomingFiles) {
      if (remainingSlots === 0) {
        rejected = true;
        continue;
      }
      selectedInspirationFiles.push(file);
      remainingSlots -= 1;
    }
    syncFileInput(inspirationInput, selectedInspirationFiles);
    if (!uploadsEnabled && selectedInspirationFiles.length) {
      announce(inspirationStatus, 'File uploads are temporarily unavailable. Your project has not been saved.', true);
    } else if (rejected) {
      announce(inspirationStatus, 'Max uploads: 3', true);
    } else if (selectedInspirationFiles.length) {
      announce(
        inspirationStatus,
        `${selectedInspirationFiles.length} inspiration file${selectedInspirationFiles.length === 1 ? '' : 's'} selected.`,
      );
    } else if (inspirationStatus.getAttribute('role') === 'alert') {
      announce(inspirationStatus, '');
    }
  });
  const fontImageExtensions = ['.avif', '.bmp', '.gif', '.heic', '.heif', '.jpeg', '.jpg', '.png', '.tif', '.tiff', '.webp'];
  const fontInspirationError = () => {
    const file = fontInspirationInput.files[0];
    if (!file) return '';
    const extension = file.name.includes('.') ? `.${file.name.split('.').pop().toLowerCase()}` : '';
    if (['.doc', '.docx', '.pdf'].includes(extension)) return 'Word documents and PDFs are not allowed.';
    if (!file.type.startsWith('image/') || !fontImageExtensions.includes(extension)) return 'Upload a picture file.';
    if (file.size >= 1024 * 1024) return 'The picture must be less than 1 MB.';
    return '';
  };
  fontInspirationInput.addEventListener('change', () => {
    const error = fontInspirationError();
    if (error) announce(fontInspirationStatus, error, true);
    else if (fontInspirationStatus.getAttribute('role') === 'alert') announce(fontInspirationStatus, '');
  });
  submitButton.addEventListener('click', () => {
    const invalidField = newOrderForm.querySelector(':invalid');
    if (!invalidField) return;
    const label = invalidField.labels?.[0]?.textContent?.trim() || 'the highlighted required field';
    announce(submitStatus, `Complete ${label} before saving.`, true);
  });
  newOrderForm.addEventListener('submit', async event => {
    const clipFiles = [...(selectedClipFiles.length ? selectedClipFiles : clipInput.files)];
    const inspirationFiles = [
      ...(selectedInspirationFiles.length ? selectedInspirationFiles : inspirationInput.files),
    ];
    const fontInspirationFiles = fontInspirationInput.disabled ? [] : [...fontInspirationInput.files];
    const hasUploads = clipFiles.length || inspirationFiles.length || fontInspirationFiles.length;
    if (hasUploads && !uploadsEnabled) {
      event.preventDefault();
      const activeStatus = clipFiles.length ? clipStatus : inspirationFiles.length ? inspirationStatus : fontInspirationStatus;
      announce(activeStatus, 'File uploads are temporarily unavailable. Your project has not been saved.', true);
      announce(submitStatus, 'Remove the selected files or try again when uploads are available.', true);
      return;
    }
    const fontError = fontInspirationError();
    if (fontError) {
      event.preventDefault();
      announce(fontInspirationStatus, fontError, true);
      announce(submitStatus, 'Correct the font inspiration file before saving.', true);
      return;
    }
    announce(submitStatus, 'Saving your creative brief…');
    submitButton.disabled = true;
    if (!hasUploads) return;
    event.preventDefault();
    const button = submitButton;
    const clipProgress = newOrderForm.querySelector('.brief-upload-progress');
    const inspirationProgress = newOrderForm.querySelector('.brief-inspiration-progress');
    const fontInspirationProgress = newOrderForm.querySelector('.brief-font-inspiration-progress');
    button.disabled = true;
    try {
      const activeStatus = clipFiles.length ? clipStatus : inspirationFiles.length ? inspirationStatus : fontInspirationStatus;
      announce(activeStatus, 'Saving your creative brief…');
      const formData = new FormData(newOrderForm);
      formData.delete('clips');
      formData.delete('inspiration_files');
      formData.delete('font_inspiration');
      const response = await fetch(newOrderForm.action || window.location.href, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: formData,
      });
      if (!response.ok) throw new Error('The creative brief could not be saved. Please try again.');
      if (!response.redirected) {
        document.open(); document.write(await response.text()); document.close();
        return;
      }
      const savedPath = new URL(response.url).pathname;
      const projectMatch = savedPath.match(
        /^\/client\/(?:projects|checkout)\/([0-9a-f-]+)\/$/i,
      );
      if (!projectMatch) throw new Error('The saved project could not be identified. Please upload your files from the project page.');
      const projectId = projectMatch[1];
      newOrderForm.action = `/client/projects/${projectId}/edit/`;
      window.history.replaceState({}, '', newOrderForm.action);
      const uploadedFileIds = [];
      const uploadFiles = async (files, category, progress, status, onUploaded) => {
        for (const file of files) {
          announce(status, `Checking original: ${file.name}`);
          const sha256 = await window.hashOriginal(file);
          const result = await postJSON(`/api/projects/${projectId}/uploads/`, {
            filename: file.name, size_bytes: file.size,
            content_type: file.type || 'application/octet-stream', category, sha256,
          });
          progress.hidden = false; progress.value = 0;
          announce(status, `Uploading ${file.name}…`);
          await uploadOriginal(result.upload, file, progress);
          announce(status, `Verifying ${file.name}…`);
          await postJSON(`/api/files/${result.file_id}/complete/`);
          uploadedFileIds.push(result.file_id);
          onUploaded(file);
        }
      };
      await uploadFiles(clipFiles, 'source', clipProgress, clipStatus, file => {
        selectedClipFiles = selectedClipFiles.filter(item => item !== file);
        syncFileInput(clipInput, selectedClipFiles);
      });
      await uploadFiles(inspirationFiles, 'reference', inspirationProgress, inspirationStatus, file => {
        selectedInspirationFiles = selectedInspirationFiles.filter(item => item !== file);
        syncFileInput(inspirationInput, selectedInspirationFiles);
      });
      await uploadFiles(fontInspirationFiles, 'font_reference', fontInspirationProgress, fontInspirationStatus, () => {
        fontInspirationInput.value = '';
      });
      const storedProject = await getJSON(`/api/projects/${projectId}/`);
      const storedFileIds = new Set(storedProject.files.map(file => file.id));
      if (uploadedFileIds.some(fileId => !storedFileIds.has(fileId))) {
        throw new Error('A file could not be confirmed in Project Files. Please retry before leaving this page.');
      }
      window.location.assign(response.url);
    } catch (error) {
      const activeStatus = clipFiles.length ? clipStatus : inspirationFiles.length ? inspirationStatus : fontInspirationStatus;
      announce(activeStatus, error.message, true);
      announce(submitStatus, error.message, true);
      button.disabled = false;
    }
  });
  updateOrderFields();
}

const pricingCurrency = document.querySelector('#id_currency');
const majorUnitInputs = [...document.querySelectorAll('[data-money-input]')];
if (pricingCurrency && majorUnitInputs.length) {
  const currencySpecs = {
    INR: {symbol: '₹', exponent: 2},
    USD: {symbol: '$', exponent: 2},
    EUR: {symbol: '€', exponent: 2},
    GBP: {symbol: '£', exponent: 2},
    JPY: {symbol: '¥', exponent: 0},
    KRW: {symbol: '₩', exponent: 0},
  };
  const updateMoneyInputs = () => {
    const spec = currencySpecs[pricingCurrency.value] || {symbol: '', exponent: 2};
    majorUnitInputs.forEach(input => {
      const symbol = input.closest('.money-input-shell')?.querySelector('[data-currency-symbol]');
      if (symbol) symbol.textContent = spec.symbol;
      input.step = spec.exponent === 0 ? '1' : '0.01';
      input.inputMode = spec.exponent === 0 ? 'numeric' : 'decimal';
      const label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
      if (label) label.textContent = `${input.dataset.baseLabel}${spec.symbol ? ` (${spec.symbol})` : ''}`;
    });
  };
  pricingCurrency.addEventListener('change', updateMoneyInputs);
  updateMoneyInputs();
}
