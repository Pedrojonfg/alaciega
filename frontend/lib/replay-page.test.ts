import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../app/games/[id]/page.tsx", import.meta.url), "utf8");

test("ongoing replay links to the play screen", () => {
  assert.match(page, /status === "ongoing"/);
  assert.match(page, /\/play\/\$\{id\}/);
});
