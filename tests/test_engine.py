import random

import chess
import pytest

from backend.engine import (
    DEFAULT_WEIGHTS_DIR,
    FakeOpponent,
    available_levels,
    choose_maia_move,
    make_opponent,
    rank_weights,
    sample_weighted,
    weights_path,
)


def _stub_weights(dirpath, *levels, junk=()):
    dirpath.mkdir(parents=True, exist_ok=True)
    for n in levels:
        (dirpath / f"maia-{n}.pb.gz").write_bytes(b"")
    for name in junk:
        (dirpath / name).write_bytes(b"")


def test_available_levels_sorted_ignores_junk(tmp_path):
    _stub_weights(tmp_path, 1900, 1100, 1500, junk=("readme.txt", "maia-notes.pb.gz.bak"))
    assert available_levels(str(tmp_path)) == [1100, 1500, 1900]


def test_available_levels_missing_dir(tmp_path):
    assert available_levels(str(tmp_path / "nope")) == []


def test_available_levels_reads_env(tmp_path, monkeypatch):
    _stub_weights(tmp_path, 1200)
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(tmp_path))
    assert available_levels() == [1200]


def test_weights_path_joins_dir_and_level(tmp_path):
    assert weights_path(1500, str(tmp_path)) == str(tmp_path / "maia-1500.pb.gz")


def test_default_weights_dir_is_relative():
    assert DEFAULT_WEIGHTS_DIR == "maia_weights"
    assert not DEFAULT_WEIGHTS_DIR.startswith("/")


def test_fake_plays_legal_move():
    board = chess.Board()
    move = FakeOpponent().play(board)
    assert move in board.legal_moves


def test_fake_quit_is_safe():
    FakeOpponent().quit()


def test_make_opponent_defaults_to_fake(monkeypatch):
    monkeypatch.delenv("LC0_PATH", raising=False)
    assert isinstance(make_opponent(), FakeOpponent)


def test_make_opponent_fake_records_level(monkeypatch):
    monkeypatch.delenv("LC0_PATH", raising=False)
    assert make_opponent(1500).level == 1500


def test_make_opponent_lc0_when_path_set(monkeypatch, tmp_path):
    monkeypatch.setenv("LC0_PATH", "lc0")
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(tmp_path))

    class Dummy:
        def configure(self, cfg):
            self.cfg = cfg

        def quit(self):
            pass

    dummy = Dummy()
    monkeypatch.setattr("chess.engine.SimpleEngine.popen_uci", lambda path: dummy)
    from backend.engine import Lc0Opponent

    opp = make_opponent(1500)
    assert isinstance(opp, Lc0Opponent)
    assert dummy.cfg == {"WeightsFile": weights_path(1500, str(tmp_path))}
    opp.quit()


def test_lc0_play_uses_analyse_not_argmax(monkeypatch, tmp_path):
    monkeypatch.setenv("LC0_PATH", "lc0")
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(tmp_path))
    monkeypatch.setenv("MAIA_TEMPERATURE", "0")
    e4, d4 = chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4")
    dummy = _DummyEngine(info=[{"pv": [d4]}, {"pv": [e4]}], play_move=e4)
    dummy.configure = lambda cfg: None
    dummy.quit = lambda: None
    monkeypatch.setattr("chess.engine.SimpleEngine.popen_uci", lambda path: dummy)
    from backend.engine import Lc0Opponent

    opp = make_opponent(1500)
    assert isinstance(opp, Lc0Opponent)
    move = opp.play(chess.Board())
    assert move == d4
    assert dummy.analyse_calls
    assert dummy.play_calls == []
    opp.quit()


def test_fake_raises_when_no_legal_moves():
    board = chess.Board()
    for san in ("f3", "e5", "g4", "Qh4#"):
        board.push_san(san)
    with pytest.raises(StopIteration):
        FakeOpponent().play(board)


class _DummyEngine:
    def __init__(self, info, play_move=None):
        self.info = info
        self.play_move = play_move
        self.analyse_calls = []
        self.play_calls = []

    def analyse(self, board, limit, multipv=None):
        self.analyse_calls.append((board, limit, multipv))
        return self.info

    def play(self, board, limit):
        self.play_calls.append((board, limit))
        return type("R", (), {"move": self.play_move})()


def test_sample_weighted_t0_picks_max():
    a, b, c = chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4"), chess.Move.from_uci("c2c4")
    assert sample_weighted([a, b, c], [0.2, 0.9, 0.4], 0) == b
    assert sample_weighted([a, b, c], [0.2, 0.9, 0.4], -1) == b


