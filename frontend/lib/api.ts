const BASE = "/api/proxy";

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}

async function request(path: string, init?: RequestInit): Promise<{ status: number; body: unknown }> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const r = await fetch(apiUrl(path), { ...init, headers });
  const body = await r.json().catch(() => ({}));
  return { status: r.status, body };
}

export function getLevels() {
  return request("/maia/levels");
}

export function createGame(
  player_color: string,
  maia_level: number,
  config?: { questions_per_batch?: number; moves_interval?: number },
) {
  return request("/games", {
    method: "POST",
    body: JSON.stringify({ player_color, maia_level, ...config }),
  });
}

export function postMove(gameId: string, move_text: string) {
  return request(`/games/${gameId}/move`, {
    method: "POST",
    body: JSON.stringify({ move_text }),
  });
}

export function postResign(gameId: string) {
  return request(`/games/${gameId}/resign`, { method: "POST" });
}

export function getGames() {
  return request("/games");
}

export function getGame(gameId: string) {
  return request(`/games/${gameId}`);
}

export function postAnswer(
  gameId: string,
  body: {
    ply_number: number;
    question_text: string;
    correct_answer: string;
    user_answer: string;
    was_correct: boolean;
  },
) {
  return request(`/games/${gameId}/answer`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postPeek(gameId: string) {
  return request(`/games/${gameId}/peek`, { method: "POST" });
}

export function deleteGame(gameId: string) {
  return request(`/games/${gameId}`, { method: "DELETE" });
}

// ponytail: el PGN llega como texto plano, no como json
export async function downloadGamePgn(gameId: string): Promise<{ status: number; text: string }> {
  const r = await fetch(apiUrl(`/games/${gameId}/pgn`));
  return { status: r.status, text: await r.text() };
}

export function pgnFilename(createdAt: string, result: string | null): string {
  const date = createdAt.slice(0, 10).replaceAll("-", "");
  return `alaciega_${date}_${(result ?? "final").replaceAll("/", "-")}.pgn`;
}

export function saveTextAs(text: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/x-chess-pgn" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
