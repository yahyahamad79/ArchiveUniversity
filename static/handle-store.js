/* handle-store.js
   وحدة مشتركة بين شاشات النظام (paths.html و matching.html) لإدارة:
   1) صلاحيات الوصول الفعلية للملفات/المجلدات (FileSystemHandle) عبر IndexedDB
      — هذه خاصة بكل متصفح على حدة، ولا يمكن تخزينها كنص JSON عادي.
   2) الأسماء/الحالة المعروضة، عبر paths.json على السيرفر (مشتركة بين كل الشاشات
      وحتى بين متصفحات مختلفة تتصل بنفس السيرفر).

   المفاتيح الموحّدة المستخدمة في كل الشاشات:
     'excelFile'       → ملف قاعدة البيانات (students_db.xlsx)
     'workspaceFolder' → مجلد صندوق العمل المؤقت (الملفات: صور، وثائق...)
     'archiveFolder'   → مجلد الأرشيف الفعلي / مسار الوجهة (نقل الملفات إليه)
*/

const HANDLE_DB_NAME = 'archiveUniversityHandles';
const HANDLE_STORE_NAME = 'handles';
const HANDLE_DB_VERSION = 1;

function openHandleDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(HANDLE_DB_NAME, HANDLE_DB_VERSION);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(HANDLE_STORE_NAME)) {
        req.result.createObjectStore(HANDLE_STORE_NAME);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function saveHandle(key, handle) {
  try {
    const db = await openHandleDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(HANDLE_STORE_NAME, 'readwrite');
      tx.objectStore(HANDLE_STORE_NAME).put(handle, key);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('saveHandle failed:', err);
    return false;
  }
}

async function getHandle(key) {
  try {
    const db = await openHandleDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(HANDLE_STORE_NAME, 'readonly');
      const req = tx.objectStore(HANDLE_STORE_NAME).get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn('getHandle failed:', err);
    return null;
  }
}

async function deleteHandle(key) {
  try {
    const db = await openHandleDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(HANDLE_STORE_NAME, 'readwrite');
      tx.objectStore(HANDLE_STORE_NAME).delete(key);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    return false;
  }
}

// 'granted' | 'prompt' | 'denied' | null (لا يوجد handle محفوظ أصلاً)
async function checkHandlePermission(handle, mode = 'readwrite') {
  if (!handle) return null;
  try {
    return await handle.queryPermission({ mode });
  } catch (err) {
    return null;
  }
}

async function requestHandlePermission(handle, mode = 'readwrite') {
  if (!handle) return 'denied';
  try {
    return await handle.requestPermission({ mode });
  } catch (err) {
    return 'denied';
  }
}

/* ============================================================
   مزامنة الأسماء/الحالة عبر السيرفر (database/paths.json)
   ============================================================ */
async function fetchSharedPaths() {
  try {
    const res = await fetch('/api/get-paths');
    const data = await res.json();
    return data.success ? (data.paths || {}) : {};
  } catch (err) {
    console.warn('fetchSharedPaths failed:', err);
    return {};
  }
}

// partialEntry: { [key]: { name, kind: 'file'|'directory', updated_at } }
async function saveSharedPaths(partialEntry) {
  try {
    const res = await fetch('/api/save-paths', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: partialEntry })
    });
    return await res.json();
  } catch (err) {
    console.warn('saveSharedPaths failed:', err);
    return { success: false };
  }
}
