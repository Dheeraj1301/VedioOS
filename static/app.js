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
document.querySelectorAll('.upload-form').forEach(uploadForm => uploadForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = uploadForm.querySelector('button');
  const status = uploadForm.querySelector('.upload-status');
  const progress = uploadForm.querySelector('.upload-progress');
  const files = [...uploadForm.querySelector('.upload-files').files];
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
}));
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
