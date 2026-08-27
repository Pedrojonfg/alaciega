import { englishPrompt, englishShort } from "./question-i18n";

export type AnswerShape = "number" | "boolean" | "square" | "square_list" | "piece_symbol";

export type Question = {
  type: string;
  // prompt es la versión larga: se muestra en la partida
  prompt: string;
  // promptShort se persiste en el historial y se lee en el visor
  promptShort?: string;
  promptEn?: string;
  promptShortEn?: string;
  answer: number | boolean | string | string[] | null;
  expectedAnswerType?: AnswerShape;
  allowsEmptyAnswer?: boolean;
};

export type Session = {
  gameId: string;
  maiaLevel: number;
  playerColor: "white" | "black";
  history: string[];
  pendingQuestion: Question | null;
  pendingQuestions: Question[];
  batchTotal: number;
  pendingMaia: string | null;
  lastFeedback: "correct" | "incorrect" | null;
  status: "ongoing" | "finished";
  result: string | null;
  error: string | null;
  pendingFinish: { status: "finished"; result: string | null } | null;
  peeksRemaining: number;
  consecutiveFails: number;
  totalFails: number;
  suggestPeek: boolean;
};

function emptyVerification(): Pick<
  Session,
  | "pendingQuestion"
  | "pendingQuestions"
  | "batchTotal"
  | "consecutiveFails"
  | "totalFails"
  | "suggestPeek"
> {
  return {
    pendingQuestion: null,
    pendingQuestions: [],
    batchTotal: 0,
    consecutiveFails: 0,
    totalFails: 0,
    suggestPeek: false,
  };
}

export function seedFromCreate(payload: {
  game_id: string;
  maia_level: number;
  player_color?: "white" | "black";
  status: "ongoing" | "finished";
  maia_move?: string;
  result?: string;
}): Session {
  return {
    gameId: payload.game_id,
    maiaLevel: payload.maia_level,
    playerColor: payload.player_color ?? "white",
    history: payload.maia_move ? [payload.maia_move] : [],
    pendingMaia: null,
    lastFeedback: null,
    status: payload.status,
    result: payload.result ?? null,
    error: null,
    pendingFinish: null,
    peeksRemaining: 3,
    ...emptyVerification(),
  };
}

export function seedFromDetail(payload: {
  id: string;
  maia_level: number;
  player_color: "white" | "black";
  status: "ongoing" | "finished";
  moves: string[];
  result?: string | null;
  peeks_remaining?: number;
  questions?: Question[];
  suggest_peek?: boolean;
  consecutive_fails?: number;
  total_fails?: number;
}): Session {
  const qs = payload.questions ?? [];
  return {
    gameId: payload.id,
    maiaLevel: payload.maia_level,
    playerColor: payload.player_color,
    history: payload.moves,
    pendingQuestion: qs[0] ?? null,
    pendingQuestions: qs,
    batchTotal: qs.length,
    pendingMaia: null,
    lastFeedback: null,
    status: payload.status,
    result: payload.result ?? null,
    error: null,
    pendingFinish: null,
    peeksRemaining: payload.peeks_remaining ?? 3,
    consecutiveFails: payload.consecutive_fails ?? 0,
    totalFails: payload.total_fails ?? 0,
    suggestPeek: payload.suggest_peek ?? false,
  };
}

export function playOrReplayHref(status: "ongoing" | "finished", id: string): string {
  return status === "ongoing" ? `/play/${id}` : `/games/${id}`;
}

// ponytail: movetext tokenizer — no chess.js; nested () stripped iteratively
export function movesFromPgn(pgn: string): string[] {
  let s = pgn;
  let prev = "";
  while (s !== prev) {
    prev = s;
    s = s.replace(/\{[^}]*\}/g, " ").replace(/\([^()]*\)/g, " ");
  }
  s = s.replace(/\[[^\]]*\]/g, " ");
  const skip = new Set(["*", "1-0", "0-1", "1/2-1/2"]);
  const out: string[] = [];
  for (const t of s.split(/\s+/).filter(Boolean)) {
    if (/^\d+\.+$/.test(t) || skip.has(t) || /^\$\d+$/.test(t)) continue;
    out.push(t);
  }
  return out;
}

