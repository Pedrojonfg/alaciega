import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import chess
import chess.pgn

from backend.questions import DEFAULT_ENABLED, evaluate, generate_batch

START_FEN = chess.STARTING_FEN
PEEK_MAX = 3
PEEK_SECONDS = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    player_color TEXT NOT NULL,
    maia_level INTEGER NOT NULL,
    pgn TEXT NOT NULL,
    fen_current TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    verification_json TEXT
)
"""

EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_events (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES games(id),
    ply_number INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    question_text TEXT,
    correct_answer TEXT,
    user_answer TEXT,
    was_correct INTEGER,
    created_at TEXT NOT NULL
)
"""


def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.execute(EVENTS_SCHEMA)
    try:
        conn.execute("ALTER TABLE games ADD COLUMN verification_json TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


def _starting_pgn() -> str:
    game = chess.pgn.Game()
    game.headers["Result"] = "*"
    return str(game)


def default_config(override=None) -> dict:
    cfg = {
        "movesInterval": 3,
        "questionsPerBatch": 2,
        "enabledQuestionTypes": list(DEFAULT_ENABLED),
        "failureThresholds": {"consecutiveFails": 3, "totalFails": 5},
        "resetTotalFailsOnBoardView": False,
    }
    if not override:
        return cfg
    out = dict(cfg)
    for k, v in override.items():
        if k not in cfg:
            continue
        if k == "failureThresholds" and isinstance(v, dict):
            out[k] = {**cfg[k], **v}
        else:
            out[k] = v
    out["movesInterval"] = max(1, int(out["movesInterval"]))
    # ponytail: 0 disables verification batches for the whole game
    out["questionsPerBatch"] = max(0, int(out["questionsPerBatch"]))
    return out


def default_state(config=None) -> dict:
    return {
        "config": config or default_config(),
        "movesSinceLastBatch": 0,
        "consecutiveFails": 0,
        "totalFails": 0,
        "lastQuestionTypeIds": [],
        "pending": [],
        "history": [],
        "suggestPeek": False,
    }


def _state_from_row(row) -> dict:
    raw = None
    try:
        raw = row["verification_json"]
    except (IndexError, KeyError):
        raw = None
    if not raw:
        return default_state()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default_state()
    base = default_state()
    base.update(data)
    if "config" in data:
        base["config"] = default_config(data["config"])
    return base


def _save_state(conn: sqlite3.Connection, game_id: str, state: dict) -> None:
    conn.execute(
        "UPDATE games SET verification_json = ? WHERE id = ?",
        (json.dumps(state), game_id),
    )
    conn.commit()


def verification_view(row) -> dict:
    state = _state_from_row(row)
    return {
        "questions": state["pending"],
        "suggest_peek": state["suggestPeek"],
        "consecutive_fails": state["consecutiveFails"],
        "total_fails": state["totalFails"],
    }


def record_answer(
    conn: sqlite3.Connection,
    game_id: str,
    ply_number: int,
    question_text: str,
    correct_answer: str,
    user_answer: str,
    was_correct: bool,
) -> dict:
    row = get_game(conn, game_id)
    if row is None:
        raise NotFound()
    state = _state_from_row(row)
    scored = bool(was_correct)
    if state["pending"]:
        head = state["pending"][0]
        scored = evaluate(head, user_answer)
        state["pending"] = state["pending"][1:]
        if scored:
            state["consecutiveFails"] = 0
        else:
            state["consecutiveFails"] += 1
            state["totalFails"] += 1
        thr = state["config"]["failureThresholds"]
        if (
            state["consecutiveFails"] >= thr["consecutiveFails"]
            or state["totalFails"] >= thr["totalFails"]
        ):
            state["suggestPeek"] = True
        state["history"].append(
            {
                "questionTypeId": head["type"],
                "promptEs": head["prompt"],
                "correctAnswer": head["answer"],
                "userAnswer": user_answer,
                "wasCorrect": scored,
                "moveNumber": ply_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        _save_state(conn, game_id, state)
    insert_event(
        conn,
        game_id,
        ply_number,
        "question",
        question_text=question_text,
        correct_answer=correct_answer,
        user_answer=user_answer,
        was_correct=scored,
    )
    return {
        "ok": True,
        "suggest_peek": state["suggestPeek"],
        "consecutive_fails": state["consecutiveFails"],
        "total_fails": state["totalFails"],
        "questions_remaining": len(state["pending"]),
    }


def create_game(
    conn: sqlite3.Connection,
    player_color: str = "white",
    maia_level: int = 1900,
    verification_questions=None,
) -> dict:
    game_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    state = default_state(default_config(verification_questions))
    conn.execute(
        """INSERT INTO games
           (id, created_at, player_color, maia_level, pgn, fen_current, status, result, verification_json)
           VALUES (?, ?, ?, ?, ?, ?, 'ongoing', NULL, ?)""",
        (game_id, now, player_color, maia_level, _starting_pgn(), START_FEN, json.dumps(state)),
    )
    conn.commit()
    return {"id": game_id}


def get_game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()


def list_games(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    # ponytail: list payload is a column subset — no FEN/PGN on the index
    return conn.execute(
        """SELECT id, created_at, player_color, maia_level, status, result
           FROM games ORDER BY created_at DESC"""
    ).fetchall()


def insert_event(
    conn: sqlite3.Connection,
    game_id: str,
    ply_number: int,
    event_type: str,
    question_text: str | None = None,
    correct_answer: str | None = None,
    user_answer: str | None = None,
    was_correct: bool | None = None,
) -> str:
    if get_game(conn, game_id) is None:
        raise NotFound()
    event_id = str(uuid.uuid4())
    flag = None if was_correct is None else int(bool(was_correct))
    conn.execute(
        """INSERT INTO game_events
           (id, game_id, ply_number, event_type, question_text,
            correct_answer, user_answer, was_correct, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            game_id,
            ply_number,
            event_type,
            question_text,
            correct_answer,
            user_answer,
            flag,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return event_id


def list_events(conn: sqlite3.Connection, game_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM game_events
           WHERE game_id = ? ORDER BY ply_number, created_at""",
        (game_id,),
    ).fetchall()


def count_peeks(conn: sqlite3.Connection, game_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM game_events WHERE game_id = ? AND event_type = 'peek'",
        (game_id,),
    ).fetchone()[0]


def peeks_remaining(conn: sqlite3.Connection, game_id: str) -> int:
    return max(0, PEEK_MAX - count_peeks(conn, game_id))


def moves_from_pgn(pgn: str) -> list[str]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return []
    board = game.board()
    sans = []
    for move in game.mainline_moves():
        sans.append(board.san(move))
        board.push(move)
    return sans


def turn_of(fen: str) -> str:
    return _side(chess.Board(fen))


def peek_board(conn: sqlite3.Connection, game_id: str) -> dict:
    row = get_game(conn, game_id)
    if row is None:
        raise NotFound()
    if row["status"] == "finished":
        raise FinishedGame()
    if peeks_remaining(conn, game_id) <= 0:
        raise PeekExhausted()
    ply = chess.Board(row["fen_current"]).ply()
    insert_event(conn, game_id, ply, "peek")
    state = _state_from_row(row)
    state["consecutiveFails"] = 0
    state["suggestPeek"] = False
    if state["config"].get("resetTotalFailsOnBoardView"):
        state["totalFails"] = 0
    _save_state(conn, game_id, state)
    return {
        "fen": row["fen_current"],
        "peeks_remaining": peeks_remaining(conn, game_id),
        "seconds": PEEK_SECONDS,
        "suggest_peek": False,
        "consecutive_fails": 0,
        "total_fails": state["totalFails"],
    }


class IllegalMove(Exception):
    pass


class NotFound(Exception):
    pass


class FinishedGame(Exception):
    pass


class OpponentFailed(Exception):
    pass


class PeekExhausted(Exception):
    pass


class QuestionsPending(Exception):
    pass


def count_ongoing(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM games WHERE status = 'ongoing'").fetchone()[0]


def resign(conn: sqlite3.Connection, game_id: str) -> dict:
    row = get_game(conn, game_id)
    if row is None:
        raise NotFound()
    if row["status"] == "finished":
        raise FinishedGame()
    result = "0-1" if row["player_color"] == "white" else "1-0"
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    game.headers["Result"] = result
    conn.execute(
        "UPDATE games SET pgn = ?, status = ?, result = ? WHERE id = ?",
        (str(game), "finished", result, game_id),
    )
    conn.commit()
    return {"ok": True, "status": "finished", "result": result}


def build_pgn(row: sqlite3.Row) -> str:
    # ponytail: rebuild headers on the stored game tree
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    guest, maia = "Guest", f"Maia {row['maia_level']}"
    if row["player_color"] == "white":
        white, black = guest, maia
    else:
        white, black = maia, guest
    dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    game.headers["Event"] = "alaciega"
    game.headers["Site"] = os.environ.get("PGN_SITE") or "localhost"
    game.headers["Date"] = dt.strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = white
    game.headers["Black"] = black
    game.headers["Result"] = row["result"] or "*"
    return str(game)


def delete_game(conn: sqlite3.Connection, game_id: str) -> dict:
    # ponytail: events first — schema has no ON DELETE CASCADE
    if get_game(conn, game_id) is None:
        raise NotFound()
    conn.execute("DELETE FROM game_events WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    return {"ok": True}


def _side(board: chess.Board) -> str:
    return "white" if board.turn == chess.WHITE else "black"


def _load_playable(conn: sqlite3.Connection, game_id: str):
    row = get_game(conn, game_id)
    if row is None:
        raise NotFound()
    if row["status"] == "finished":
        raise FinishedGame()
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    node = game.end()
    return row, game, node, node.board()


def _save(conn: sqlite3.Connection, game_id: str, game: chess.pgn.Game, board: chess.Board) -> dict:
    outcome = board.outcome()
    if outcome is None:
        status, result = "ongoing", None
        game.headers["Result"] = "*"
    else:
        status, result = "finished", outcome.result()
        game.headers["Result"] = result
    conn.execute(
        "UPDATE games SET pgn = ?, fen_current = ?, status = ?, result = ? WHERE id = ?",
        (str(game), board.fen(), status, result, game_id),
    )
    conn.commit()
    out = {"ok": True, "turn": _side(board), "status": status}
    if result is not None:
        out["result"] = result
    return out


def _engine_move(opponent, board: chess.Board) -> chess.Move:
    try:
        move = opponent.play(board)
    except Exception as exc:
        raise OpponentFailed() from exc
    if move not in board.legal_moves:
        raise OpponentFailed()
    return move


def apply_engine_move(conn: sqlite3.Connection, game_id: str, opponent) -> dict:
    row, game, node, board = _load_playable(conn, game_id)
    if _side(board) == row["player_color"]:
        raise IllegalMove()
    move = _engine_move(opponent, board)
    applied = board.san(move)
    node.add_variation(move)
    board.push(move)
    out = _save(conn, game_id, game, board)
    out["applied"] = applied
    return out


def apply_move(conn: sqlite3.Connection, game_id: str, move_text: str, opponent) -> dict:
    row, game, node, board = _load_playable(conn, game_id)
    state = _state_from_row(row)
    if state["pending"]:
        raise QuestionsPending()
    if _side(board) != row["player_color"]:
        raise IllegalMove()
    text = (move_text or "").strip()
    if not text:
        raise IllegalMove()
    try:
        move = board.parse_san(text)
    except ValueError as exc:
        raise IllegalMove() from exc
    applied = board.san(move)
    node = node.add_variation(move)
    board.push(move)
    cfg = state["config"]
    state["movesSinceLastBatch"] += 1
    questions = []
    batch_n = cfg["questionsPerBatch"]
    if batch_n > 0 and state["movesSinceLastBatch"] >= cfg["movesInterval"]:
        questions = generate_batch(
            board,
            enabled=cfg["enabledQuestionTypes"],
            n=batch_n,
            last_ids=state["lastQuestionTypeIds"],
        )
        state["pending"] = questions
        state["movesSinceLastBatch"] = 0
        state["lastQuestionTypeIds"] = [q["type"] for q in questions]
    maia = None
    if board.outcome() is None:
        omove = _engine_move(opponent, board)
        maia = board.san(omove)
        node.add_variation(omove)
        board.push(omove)
    out = _save(conn, game_id, game, board)
    _save_state(conn, game_id, state)
    out["applied"] = applied
    out["questions"] = questions
    out["suggest_peek"] = state["suggestPeek"]
    if questions:
        out["question"] = questions[0]
    if maia is not None:
        out["maia_move"] = maia
    return out

