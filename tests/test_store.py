import chess
import pytest

from backend.engine import FakeOpponent
from backend.questions import PROMPTS
from backend.store import (
    PEEK_MAX,
    PEEK_SECONDS,
    START_FEN,
    FinishedGame,
    IllegalMove,
    NotFound,
    OpponentFailed,
    QuestionsPending,
    apply_engine_move,
    apply_move,
    build_pgn,
    count_ongoing,
    count_peeks,
    create_game,
    delete_game,
    get_game,
    init_db,
    insert_event,
    list_events,
    list_games,
    moves_from_pgn,
    peek_board,
    peeks_remaining,
    record_answer,
    resign,
    verification_view,
)


class ScriptedOpponent:
    def __init__(self, sans):
        self.sans = list(sans)

    def play(self, board):
        return board.parse_san(self.sans.pop(0))

    def quit(self):
        pass


class BoomOpponent:
    def play(self, board):
        raise RuntimeError("boom")

    def quit(self):
        pass


@pytest.fixture
def conn(tmp_path):
    return init_db(str(tmp_path / "t02.db"))


def test_create_game_persists_starting_position(conn):
    game = create_game(conn)
    row = get_game(conn, game["id"])
    assert row["status"] == "ongoing"
    assert row["fen_current"] == START_FEN
    assert row["player_color"] == "white"


def test_player_move_then_opponent_persisted(conn):
    gid = create_game(conn)["id"]
    out = apply_move(conn, gid, "e4", FakeOpponent())
    assert out["applied"] == "e4"
    assert out["status"] == "ongoing"
    assert "maia_move" in out
    row = get_game(conn, gid)
    assert "e4" in row["pgn"]
    assert out["maia_move"] in row["pgn"]
    board = chess.Board(row["fen_current"])
    assert board.turn == chess.WHITE
    assert board.fullmove_number == 2


def test_illegal_san_does_not_call_opponent_or_advance(conn):
    gid = create_game(conn)["id"]
    apply_move(conn, gid, "e4", FakeOpponent())
    before = dict(get_game(conn, gid))

    class Guard:
        def play(self, board):
            raise AssertionError("opponent should not be called")

        def quit(self):
            pass

    with pytest.raises(IllegalMove):
        apply_move(conn, gid, "e4", Guard())
    after = dict(get_game(conn, gid))
    assert after["pgn"] == before["pgn"]
    assert after["fen_current"] == before["fen_current"]


def test_black_player_cannot_move_first(conn):
    gid = create_game(conn, player_color="black")["id"]
    with pytest.raises(IllegalMove):
        apply_move(conn, gid, "e4", FakeOpponent())
    assert get_game(conn, gid)["fen_current"] == START_FEN


def test_engine_opening_for_black(conn):
    gid = create_game(conn, player_color="black")["id"]
    out = apply_engine_move(conn, gid, FakeOpponent())
    assert out["applied"]
    row = get_game(conn, gid)
    assert out["applied"] in row["pgn"]
    assert chess.Board(row["fen_current"]).turn == chess.BLACK


def test_opponent_fools_mate_finishes(conn):
    gid = create_game(conn)["id"]
    opp = ScriptedOpponent(["e5", "Qh4#"])
    apply_move(conn, gid, "f3", opp)
    out = apply_move(conn, gid, "g4", opp)
    assert out["status"] == "finished"
    assert out["result"] == "0-1"
    assert out["maia_move"] == "Qh4#"
    with pytest.raises(FinishedGame):
        apply_move(conn, gid, "a3", FakeOpponent())


def test_player_mate_has_no_maia_move(conn):
    # White mates: Scholar's mate 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7#
    gid = create_game(conn, verification_questions={"enabledQuestionTypes": []})["id"]
    opp = ScriptedOpponent(["e5", "Nc6", "Nf6"])
    apply_move(conn, gid, "e4", opp)
    apply_move(conn, gid, "Qh5", opp)
    apply_move(conn, gid, "Bc4", opp)
    out = apply_move(conn, gid, "Qxf7#", BoomOpponent())
    assert out["status"] == "finished"
    assert out["result"] == "1-0"
    assert "maia_move" not in out
    assert "Qxf7" in get_game(conn, gid)["pgn"]