export function resumeFromGet(body: unknown): Session | "finished" | null {
  if (!body || typeof body !== "object") return null;
  const r = body as Record<string, unknown>;
  if (r.status === "finished") return "finished";
  if (typeof r.id !== "string") return null;
  if (typeof r.maia_level !== "number") return null;
  if (r.player_color !== "white" && r.player_color !== "black") return null;
  if (r.status !== "ongoing") return null;
  const moves = Array.isArray(r.moves) && r.moves.every((m) => typeof m === "string")
    ? (r.moves as string[])
    : typeof r.pgn === "string"
      ? movesFromPgn(r.pgn)
      : null;
  if (moves === null) return null;
  const questions = Array.isArray(r.questions) ? (r.questions as Question[]) : [];
  return seedFromDetail({
    id: r.id,
    maia_level: r.maia_level,
    player_color: r.player_color,
    status: "ongoing",
    moves,
    result: typeof r.result === "string" ? r.result : null,
    peeks_remaining: typeof r.peeks_remaining === "number" ? r.peeks_remaining : 3,
    questions,
    suggest_peek: r.suggest_peek === true,
    consecutive_fails: typeof r.consecutive_fails === "number" ? r.consecutive_fails : 0,
    total_fails: typeof r.total_fails === "number" ? r.total_fails : 0,
  });
}

function queueFrom(body: { questions?: Question[]; question?: Question }): Question[] {
  if (body.questions) return body.questions;
  if (body.question) return [body.question];
  return [];
}

export function applyMoveOk(
  s: Session,
  body: {
    applied: string;
    maia_move?: string;
    status: "ongoing" | "finished";
    result?: string;
    question?: Question;
    questions?: Question[];
    suggest_peek?: boolean;
  },
): Session {
  const qs = queueFrom(body);
  const finished = body.status === "finished";
  if (qs.length === 0) {
    return {
      ...s,
      history: body.maia_move ? [...s.history, body.applied, body.maia_move] : [...s.history, body.applied],
      pendingQuestion: null,
      pendingQuestions: [],
      batchTotal: 0,
      pendingMaia: null,
      lastFeedback: null,
      error: null,
      status: finished ? "finished" : "ongoing",
      result: finished ? (body.result ?? null) : s.result,
      pendingFinish: null,
      suggestPeek: body.suggest_peek ?? s.suggestPeek,
    };
  }
  return {
    ...s,
    history: [...s.history, body.applied],
    pendingQuestion: qs[0],
    pendingQuestions: qs,
    batchTotal: qs.length,
    pendingMaia: body.maia_move ?? null,
    lastFeedback: null,
    error: null,
    // ponytail: keep status ongoing until the player answers the last question
    status: "ongoing",
    pendingFinish: finished ? { status: "finished", result: body.result ?? null } : null,
    suggestPeek: body.suggest_peek ?? s.suggestPeek,
  };
}

export function applyMoveError(s: Session, error: string): Session {
  return { ...s, error, lastFeedback: null };
}

export function answerQuestion(s: Session, input: string): Session {
  const current = s.pendingQuestion ?? s.pendingQuestions[0];
  if (!current) return s;
  const correct = score(current, input);
  const rest = s.pendingQuestions.slice(1);
  const consecutiveFails = correct ? 0 : s.consecutiveFails + 1;
  const totalFails = correct ? s.totalFails : s.totalFails + 1;
  const suggestPeek = s.suggestPeek || consecutiveFails >= 3 || totalFails >= 5;
  if (rest.length > 0) {
    return {
      ...s,
      pendingQuestion: rest[0],
      pendingQuestions: rest,
      lastFeedback: correct ? "correct" : "incorrect",
      error: null,
      consecutiveFails,
      totalFails,
      suggestPeek,
    };
  }
  const history = s.pendingMaia ? [...s.history, s.pendingMaia] : s.history;
  const finish = s.pendingFinish;
  return {
    ...s,
    history,
    pendingQuestion: null,
    pendingQuestions: [],
    batchTotal: 0,
    pendingMaia: null,
    lastFeedback: correct ? "correct" : "incorrect",
    error: null,
    status: finish ? "finished" : s.status,
    result: finish ? finish.result : s.result,
    pendingFinish: null,
    consecutiveFails,
    totalFails,
    suggestPeek,
  };
}

export function promptForLocale(q: Question, locale: string): string {
  return locale === "en" ? englishPrompt(q) : q.prompt;
}

export function answerPayload(s: Session, input: string, locale = "es") {
  const current = s.pendingQuestion ?? s.pendingQuestions[0];
  if (!current) return null;
  const frozen = current.answer;
  const question_text =
    locale === "en" ? englishShort(current) : (current.promptShort ?? current.prompt);
  return {
    ply_number: s.history.length,
    question_text,
    correct_answer: Array.isArray(frozen) ? frozen.join(" ") : String(frozen),
    user_answer: input,
    was_correct: score(current, input),
  };
}

