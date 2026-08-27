import { test } from "node:test";
import assert from "node:assert/strict";
import {
  seedFromCreate,
  seedFromDetail,
  playOrReplayHref,
  resumeFromGet,
  applyMoveOk,
  applyMoveError,
  applyPeek,
  answerQuestion,
  answerPayload,
  promptForLocale,
  formatHistory,
  canTypeMove,
  inputIsRequired,
  isFallbackQuestion,
  type Session,
} from "./play-session.ts";

const q = {
  type: "captures" as const,
  prompt: "¿Cuántas capturas legales tiene el jugador en turno?",
  answer: 0,
};

test("seed white has empty history and no question", () => {
  const s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  assert.equal(s.gameId, "g1");
  assert.deepEqual(s.history, []);
  assert.equal(s.pendingQuestion, null);
  assert.equal(s.pendingMaia, null);
});

test("seed black puts opening SAN in history, no question", () => {
  const s = seedFromCreate({
    game_id: "g2",
    maia_level: 1100,
    player_color: "black",
    status: "ongoing",
    maia_move: "e4",
  });
  assert.deepEqual(s.history, ["e4"]);
  assert.equal(s.pendingQuestion, null);
});

test("legal move appends player SAN and hides maia until answered", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", question: q });
  assert.deepEqual(s.history, ["e4"]);
  assert.equal(s.pendingMaia, "e5");
  assert.equal(s.pendingQuestion?.type, "captures");
  assert.equal(s.error, null);
});

test("correct answer reveals maia and sets feedback", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", question: q });
  s = answerQuestion(s, "0");
  assert.equal(s.lastFeedback, "correct");
  assert.deepEqual(s.history, ["e4", "e5"]);
  assert.equal(s.pendingQuestion, null);
  assert.equal(s.pendingMaia, null);
  assert.equal(s.status, "ongoing");
});

test("wrong answer still reveals maia", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", question: q });
  s = answerQuestion(s, "9");
  assert.equal(s.lastFeedback, "incorrect");
  assert.deepEqual(s.history, ["e4", "e5"]);
});

test("illegal move sets error and does not change history", () => {
  const s0 = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  const s = applyMoveError(s0, "jugada ilegal o no reconocida");
  assert.equal(s.error, "jugada ilegal o no reconocida");
  assert.deepEqual(s.history, []);
  assert.equal(s.pendingQuestion, null);
});

test("player-ending move has no pending maia; answer marks finished", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "Qxf7#",
    status: "finished",
    result: "1-0",
    question: { type: "in_check", prompt: "jaque?", answer: true },
  });
  assert.deepEqual(s.history, ["Qxf7#"]);
  assert.equal(s.pendingMaia, null);
  assert.equal(s.status, "ongoing");
  s = answerQuestion(s, "sí");
  assert.equal(s.lastFeedback, "correct");
  assert.equal(s.status, "finished");
  assert.equal(s.result, "1-0");
});

test("in_check no is scored", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: { type: "in_check", prompt: "jaque?", answer: false },
  });
  s = answerQuestion(s, "no");
  assert.equal(s.lastFeedback, "correct");
});

test("formatHistory numbers pairs; pending maia stays out of visible history", () => {
  assert.equal(formatHistory(["e4", "e5", "Nf3"]), "1. e4 e5  2. Nf3");
  assert.equal(formatHistory([]), "");
});

test("canTypeMove is false while a question is pending or the game is finished", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  assert.equal(canTypeMove(s, false), true);
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", question: q });
  assert.equal(canTypeMove(s, false), false);
  s = answerQuestion(s, "0");
  assert.equal(canTypeMove(s, true), false);
});


test("answerPayload uses history length as ply and scores the answer", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", question: q });
  const body = answerPayload(s, "0");
  assert.deepEqual(body, {
    ply_number: 1,
    question_text: q.prompt,
    correct_answer: "0",
    user_answer: "0",
    was_correct: true,
  });
  assert.equal(answerPayload(s, "9")?.was_correct, false);
  assert.equal(answerPayload(seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  }), "0"), null);
});


test("answerPayload persists the short prompt when the catalogue sends one", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: {
      type: "legal_moves_for_piece",
      prompt: "¿Cuántos movimientos legales tiene la pieza en c8? (si esa pieza no es del bando que mueve ahora, la respuesta es 0)",
      promptShort: "Movimientos legales en c8",
      answer: 0,
      expectedAnswerType: "number",
    },
  });
  assert.match(s.pendingQuestion?.prompt ?? "", /Cuántos movimientos legales/);
  assert.equal(answerPayload(s, "0")?.question_text, "Movimientos legales en c8");
});

