import logging
import os
import random

import chess
import chess.engine

DEFAULT_WEIGHTS_DIR = "maia_weights"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MULTIPV = 5
DEFAULT_SEARCH_NODES = 12
SEARCH_TIME_CAP = 5
RANK_WEIGHTS = (1.0, 0.6, 0.4, 0.25, 0.15)

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default


def rank_weights(n: int) -> list[float]:
    # ponytail: InfoDict has no policy; MultiPV order + fixed decay (FR-010)
    last = RANK_WEIGHTS[-1]
    return [RANK_WEIGHTS[i] if i < len(RANK_WEIGHTS) else last for i in range(n)]


def sample_weighted(moves, weights, temperature, rng=None):
    if temperature <= 0:
        return moves[weights.index(max(weights))]
    scaled = [w ** (1 / temperature) for w in weights]
    chooser = random.choices if rng is None else rng.choices
    return chooser(list(moves), weights=scaled, k=1)[0]


def _pv_moves(info):
    lines = [info] if isinstance(info, dict) else info
    moves = []
    for line in lines:
        pv = line.get("pv") if isinstance(line, dict) else None
        if pv:
            moves.append(pv[0])
    return moves


def choose_maia_move(engine, board: chess.Board, *, temperature=None, multipv=None, nodes=None, rng=None):
    legal = list(board.legal_moves)
    if len(legal) == 1:
        return legal[0]
    if temperature is None:
        temperature = _env_float("MAIA_TEMPERATURE", DEFAULT_TEMPERATURE)
    if multipv is None:
        multipv = _env_int("MAIA_MULTIPV", DEFAULT_MULTIPV)
    if nodes is None:
        nodes = _env_int("MAIA_SEARCH_NODES", DEFAULT_SEARCH_NODES)
    limit = chess.engine.Limit(nodes=nodes, time=SEARCH_TIME_CAP)
    info = engine.analyse(board, limit, multipv=min(multipv, len(legal)))
    moves = _pv_moves(info)
    if not moves:
        return engine.play(board, limit).move
    weights = rank_weights(len(moves))
    chosen = sample_weighted(moves, weights, temperature, rng)
    logger.debug("Maia eligió %s entre candidatos=%s pesos=%s", chosen, moves, weights)
    return chosen


def available_levels(weights_dir=None):
    # ponytail: catalog is the directory listing, not a constant
    directory = weights_dir or os.environ.get("MAIA_WEIGHTS_DIR", DEFAULT_WEIGHTS_DIR)
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    levels = []
    for name in names:
        if name.startswith("maia-") and name.endswith(".pb.gz"):
            mid = name[len("maia-") : -len(".pb.gz")]
            if mid.isdigit():
                levels.append(int(mid))
    return sorted(levels)


def weights_path(level: int, weights_dir=None) -> str:
    directory = weights_dir or os.environ.get("MAIA_WEIGHTS_DIR", DEFAULT_WEIGHTS_DIR)
    return os.path.join(directory, f"maia-{level}.pb.gz")


class FakeOpponent:
    def __init__(self, level=None):
        self.level = level

    def play(self, board: chess.Board) -> chess.Move:
        return next(iter(board.legal_moves))

    def quit(self) -> None:
        pass


class Lc0Opponent:
    def __init__(self, path: str, weights: str):
        self._eng = chess.engine.SimpleEngine.popen_uci(path)
        try:
            self._eng.configure({"WeightsFile": weights})
        except Exception:
            self._eng.quit()
            raise

    def play(self, board: chess.Board) -> chess.Move:
        # ponytail: sampling lives in choose_maia_move; time=5 still caps SC-002
        return choose_maia_move(self._eng, board)

    def quit(self) -> None:
        self._eng.quit()


def make_opponent(maia_level: int = 1900):
    path = os.environ.get("LC0_PATH")
    if not path:
        return FakeOpponent(maia_level)
    # ponytail: per-game path from level; MAIA_WEIGHTS no longer overrides
    return Lc0Opponent(path, weights_path(maia_level))
