from dotenv import load_dotenv
load_dotenv()

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from backend.engine import _env_int, available_levels, make_opponent
from backend.store import (
    FinishedGame,
    IllegalMove,
    NotFound,
    OpponentFailed,
    PeekExhausted,
    QuestionsPending,
    apply_engine_move,
    apply_move,
    build_pgn,
    count_ongoing,
    create_game,
    delete_game,
    get_game,
    init_db,
    list_events,
    list_games,
    moves_from_pgn,
    peek_board,
    peeks_remaining,
    record_answer,
    resign,
    turn_of,
    verification_view,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: one connection + check_same_thread=False — personal app, not multi-worker
    app.state.conn = init_db(os.environ.get("DATABASE_PATH", "games.db"))
    app.state.engines = {}
    yield
    for opp in list(app.state.engines.values()):
        try:
            opp.quit()
        except Exception:
            pass
    app.state.engines.clear()
    app.state.conn.close()


app = FastAPI(lifespan=lifespan)
# ponytail: CORS outermost so preflight still gets headers on 401
_cors = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def require_token(request, call_next):
    if request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)
    expected = os.environ.get("API_TOKEN", "")
    got = request.headers.get("authorization", "")
    if not expected or got != f"Bearer {expected}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


class CreateGameBody(BaseModel):
    player_color: str = "white"
    maia_level: int = Field(default=1900, ge=1)
    verification_questions: dict | None = None
    questions_per_batch: int | None = Field(default=None, ge=0, le=10)
    moves_interval: int | None = Field(default=None, ge=1, le=20)


class MoveBody(BaseModel):
    move_text: str


class AnswerBody(BaseModel):
    ply_number: int
    question_text: str
    correct_answer: str
    user_answer: str
    was_correct: bool


def _drop_engine(game_id: str) -> None:
    opp = app.state.engines.pop(game_id, None)
    if opp is not None:
        opp.quit()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/maia/levels")
def get_levels():
    return {"levels": available_levels()}


@app.post("/games")
def post_game(body: CreateGameBody | None = None):
    body = body or CreateGameBody()
    if body.player_color not in ("white", "black"):
        raise HTTPException(status_code=422, detail="player_color must be white or black")
    if body.maia_level not in available_levels():
        return JSONResponse({"error": "nivel de Maia no disponible"}, status_code=400)
    if count_ongoing(app.state.conn) >= _env_int("MAX_ONGOING", 3):
        return JSONResponse({"error": "demasiadas partidas en curso"}, status_code=429)
    vq = dict(body.verification_questions or {})
    # ponytail: top-level snake_case wins over nested camelCase for the two sliders
    if body.questions_per_batch is not None:
        vq["questionsPerBatch"] = body.questions_per_batch
    if body.moves_interval is not None:
        vq["movesInterval"] = body.moves_interval
    game = create_game(
        app.state.conn,
        player_color=body.player_color,
        maia_level=body.maia_level,
        verification_questions=vq or None,
    )
    app.state.engines[game["id"]] = make_opponent(body.maia_level)
    payload = {
        "game_id": game["id"],
        "your_turn": True,
        "turn": "white",
        "status": "ongoing",
        "maia_level": body.maia_level,
    }
    if body.player_color != "black":
        return payload
    try:
        opening = apply_engine_move(app.state.conn, game["id"], app.state.engines[game["id"]])
    except OpponentFailed:
        _drop_engine(game["id"])
        app.state.conn.execute("DELETE FROM games WHERE id = ?", (game["id"],))
        app.state.conn.commit()
        return JSONResponse({"error": "el rival no pudo mover"}, status_code=500)
    payload["maia_move"] = opening["applied"]
    payload["turn"] = opening["turn"]
    payload["status"] = opening["status"]
    if opening.get("result") is not None:
        payload["result"] = opening["result"]
        _drop_engine(game["id"])
    return payload