test("resumeFromGet keeps promptShort on restored questions", () => {
  const loaded = resumeFromGet({
    id: "g9",
    maia_level: 1100,
    player_color: "white",
    status: "ongoing",
    moves: ["e4"],
    questions: [
      { type: "in_check", prompt: "¿Está el rey en jaque? Responde sí o no.", promptShort: "¿Jaque?", answer: false, expectedAnswerType: "boolean" },
    ],
  });
  const s = loaded as Session;
  assert.equal(s.pendingQuestion?.promptShort, "¿Jaque?");
  assert.equal(answerPayload(s, "no")?.question_text, "¿Jaque?");
});

test("seedFromDetail restores history and peeks; href splits ongoing vs finished", () => {
  const s = seedFromDetail({
    id: "g9",
    maia_level: 1100,
    player_color: "black",
    status: "ongoing",
    moves: ["e4", "e5"],
    peeks_remaining: 2,
  });
  assert.equal(s.gameId, "g9");
  assert.equal(s.maiaLevel, 1100);
  assert.equal(s.playerColor, "black");
  assert.deepEqual(s.history, ["e4", "e5"]);
  assert.equal(s.pendingQuestion, null);
  assert.equal(s.peeksRemaining, 2);
  assert.equal(s.status, "ongoing");
  assert.equal(playOrReplayHref("ongoing", "g9"), "/play/g9");
  assert.equal(playOrReplayHref("finished", "g9"), "/games/g9");
  assert.equal(resumeFromGet({ status: "finished" }), "finished");
  assert.equal(resumeFromGet({ error: "partida no encontrada" }), null);
  const loaded = resumeFromGet({
    id: "g9",
    maia_level: 1100,
    player_color: "black",
    status: "ongoing",
    moves: ["e4"],
    peeks_remaining: 3,
    result: null,
  });
  assert.notEqual(loaded, "finished");
  assert.notEqual(loaded, null);
  assert.deepEqual((loaded as { history: string[] }).history, ["e4"]);
});


test("applyPeek sets remaining; zero remaining is allowed", () => {
  const s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  assert.equal(s.peeksRemaining, 3);
  assert.equal(applyPeek(s, 2).peeksRemaining, 2);
  assert.equal(applyPeek(s, 0).peeksRemaining, 0);
});

test("empty questions list reveals maia immediately", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, { applied: "e4", maia_move: "e5", status: "ongoing", questions: [] });
  assert.deepEqual(s.history, ["e4", "e5"]);
  assert.equal(s.pendingQuestion, null);
  assert.equal(canTypeMove(s, false), true);
});

test("batch queues questions and only reveals maia after the last answer", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  const qs = [
    { type: "in_check", prompt: "jaque?", answer: false, expectedAnswerType: "boolean" as const },
    { type: "total_piece_count", prompt: "piezas?", answer: 32, expectedAnswerType: "number" as const },
    { type: "side_to_move", prompt: "blancas?", answer: true, expectedAnswerType: "boolean" as const },
  ];
  s = applyMoveOk(s, { applied: "Nf3", maia_move: "Nc6", status: "ongoing", questions: qs });
  assert.equal(s.pendingQuestions.length, 3);
  assert.equal(canTypeMove(s, false), false);
  s = answerQuestion(s, "no");
  assert.equal(s.lastFeedback, "correct");
  assert.equal(s.pendingQuestions.length, 2);
  assert.equal(s.pendingMaia, "Nc6");
  assert.deepEqual(s.history, ["Nf3"]);
  s = answerQuestion(s, "32");
  s = answerQuestion(s, "sí");
  assert.equal(s.pendingQuestion, null);
  assert.deepEqual(s.history, ["Nf3", "Nc6"]);
  assert.equal(canTypeMove(s, false), true);
});

test("misses update counters; a hit resets consecutive only", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    status: "ongoing",
    questions: [
      { type: "in_check", prompt: "a", answer: false, expectedAnswerType: "boolean" },
      { type: "in_check", prompt: "b", answer: false, expectedAnswerType: "boolean" },
    ],
  });
  s = answerQuestion(s, "sí");
  assert.equal(s.consecutiveFails, 1);
  assert.equal(s.totalFails, 1);
  s = answerQuestion(s, "no");
  assert.equal(s.consecutiveFails, 0);
  assert.equal(s.totalFails, 1);
});

