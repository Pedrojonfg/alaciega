"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { getGame, postAnswer, postMove, postPeek, postResign } from "../../../lib/api";
import {
  applyMoveError,
  applyMoveOk,
  applyPeek,
  applyResign,
  answerPayload,
  answerQuestion,
  batchProgress,
  canTypeMove,
  inputIsRequired,
  isFallbackQuestion,
  formatHistory,
  resumeFromGet,
  stashSession,
  takeSession,
  promptForLocale,
  type Question,
  type Session,
} from "../../../lib/play-session";
import { ChessBoardView } from "../../../components/ChessBoardView";
import { HomeLink } from "../../../components/HomeLink";

type ApiBody = {
  applied?: string;
  maia_move?: string;
  status?: "ongoing" | "finished";
  result?: string;
  question?: Question;
  questions?: Question[];
  suggest_peek?: boolean;
  consecutive_fails?: number;
  total_fails?: number;
  error?: string;
  ok?: boolean;
};

export default function PlayPage() {
  const t = useTranslations("play");
  const common = useTranslations("common");
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [moveText, setMoveText] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [peekFen, setPeekFen] = useState<string | null>(null);
  const [peekLeft, setPeekLeft] = useState(0);

  useEffect(() => {
    const stashed = takeSession(id);
    if (stashed) {
      setSession(stashed);
      return;
    }
    let cancelled = false;
    getGame(id)
      .then(({ status, body }) => {
        if (cancelled) return;
        if (status === 404) {
          setLoadError(t("notFound"));
          return;
        }
        const loaded = resumeFromGet(body);
        if (loaded === "finished") {
          router.replace(`/games/${id}`);
          return;
        }
        if (!loaded) {
          setLoadError(t("notFound"));
          return;
        }
        setSession(loaded);
      })
      .catch(() => {
        if (!cancelled) setLoadError(common("connectError"));
      });
    return () => {
      cancelled = true;
    };
  }, [id, router, t, common]);

  useEffect(() => {
    if (!peekFen) return;
    if (peekLeft <= 0) {
      setPeekFen(null);
      return;
    }
    const t = window.setTimeout(() => setPeekLeft((n) => n - 1), 1000);
    return () => window.clearTimeout(t);
  }, [peekFen, peekLeft]);

  function commit(next: Session) {
    stashSession(next);
    setSession(next);
  }

  async function onMove(e: FormEvent) {
    e.preventDefault();
    if (!session || !canTypeMove(session, busy)) return;
    setBusy(true);
    try {
      const { status, body } = await postMove(session.gameId, moveText);
      const payload = body as ApiBody;
      if (status === 200 && payload.applied) {
        commit(
          applyMoveOk(session, {
            applied: payload.applied,
            maia_move: payload.maia_move,
            status: payload.status ?? "ongoing",
            result: payload.result,
            question: payload.question,
            questions: payload.questions,
            suggest_peek: payload.suggest_peek,
          }),
        );
        setMoveText("");
      } else {
        commit(applyMoveError(session, payload.error ?? t("moveError")));
      }
    } catch {
      commit(applyMoveError(session, common("connectError")));
    } finally {
      setBusy(false);
    }
  }

  function onAnswer(raw: string) {
    if (!session?.pendingQuestion) return;
    const payload = answerPayload(session, raw, locale);
    commit(answerQuestion(session, raw));
    setAnswer("");
    if (payload) {
      void postAnswer(session.gameId, payload);
    }
  }

  async function onPeek() {
    if (!session || session.status !== "ongoing" || busy || peekFen) return;
    if ((session.peeksRemaining ?? 0) <= 0) return;
    setBusy(true);
    try {
      const { status, body } = await postPeek(session.gameId);
      const payload = body as ApiBody & { fen?: string; peeks_remaining?: number; seconds?: number };
      if (status === 200 && payload.fen) {
        commit(
          applyPeek(session, payload.peeks_remaining ?? 0, {
            consecutiveFails: payload.consecutive_fails,
            totalFails: payload.total_fails,
            suggestPeek: payload.suggest_peek,
          }),
        );
        setPeekFen(payload.fen);
        setPeekLeft(payload.seconds ?? 10);
      } else {
        commit(applyMoveError(session, payload.error ?? t("peekError")));
      }
    } catch {
      commit(applyMoveError(session, common("connectError")));
    } finally {
      setBusy(false);
    }
  }

  async function onResign() {
    if (!session || session.status !== "ongoing" || busy) return;
    setBusy(true);
    try {
      const { status, body } = await postResign(session.gameId);
      const payload = body as ApiBody;
      if (status === 200 && payload.result) {
        commit(applyResign(session, payload.result));
      } else {
        commit(applyMoveError(session, payload.error ?? t("resignError")));
      }
    } catch {
      commit(applyMoveError(session, common("connectError")));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <main className="shell">
        <HomeLink />
        <p className="kicker">
          <Link href="/games">{common("games")}</Link>
        </p>
        <h1>{t("title")}</h1>
        <p className="alert">{loadError}</p>
      </main>
    );
  }

  if (!session) return null;

  const q = session.pendingQuestion;
  const finished = session.status === "finished";
  const progress = batchProgress(session);
  const shape = q?.expectedAnswerType ?? (q?.type === "in_check" ? "boolean" : "number");

  return (
    <main className="shell">
      <HomeLink />
      <div className="topbar">
        <div>
          <p className="kicker">
            <Link href="/">{common("newGame")}</Link>
            {" · "}
            <Link href="/games">{common("games")}</Link>
          </p>
          <h1>{t("title")}</h1>
        </div>
        {session.maiaLevel > 0 && <p className="level-chip">Maia {session.maiaLevel}</p>}
      </div>

      <p className="history" aria-live="polite">
        {formatHistory(session.history) || t("noMoves")}
      </p>

      {session.lastFeedback && (
        <p className={`feedback ${session.lastFeedback === "correct" ? "ok" : "bad"}`}>
          {session.lastFeedback === "correct" ? t("correct") : t("incorrect")}
        </p>
      )}

      {q && (
        <form
          className="question"
          onSubmit={(e) => {
            e.preventDefault();
            onAnswer(answer);
          }}
        >
          {progress && (
            <p className="muted">
              {t("questionProgress", { current: progress.current, total: progress.total })}
            </p>
          )}
          <p>{promptForLocale(q, locale)}</p>
          {isFallbackQuestion(q) ? (
            <div className="move-row">
              <button type="button" className="primary" onClick={() => onAnswer("")}>
                {t("continue")}
              </button>
            </div>
          ) : shape === "boolean" ? (
            <div className="choice-row">
              <button type="button" className="primary" onClick={() => onAnswer("sí")}>
                {t("yes")}
              </button>
              <button type="button" className="ghost" onClick={() => onAnswer("no")}>
                {t("no")}
              </button>
            </div>
          ) : (
            <div className="move-row">
              <input
                type={shape === "number" ? "number" : "text"}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                aria-label={t("answerLabel")}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                required={inputIsRequired(q)}
              />
              <button className="primary" type="submit">
                {t("answerButton")}
              </button>
            </div>
          )}
        </form>
      )}

      {session.status === "ongoing" && !q && (
        <form className="stack" onSubmit={onMove}>
          <label className="field">
            <span>{t("moveLabel")}</span>
            <div className="move-row">
              <input
                type="text"
                value={moveText}
                onChange={(e) => setMoveText(e.target.value)}
                placeholder={t("movePlaceholder")}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                aria-label={t("moveLabel")}
                disabled={busy}
              />
              <button className="primary" type="submit" disabled={busy || !moveText.trim()}>
                {busy ? t("playing") : t("playButton")}
              </button>
            </div>
          </label>
        </form>
      )}

      {session.error && <p className="alert">{session.error}</p>}

      {peekFen && (
        <>
          <ChessBoardView fen={peekFen} orientation={session.playerColor} />
          <p className="muted">{peekLeft}s</p>
          <p className="actions">
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setPeekFen(null);
                setPeekLeft(0);
              }}
            >
              {t("closePeek")}
            </button>
          </p>
        </>
      )}

      {finished && (
        <p className="muted">
          {t("finished")}
          {session.result ? ` · ${session.result}` : ""}.{" "}
          <Link href={`/games/${session.gameId}`}>{t("viewBoard")}</Link>
        </p>
      )}

      {session.status === "ongoing" && (
        <p className="actions">
          <button
            type="button"
            className={session.suggestPeek ? "ghost suggest" : "ghost"}
            onClick={onPeek}
            disabled={busy || !!peekFen || (session.peeksRemaining ?? 0) <= 0}
          >
            {t("peekBoard", { count: session.peeksRemaining ?? 0 })}
          </button>
          {!q && (
            <button type="button" className="ghost" onClick={onResign} disabled={busy}>
              {t("resign")}
            </button>
          )}
        </p>
      )}
      {session.status === "ongoing" && session.suggestPeek && !peekFen && (
        <p className="muted">{t("suggestPeek")}</p>
      )}
    </main>
  );
}
