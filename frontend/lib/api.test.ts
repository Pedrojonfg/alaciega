import { test } from "node:test";
import assert from "node:assert/strict";
import { apiUrl, createGame, deleteGame, downloadGamePgn, pgnFilename } from "./api.ts";

test("apiUrl prefixes the same-origin backend proxy", () => {
  assert.equal(apiUrl("/maia/levels"), "/api/proxy/maia/levels");
  assert.equal(apiUrl("/games/abc/resign"), "/api/proxy/games/abc/resign");
  assert.equal(apiUrl("/games/abc/answer"), "/api/proxy/games/abc/answer");
  assert.equal(apiUrl("/games/abc/peek"), "/api/proxy/games/abc/peek");
  assert.equal(apiUrl("/games"), "/api/proxy/games");
});

test("deleteGame sends DELETE to the game path", async () => {
  const orig = globalThis.fetch;
  const seen: { url?: string | URL; method?: string } = {};
  globalThis.fetch = async (url, init) => {
    seen.url = url as string;
    seen.method = init?.method;
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  try {
    const r = await deleteGame("abc");
    assert.equal(seen.method, "DELETE");
    assert.equal(seen.url, "/api/proxy/games/abc");
    assert.equal(r.status, 200);
    assert.deepEqual(r.body, { ok: true });
  } finally {
    globalThis.fetch = orig;
  }
});

test("createGame sends the verification sliders as snake_case fields", async () => {
  const orig = globalThis.fetch;
  let sent = "";
  globalThis.fetch = async (_url, init) => {
    sent = String(init?.body ?? "");
    return new Response(JSON.stringify({ game_id: "g1" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  try {
    await createGame("black", 1100, { questions_per_batch: 0, moves_interval: 5 });
    assert.deepEqual(JSON.parse(sent), {
      player_color: "black",
      maia_level: 1100,
      questions_per_batch: 0,
      moves_interval: 5,
    });
    await createGame("white", 1900);
    assert.deepEqual(JSON.parse(sent), { player_color: "white", maia_level: 1900 });
  } finally {
    globalThis.fetch = orig;
  }
});

test("downloadGamePgn returns raw text, not json", async () => {
  const orig = globalThis.fetch;
  const seen: { url?: string } = {};
  const pgn = '[Event "alaciega"]\n\n1. e4 e5 1-0\n';
  globalThis.fetch = async (url) => {
    seen.url = url as string;
    return new Response(pgn, {
      status: 200,
      headers: { "content-type": "application/x-chess-pgn" },
    });
  };
  try {
    const r = await downloadGamePgn("abc");
    assert.equal(seen.url, "/api/proxy/games/abc/pgn");
    assert.equal(r.status, 200);
    assert.equal(r.text, pgn);
  } finally {
    globalThis.fetch = orig;
  }
});

test("downloadGamePgn surfaces the 409 of an ongoing game", async () => {
  const orig = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "partida en curso" }), { status: 409 });
  try {
    const r = await downloadGamePgn("abc");
    assert.equal(r.status, 409);
  } finally {
    globalThis.fetch = orig;
  }
});

test("pgnFilename suggests origin, date and result", () => {
  assert.equal(pgnFilename("2026-08-26T10:12:00", "1-0"), "alaciega_20260826_1-0.pgn");
  assert.equal(pgnFilename("2026-01-02T00:00:00", "1/2-1/2"), "alaciega_20260102_1-2-1-2.pgn");
  assert.equal(pgnFilename("2026-01-02T00:00:00", null), "alaciega_20260102_final.pgn");
});

test("deleteGame surfaces 404 without throwing", async () => {
  const orig = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "partida no encontrada" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
  try {
    const r = await deleteGame("missing");
    assert.equal(r.status, 404);
    assert.deepEqual(r.body, { error: "partida no encontrada" });
  } finally {
    globalThis.fetch = orig;
  }
});