test("square_list answers compare as a set", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    status: "ongoing",
    questions: [{ type: "hanging_pieces", prompt: "h", answer: ["e5", "a4"], expectedAnswerType: "square_list" }],
  });
  s = answerQuestion(s, "a4, e5");
  assert.equal(s.lastFeedback, "correct");
});

test("resumeFromGet restores pending questions", () => {
  const loaded = resumeFromGet({
    id: "g9",
    maia_level: 1100,
    player_color: "white",
    status: "ongoing",
    moves: ["e4", "e5", "Nf3"],
    peeks_remaining: 3,
    questions: [{ type: "in_check", prompt: "jaque?", answer: false, expectedAnswerType: "boolean" }],
    suggest_peek: true,
    consecutive_fails: 3,
    total_fails: 4,
  });
  assert.notEqual(loaded, "finished");
  assert.notEqual(loaded, null);
  const s = loaded as Session;
  assert.equal(s.pendingQuestion?.type, "in_check");
  assert.equal(s.suggestPeek, true);
  assert.equal(s.consecutiveFails, 3);
});

const BASE = {
  id: "g9",
  maia_level: 1100,
  player_color: "black" as const,
  status: "ongoing" as const,
};

test("resumeFromGet derives SAN from pgn when moves is missing", () => {
  const pgn = `[Event "?"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 {comment} Nc6 *`;
  const loaded = resumeFromGet({ ...BASE, pgn });
  assert.notEqual(loaded, "finished");
  assert.notEqual(loaded, null);
  assert.deepEqual((loaded as { history: string[] }).history, ["e4", "e5", "Nf3", "Nc6"]);
});

test("resumeFromGet keeps moves array when present", () => {
  const loaded = resumeFromGet({
    ...BASE,
    moves: ["e4"],
    pgn: "1. d4 d5 *",
  });
  assert.deepEqual((loaded as { history: string[] }).history, ["e4"]);
});

test("resumeFromGet uses header-only pgn as empty history, not null", () => {
  const loaded = resumeFromGet({ ...BASE, pgn: `[Event "?"]\n[Result "*"]\n\n*` });
  assert.notEqual(loaded, null);
  assert.deepEqual((loaded as { history: string[] }).history, []);
});

test("resumeFromGet returns null without moves or pgn", () => {
  assert.equal(resumeFromGet({ ...BASE }), null);
});

const pinnedEmpty = {
  type: "pinned_pieces",
  prompt: "¿En qué casillas hay piezas clavadas?",
  answer: [] as string[],
  expectedAnswerType: "square_list" as const,
  allowsEmptyAnswer: true,
};

const pinnedSome = {
  type: "pinned_pieces",
  prompt: "¿En qué casillas hay piezas clavadas?",
  answer: ["c3"],
  expectedAnswerType: "square_list" as const,
  allowsEmptyAnswer: true,
};

const fallbackQ = {
  type: "no_more_questions",
  prompt: "No quedan más preguntas por hacer en este tipo de posición",
  answer: "",
  expectedAnswerType: "square_list" as const,
  allowsEmptyAnswer: true,
};

test("inputIsRequired is false only when allowsEmptyAnswer is true", () => {
  assert.equal(inputIsRequired(pinnedEmpty), false);
  assert.equal(inputIsRequired({ type: "captures", prompt: "c", answer: 0 }), true);
  assert.equal(
    inputIsRequired({
      type: "king_square",
      prompt: "k",
      answer: "e1",
      expectedAnswerType: "square",
      allowsEmptyAnswer: false,
    }),
    true,
  );
  assert.equal(inputIsRequired(fallbackQ), false);
});

test("isFallbackQuestion is true only for no_more_questions", () => {
  assert.equal(isFallbackQuestion(fallbackQ), true);
  assert.equal(isFallbackQuestion(pinnedEmpty), false);
  assert.equal(isFallbackQuestion(q), false);
});

test("answerPayload accepts empty user answer when allowsEmptyAnswer is true", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: pinnedEmpty,
  });
  const body = answerPayload(s, "");
  assert.equal(body?.user_answer, "");
  assert.equal(body?.was_correct, true);
  s = answerQuestion(s, "");
  assert.equal(s.lastFeedback, "correct");
  assert.equal(s.pendingQuestion, null);
});

