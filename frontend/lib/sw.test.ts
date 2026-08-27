import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sw = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

test("service worker uses v3 cache and network-first for documents and scripts", () => {
  assert.match(sw, /aciega-static-v3/);
  assert.doesNotMatch(sw, /aciega-static-v2/);
  assert.match(sw, /destination === "document"|destination === 'document'/);
  assert.match(sw, /destination === "script"|destination === 'script'/);
  assert.match(sw, /caches\.delete/);
});
