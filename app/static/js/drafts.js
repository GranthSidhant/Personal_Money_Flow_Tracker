/**
 * Personal Money Flow Tracker - Offline Drafts & Sync Manager
 * Conforms to Project Requirements Section 16 (PWA & Offline Draft Capture)
 */

const DB_NAME = 'MoneyFlowDraftsDB';
const DB_VERSION = 1;
const STORE_NAME = 'offline_drafts';

function openDraftsDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'client_draft_id' });
        store.createIndex('sync_status', 'sync_status', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Save a new pending draft to IndexedDB.
 */
async function saveOfflineDraft(draftData) {
  const db = await openDraftsDB();
  const client_draft_id = 'draft_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
  
  const draft = {
    client_draft_id: client_draft_id,
    title: draftData.title || 'Offline Memo',
    text_note: draftData.text_note || '',
    audio_blob: draftData.audio_blob || null,
    audio_mime_type: draftData.audio_mime_type || (draftData.audio_blob ? 'audio/webm' : null),
    location: draftData.location || null,
    captured_at: draftData.captured_at || new Date().toISOString(),
    created_at: new Date().toISOString(),
    sync_status: 'SAVED_LOCAL', // SAVED_LOCAL, SYNCING, SYNCED, SYNC_FAILED
    sync_error: null,
    server_note_id: null
  };

  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(draft);
    req.onsuccess = () => {
      window.dispatchEvent(new CustomEvent('moneyflow:drafts-updated'));
      if (navigator.onLine) {
        syncPendingDrafts();
      }
      resolve(draft);
    };
    req.onerror = () => reject(req.error);
  });
}

/**
 * Fetch all pending (unsynced) drafts.
 */
async function getPendingDrafts() {
  const db = await openDraftsDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => {
      const all = req.result || [];
      resolve(all.filter(d => d.sync_status !== 'SYNCED'));
    };
    req.onerror = () => reject(req.error);
  });
}

/**
 * Fetch all drafts in local storage.
 */
async function getAllDrafts() {
  const db = await openDraftsDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

/**
 * Delete a draft from IndexedDB.
 */
async function deleteOfflineDraft(client_draft_id) {
  const db = await openDraftsDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(client_draft_id);
    req.onsuccess = () => {
      window.dispatchEvent(new CustomEvent('moneyflow:drafts-updated'));
      resolve(true);
    };
    req.onerror = () => reject(req.error);
  });
}

/**
 * Synchronize all pending drafts with server.
 * Uses idempotent client_draft_id so retries never create duplicates.
 */
let isSyncing = false;
async function syncPendingDrafts() {
  if (isSyncing || !navigator.onLine) return;
  isSyncing = true;

  try {
    const pending = await getPendingDrafts();
    if (!pending || pending.length === 0) {
      isSyncing = false;
      return;
    }

    // Get CSRF Token from meta or DOM
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                      document.querySelector('input[name="csrf_token"]')?.value || '';

    const db = await openDraftsDB();

    for (const draft of pending) {
      // Mark draft as SYNCING
      draft.sync_status = 'SYNCING';
      await new Promise((res) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).put(draft).onsuccess = res;
      });
      window.dispatchEvent(new CustomEvent('moneyflow:drafts-updated'));

      const formData = new FormData();
      formData.append('client_draft_id', draft.client_draft_id);
      formData.append('title', draft.title);
      formData.append('text_note', draft.text_note);
      formData.append('captured_at', draft.captured_at);
      if (csrfToken) formData.append('csrf_token', csrfToken);

      if (draft.audio_blob) {
        formData.append('audio_file', draft.audio_blob, `${draft.client_draft_id}.webm`);
      }
      if (draft.location) {
        formData.append('latitude', draft.location.latitude);
        formData.append('longitude', draft.location.longitude);
        formData.append('accuracy', draft.location.accuracy || 0);
      }

      try {
        const response = await fetch('/api/sync/drafts', {
          method: 'POST',
          headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
          body: formData
        });

        if (response.ok) {
          const resJson = await response.json();
          draft.sync_status = 'SYNCED';
          draft.server_note_id = resJson.note_id;
          draft.sync_error = null;
        } else {
          const errText = await response.text();
          draft.sync_status = 'SYNC_FAILED';
          draft.sync_error = `Server status ${response.status}: ${errText.substring(0, 100)}`;
        }
      } catch (networkErr) {
        draft.sync_status = 'SYNC_FAILED';
        draft.sync_error = networkErr.message || 'Network disconnected';
      }

      // Update draft record
      await new Promise((res) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).put(draft).onsuccess = res;
      });
    }
  } catch (err) {
    console.warn('[Sync Error]', err);
  } finally {
    isSyncing = false;
    window.dispatchEvent(new CustomEvent('moneyflow:drafts-updated'));
  }
}

/**
 * UI Connection & Drafts Status Manager
 */
function updateNetworkUI(isOnline) {
  const badge = document.getElementById('networkStatusBadge');
  const text = document.getElementById('networkStatusText');
  if (badge) {
    if (isOnline) {
      badge.className = 'badge bg-success-subtle text-success border border-success-subtle d-inline-flex align-items-center gap-1';
      if (text) text.textContent = 'Online';
    } else {
      badge.className = 'badge bg-warning-subtle text-warning border border-warning-subtle d-inline-flex align-items-center gap-1';
      if (text) text.textContent = 'Offline (Draft Mode)';
    }
  }
}

async function renderDraftsCounter() {
  const badge = document.getElementById('pendingDraftsCount');
  const drafts = await getPendingDrafts();
  if (badge) {
    if (drafts.length > 0) {
      badge.textContent = drafts.length;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

// Global Event Listeners
window.addEventListener('online', () => {
  updateNetworkUI(true);
  syncPendingDrafts();
});

window.addEventListener('offline', () => {
  updateNetworkUI(false);
});

window.addEventListener('moneyflow:drafts-updated', () => {
  renderDraftsCounter();
});

// Initial load registration
document.addEventListener('DOMContentLoaded', () => {
  updateNetworkUI(navigator.onLine);
  renderDraftsCounter();

  // Register Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => console.log('[PWA] Service Worker registered with scope:', reg.scope))
      .catch((err) => console.log('[PWA] Service Worker registration failed:', err));
  }
});