def test_opponent_failure_does_not_persist_player_move(conn):
    gid = create_game(conn)["id"]
    before = dict(get_game(conn, gid))
    with pytest.raises(OpponentFailed):
        apply_move(conn, gid, "e4", BoomOpponent())
    after = dict(get_game(conn, gid))
    assert after["pgn"] == before["pgn"]
    assert after["fen_current"] == before["fen_current"]


def test_unknown_and_empty(conn):
    with pytest.raises(NotFound):
        apply_move(conn, "missing", "e4", FakeOpponent())
    gid = create_game(conn)["id"]
    with pytest.raises(IllegalMove):
        apply_move(conn, gid, "  ", FakeOpponent())


def test_count_ongoing(conn):
    a = create_game(conn)["id"]
    create_game(conn)
    assert count_ongoing(conn) == 2
    apply_move(conn, a, "f3", ScriptedOpponent(["e5", "Qh4#"]))
    apply_move(conn, a, "g4", ScriptedOpponent(["Qh4#"]))
    assert count_ongoing(conn) == 1


def test_question_is_after_player_move_not_maia(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 1,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["checks"],
        },
    )["id"]
    out = apply_move(conn, gid, "e4", ScriptedOpponent(["d5"]))
    assert out["maia_move"] == "d5"
    assert len(out["questions"]) == 1
    q = out["questions"][0]
    assert q["type"] == "checks"
    assert q["prompt"] == PROMPTS["checks"]
    assert q["promptEn"]
    assert not q["promptEn"].startswith("¿")
    assert q["promptShortEn"]
    assert q["answer"] == 0
    assert q["expectedAnswerType"] == "number"
    assert q["promptShort"]
    assert q["turnDependent"] is True


def test_engine_opening_has_no_question(conn):
    gid = create_game(conn, player_color="black")["id"]
    out = apply_engine_move(conn, gid, FakeOpponent())
    assert "question" not in out


def test_resign_white_is_0_1(conn):
    gid = create_game(conn)["id"]
    out = resign(conn, gid)
    assert out == {"ok": True, "status": "finished", "result": "0-1"}
    row = get_game(conn, gid)
    assert row["status"] == "finished"
    assert row["result"] == "0-1"
    assert '[Result "0-1"]' in row["pgn"]
    with pytest.raises(FinishedGame):
        resign(conn, gid)
    with pytest.raises(FinishedGame):
        apply_move(conn, gid, "e4", FakeOpponent())


def test_build_pgn_site_from_env(conn, monkeypatch):
    monkeypatch.setenv("PGN_SITE", "example.test")
    gid = create_game(conn)["id"]
    resign(conn, gid)
    text = build_pgn(get_game(conn, gid))
    assert '[Site "example.test"]' in text
    assert "duckdns" not in text


def test_build_pgn_site_default(conn, monkeypatch):
    monkeypatch.delenv("PGN_SITE", raising=False)
    gid = create_game(conn)["id"]
    resign(conn, gid)
    assert '[Site "localhost"]' in build_pgn(get_game(conn, gid))


def test_resign_black_is_1_0(conn):
    gid = create_game(conn, player_color="black")["id"]
    out = resign(conn, gid)
    assert out["result"] == "1-0"
    assert get_game(conn, gid)["result"] == "1-0"


def test_resign_unknown(conn):
    with pytest.raises(NotFound):
        resign(conn, "missing")


def test_delete_ongoing_and_finished_removes_events(conn):
    ongoing = create_game(conn)["id"]
    finished = create_game(conn)["id"]
    insert_event(conn, ongoing, ply_number=1, event_type="peek")
    insert_event(conn, finished, ply_number=1, event_type="peek")
    resign(conn, finished)
    assert delete_game(conn, ongoing) == {"ok": True}
    assert get_game(conn, ongoing) is None
    assert list_events(conn, ongoing) == []
    assert delete_game(conn, finished) == {"ok": True}
    assert get_game(conn, finished) is None
    assert list_events(conn, finished) == []
    with pytest.raises(NotFound):
        delete_game(conn, "missing")


