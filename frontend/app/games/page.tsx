"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { deleteGame, downloadGamePgn, getGames, pgnFilename, saveTextAs } from "../../lib/api";
import { parseList, type ListGame } from "../../lib/replay-session";
import { playOrReplayHref } from "../../lib/play-session";
import { HomeLink } from "../../components/HomeLink";

export default function GamesPage() {
  const t = useTranslations("gamesList");
  const common = useTranslations("common");
  const [games, setGames] = useState<ListGame[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    getGames()
      .then(({ status, body }) => {
        if (status !== 200) {
          setError(t("loadError"));
          setGames([]);
          return;
        }
        setGames(parseList(body));
      })
      .catch(() => {
        setError(common("connectError"));
        setGames([]);
      });
  }, [t, common]);

  async function onDelete(id: string) {
    if (!confirm(t("deleteConfirm"))) return;
    setBusyId(id);
    try {
      const { status } = await deleteGame(id);
      if (status === 200) {
        setGames((gs) => (gs ? gs.filter((g) => g.id !== id) : gs));
      } else {
        setError(t("deleteError"));
      }
    } catch {
      setError(common("connectError"));
    } finally {
      setBusyId(null);
    }
  }

  async function onDownload(g: ListGame) {
    setBusyId(g.id);
    try {
      const { status, text } = await downloadGamePgn(g.id);
      if (status !== 200) {
        setError(t("downloadError"));
        return;
      }
      saveTextAs(text, pgnFilename(g.createdAt, g.result));
    } catch {
      setError(common("connectError"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="shell">
      <HomeLink />
      <p className="kicker">
        <Link href="/">{common("newGame")}</Link>
      </p>
      <h1>{t("title")}</h1>
      {error && <p className="alert">{error}</p>}
      {games && games.length === 0 && !error && <p className="muted">{t("empty")}</p>}
      {games && games.length > 0 && (
        <ul className="game-list">
          {games.map((g) => (
            <li key={g.id}>
              <Link href={playOrReplayHref(g.status, g.id)} className={`game-row ${g.status}`}>
                <span>{g.createdAt.slice(0, 10)}</span>
                <span>Maia {g.maiaLevel}</span>
                <span>{g.playerColor === "black" ? t("black") : t("white")}</span>
                <span>{g.status === "ongoing" ? t("ongoing") : (g.result ?? "—")}</span>
              </Link>
              {g.status === "finished" && (
                <button
                  type="button"
                  className="ghost"
                  aria-label={t("downloadPgn")}
                  title={t("downloadPgn")}
                  disabled={busyId === g.id}
                  onClick={() => onDownload(g)}
                >
                  ↓
                </button>
              )}
              <button
                type="button"
                className="ghost"
                disabled={busyId === g.id}
                onClick={() => onDelete(g.id)}
              >
                {t("delete")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
