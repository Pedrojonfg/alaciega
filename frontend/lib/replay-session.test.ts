import { test } from "node:test";
import assert from "node:assert/strict";
import {
  canShowBoard,
  eventsAtPly,
  fensFromPgn,
  moveTokensFromPgn,
  nextPly,
  parseDetail,
  parseList,
  prevPly,
  questionEventsAtPly,
  replayHeader,
  toSpanishSan,
} from "./replay-session.ts";

test("toSpanishSan maps piece letters", () => {
  assert.equal(toSpanishSan("Nf3"), "Cf3");
  assert.equal(toSpanishSan("O-O"), "O-O");
  assert.equal(toSpanishSan("exd5"), "exd5");
  assert.equal(toSpanishSan("Qxe5+"), "Dxe5+");
  assert.equal(toSpanishSan("Rae1"), "Tae1");
  assert.equal(toSpanishSan("Bb5"), "Ab5");
  assert.equal(toSpanishSan("Kh1"), "Rh1");
});

test("moveTokensFromPgn pairs numbers and Spanish SANs", () => {
  const tokens = moveTokensFromPgn(`[Result "*"]\n\n1. e4 c5 2. Nf3 *`);
  assert.deepEqual(
    tokens.map((t) => t.text),
    ["1.", "e4", "c5", "2.", "Cf3"],
  );
  assert.equal(tokens[1].ply, 1);
  assert.equal(tokens[2].ply, 2);
  assert.equal(tokens[4].ply, 3);
});

test("replayHeader and questionEventsAtPly", () => {
  assert.equal(replayHeader(1200, "1-0"), "Maia 1200 · 1-0");
  assert.equal(replayHeader(1500, null), "Maia 1500");
  const events = [
    {
      id: "e1",
      plyNumber: 1,
      eventType: "question" as const,
      questionText: "Corta",
      correctAnswer: "0",
      userAnswer: "1",
      wasCorrect: false,
      createdAt: "t",
    },
    {
      id: "e2",
      plyNumber: 1,
      eventType: "peek" as const,
      questionText: null,
      correctAnswer: null,
      userAnswer: null,
      wasCorrect: null,
      createdAt: "t",
    },
  ];
  assert.equal(questionEventsAtPly(events, 1).length, 1);
  assert.equal(questionEventsAtPly(events, 1)[0].questionText, "Corta");
});

test("parseList copies rows and drops junk", () => {
  const rows = parseList({
    games: [
      {
        id: "a",
        created_at: "2026-08-24T00:00:00+00:00",
        player_color: "white",
        maia_level: 1900,
        status: "finished",
        result: "0-1",
      },
      { id: "skip" },
    ],
  });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, "a");
  assert.equal(rows[0].maiaLevel, 1900);
  assert.deepEqual(parseList({ games: [] }), []);
  assert.deepEqual(parseList(null), []);
});

test("parseDetail keeps pgn and fen only when present", () => {
  const ongoing = parseDetail({
    id: "g1",
    created_at: "t",
    player_color: "black",
    maia_level: 1100,
    status: "ongoing",
    result: null,
    pgn: "1. e4",
  });
  assert.equal(ongoing?.fenCurrent, null);
  assert.equal(ongoing?.pgn, "1. e4");
  const done = parseDetail({
    id: "g1",
    created_at: "t",
    player_color: "white",
    maia_level: 1500,
    status: "finished",
    result: "1-0",
    pgn: "1. e4 e5",
    fen_current: "fen",
  });
  assert.equal(done?.fenCurrent, "fen");
  assert.equal(parseDetail({ error: "partida no encontrada" }), null);
});

test("fensFromPgn includes start and each ply", () => {
  const pgn = `[Result "*"]\n\n1. e4 e5 *`;
  const fens = fensFromPgn(pgn);
  assert.equal(fens.length, 3);
  assert.ok(fens[0].startsWith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"));
  assert.ok(fens[1].includes("4P3"));
  assert.equal(fensFromPgn("not a pgn").length, 1);
});

test("next/prev clamp; board only when finished", () => {
  assert.equal(nextPly(0, 2), 1);
  assert.equal(nextPly(2, 2), 2);
  assert.equal(prevPly(0), 0);
  assert.equal(prevPly(1), 0);
  assert.equal(canShowBoard("finished"), true);
  assert.equal(canShowBoard("ongoing"), false);
});

test("parseDetail keeps events; eventsAtPly filters by ply", () => {
  const done = parseDetail({
    id: "g1",
    created_at: "t",
    player_color: "white",
    maia_level: 1500,
    status: "finished",
    result: "1-0",
    pgn: "1. e4 e5",
    fen_current: "fen",
    events: [
      {
        id: "e1",
        ply_number: 1,
        event_type: "question",
        question_text: "¿Cuántas capturas legales tiene el jugador en turno?",
        correct_answer: "0",
        user_answer: "2",
        was_correct: false,
        created_at: "t1",
      },
      {
        id: "e2",
        ply_number: 2,
        event_type: "peek",
        question_text: null,
        correct_answer: null,
        user_answer: null,
        was_correct: null,
        created_at: "t2",
      },
    ],
  });
  assert.equal(done?.events.length, 2);
  assert.equal(done?.events[0].plyNumber, 1);
  assert.equal(done?.events[0].eventType, "question");
  assert.equal(done?.events[0].wasCorrect, false);
  const at1 = eventsAtPly(done!.events, 1);
  assert.equal(at1.length, 1);
  assert.equal(at1[0].userAnswer, "2");
  assert.equal(eventsAtPly(done!.events, 2)[0].eventType, "peek");
  assert.deepEqual(eventsAtPly(done!.events, 0), []);
  const ongoing = parseDetail({
    id: "g1",
    created_at: "t",
    player_color: "black",
    maia_level: 1100,
    status: "ongoing",
    result: null,
    pgn: "1. e4",
  });
  assert.deepEqual(ongoing?.events, []);
});
