import type { Cover } from "./types";
const db = () =>
  new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("afterstory-covers", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("covers");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
export async function coverStorage(
  key: string,
  value?: Cover | null,
): Promise<Cover | undefined> {
  const database = await db();
  return new Promise((resolve, reject) => {
    const tx = database.transaction(
      "covers",
      value === undefined ? "readonly" : "readwrite",
    );
    const store = tx.objectStore("covers");
    const request =
      value === undefined
        ? store.get(key)
        : value === null
          ? store.delete(key)
          : store.put(value, key);
    tx.oncomplete = () => {
      database.close();
      resolve(value === undefined ? request.result : undefined);
    };
    tx.onerror = () => {
      database.close();
      reject(tx.error);
    };
    tx.onabort = () => {
      database.close();
      reject(tx.error);
    };
  });
}
