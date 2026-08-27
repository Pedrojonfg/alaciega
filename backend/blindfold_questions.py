"""
blindfold_questions.py

Funciones deterministas para generar y verificar preguntas de "¿estás viendo
bien el tablero?" en una app de ajedrez a la ciega, usando python-chess.

Todas las funciones son O(numero_de_piezas) o menos, no requieren ningun LLM
ni heuristica de evaluacion: son consultas de reglas puras sobre un chess.Board.

Convencion: color = chess.WHITE / chess.BLACK
"""

import chess

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

MINOR_PIECES = (chess.KNIGHT, chess.BISHOP)
MAJOR_PIECES = (chess.ROOK, chess.QUEEN)


# ---------------------------------------------------------------------------
# 1. Posicion global
# ---------------------------------------------------------------------------

def total_piece_count(board: chess.Board) -> int:
    """Cuantas piezas hay en total sobre el tablero."""
    return len(board.piece_map())


def piece_counts_by_type(board: chess.Board, color: chess.Color) -> dict:
    """Cuantos peones / piezas menores / piezas mayores tiene un bando."""
    pawns = len(board.pieces(chess.PAWN, color))
    minors = sum(len(board.pieces(pt, color)) for pt in MINOR_PIECES)
    majors = sum(len(board.pieces(pt, color)) for pt in MAJOR_PIECES)
    queens = len(board.pieces(chess.QUEEN, color))
    return {"peones": pawns, "menores": minors, "mayores": majors, "damas": queens}


def material_balance(board: chess.Board) -> int:
    """
    Balance de material en puntos, positivo a favor de las blancas.
    (peon=1, caballo/alfil=3, torre=5, dama=9)
    """
    balance = 0
    for piece_type, value in PIECE_VALUES.items():
        balance += value * len(board.pieces(piece_type, chess.WHITE))
        balance -= value * len(board.pieces(piece_type, chess.BLACK))
    return balance


def can_castle(board: chess.Board, color: chess.Color) -> dict:
    """Si el jugador puede enrocar corto y/o largo (derecho + no bloqueado)."""
    return {
        "corto": board.has_kingside_castling_rights(color)
        and any(m.from_square == board.king(color) and chess.square_file(m.to_square) == 6
                for m in board.legal_moves),
        "largo": board.has_queenside_castling_rights(color)
        and any(m.from_square == board.king(color) and chess.square_file(m.to_square) == 2
                for m in board.legal_moves),
    }


def en_passant_available(board: chess.Board) -> bool:
    """Si hay una captura al paso legal disponible ahora mismo."""
    return board.has_legal_en_passant()


def draw_conditions(board: chess.Board) -> dict:
    """Condiciones de tablas activas en la posicion actual."""
    return {
        "ahogado": board.is_stalemate(),
        "material_insuficiente": board.is_insufficient_material(),
        "repeticion_triple": board.can_claim_threefold_repetition(),
        "repeticion_quintuple": board.is_fivefold_repetition(),
        "regla_50_movimientos": board.can_claim_fifty_moves(),
        "regla_75_movimientos": board.is_seventyfive_moves(),
    }


# ---------------------------------------------------------------------------
# 2. Localizacion y color de casillas
# ---------------------------------------------------------------------------

def king_square(board: chess.Board, color: chess.Color) -> str:
    """Casilla (en notacion algebraica) donde esta el rey de ese color."""
    return chess.square_name(board.king(color))


def piece_at(board: chess.Board, square_name: str) -> str | None:
    """Que pieza (simbolo FEN) hay en una casilla, o None si esta vacia."""
    piece = board.piece_at(chess.parse_square(square_name))
    return piece.symbol() if piece else None


