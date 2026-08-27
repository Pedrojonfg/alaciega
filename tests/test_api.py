import chess
import pytest
from fastapi.testclient import TestClient

from conftest import AUTH


class ScriptedOpponent:
    def __init__(self, sans):
        self.sans = list(sans)

    def play(self, board):
        return board.parse_san(self.sans.pop(0))

    def quit(self):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.db"))
    monkeypatch.delenv("LC0_PATH", raising=False)
    from backend.app import app

    with TestClient(app, headers=AUTH) as test_client:
        yield test_client


def test_create_white_has_no_maia_move(client):
    r = client.post("/games", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["your_turn"] is True
    assert body["turn"] == "white"
    assert "maia_move" not in body
    assert "fen" not in body and "fen_current" not in body
    assert "question" not in body


def test_create_black_has_maia_move(client):
    r = client.post("/games", json={"player_color": "black"})
    assert r.status_code == 200
    body = r.json()
    assert body["your_turn"] is True
    assert body["turn"] == "black"
    assert body["maia_move"]
    assert "fen" not in body
    assert "question" not in body


def test_move_returns_maia_reply(client):
    gid = client.post("/games", json={}).json()["game_id"]
    ok = client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["applied"] == "e4"
    assert data["maia_move"]
    assert data["turn"] == "white"
    assert "fen" not in data and "fen_current" not in data
    assert data["questions"] == []
    bad = client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    assert bad.status_code == 400
    assert "question" not in bad.json()


def test_move_unknown_game(client):
    r = client.post("/games/not-a-game/move", json={"move_text": "e4"})
    assert r.status_code == 404
    assert "question" not in r.json()


def test_finished_conflict_fools_mate(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "mate.db"))
    monkeypatch.delenv("LC0_PATH", raising=False)
    import backend.app as appmod

    monkeypatch.setattr(
        appmod, "make_opponent", lambda *a, **k: ScriptedOpponent(["e5", "Qh4#"])
    )
    with TestClient(appmod.app, headers=AUTH) as client:
        gid = client.post(
            "/games",
            json={
                "verification_questions": {
                    "movesInterval": 2,
                    "questionsPerBatch": 3,
                }
            },
        ).json()["game_id"]
        assert client.post(f"/games/{gid}/move", json={"move_text": "f3"}).status_code == 200
        r = client.post(f"/games/{gid}/move", json={"move_text": "g4"})
        assert r.status_code == 200
        assert r.json()["status"] == "finished"
        assert r.json()["result"] == "0-1"
        assert r.json()["maia_move"] == "Qh4#"
        assert len(r.json()["questions"]) == 3
        again = client.post(f"/games/{gid}/move", json={"move_text": "a3"})
        assert again.status_code == 409
        assert "question" not in again.json()


def test_too_many_ongoing(client):
    for _ in range(3):
        assert client.post("/games", json={}).status_code == 200
    r = client.post("/games", json={})
    assert r.status_code == 429
    assert "error" in r.json()


def test_max_ongoing_from_env(client, monkeypatch):
    monkeypatch.setenv("MAX_ONGOING", "1")
    assert client.post("/games", json={}).status_code == 200
    r = client.post("/games", json={})
    assert r.status_code == 429
    assert "error" in r.json()


def test_persist_across_client_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "persist.db"))
    monkeypatch.delenv("LC0_PATH", raising=False)
    from backend.app import app

    with TestClient(app, headers=AUTH) as c1:
        gid = c1.post("/games", json={}).json()["game_id"]
        assert c1.post(f"/games/{gid}/move", json={"move_text": "e4"}).status_code == 200
    with TestClient(app, headers=AUTH) as c2:
        r = c2.post(f"/games/{gid}/move", json={"move_text": "Nf3"})
        assert r.status_code == 200
        assert r.json()["applied"] == "Nf3"
        assert r.json()["maia_move"]