test("empty answer is incorrect when the list is not empty", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    status: "ongoing",
    question: pinnedSome,
  });
  assert.equal(answerPayload(s, "")?.was_correct, false);
  s = answerQuestion(s, "");
  assert.equal(s.lastFeedback, "incorrect");
});

test("answerQuestion advances the batch on no_more_questions", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    questions: [fallbackQ, { type: "in_check", prompt: "jaque?", answer: false, expectedAnswerType: "boolean" }],
  });
  assert.equal(s.pendingQuestion?.type, "no_more_questions");
  s = answerQuestion(s, "");
  assert.equal(s.lastFeedback, "correct");
  assert.equal(s.pendingQuestion?.type, "in_check");
  assert.equal(s.pendingQuestions.length, 1);
  assert.deepEqual(s.history, ["e4"]);
});

test("promptForLocale prefers promptEn in English and prompt in Spanish", () => {
  const qEn = {
    type: "in_check",
    prompt: "¿Está el rey en jaque?",
    promptEn: "Is the king in check?",
    answer: false,
  };
  assert.equal(promptForLocale(qEn, "en"), "Is the king in check?");
  assert.equal(promptForLocale(qEn, "es"), "¿Está el rey en jaque?");
  assert.equal(promptForLocale({ type: "x", prompt: "solo es", answer: 0 }, "en"), "solo es");
});

test("promptForLocale builds English from type when the API omitted promptEn", () => {
  assert.equal(
    promptForLocale(
      {
        type: "in_check",
        prompt: "¿Está el rey del bando en turno actualmente en jaque? Responde sí o no.",
        answer: false,
      },
      "en",
    ),
    "Is the side to move's king currently in check? Answer yes or no.",
  );
  assert.match(
    promptForLocale(
      {
        type: "king_square",
        prompt: "¿En qué casilla está el rey de las negras? (una casilla, p. ej. e1)",
        answer: "e8",
      },
      "en",
    ),
    /Black king/,
  );
  assert.match(
    promptForLocale(
      {
        type: "piece_at_square",
        prompt: "¿Qué pieza hay en c8? Usa el símbolo FEN (KQRBNPkqrbnp). Si está vacía, deja la respuesta vacía.",
        answer: "q",
      },
      "en",
    ),
    /piece is on c8/i,
  );
});

test("answerPayload persists the English short prompt when locale is en", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: {
      type: "legal_moves_for_piece",
      prompt: "¿Cuántos movimientos legales tiene la pieza en c8?",
      promptShort: "Movimientos legales en c8",
      promptEn: "How many legal moves does the piece on c8 have?",
      promptShortEn: "Legal moves from c8",
      answer: 0,
      expectedAnswerType: "number",
    },
  });
  assert.equal(answerPayload(s, "0")?.question_text, "Movimientos legales en c8");
  assert.equal(answerPayload(s, "0", "en")?.question_text, "Legal moves from c8");
  const noEn = {
    ...s,
    pendingQuestion: {
      type: "in_check",
      prompt: "¿Está el rey del bando en turno actualmente en jaque? Responde sí o no.",
      promptShort: "Rey en turno en jaque",
      answer: false,
      expectedAnswerType: "boolean" as const,
    },
  };
  assert.equal(answerPayload(noEn, "no", "en")?.question_text, "Side to move in check");
});

test("score accepts English colour and line words", () => {
  let s = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s = applyMoveOk(s, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: {
      type: "square_color",
      prompt: "color?",
      answer: "clara",
      expectedAnswerType: "piece_symbol",
    },
  });
  s = answerQuestion(s, "light");
  assert.equal(s.lastFeedback, "correct");

  let s2 = seedFromCreate({
    game_id: "g1",
    maia_level: 1900,
    player_color: "white",
    status: "ongoing",
  });
  s2 = applyMoveOk(s2, {
    applied: "e4",
    maia_move: "e5",
    status: "ongoing",
    question: {
      type: "alignment",
      prompt: "lines?",
      answer: ["fila", "diagonal"],
      expectedAnswerType: "square_list",
    },
  });
  s2 = answerQuestion(s2, "rank, diagonal");
  assert.equal(s2.lastFeedback, "correct");
});