export function batchProgress(s: Session): { current: number; total: number } | null {
  if (!s.pendingQuestion || s.batchTotal < 2) return null;
  return { current: s.batchTotal - s.pendingQuestions.length + 1, total: s.batchTotal };
}

// ponytail: two one-liners
export function inputIsRequired(q: Question): boolean {
  return q.allowsEmptyAnswer !== true;
}

export function isFallbackQuestion(q: Question): boolean {
  return q.type === "no_more_questions";
}

const ANSWER_ALIAS: Record<string, string> = {
  light: "clara",
  dark: "oscura",
  rank: "fila",
  file: "columna",
  row: "fila",
};

function canonAnswer(t: string): string {
  return ANSWER_ALIAS[t] ?? t;
}

function score(q: Question, input: string): boolean {
  const t = input.trim().toLowerCase();
  const expected = q.expectedAnswerType ?? (q.type === "in_check" ? "boolean" : "number");
  const frozen = q.answer;
  if (expected === "boolean") {
    if (["sí", "si", "true", "1", "yes"].includes(t)) return frozen === true;
    if (["no", "false", "0"].includes(t)) return frozen === false;
    return false;
  }
  if (expected === "number") return Number(t) === frozen;
  if (expected === "square") {
    if (frozen == null) return ["", "ninguna", "none", "-", "empty"].includes(t);
    return t === String(frozen).toLowerCase();
  }
  if (expected === "square_list") {
    const want = new Set((Array.isArray(frozen) ? frozen : []).map((x) => String(x).toLowerCase()));
    const got =
      ["", "ninguna", "none", "0"].includes(t)
        ? new Set<string>()
        : new Set(
            t
              .replaceAll(",", " ")
              .split(/\s+/)
              .filter(Boolean)
              .map(canonAnswer),
          );
    if (want.size !== got.size) return false;
    for (const x of want) if (!got.has(x)) return false;
    return true;
  }
  if (frozen == null) return ["", "ninguna", "none", "-", "vacía", "vacia", "empty"].includes(t);
  return canonAnswer(t) === String(frozen).toLowerCase();
}

export function applyResign(s: Session, result: string): Session {
  return {
    ...s,
    status: "finished",
    result,
    pendingQuestion: null,
    pendingQuestions: [],
    pendingMaia: null,
    pendingFinish: null,
    error: null,
  };
}

export function applyPeek(
  s: Session,
  remaining: number,
  extras?: { consecutiveFails?: number; totalFails?: number; suggestPeek?: boolean },
): Session {
  return {
    ...s,
    peeksRemaining: remaining,
    error: null,
    consecutiveFails: extras?.consecutiveFails ?? 0,
    totalFails: extras?.totalFails ?? s.totalFails,
    suggestPeek: extras?.suggestPeek ?? false,
  };
}

export function formatHistory(sans: string[]): string {
  const parts: string[] = [];
  for (let i = 0; i < sans.length; i += 2) {
    const n = i / 2 + 1;
    parts.push(sans[i + 1] ? `${n}. ${sans[i]} ${sans[i + 1]}` : `${n}. ${sans[i]}`);
  }
  return parts.join("  ");
}

export function canTypeMove(s: Session, busy: boolean): boolean {
  return !busy && s.status === "ongoing" && s.pendingQuestion == null;
}

const STASH_KEY = "alaciega-play";

export function stashSession(s: Session): void {
  sessionStorage.setItem(STASH_KEY, JSON.stringify(s));
}

export function takeSession(gameId: string): Session | null {
  const raw = sessionStorage.getItem(STASH_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as Session;
    if (s.gameId !== gameId) return null;
    const qs = Array.isArray(s.pendingQuestions)
      ? s.pendingQuestions
      : s.pendingQuestion
        ? [s.pendingQuestion]
        : [];
    return {
      ...emptyVerification(),
      ...s,
      peeksRemaining: typeof s.peeksRemaining === "number" ? s.peeksRemaining : 3,
      pendingQuestions: qs,
      pendingQuestion: qs[0] ?? null,
      consecutiveFails: typeof s.consecutiveFails === "number" ? s.consecutiveFails : 0,
      totalFails: typeof s.totalFails === "number" ? s.totalFails : 0,
      suggestPeek: s.suggestPeek === true,
      batchTotal: typeof s.batchTotal === "number" ? s.batchTotal : qs.length,
    };
  } catch {
    return null;
  }
}