@app.get("/games")
def get_games():
    # ponytail: list_games already selects the public columns
    return {"games": [dict(r) for r in list_games(app.state.conn)]}


@app.get("/games/{game_id}")
def get_game_detail(game_id: str):
    row = get_game(app.state.conn, game_id)
    if row is None:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    out = {
        "id": row["id"],
        "created_at": row["created_at"],
        "player_color": row["player_color"],
        "maia_level": row["maia_level"],
        "status": row["status"],
        "result": row["result"],
        "pgn": row["pgn"],
    }
    if row["status"] == "finished":
        out["fen_current"] = row["fen_current"]
        out["events"] = [_event_out(e) for e in list_events(app.state.conn, game_id)]
        return out
    turn = turn_of(row["fen_current"])
    out["moves"] = moves_from_pgn(row["pgn"])
    out["turn"] = turn
    out["your_turn"] = turn == row["player_color"]
    out["peeks_remaining"] = peeks_remaining(app.state.conn, game_id)
    out.update(verification_view(row))
    return out


@app.get("/games/{game_id}/pgn")
def get_game_pgn(game_id: str):
    row = get_game(app.state.conn, game_id)
    if row is None:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    if row["status"] != "finished":
        return JSONResponse({"error": "partida en curso"}, status_code=409)
    return PlainTextResponse(
        build_pgn(row),
        media_type="application/x-chess-pgn",
    )


def _event_out(row) -> dict:
    flag = row["was_correct"]
    return {
        "id": row["id"],
        "ply_number": row["ply_number"],
        "event_type": row["event_type"],
        "question_text": row["question_text"],
        "correct_answer": row["correct_answer"],
        "user_answer": row["user_answer"],
        "was_correct": None if flag is None else bool(flag),
        "created_at": row["created_at"],
    }


@app.post("/games/{game_id}/answer")
def post_answer(game_id: str, body: AnswerBody):
    try:
        return record_answer(
            app.state.conn,
            game_id,
            body.ply_number,
            body.question_text,
            body.correct_answer,
            body.user_answer,
            body.was_correct,
        )
    except NotFound:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)


@app.post("/games/{game_id}/peek")
def post_peek(game_id: str):
    try:
        return peek_board(app.state.conn, game_id)
    except NotFound:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    except FinishedGame:
        return JSONResponse({"error": "partida terminada"}, status_code=409)
    except PeekExhausted:
        return JSONResponse({"error": "no quedan ayudas"}, status_code=403)


@app.post("/games/{game_id}/move")
def post_move(game_id: str, body: MoveBody):
    row = get_game(app.state.conn, game_id)
    if row is None:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    if row["status"] == "finished":
        return JSONResponse({"error": "partida terminada"}, status_code=409)
    try:
        opp = app.state.engines.get(game_id)
        if opp is None:
            opp = make_opponent(row["maia_level"])
            app.state.engines[game_id] = opp
        out = apply_move(app.state.conn, game_id, body.move_text, opp)
    except IllegalMove:
        return JSONResponse({"error": "jugada ilegal o no reconocida"}, status_code=400)
    except QuestionsPending:
        return JSONResponse({"error": "responde las preguntas primero"}, status_code=409)
    except OpponentFailed:
        return JSONResponse({"error": "el rival no pudo mover"}, status_code=500)
    if out["status"] == "finished":
        _drop_engine(game_id)
    return out


@app.post("/games/{game_id}/resign")
def post_resign(game_id: str):
    try:
        out = resign(app.state.conn, game_id)
    except NotFound:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    except FinishedGame:
        return JSONResponse({"error": "partida terminada"}, status_code=409)
    _drop_engine(game_id)
    return out


@app.delete("/games/{game_id}")
def delete_game_route(game_id: str):
    try:
        out = delete_game(app.state.conn, game_id)
    except NotFound:
        return JSONResponse({"error": "partida no encontrada"}, status_code=404)
    _drop_engine(game_id)
    return out