def test_get_maia_levels(client, tmp_path, monkeypatch):
    d = tmp_path / "only"
    d.mkdir()
    (d / "maia-1900.pb.gz").write_bytes(b"")
    (d / "maia-1100.pb.gz").write_bytes(b"")
    (d / "noise.txt").write_bytes(b"")
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(d))
    r = client.get("/maia/levels")
    assert r.status_code == 200
    assert r.json() == {"levels": [1100, 1900]}


def test_get_maia_levels_empty(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(tmp_path / "missing"))
    r = client.get("/maia/levels")
    assert r.status_code == 200
    assert r.json() == {"levels": []}


def test_create_returns_chosen_level(client):
    r = client.post("/games", json={"maia_level": 1500})
    assert r.status_code == 200
    assert r.json()["maia_level"] == 1500
    assert client.app.state.engines[r.json()["game_id"]].level == 1500


def test_create_default_level_is_1900(client):
    r = client.post("/games", json={})
    assert r.status_code == 200
    assert r.json()["maia_level"] == 1900


def test_create_unavailable_level(client, tmp_path, monkeypatch):
    d = tmp_path / "only1900"
    d.mkdir()
    (d / "maia-1900.pb.gz").write_bytes(b"")
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(d))
    r = client.post("/games", json={"maia_level": 1200})
    assert r.status_code == 400
    assert r.json()["error"] == "nivel de Maia no disponible"
    assert client.get("/maia/levels").json() == {"levels": [1900]}
    assert client.post("/games", json={"maia_level": 1900}).status_code == 200


def test_create_default_unavailable_when_catalog_empty(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(tmp_path / "empty"))
    r = client.post("/games", json={})
    assert r.status_code == 400
    assert r.json()["error"] == "nivel de Maia no disponible"


def test_parallel_games_keep_distinct_levels(client):
    a = client.post("/games", json={"maia_level": 1100}).json()
    b = client.post("/games", json={"maia_level": 1900}).json()
    assert a["maia_level"] == 1100
    assert b["maia_level"] == 1900
    engines = client.app.state.engines
    assert engines[a["game_id"]].level == 1100
    assert engines[b["game_id"]].level == 1900
    client.post(f"/games/{a['game_id']}/move", json={"move_text": "e4"})
    assert engines[b["game_id"]].level == 1900


class BoomOpponent:
    def play(self, board):
        raise RuntimeError("boom")

    def quit(self):
        pass


def test_opponent_failure_has_no_question(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "boom.db"))
    monkeypatch.delenv("LC0_PATH", raising=False)
    import backend.app as appmod

    monkeypatch.setattr(appmod, "make_opponent", lambda *a, **k: BoomOpponent())
    with TestClient(appmod.app, headers=AUTH) as client:
        gid = client.post("/games", json={}).json()["game_id"]
        r = client.post(f"/games/{gid}/move", json={"move_text": "e4"})
        assert r.status_code == 500
        assert "question" not in r.json()


def test_resign_white_via_http(client):
    gid = client.post("/games", json={}).json()["game_id"]
    assert gid in client.app.state.engines
    r = client.post(f"/games/{gid}/resign")
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "status": "finished", "result": "0-1"}
    assert "question" not in body
    assert "fen" not in body and "fen_current" not in body
    assert gid not in client.app.state.engines
    again = client.post(f"/games/{gid}/resign")
    assert again.status_code == 409
    assert again.json()["error"] == "partida terminada"
    move = client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    assert move.status_code == 409


def test_resign_black_via_http(client):
    gid = client.post("/games", json={"player_color": "black"}).json()["game_id"]
    r = client.post(f"/games/{gid}/resign")
    assert r.status_code == 200
    assert r.json()["result"] == "1-0"


def test_resign_unknown_game(client):
    r = client.post("/games/not-a-game/resign")
    assert r.status_code == 404
    assert r.json()["error"] == "partida no encontrada"
    assert "question" not in r.json()


