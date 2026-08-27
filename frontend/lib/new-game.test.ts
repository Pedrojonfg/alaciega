import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseLevels,
  canSubmit,
  clampRange,
  QUESTIONS_PER_BATCH,
  MOVES_INTERVAL,
} from "./new-game.ts";

test("parseLevels copies the live catalog and drops junk", () => {
  assert.deepEqual(parseLevels({ levels: [1100, 1500, 1900] }), [1100, 1500, 1900]);
  assert.deepEqual(parseLevels({ levels: [] }), []);
  assert.deepEqual(parseLevels({ levels: [1100, "x", 1900] }), [1100, 1900]);
  assert.deepEqual(parseLevels({}), []);
  assert.deepEqual(parseLevels(null), []);
});

test("canSubmit requires a listed level and idle form", () => {
  const levels = [1100, 1900];
  assert.equal(canSubmit(levels, 1900, false), true);
  assert.equal(canSubmit(levels, 1200, false), false);
  assert.equal(canSubmit(levels, 1900, true), false);
  assert.equal(canSubmit([], 1900, false), false);
  assert.equal(canSubmit(levels, null, false), false);
});

test("verification ranges match the spec defaults", () => {
  assert.deepEqual(QUESTIONS_PER_BATCH, { min: 0, max: 10, default: 2 });
  assert.deepEqual(MOVES_INTERVAL, { min: 1, max: 20, default: 3 });
});

test("clampRange keeps slider values inside the range", () => {
  assert.equal(clampRange(QUESTIONS_PER_BATCH, 0), 0);
  assert.equal(clampRange(QUESTIONS_PER_BATCH, -4), 0);
  assert.equal(clampRange(QUESTIONS_PER_BATCH, 99), 10);
  assert.equal(clampRange(MOVES_INTERVAL, 0), 1);
  assert.equal(clampRange(MOVES_INTERVAL, 7.6), 8);
  assert.equal(clampRange(MOVES_INTERVAL, Number.NaN), 3);
});