def test_delete_ongoing_frees_slot(conn):
    gid = create_game(conn)["id"]
    create_game(conn)
    assert count_ongoing(conn) == 2
    delete_game(conn, gid)
    assert count_ongoing(conn) == 1


def test_list_games_newest_first_without_fen(conn):
    a = create_game(conn, maia_level=1100)["id"]
    b = create_game(conn, maia_level=1900, player_color="black")["id"]
    resign(conn, a)
    rows = list_games(conn)
    assert [r["id"] for r in rows] == [b, a]
    assert rows[0]["status"] == "ongoing"
    assert rows[1]["status"] == "finished"
    assert rows[1]["result"] == "0-1"
    assert "fen_current" not in rows[0].keys()
    assert "pgn" not in rows[0].keys()


def test_resign_frees_ongoing_slot(conn):
    gid = create_game(conn)["id"]
    create_game(conn)
    assert count_ongoing(conn) == 2
    resign(conn, gid)
    assert count_ongoing(conn) == 1


def test_player_mate_has_in_check_question(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 4,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["in_check"],
        },
    )["id"]
    opp = ScriptedOpponent(["e5", "Nc6", "Nf6"])
    apply_move(conn, gid, "e4", opp)
    apply_move(conn, gid, "Qh5", opp)
    apply_move(conn, gid, "Bc4", opp)
    out = apply_move(conn, gid, "Qxf7#", BoomOpponent())
    assert "maia_move" not in out
    assert len(out["questions"]) == 1
    q = out["questions"][0]
    assert q["type"] == "in_check"
    assert q["prompt"] == PROMPTS["in_check"]
    assert q["answer"] is True
    assert q["expectedAnswerType"] == "boolean"


def test_peek_constants_are_named():
    assert PEEK_MAX == 3
    assert PEEK_SECONDS == 10


def test_insert_and_list_question_event(conn):
    gid = create_game(conn)["id"]
    insert_event(
        conn,
        gid,
        ply_number=1,
        event_type="question",
        question_text="¿Cuántas capturas legales tiene el jugador en turno?",
        correct_answer="0",
        user_answer="2",
        was_correct=False,
    )
    rows = list_events(conn, gid)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "question"
    assert rows[0]["ply_number"] == 1
    assert rows[0]["user_answer"] == "2"
    assert rows[0]["was_correct"] == 0
    assert rows[0]["id"]


def test_peek_count_and_remaining(conn):
    gid = create_game(conn)["id"]
    assert count_peeks(conn, gid) == 0
    assert peeks_remaining(conn, gid) == PEEK_MAX
    insert_event(conn, gid, ply_number=0, event_type="peek")
    insert_event(conn, gid, ply_number=2, event_type="peek")
    assert count_peeks(conn, gid) == 2
    assert peeks_remaining(conn, gid) == 1
    insert_event(conn, gid, ply_number=2, event_type="question", question_text="q",
                 correct_answer="0", user_answer="0", was_correct=True)
    assert count_peeks(conn, gid) == 2


def test_list_events_empty_and_ordered_by_ply(conn):
    gid = create_game(conn)["id"]
    assert list_events(conn, gid) == []
    insert_event(conn, gid, ply_number=3, event_type="peek")
    insert_event(conn, gid, ply_number=1, event_type="peek")
    plies = [r["ply_number"] for r in list_events(conn, gid)]
    assert plies == [1, 3]


def test_insert_event_unknown_game_raises(conn):
    with pytest.raises(NotFound):
        insert_event(conn, "missing", ply_number=0, event_type="peek")


def test_moves_from_pgn_start_and_after_play(conn):
    gid = create_game(conn)["id"]
    assert moves_from_pgn(get_game(conn, gid)["pgn"]) == []
    apply_move(conn, gid, "e4", FakeOpponent())
    sans = moves_from_pgn(get_game(conn, gid)["pgn"])
    assert sans[0] == "e4"
    assert len(sans) == 2
    assert moves_from_pgn("not pgn") == []


def _quiet_cfg(**extra):
    cfg = {
        "movesInterval": 2,
        "questionsPerBatch": 3,
        "enabledQuestionTypes": ["in_check", "side_to_move", "total_piece_count"],
    }
    cfg.update(extra)
    return cfg


