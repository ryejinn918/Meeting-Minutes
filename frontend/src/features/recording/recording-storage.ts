const DB_NAME = "meetflow-recordings";
const STORE = "chunks";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: ["draftId", "index"] });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveChunk(draftId: string, index: number, blob: Blob): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ draftId, index, blob });
    tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function loadChunks(draftId: string): Promise<Blob[]> {
  const db = await openDb();
  const rows = await new Promise<Array<{ index: number; blob: Blob }>>((resolve, reject) => {
    const request = db.transaction(STORE).objectStore(STORE).getAll(IDBKeyRange.bound([draftId, 0], [draftId, Number.MAX_SAFE_INTEGER]));
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  });
  db.close();
  return rows.sort((a, b) => a.index - b.index).map((row) => row.blob);
}

export async function clearChunks(draftId: string): Promise<void> {
  const db = await openDb();
  const keys = await new Promise<IDBValidKey[]>((resolve, reject) => {
    const request = db.transaction(STORE).objectStore(STORE).getAllKeys(IDBKeyRange.bound([draftId, 0], [draftId, Number.MAX_SAFE_INTEGER]));
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  });
  const tx = db.transaction(STORE, "readwrite"); keys.forEach((key) => tx.objectStore(STORE).delete(key));
  await new Promise<void>((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); });
  db.close();
}
