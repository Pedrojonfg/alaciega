import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { authorize, upstream } from "./proxy.ts";

test("authorize sets Bearer and skips empty token", () => {
  const h = new Headers();
  authorize(h, "secret");
  assert.equal(h.get("Authorization"), "Bearer secret");
  const empty = new Headers();
  authorize(empty, "");
  assert.equal(empty.get("Authorization"), null);
});

test("upstream joins API base and path parts", () => {
  assert.equal(upstream("http://127.0.0.1:8000", ["games", "abc", "move"]), "http://127.0.0.1:8000/games/abc/move");
  assert.equal(upstream("http://127.0.0.1:8000/", ["health"]), "http://127.0.0.1:8000/health");
});

test("proxy route exports DELETE", () => {
  const src = readFileSync(new URL("../app/api/proxy/[...path]/route.ts", import.meta.url), "utf8");
  assert.match(src, /export async function DELETE/);
});
