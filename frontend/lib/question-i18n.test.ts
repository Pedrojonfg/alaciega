import { test } from "node:test";
import assert from "node:assert/strict";
import { englishPrompt, englishShort } from "./question-i18n.ts";

test("static kinds translate without promptEn", () => {
  const q = { type: "captures", prompt: "¿Cuántas capturas legales tiene el jugador en turno (el bando que mueve ahora)?" };
  assert.match(englishPrompt(q), /legal captures/i);
  assert.match(englishShort(q), /Legal captures/);
});

test("parameterized kinds keep squares, colour and files", () => {
  assert.match(
    englishPrompt({
      type: "pawns_on_file",
      prompt: "¿Cuántos peones tienen las negras en la columna d?",
    }),
    /Black pawns are on the d-file/,
  );
  assert.match(
    englishPrompt({
      type: "castling_rights",
      prompt: "¿Pueden las blancas (bando en turno) enrocar largo? Responde sí o no.",
    }),
    /White.*queenside/,
  );
  assert.match(
    englishPrompt({
      type: "draw_conditions",
      prompt: "¿Hay ahogado en esta posición? Responde sí o no.",
    }),
    /stalemate/,
  );
  assert.equal(
    englishShort({ type: "alignment", prompt: "¿En qué líneas coinciden a3 y f6? Lista fila, columna y/o diagonal." }),
    "Alignment a3-f6",
  );
});
