window.hashOriginal = async function(file) {
  const hasher = await hashwasm.createSHA256();
  hasher.init();
  const chunkSize = 4 * 1024 * 1024;
  for (let offset = 0; offset < file.size; offset += chunkSize) {
    const bytes = new Uint8Array(await file.slice(offset, offset + chunkSize).arrayBuffer());
    hasher.update(bytes);
  }
  return hasher.digest('hex');
};
