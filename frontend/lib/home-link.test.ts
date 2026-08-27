import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const HOME = "../app/page.tsx";
const SCREENS_WITH_HOME_LINK = [
  "../app/play/[id]/page.tsx",
  "../app/games/page.tsx",
  "../app/games/[id]/page.tsx",
];
const COPY = [HOME, ...SCREENS_WITH_HOME_LINK, "../app/layout.tsx", "../app/manifest.ts"];

function read(rel: string) {
  return readFileSync(new URL(rel, import.meta.url), "utf8");
}

test("no visible copy says 'a ciegas' or 'a la ciega'", () => {
  for (const rel of COPY) {
    assert.doesNotMatch(read(rel), /a\s+(la\s+)?ciega/i, rel);
  }
  assert.match(read("../app/layout.tsx"), /getTranslations\("meta"\)/);
  assert.match(read("../messages/en.json"), /alaciega/);
  assert.match(read("../app/manifest.ts"), /alaciega/);
  assert.match(read("../app/page.tsx"), /alaciega/);
});

test("the home screen does not render the home link", () => {
  assert.doesNotMatch(read(HOME), /<HomeLink \/>/);
});

test("play, list, and replay render the home link", () => {
  for (const rel of SCREENS_WITH_HOME_LINK) {
    assert.match(read(rel), /<HomeLink \/>/, rel);
  }
  const component = read("../components/HomeLink.tsx");
  assert.match(component, /href="\/"/);
  assert.match(component, /t\("home"\)/);
  assert.match(read("../app/globals.css"), /\.home-link\s*\{[^}]*position:\s*fixed/);
});
