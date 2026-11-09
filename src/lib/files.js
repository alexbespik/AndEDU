// ---------------------------------------------------------------------------
// File helpers: filename disambiguation and stable identification
// ---------------------------------------------------------------------------

const GENERIC_NAME_RE = /^(image|clipboard|unnamed|blob|screenshot|screen[ _-]?shot)(\.[a-zA-Z0-9]+)?$/i;
const SUFFIX_COUNTER_RE = /\s*\(\d+\)$/;

/**
 * Disambiguates a file against a list of existing files.
 * Handles generic clipboard/screenshot names and duplicate collisions.
 *
 * @param {File|Blob|object} file
 * @param {Array<File|object|string>} existingList
 * @returns {File|object}
 */
export function disambiguateFile(file, existingList = []) {
  if (!file) return file;

  const uid =
    file.uid ||
    file._uid ||
    (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`);

  const rawName = (file.name || file._displayName || 'screenshot.png').trim();

  // Normalize existing list names (case-insensitive)
  const existingNames = new Set(
    (existingList || [])
      .filter((item) => {
        if (!item) return false;
        const itemUid = item.uid || item._uid || item.id;
        if (itemUid && itemUid === uid) return false;
        return true;
      })
      .map((item) => {
        const n = typeof item === 'string' ? item : item?.name || item?._displayName || item?.filename || '';
        return n.trim().toLowerCase();
      })
      .filter(Boolean)
  );

  // Extract extension and stem/base
  const dotIdx = rawName.lastIndexOf('.');
  let ext = dotIdx !== -1 ? rawName.slice(dotIdx) : '';
  let base = dotIdx !== -1 ? rawName.slice(0, dotIdx) : rawName;

  const suffixMatch = base.match(SUFFIX_COUNTER_RE);
  const initialCounter = suffixMatch ? parseInt(suffixMatch[0].replace(/[^\d]/g, ''), 10) : 0;

  const isGeneric =
    GENERIC_NAME_RE.test(rawName) ||
    /^(image|clipboard|unnamed|blob|screenshot|screen[ _-]?shot)$/i.test(base.replace(SUFFIX_COUNTER_RE, '').trim());

  if (isGeneric) {
    base = 'screenshot';
    if (!ext) {
      const mime = file.type || '';
      const sub = mime.startsWith('image/') ? mime.split('/')[1] : '';
      ext = sub ? `.${sub === 'jpeg' ? 'jpg' : sub}` : '.png';
    }
  }

  let finalName = rawName;
  if (isGeneric) {
    finalName = `${base}${ext}`;
  }

  if (existingNames.has(finalName.toLowerCase())) {
    base = base.replace(SUFFIX_COUNTER_RE, '').trim();
    if (!base) base = 'screenshot';
    let counter = Math.max(1, initialCounter + 1);
    while (existingNames.has(`${base} (${counter})${ext}`.toLowerCase())) {
      counter++;
    }
    finalName = `${base} (${counter})${ext}`;
  }

  try {
    const newFile = new File([file], finalName, {
      type: file.type || (ext === '.png' ? 'image/png' : ''),
      lastModified: Date.now(),
    });
    newFile.uid = uid;
    newFile._uid = uid;
    return newFile;
  } catch {
    file._displayName = finalName;
    file.uid = uid;
    file._uid = uid;
    return file;
  }
}
