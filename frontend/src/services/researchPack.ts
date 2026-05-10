/** localStorage-backed research pack: a saved set of document IDs. */
const KEY = "uap_research_pack";

function read(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  localStorage.setItem(KEY, JSON.stringify(ids));
  window.dispatchEvent(new CustomEvent("uap:pack-change"));
}

export function getPack(): string[] {
  return read();
}

export function isInPack(id: string): boolean {
  return read().includes(id);
}

export function addToPack(id: string): void {
  const cur = read();
  if (!cur.includes(id)) write([...cur, id]);
}

export function removeFromPack(id: string): void {
  write(read().filter((x) => x !== id));
}

export function togglePack(id: string): boolean {
  if (isInPack(id)) {
    removeFromPack(id);
    return false;
  }
  addToPack(id);
  return true;
}

export function clearPack(): void {
  write([]);
}

export function packSize(): number {
  return read().length;
}

export function onPackChange(cb: () => void): () => void {
  const handler = () => cb();
  window.addEventListener("uap:pack-change", handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener("uap:pack-change", handler);
    window.removeEventListener("storage", handler);
  };
}