def test_batch_on_player_moves_2_4_not_1_3(conn):
    gid = create_game(conn, verification_questions=_quiet_cfg())["id"]
    a = apply_move(conn, gid, "e4", FakeOpponent())
    assert a["questions"] == []
    b = apply_move(conn, gid, "Nf3", FakeOpponent())
    assert len(b["questions"]) == 3
    types = [q["type"] for q in b["questions"]]
    assert len(types) == len(set(types))
    with pytest.raises(QuestionsPending):
        apply_move(conn, gid, "Bc4", FakeOpponent())


def test_new_game_verification_counters_are_zero(conn):
    gid = create_game(conn)["id"]
    view = verification_view(get_game(conn, gid))
    assert view["questions"] == []
    assert view["consecutive_fails"] == 0
    assert view["total_fails"] == 0
    assert view["suggest_peek"] is False


def test_empty_enabled_never_blocks(conn):
    gid = create_game(
        conn,
        verification_questions={"enabledQuestionTypes": [], "movesInterval": 1},
    )["id"]
    apply_move(conn, gid, "e4", FakeOpponent())
    apply_move(conn, gid, "Nf3", FakeOpponent())
    assert verification_view(get_game(conn, gid))["questions"] == []


def _answer(conn, gid, q, user, ply=1):
    return record_answer(
        conn, gid, ply, q["prompt"], str(q["answer"]), user, was_correct=False
    )


def test_consecutive_fails_reset_on_hit_total_does_not(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 1,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["in_check"],
            "failureThresholds": {"consecutiveFails": 3, "totalFails": 99},
        },
    )["id"]
    q = apply_move(conn, gid, "e4", FakeOpponent())["questions"][0]
    assert q["answer"] is False
    r = _answer(conn, gid, q, "sí")
    assert r["consecutive_fails"] == 1
    assert r["total_fails"] == 1
    q = apply_move(conn, gid, "Nf3", FakeOpponent())["questions"][0]
    r = _answer(conn, gid, q, "no")  # after e4 Nf3 still not in check typically
    # in_check after Nf3: black to move, not in check → False, "no" is correct
    assert r["consecutive_fails"] == 0
    assert r["total_fails"] == 1
    assert r["suggest_peek"] is False


def test_three_consecutive_misses_suggest_peek(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 1,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["in_check"],
            "failureThresholds": {"consecutiveFails": 3, "totalFails": 99},
        },
    )["id"]
    last = None
    for san in ("e4", "Nf3", "Bc4"):
        q = apply_move(conn, gid, san, FakeOpponent())["questions"][0]
        last = _answer(conn, gid, q, "sí")
    assert last["consecutive_fails"] == 3
    assert last["suggest_peek"] is True


def test_total_fails_alone_suggests(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 1,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["in_check"],
            "failureThresholds": {"consecutiveFails": 99, "totalFails": 2},
        },
    )["id"]
    q = apply_move(conn, gid, "e4", FakeOpponent())["questions"][0]
    _answer(conn, gid, q, "sí")
    q = apply_move(conn, gid, "Nf3", FakeOpponent())["questions"][0]
    r = _answer(conn, gid, q, "sí")
    assert r["total_fails"] == 2
    assert r["consecutive_fails"] == 2
    assert r["suggest_peek"] is True


def test_peek_resets_consecutive_not_total(conn):
    gid = create_game(
        conn,
        verification_questions={
            "movesInterval": 1,
            "questionsPerBatch": 1,
            "enabledQuestionTypes": ["in_check"],
            "failureThresholds": {"consecutiveFails": 3, "totalFails": 99},
        },
    )["id"]
    q = apply_move(conn, gid, "e4", FakeOpponent())["questions"][0]
    _answer(conn, gid, q, "sí")
    out = peek_board(conn, gid)
    assert out["consecutive_fails"] == 0
    assert out["total_fails"] == 1
    assert out["suggest_peek"] is False
    assert verification_view(get_game(conn, gid))["consecutive_fails"] == 0
    assert verification_view(get_game(conn, gid))["total_fails"] == 1
