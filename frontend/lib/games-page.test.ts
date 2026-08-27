import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../app/games/page.tsx", import.meta.url), "utf8");

test("games list confirms before delete", () => {
  assert.match(page, /deleteGame/);
  assert.match(page, /t\("deleteConfirm"\)/);
  assert.match(page, /type="button"/);
  assert.match(page, /t\("delete"\)/);
});

test("games list offers the PGN download only on finished rows", () => {
  assert.match(page, /downloadGamePgn/);
  assert.match(page, /pgnFilename/);
  assert.match(page, /g\.status === "finished" &&/);
  assert.match(page, /t\("downloadPgn"\)/);
});
