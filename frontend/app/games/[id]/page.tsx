"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ChessBoardView } from "../../../components/ChessBoardView";
import { HomeLink } from "../../../components/HomeLink";
import { downloadGamePgn, getGame, pgnFilename, saveTextAs } from "../../../lib/api";
import {
  canShowBoard,
  eventsAtPly,
  fensFromPgn,
  moveTokensFromPgn,
  nextPly,
  parseDetail,
  prevPly,
  replayHeader,
  type GameDetail,
} from "../../../lib/replay-session";

export default function ReplayPage() {
  const t = useTranslations("replay");
  const common = useTranslations("common");
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [ply, setPly] = useState(0);
  const [fens, setFens] = useState<string[]>([]);
  const [mobileTab, setMobileTab] = useState<"q" | "moves">("q");

  useEffect(() => {
    getGame(id)
      .then(({ status, body }) => {
        if (status === 404) {
          setError(t("notFound"));
          setDetail(null);
          return;
        }
        if (status !== 200) {
          setError(t("openError"));
          setDetail(null);
          return;
        }
        const parsed = parseDetail(body);
        if (!parsed) {
          setError(t("notFound"));
          setDetail(null);
          return;
        }
        setDetail(parsed);
        if (canShowBoard(parsed.status)) {
          setFens(fensFromPgn(parsed.pgn));
          setPly(0);
        }
      })
      .catch(() => {
        setError(common("connectError"));
        setDetail(null);
      });
  }, [id, t, common]);

  const last = Math.max(0, fens.length - 1);

  const onKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") setPly((p) => prevPly(p));
      if (e.key === "ArrowRight") setPly((p) => nextPly(p, last));
    },
    [last],
  );

  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);

  async function onDownload() {
    if (!detail) return;
    const { status, text } = await downloadGamePgn(detail.id);
    if (status !== 200) return;
    saveTextAs(text, pgnFilename(detail.createdAt, detail.result));
  }

  if (detail === undefined) return null;

  const showBoard = detail !== null && canShowBoard(detail.status) && fens.length > 0;
  const plyEvents = detail ? eventsAtPly(detail.events, ply) : [];
  const tokens = detail ? moveTokensFromPgn(detail.pgn) : [];

  const questionsPanel = (
    <section className="replay-panel" aria-label={t("questionsAria")}>
      <h2 className="replay-panel-title">{t("questionsTitle")}</h2>
      {plyEvents.length === 0 ? (
        <p className="muted">{t("noQuestion")}</p>
      ) : (
        plyEvents.map((ev) =>
          ev.eventType === "peek" ? (
            <div key={ev.id} className="replay-qa">
              <p className="muted">{t("peekUsed")}</p>
            </div>
          ) : (
            <div key={ev.id} className="replay-qa">
              <p>{ev.questionText}</p>
              <p className="muted">{t("answer", { value: ev.userAnswer ?? "—" })}</p>
              {ev.wasCorrect === false && (
                <p className="muted">{t("expectedAnswer", { value: ev.correctAnswer ?? "—" })}</p>
              )}
            </div>
          ),
        )
      )}
    </section>
  );

  const movesPanel = (
    <section className="replay-panel" aria-label={t("movesAria")}>
      <h2 className="replay-panel-title">{t("movesTitle")}</h2>
      <div className="movetext">
        {tokens.map((tok, i) =>
          tok.kind === "num" ? (
            <span key={`${tok.ply}-n-${i}`} className="movetext-num">
              {tok.text}
            </span>
          ) : (
            <button
              key={`${tok.ply}-s-${i}`}
              type="button"
              className={`movetext-san${tok.ply === ply ? " active" : ""}`}
              onClick={() => setPly(tok.ply)}
            >
              {tok.text}
            </button>
          ),
        )}
      </div>
    </section>
  );

  return (
    <main className="shell shell-replay">
      <HomeLink />
      <div className="topbar">
        <div>
          <p className="kicker">
            <Link href="/games">{common("games")}</Link>
            {" · "}
            <Link href="/">{t("newShort")}</Link>
          </p>
          <h1>{t("title")}</h1>
        </div>
        {detail && (
          <p className="level-chip">{replayHeader(detail.maiaLevel, detail.result)}</p>
        )}
      </div>

      {error && <p className="alert">{error}</p>}

      {detail && detail.status === "ongoing" && (
        <>
          <p className="muted">{t("ongoing")}</p>
          <p>
            <Link href={`/play/${id}`}>{t("continue")}</Link>
          </p>
        </>
      )}

      {showBoard && detail && (
        <>
          <div className="replay-grid">
            <div className="replay-side replay-side-q">{questionsPanel}</div>
            <div className="replay-center">
              <ChessBoardView fen={fens[ply]} orientation={detail.playerColor} />
            </div>
            <div className="replay-side replay-side-moves">{movesPanel}</div>
          </div>

          <div className="replay-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mobileTab === "q"}
              className={mobileTab === "q" ? "active" : ""}
              onClick={() => setMobileTab("q")}
            >
              {t("questionsTab")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mobileTab === "moves"}
              className={mobileTab === "moves" ? "active" : ""}
              onClick={() => setMobileTab("moves")}
            >
              {t("movesTab")}
            </button>
          </div>
          <div className="replay-mobile-panel">
            {mobileTab === "q" ? questionsPanel : movesPanel}
          </div>

          <div className="replay-nav">
            <button
              type="button"
              className="icon-nav"
              aria-label={t("prev")}
              onClick={() => setPly((p) => prevPly(p))}
              disabled={ply <= 0}
            >
              ‹
            </button>
            <button
              type="button"
              className="icon-nav"
              aria-label={t("downloadPgn")}
              onClick={onDownload}
            >
              ↓
            </button>
            <button
              type="button"
              className="icon-nav"
              aria-label={t("next")}
              onClick={() => setPly((p) => nextPly(p, last))}
              disabled={ply >= last}
            >
              ›
            </button>
          </div>
        </>
      )}
    </main>
  );
}
