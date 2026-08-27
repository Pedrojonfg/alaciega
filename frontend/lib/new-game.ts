export function parseLevels(body: unknown): number[] {
  if (!body || typeof body !== "object") return [];
  const raw = (body as { levels?: unknown }).levels;
  if (!Array.isArray(raw)) return [];
  return raw.filter((n): n is number => typeof n === "number" && Number.isInteger(n));
}

export function canSubmit(
  levels: number[],
  level: number | null,
  busy: boolean,
): boolean {
  return !busy && level != null && levels.includes(level);
}

export type Range = { min: number; max: number; default: number };

export const QUESTIONS_PER_BATCH: Range = { min: 0, max: 10, default: 2 };
// jugadas completas (par blancas+negras)
export const MOVES_INTERVAL: Range = { min: 1, max: 20, default: 3 };

export function clampRange(r: Range, n: number): number {
  if (!Number.isFinite(n)) return r.default;
  return Math.min(r.max, Math.max(r.min, Math.round(n)));
}
