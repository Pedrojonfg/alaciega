import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const action = readFileSync(new URL("../app/actions/set-locale.ts", import.meta.url), "utf8");
const toggle = readFileSync(new URL("../components/LanguageToggle.tsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("root layout provides next-intl and sets html lang from locale", () => {
  assert.match(layout, /NextIntlClientProvider/);
  assert.match(layout, /getLocale/);
  assert.match(layout, /lang=\{locale\}/);
  assert.match(layout, /<LanguageToggle/);
});

test("setLocale writes NEXT_LOCALE for one year and ignores junk", () => {
  assert.match(action, /"use server"/);
  assert.match(action, /COOKIE_NAME/);
  assert.match(action, /isLocale/);
  assert.match(action, /maxAge:\s*60 \* 60 \* 24 \* 365/);
  assert.match(action, /path:\s*"\/"/);
});

test("LanguageToggle is a client globe that refreshes after setLocale", () => {
  assert.match(toggle, /"use client"/);
  assert.match(toggle, /useTranslations\("language"\)/);
  assert.match(toggle, /setLocale/);
  assert.match(toggle, /router\.refresh/);
  assert.match(css, /\.lang-toggle/);
});

test("play posts sí/no protocol values while labels come from messages", () => {
  const play = readFileSync(new URL("../app/play/[id]/page.tsx", import.meta.url), "utf8");
  assert.match(play, /onAnswer\("sí"\)/);
  assert.match(play, /onAnswer\("no"\)/);
  assert.match(play, /t\("yes"\)/);
  assert.match(play, /t\("no"\)/);
  assert.match(play, /promptForLocale/);
  assert.match(play, /useLocale/);
});
