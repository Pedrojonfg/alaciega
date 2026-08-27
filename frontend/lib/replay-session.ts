import { Chess } from "chess.js";

export type ListGame = {
  id: string;
  createdAt: string;
  playerColor: "white" | "black";
  maiaLevel: number;
  status: "ongoing" | "finished";
  result: string | null;
};

export type GameDetail = ListGame & {
  pgn: string;
  fenCurrent: string | null;
  events: GameEvent[];
};

export type GameEvent = {
  id: string;
  plyNumber: number;
  eventType: "question" | "peek";
  questionText: string | null;
  correctAnswer: string | null;
  userAnswer: string | null;
  wasCorrect: boolean | null;
  createdAt: string;
};

function isColor(v: unknown): v is "white" | "black" {
  return v === "white" || v === "black";
}

function isStatus(v: unknown): v is "ongoing" | "finished" {
  return v === "ongoing" || v === "finished";
}

export function parseList(body: unknown): ListGame[] {
  if (!body || typeof body !== "object") return [];
  const raw = (body as { games?: unknown }).games;
  if (!Array.isArray(raw)) return [];
  const out: ListGame[] = [];
  for (const item of raw) {
    const row = parseRow(item);
    if (row) out.push(row);
  }
  return out;
}

function parseRow(item: unknown): ListGame | null {
  if (!item || typeof item !== "object") return null;
  const r = item as Record<string, unknown>;
  if (typeof r.id !== "string") return null;
  if (typeof r.created_at !== "string") return null;
  if (!isColor(r.player_color)) return null;
  if (typeof r.maia_level !== "number") return null;
  if (!isStatus(r.status)) return null;
  if (r.result !== null && typeof r.result !== "string") return null;
  return {
    id: r.id,
    createdAt: r.created_at,
    playerColor: r.player_color,
    maiaLevel: r.maia_level,
    status: r.status,
    result: r.result,
  };
}

export function parseDetail(body: unknown): GameDetail | null {
  const row = parseRow(body);
  if (!row) return null;
  const r = body as Record<string, unknown>;
  if (typeof r.pgn !== "string") return null;
  return {
    ...row,
    pgn: r.pgn,
    fenCurrent: typeof r.fen_current === "string" ? r.fen_current : null,
    events: parseEvents(r.events),
  };
}

function parseEvents(raw: unknown): GameEvent[] {
  if (!Array.isArray(raw)) return [];
  const out: GameEvent[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const e = item as Record<string, unknown>;
    if (typeof e.id !== "string") continue;
    if (typeof e.ply_number !== "number") continue;
    if (e.event_type !== "question" && e.event_type !== "peek") continue;
    if (typeof e.created_at !== "string") continue;
    out.push({
      id: e.id,
      plyNumber: e.ply_number,
      eventType: e.event_type,
      questionText: typeof e.question_text === "string" ? e.question_text : null,
      correctAnswer: typeof e.correct_answer === "string" ? e.correct_answer : null,
      userAnswer: typeof e.user_answer === "string" ? e.user_answer : null,
      wasCorrect: typeof e.was_correct === "boolean" ? e.was_correct : null,
      createdAt: e.created_at,
    });
  }
  return out;
}

export function eventsAtPly(events: GameEvent[], ply: number): GameEvent[] {
  return events.filter((e) => e.plyNumber === ply);
}

export function questionEventsAtPly(events: GameEvent[], ply: number): GameEvent[] {
  return eventsAtPly(events, ply).filter((e) => e.eventType === "question");
}

export function replayHeader(maiaLevel: number, result: string | null): string {
  return result ? `Maia ${maiaLevel} · ${result}` : `Maia ${maiaLevel}`;
}

const PIECE_ES: Record<string, string> = {
  K: "R",
  Q: "D",
  R: "T",
  B: "A",
  N: "C",
};

export function toSpanishSan(san: string): string {
  // ponytail: only leading piece letter; pawns and castling untouched
  return san.replace(/^[KQRBN]/, (ch) => PIECE_ES[ch] ?? ch);
}

export type MoveToken = { ply: number; text: string; kind: "num" | "san" };

export function moveTokensFromPgn(pgn: string): MoveToken[] {
  const chess = new Chess();
  try {
    chess.loadPgn(pgn);
  } catch {
    return [];
  }
  const sans = chess.history();
  const tokens: MoveToken[] = [];
  for (let i = 0; i < sans.length; i++) {
    const ply = i + 1;
    if (i % 2 === 0) {
      tokens.push({ ply, text: `${i / 2 + 1}.`, kind: "num" });
    }
    tokens.push({ ply, text: toSpanishSan(sans[i]), kind: "san" });
  }
  return tokens;
}

export function fensFromPgn(pgn: string): string[] {
  const chess = new Chess();
  try {
    chess.loadPgn(pgn);
  } catch {
    return [new Chess().fen()];
  }
  const sans = chess.history();
  chess.reset();
  const fens = [chess.fen()];
  for (const san of sans) {
    const mv = chess.move(san);
    if (!mv) break;
    fens.push(chess.fen());
  }
  return fens;
}

export function nextPly(ply: number, last: number): number {
  return ply >= last ? last : ply + 1;
}

export function prevPly(ply: number): number {
  return ply <= 0 ? 0 : ply - 1;
}

export function canShowBoard(status: string): boolean {
  return status === "finished";
}
