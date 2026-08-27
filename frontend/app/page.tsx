"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createGame, getLevels } from "../lib/api";
import {
  canSubmit,
  clampRange,
  parseLevels,
  MOVES_INTERVAL,
  QUESTIONS_PER_BATCH,
} from "../lib/new-game";
import { seedFromCreate, stashSession } from "../lib/play-session";

export default function HomePage() {
  const t = useTranslations("newGame");
  const common = useTranslations("common");
  const router = useRouter();
  const [levels, setLevels] = useState<number[]>([]);
  const [level, setLevel] = useState<number | null>(null);
  const [color, setColor] = useState<"white" | "black">("white");
  const [questions, setQuestions] = useState(QUESTIONS_PER_BATCH.default);
  const [moves, setMoves] = useState(MOVES_INTERVAL.default);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getLevels()
      .then(({ status, body }) => {
        if (status !== 200) {
          setError(t("levelsLoadError"));
          return;
        }
        const next = parseLevels(body);
        setLevels(next);
        setLevel(next.includes(1900) ? 1900 : (next[0] ?? null));
      })
      .catch(() => setError(common("connectError")))
      .finally(() => setLoaded(true));
  }, [t, common]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit(levels, level, busy) || level == null) return;
    setBusy(true);
    setError(null);
    try {
      const { status, body } = await createGame(color, level, {
        questions_per_batch: questions,
        moves_interval: moves,
      });
      const payload = body as {
        game_id?: string;
        maia_level?: number;
        status?: "ongoing" | "finished";
        maia_move?: string;
        error?: string;
      };
      if (status !== 200 || !payload.game_id) {
        setError(payload.error ?? t("createError"));
        return;
      }
      const session = seedFromCreate({
        game_id: payload.game_id,
        maia_level: payload.maia_level ?? level,
        player_color: color,
        status: payload.status ?? "ongoing",
        maia_move: payload.maia_move,
      });
      stashSession(session);
      router.push(`/play/${payload.game_id}`);
    } catch {
      setError(common("connectError"));
    } finally {
      setBusy(false);
    }
  }

  const empty = loaded && levels.length === 0 && !error;

  return (
    <main className="shell">
      <p className="kicker">{t("kicker")}</p>
      <h1 className="hero">alaciega</h1>
      <p className="lede">{t("lede")}</p>
      <form className="stack" onSubmit={onSubmit}>
        <fieldset className="field">
          <legend>{t("colorLabel")}</legend>
          <div className="colors">
            <label>
              <input
                type="radio"
                name="color"
                value="white"
                checked={color === "white"}
                onChange={() => setColor("white")}
              />
              {t("white")}
            </label>
            <label>
              <input
                type="radio"
                name="color"
                value="black"
                checked={color === "black"}
                onChange={() => setColor("black")}
              />
              {t("black")}
            </label>
          </div>
        </fieldset>
        <label className="field">
          <span>{t("levelLabel")}</span>
          <select
            value={level ?? ""}
            onChange={(e) => setLevel(e.target.value ? Number(e.target.value) : null)}
            disabled={!levels.length}
          >
            {!levels.length && <option value="">—</option>}
            {levels.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>
            {t("questionsPerBatch")}: {questions}
          </span>
          <input
            type="range"
            min={QUESTIONS_PER_BATCH.min}
            max={QUESTIONS_PER_BATCH.max}
            step={1}
            value={questions}
            onChange={(e) => setQuestions(clampRange(QUESTIONS_PER_BATCH, Number(e.target.value)))}
          />
        </label>
        <label className="field">
          <span>
            {t("movesInterval")}: {moves}
          </span>
          <input
            type="range"
            min={MOVES_INTERVAL.min}
            max={MOVES_INTERVAL.max}
            step={1}
            value={moves}
            onChange={(e) => setMoves(clampRange(MOVES_INTERVAL, Number(e.target.value)))}
          />
        </label>
        {empty && <p className="muted">{t("emptyLevels")}</p>}
        {error && <p className="alert">{error}</p>}
        <button className="primary" type="submit" disabled={!canSubmit(levels, level, busy)}>
          {busy ? (color === "black" ? t("maiaThinking") : t("starting")) : t("startButton")}
        </button>
      </form>
      <p className="actions">
        <Link href="/games">{common("games")}</Link>
      </p>
    </main>
  );
}