def square_color(square_name: str) -> str:
    """Color de una casilla: 'clara' u 'oscura'."""
    sq = chess.parse_square(square_name)
    return "oscura" if (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 0 else "clara"


def alignment(square_a: str, square_b: str) -> list:
    """En que lineas comparten dos casillas: fila, columna y/o diagonal."""
    a, b = chess.parse_square(square_a), chess.parse_square(square_b)
    fa, ra = chess.square_file(a), chess.square_rank(a)
    fb, rb = chess.square_file(b), chess.square_rank(b)
    lines = []
    if fa == fb:
        lines.append("columna")
    if ra == rb:
        lines.append("fila")
    if abs(fa - fb) == abs(ra - rb):
        lines.append("diagonal")
    return lines


def square_distance(square_a: str, square_b: str) -> int:
    """Distancia (Chebyshev, la que usaria un rey) entre dos casillas."""
    return chess.square_distance(chess.parse_square(square_a), chess.parse_square(square_b))


def most_advanced_piece(board: chess.Board, color: chess.Color) -> str | None:
    """Casilla de la pieza (no rey) mas cercana a la coronacion para ese bando."""
    squares = [sq for pt in PIECE_VALUES if pt != chess.KING
               for sq in board.pieces(pt, color)]
    if not squares:
        return None
    key = (lambda s: chess.square_rank(s)) if color == chess.WHITE else \
          (lambda s: -chess.square_rank(s))
    return chess.square_name(max(squares, key=key))


# ---------------------------------------------------------------------------
# 3. Movilidad y control
# ---------------------------------------------------------------------------

def legal_move_count(board: chess.Board) -> int:
    """Cuantos movimientos legales tiene el jugador al que le toca mover."""
    return board.legal_moves.count()


def legal_moves_for_piece(board: chess.Board, square_name: str) -> list:
    """Movimientos legales (destinos) de la pieza en una casilla concreta."""
    sq = chess.parse_square(square_name)
    return [chess.square_name(m.to_square) for m in board.legal_moves if m.from_square == sq]


def can_reach(board: chess.Board, from_square: str, to_square: str) -> bool:
    """Si la pieza en from_square puede llegar a to_square en un movimiento legal."""
    fs, ts = chess.parse_square(from_square), chess.parse_square(to_square)
    return any(m.from_square == fs and m.to_square == ts for m in board.legal_moves)


def squares_attacked_by(board: chess.Board, square_name: str) -> int:
    """Cuantas casillas ataca (pseudo-legal) la pieza situada en square_name."""
    return len(board.attacks(chess.parse_square(square_name)))


def who_controls(board: chess.Board, square_name: str) -> dict:
    """Quien controla una casilla: numero de atacantes blancos y negros."""
    sq = chess.parse_square(square_name)
    return {
        "blancas": len(board.attackers(chess.WHITE, sq)),
        "negras": len(board.attackers(chess.BLACK, sq)),
    }


def king_escape_squares(board: chess.Board, color: chess.Color) -> int:
    """Casillas de escape (movimientos legales sin capturar) del rey dado."""
    king_sq = board.king(color)
    return sum(1 for m in board.legal_moves
               if m.from_square == king_sq and not board.is_capture(m))


# ---------------------------------------------------------------------------
# 4. Amenazas y relaciones tacticas
# ---------------------------------------------------------------------------

def hanging_pieces(board: chess.Board, color: chess.Color) -> list:
    """
    Piezas de 'color' atacadas por el rival y sin ninguna defensa propia.
    (version simple: colgada = 0 defensores propios y >=1 atacante rival)
    """
    hanging = []
    for sq, piece in board.piece_map().items():
        if piece.color != color:
            continue
        attackers = board.attackers(not color, sq)
        defenders = board.attackers(color, sq)
        if attackers and not defenders:
            hanging.append(chess.square_name(sq))
    return hanging


def pinned_pieces(board: chess.Board, color: chess.Color) -> list:
    """Piezas de 'color' actualmente clavadas."""
    return [chess.square_name(sq) for sq, piece in board.piece_map().items()
            if piece.color == color and board.is_pinned(color, sq)]


def defenders_count(board: chess.Board, square_name: str) -> int:
    """Cuantas piezas propias defienden la pieza situada en square_name."""
    sq = chess.parse_square(square_name)
    piece = board.piece_at(sq)
    if piece is None:
        return 0
    return len(board.attackers(piece.color, sq))


def least_valuable_attacked_piece(board: chess.Board, color: chess.Color) -> str | None:
    """Pieza de menor valor de 'color' que esta siendo atacada ahora mismo."""
    candidates = []
    for sq, piece in board.piece_map().items():
        if piece.color == color and board.attackers(not color, sq):
            candidates.append((PIECE_VALUES[piece.piece_type], chess.square_name(sq)))
    if not candidates:
        return None
    return min(candidates, key=lambda x: x[0])[1]


def attackers_count(board: chess.Board, square_name: str, attacker_color: chess.Color) -> int:
    """Cuantas piezas de attacker_color atacan esa casilla."""
    return len(board.attackers(attacker_color, chess.parse_square(square_name)))


def discovered_check_moves(board: chess.Board) -> list:
    """
    Movimientos legales que producen jaque a la descubierta, es decir,
    el jaque final NO lo da la pieza que se acaba de mover.
    """
    results = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_check() and move.to_square not in board.checkers():
            results.append(move.uci())
        board.pop()
    return results


# ---------------------------------------------------------------------------
# 5. Estructura de peones
# ---------------------------------------------------------------------------

def passed_pawns(board: chess.Board, color: chess.Color) -> list:
    """Peones de 'color' que son pasados (sin peon rival por delante en su columna o adyacentes)."""
    own = board.pieces(chess.PAWN, color)
    rival = board.pieces(chess.PAWN, not color)
    passed = []
    for sq in own:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        blocked = False
        for osq in rival:
            of, orank = chess.square_file(osq), chess.square_rank(osq)
            if abs(of - f) <= 1:
                if (color == chess.WHITE and orank > r) or (color == chess.BLACK and orank < r):
                    blocked = True
                    break
        if not blocked:
            passed.append(chess.square_name(sq))
    return passed


def doubled_pawns(board: chess.Board, color: chess.Color) -> list:
    """Columnas donde 'color' tiene mas de un peon."""
    files = {}
    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        files[f] = files.get(f, 0) + 1
    return [chess.FILE_NAMES[f] for f, count in files.items() if count > 1]


def isolated_pawns(board: chess.Board, color: chess.Color) -> list:
    """Peones de 'color' sin peones propios en columnas adyacentes."""
    own_files = {chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)}
    isolated = []
    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        if (f - 1) not in own_files and (f + 1) not in own_files:
            isolated.append(chess.square_name(sq))
    return isolated


def pawns_on_file(board: chess.Board, color: chess.Color, file_letter: str) -> int:
    """Cuantos peones tiene 'color' en una columna dada ('a'..'h')."""
    f = chess.FILE_NAMES.index(file_letter)
    return sum(1 for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == f)