def test_delete_ongoing_via_http(client):
    gid = client.post("/games", json={}).json()["game_id"]
    assert gid in client.app.state.engines
    r = client.delete(f"/games/{gid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert "fen" not in r.json() and "fen_current" not in r.json()
    assert gid not in client.app.state.engines
    assert client.get(f"/games/{gid}").status_code == 404


def test_delete_finished_via_http(client):
    gid = client.post("/games", json={}).json()["game_id"]
    assert client.post(f"/games/{gid}/resign").status_code == 200
    r = client.delete(f"/games/{gid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert client.get(f"/games/{gid}").status_code == 404


def test_delete_unknown_game(client):
    r = client.delete("/games/not-a-game")
    assert r.status_code == 404
    assert r.json()["error"] == "partida no encontrada"


def test_delete_ongoing_frees_create_slot(client):
    ids = [client.post("/games", json={}).json()["game_id"] for _ in range(3)]
    assert client.post("/games", json={}).status_code == 429
    assert client.delete(f"/games/{ids[0]}").status_code == 200
    assert client.post("/games", json={}).status_code == 200


def test_cors_preflight_allows_delete(client):
    r = client.options(
        "/games/x",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert r.status_code in (200, 204)
    allowed = r.headers.get("access-control-allow-methods", "")
    assert "DELETE" in allowed.upper()


def test_cors_allows_localhost_3000(client):
    r = client.get("/maia/levels", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_list_games_empty(client):
    r = client.get("/games")
    assert r.status_code == 200
    assert r.json() == {"games": []}


def test_list_and_get_game_hides_fen_while_ongoing(client):
    gid = client.post("/games", json={"maia_level": 1500}).json()["game_id"]
    listed = client.get("/games")
    assert listed.status_code == 200
    games = listed.json()["games"]
    assert len(games) == 1
    assert games[0]["id"] == gid
    assert games[0]["maia_level"] == 1500
    assert games[0]["player_color"] == "white"
    assert games[0]["status"] == "ongoing"
    assert games[0]["result"] is None
    assert "fen" not in games[0] and "fen_current" not in games[0]
    assert "pgn" not in games[0]
    detail = client.get(f"/games/{gid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == gid
    assert "pgn" in body
    assert "fen" not in body and "fen_current" not in body
    client.post(f"/games/{gid}/resign")
    done = client.get(f"/games/{gid}")
    assert done.status_code == 200
    finished = done.json()
    assert finished["status"] == "finished"
    assert "fen_current" in finished
    assert "fen" not in finished


def test_get_game_unknown(client):
    r = client.get("/games/not-a-game")
    assert r.status_code == 404
    assert r.json()["error"] == "partida no encontrada"
    assert "fen_current" not in r.json()


def test_health_is_public(client):
    from backend.app import app
    from fastapi.testclient import TestClient

    with TestClient(app) as naked:
        r = naked.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


def test_games_require_token(client):
    from backend.app import app
    from fastapi.testclient import TestClient

    with TestClient(app) as naked:
        assert naked.get("/games").status_code == 401
        assert naked.get("/games").json()["error"] == "unauthorized"
        assert naked.post("/games", json={}).status_code == 401
    with TestClient(app, headers={"Authorization": "Bearer wrong"}) as bad:
        assert bad.get("/maia/levels").status_code == 401


def test_ongoing_detail_has_moves_turn_peeks_no_fen_no_events(client):
    gid = client.post("/games", json={}).json()["game_id"]
    client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    body = client.get(f"/games/{gid}").json()
    assert body["status"] == "ongoing"
    assert body["moves"][0] == "e4"
    assert len(body["moves"]) == 2
    assert body["turn"] == "white"
    assert body["your_turn"] is True
    assert body["peeks_remaining"] == 3
    assert "fen_current" not in body and "fen" not in body
    assert "events" not in body


def test_answer_persists_and_finished_get_returns_events(client):
    gid = client.post("/games", json={}).json()["game_id"]
    r = client.post(
        f"/games/{gid}/answer",
        json={
            "ply_number": 1,
            "question_text": "¿Cuántas capturas legales tiene el jugador en turno?",
            "correct_answer": "0",
            "user_answer": "2",
            "was_correct": False,
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    client.post(f"/games/{gid}/resign")
    events = client.get(f"/games/{gid}").json()["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "question"
    assert events[0]["ply_number"] == 1
    assert events[0]["user_answer"] == "2"
    assert events[0]["was_correct"] is False
    assert events[0]["id"]
    assert "fen_current" in client.get(f"/games/{gid}").json()


def test_answer_works_on_finished_game(client):
    gid = client.post("/games", json={}).json()["game_id"]
    client.post(f"/games/{gid}/resign")
    r = client.post(
        f"/games/{gid}/answer",
        json={
            "ply_number": 4,
            "question_text": "q",
            "correct_answer": "true",
            "user_answer": "sí",
            "was_correct": True,
        },
    )
    assert r.status_code == 200
    events = client.get(f"/games/{gid}").json()["events"]
    assert events[0]["was_correct"] is True
    assert events[0]["user_answer"] == "sí"


def test_answer_unknown_game_404(client):
    r = client.post(
        "/games/nope/answer",
        json={
            "ply_number": 0,
            "question_text": "q",
            "correct_answer": "0",
            "user_answer": "0",
            "was_correct": True,
        },
    )
    assert r.status_code == 404
    assert r.json()["error"] == "partida no encontrada"
    assert "fen" not in r.json()


def test_peek_returns_fen_and_decrements(client):
    gid = client.post("/games", json={}).json()["game_id"]
    client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    r = client.post(f"/games/{gid}/peek")
    assert r.status_code == 200
    body = r.json()
    assert "fen" in body
    assert "fen_current" not in body
    assert body["peeks_remaining"] == 2
    assert body["seconds"] == 10
    chess.Board(body["fen"])  # valid
    detail = client.get(f"/games/{gid}").json()
    assert "fen" not in detail and "fen_current" not in detail
    assert detail["peeks_remaining"] == 2
    client.post(f"/games/{gid}/resign")
    events = client.get(f"/games/{gid}").json()["events"]
    assert any(e["event_type"] == "peek" for e in events)


def test_peek_cap_is_403_without_fen(client):
    gid = client.post("/games", json={}).json()["game_id"]
    for _ in range(3):
        assert client.post(f"/games/{gid}/peek").status_code == 200
    r = client.post(f"/games/{gid}/peek")
    assert r.status_code == 403
    assert r.json()["error"] == "no quedan ayudas"
    assert "fen" not in r.json()
    assert client.get(f"/games/{gid}").json()["peeks_remaining"] == 0


def test_peek_finished_and_unknown(client):
    gid = client.post("/games", json={}).json()["game_id"]
    client.post(f"/games/{gid}/resign")
    done = client.post(f"/games/{gid}/peek")
    assert done.status_code == 409
    assert done.json()["error"] == "partida terminada"
    assert "fen" not in done.json()
    missing = client.post("/games/nope/peek")
    assert missing.status_code == 404
    assert missing.json()["error"] == "partida no encontrada"
    assert "fen" not in missing.json()


def _vq(**kw):
    body = {
        "movesInterval": 2,
        "questionsPerBatch": 3,
        "enabledQuestionTypes": ["in_check", "side_to_move", "total_piece_count"],
        "failureThresholds": {"consecutiveFails": 3, "totalFails": 5},
    }
    body.update(kw)
    return body


def test_verification_cadence_and_skip_is_409(client):
    gid = client.post("/games", json={"verification_questions": _vq()}).json()["game_id"]
    first = client.post(f"/games/{gid}/move", json={"move_text": "e4"})
    assert first.status_code == 200
    assert first.json()["questions"] == []
    second = client.post(f"/games/{gid}/move", json={"move_text": "Nf3"})
    assert second.status_code == 200
    qs = second.json()["questions"]
    assert len(qs) == 3
    for q in qs:
        assert q["promptEn"]
        assert not q["promptEn"].startswith("¿")
        assert q["promptShortEn"]
    skip = client.post(f"/games/{gid}/move", json={"move_text": "Bc4"})
    assert skip.status_code == 409
    assert skip.json()["error"] == "responde las preguntas primero"
    detail = client.get(f"/games/{gid}").json()
    assert len(detail["questions"]) == 3
    assert all(q.get("promptEn") for q in detail["questions"])
    assert "fen" not in detail and "fen_current" not in detail

