import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseAcceptLanguage, resolveLocale, isLocale, DEFAULT_LOCALE, COOKIE_NAME } from "./locale.ts";

test("isLocale accepts only en and es", () => {
  assert.equal(isLocale("en"), true);
  assert.equal(isLocale("es"), true);
  assert.equal(isLocale("fr"), false);
  assert.equal(isLocale("en-US"), false);
  assert.equal(isLocale(""), false);
});

test("parseAcceptLanguage picks the first supported tag by q", () => {
  assert.equal(parseAcceptLanguage("es-ES,es;q=0.9,en;q=0.8"), "es");
  assert.equal(parseAcceptLanguage("en-US,en;q=0.9"), "en");
  assert.equal(parseAcceptLanguage("fr-FR,fr;q=0.9,en;q=0.8"), "en");
  assert.equal(parseAcceptLanguage("fr,de;q=0.8"), null);
  assert.equal(parseAcceptLanguage(null), null);
  assert.equal(parseAcceptLanguage(""), null);
  assert.equal(parseAcceptLanguage("en;q=0.4,es;q=0.8"), "es");
});

test("resolveLocale: cookie beats Accept-Language beats default en", () => {
  assert.equal(resolveLocale("es", "en-US"), "es");
  assert.equal(resolveLocale("en", "es-ES"), "en");
  assert.equal(resolveLocale(undefined, "es-MX"), "es");
  assert.equal(resolveLocale(undefined, "fr-FR"), DEFAULT_LOCALE);
  assert.equal(resolveLocale("fr", "es"), "es");
  assert.equal(resolveLocale(undefined, null), "en");
  assert.equal(DEFAULT_LOCALE, "en");
  assert.equal(COOKIE_NAME, "NEXT_LOCALE");
});

function keysOf(obj: unknown, prefix = ""): string[] {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [prefix];
  const entries = Object.entries(obj as Record<string, unknown>);
  if (entries.length === 0) return [prefix];
  return entries.flatMap(([k, v]) => keysOf(v, prefix ? `${prefix}.${k}` : k));
}

test("next-intl plugin and request config are wired", () => {
  const root = resolve(import.meta.dirname, "..");
  const cfg = readFileSync(resolve(root, "next.config.ts"), "utf8");
  const req = readFileSync(resolve(root, "i18n/request.ts"), "utf8");
  assert.match(cfg, /createNextIntlPlugin/);
  assert.match(req, /getRequestConfig/);
  assert.match(req, /resolveLocale/);
  assert.match(req, /COOKIE_NAME/);
});

test("en and es catalogs share the same key tree and required namespaces", () => {
  const dir = resolve(import.meta.dirname, "../messages");
  const en = JSON.parse(readFileSync(resolve(dir, "en.json"), "utf8"));
  const es = JSON.parse(readFileSync(resolve(dir, "es.json"), "utf8"));
  const enKeys = keysOf(en).sort();
  const esKeys = keysOf(es).sort();
  assert.deepEqual(enKeys, esKeys);
  for (const ns of ["meta", "language", "common", "newGame", "play", "gamesList", "replay"]) {
    assert.ok(enKeys.some((k) => k === ns || k.startsWith(`${ns}.`)), ns);
  }
  assert.ok(enKeys.length > 20);
});
