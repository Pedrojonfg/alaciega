import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, extname } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === "messages" || name === "node_modules" || name.endsWith(".test.ts")) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (extname(p) === ".tsx") out.push(p);
  }
  return out;
}

const UI_LEAK =
  /Nueva partida|Empezar partida|Aún no hay|Maia está pensando|No se pudo conectar|Partidas"|Blancas|Negras|Rendirse|Cerrar ya|Te sugerimos|Descargar PGN|¿Borrar esta partida|Sin pregunta en esta jugada|Preguntas y respuestas/;

test("tsx screens do not leak Spanish UI copy outside messages", () => {
  const files = walk(join(ROOT, "app")).concat(walk(join(ROOT, "components")));
  assert.ok(files.length > 0);
  for (const file of files) {
    const src = readFileSync(file, "utf8");
    assert.doesNotMatch(src, UI_LEAK, file);
  }
});