def test_sample_weighted_scales_and_calls_choices():
    a, b = chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4")

    class Rng:
        def __init__(self):
            self.seen = None

        def choices(self, population, weights=None, k=1):
            self.seen = (list(population), list(weights), k)
            return [population[1]]

    rng = Rng()
    assert sample_weighted([a, b], [1.0, 0.6], 0.5, rng) == b
    moves, weights, k = rng.seen
    assert moves == [a, b]
    assert k == 1
    assert weights == pytest.approx([1.0 ** 2, 0.6 ** 2])


def test_rank_weights_decay_and_tail():
    assert rank_weights(5) == [1.0, 0.6, 0.4, 0.25, 0.15]
    assert rank_weights(6)[-1] == 0.15
    assert rank_weights(1) == [1.0]
    assert rank_weights(0) == []


def test_choose_skips_analyse_when_one_legal():
    board = chess.Board("k7/8/1K6/8/8/8/8/R7 b - - 0 1")
    engine = _DummyEngine(info=[{"pv": [chess.Move.from_uci("a8b8")]}])
    move = choose_maia_move(engine, board, temperature=0.2, multipv=5, nodes=12)
    assert move == chess.Move.from_uci("a8b8")
    assert engine.analyse_calls == []
    assert engine.play_calls == []


def test_choose_t0_is_deterministic_argmax():
    e4, d4, c4 = (chess.Move.from_uci(u) for u in ("e2e4", "d2d4", "c2c4"))
    engine = _DummyEngine(
        info=[
            {"pv": [d4]},
            {"pv": [e4]},
            {"pv": [c4]},
        ]
    )
    board = chess.Board()
    first = choose_maia_move(engine, board, temperature=0, multipv=5, nodes=12)
    second = choose_maia_move(engine, board, temperature=0, multipv=5, nodes=12)
    assert first == second == d4
    assert len(engine.analyse_calls) == 2
    _board, limit, multipv = engine.analyse_calls[0]
    assert multipv == 5
    assert limit.nodes == 12
    assert limit.time == 5


def test_choose_caps_multipv_to_legal_count():
    board = chess.Board()
    engine = _DummyEngine(info=[{"pv": [chess.Move.from_uci("e2e4")]}])
    choose_maia_move(engine, board, temperature=0, multipv=99, nodes=12)
    assert engine.analyse_calls[0][2] == 20


def test_choose_fallback_when_no_pv():
    fallback = chess.Move.from_uci("g1f3")
    engine = _DummyEngine(info=[{}, {"pv": []}], play_move=fallback)
    move = choose_maia_move(engine, chess.Board(), temperature=0.2, multipv=5, nodes=12)
    assert move == fallback
    assert len(engine.play_calls) == 1


def test_choose_reads_env_defaults(monkeypatch):
    monkeypatch.delenv("MAIA_TEMPERATURE", raising=False)
    monkeypatch.delenv("MAIA_MULTIPV", raising=False)
    monkeypatch.delenv("MAIA_SEARCH_NODES", raising=False)
    e4 = chess.Move.from_uci("e2e4")
    engine = _DummyEngine(info=[{"pv": [e4]}])
    choose_maia_move(engine, chess.Board())
    _board, limit, multipv = engine.analyse_calls[0]
    assert multipv == 5
    assert limit.nodes == 12


def test_choose_invalid_env_falls_back_to_defaults(monkeypatch):
    monkeypatch.setenv("MAIA_TEMPERATURE", "nope")
    monkeypatch.setenv("MAIA_MULTIPV", "x")
    monkeypatch.setenv("MAIA_SEARCH_NODES", "-3")
    e4 = chess.Move.from_uci("e2e4")
    engine = _DummyEngine(info=[{"pv": [e4]}])
    choose_maia_move(engine, chess.Board())
    _board, limit, multipv = engine.analyse_calls[0]
    assert multipv == 5
    assert limit.nodes == 12


def test_choose_variety_with_spread_weights():
    e4, d4, nf3 = (chess.Move.from_uci(u) for u in ("e2e4", "d2d4", "g1f3"))
    engine = _DummyEngine(info=[{"pv": [e4]}, {"pv": [d4]}, {"pv": [nf3]}])
    rng = random.Random(0)
    seen = {
        choose_maia_move(engine, chess.Board(), temperature=0.2, rng=rng)
        for _ in range(40)
    }
    assert len(seen) >= 2
