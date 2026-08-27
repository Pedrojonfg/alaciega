import random
import chess

from backend import blindfold_questions as bq

# Legacy three — prompt values are promptLong (tests assert equality).
PROMPTS = {
    "captures": (
        "¿Cuántas capturas legales tiene el jugador en turno "
        "(el bando que mueve ahora)?"
    ),
    "checks": (
        "¿Cuántas jugadas legales del bando en turno dan jaque en esta posición?"
    ),
    "in_check": (
        "¿Está el rey del bando en turno actualmente en jaque? Responde sí o no."
    ),
}
PROMPTS_EN = {
    "captures": "How many legal captures does the side to move have?",
    "checks": "How many legal moves by the side to move give check in this position?",
    "in_check": "Is the side to move's king currently in check? Answer yes or no.",
}
ALIASES = {"captures": "captures_available", "checks": "checks_available"}
KINDS = tuple(PROMPTS)  # ponytail: old tests pin these three via kind=

_LIST_HINT = (
    "Sepáralas por comas (ej. a3, f6). Si no hay ninguna, deja la respuesta vacía "
    "— no pongas un guion ni \"ninguna\"."
)
_LIST_HINT_EN = (
    'Separate them with commas (e.g. a3, f6). If there are none, leave the answer empty '
    '— do not write a dash or "none".'
)
_YESNO = "Responde sí o no."
_YESNO_EN = "Answer yes or no."
_ANSWER_ALIASES = {
    "light": "clara",
    "dark": "oscura",
    "rank": "fila",
    "file": "columna",
    "row": "fila",
    "yes": "sí",
}


def _canon(kind: str) -> str:
    return ALIASES.get(kind, kind)


# ponytail: maps instead of a QuestionDefinition class
MIN_MOVE = {
    "en_passant_available": 2,
    "draw_conditions": 10,
    "hanging_pieces": 2,
    "attackers_count": 2,
    "least_valuable_attacked_piece": 2,
    "pinned_pieces": 3,
    "doubled_pawns": 4,
    "isolated_pawns": 4,
    "passed_pawns": 6,
}

# ponytail: synthetic instance, not a REGISTRY kind
FALLBACK_PROMPT = "No quedan más preguntas por hacer en este tipo de posición"
FALLBACK_PROMPT_EN = "No more questions left for this kind of position"


def _inst(kind, prompt_long, prompt_short, answer, expected, turn_dependent=False, en=None):
    canon = _canon(kind)
    long_en, short_en = en if en else (prompt_long, prompt_short)
    return {
        "type": kind,
        "prompt": prompt_long,
        "promptLong": prompt_long,
        "promptShort": prompt_short,
        "promptEn": long_en,
        "promptShortEn": short_en,
        "turnDependent": turn_dependent,
        "answer": answer,
        "expectedAnswerType": expected,
        "minMoveNumber": MIN_MOVE.get(canon, 1),
        "allowsEmptyAnswer": expected == "square_list",
    }


def _color_es(color) -> str:
    return "blancas" if color == chess.WHITE else "negras"


def _color_en(color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _color_en_s(color) -> str:
    return "White's" if color == chess.WHITE else "Black's"


def _alias(tok: str) -> str:
    return _ANSWER_ALIASES.get(tok, tok)


def _sq_names():
    return list(chess.SQUARE_NAMES)


def _occupied(board):
    return [chess.square_name(sq) for sq in board.piece_map()]


def _gen_captures(board, rng):
    n = sum(1 for m in board.legal_moves if board.is_capture(m))
    return _inst(
        "captures_available",
        PROMPTS["captures"],
        "Capturas legales del bando en turno",
        n,
        "number",
        turn_dependent=True,
        en=(PROMPTS_EN["captures"], "Legal captures by the side to move"),
    )


def _gen_checks(board, rng):
    n = sum(1 for m in board.legal_moves if board.gives_check(m))
    return _inst(
        "checks_available",
        PROMPTS["checks"],
        "Jaques legales del bando en turno",
        n,
        "number",
        turn_dependent=True,
        en=(PROMPTS_EN["checks"], "Legal checks by the side to move"),
    )


def _gen_in_check(board, rng):
    return _inst(
        "in_check",
        PROMPTS["in_check"],
        "Rey en turno en jaque",
        board.is_check(),
        "boolean",
        turn_dependent=True,
        en=(PROMPTS_EN["in_check"], "Side to move in check"),
    )


def _gen_side_to_move(board, rng):
    return _inst(
        "side_to_move",
        f"¿Le toca mover a las blancas? {_YESNO}",
        "Turno de las blancas",
        board.turn == chess.WHITE,
        "boolean",
        en=(f"Is it White's turn to move? {_YESNO_EN}", "White to move"),
    )


def _gen_total_piece_count(board, rng):
    return _inst(
        "total_piece_count",
        "¿Cuántas piezas hay en el tablero en total (blancas y negras)?",
        "Total de piezas",
        bq.total_piece_count(board),
        "number",
        en=("How many pieces are on the board in total (White and Black)?", "Total pieces"),
    )


def _gen_material_balance(board, rng):
    return _inst(
        "material_balance",
        "¿Cuál es el balance de material (positivo a favor de las blancas, "
        "negativo a favor de las negras)?",
        "Balance de material",
        bq.material_balance(board),
        "number",
        en=(
            "What is the material balance (positive favours White, negative favours Black)?",
            "Material balance",
        ),
    )


def _gen_castling_rights(board, rng):
    color = board.turn
    side = rng.choice(["corto", "largo"])
    side_en = "kingside" if side == "corto" else "queenside"
    ok = bq.can_castle(board, color)[side]
    return _inst(
        "castling_rights",
        f"¿Pueden las {_color_es(color)} (bando en turno) enrocar {side}? {_YESNO}",
        f"Enroque {side} del bando en turno",
        ok,
        "boolean",
        turn_dependent=True,
        en=(
            f"Can {_color_en(color)} (side to move) castle {side_en}? {_YESNO_EN}",
            f"{side_en.capitalize()} castle for the side to move",
        ),
    )


def _gen_en_passant(board, rng):
    return _inst(
        "en_passant_available",
        f"¿Hay una captura al paso legal ahora mismo para el bando en turno? {_YESNO}",
        "Captura al paso legal",
        bq.en_passant_available(board),
        "boolean",
        turn_dependent=True,
        en=(
            f"Is there a legal en passant capture for the side to move right now? {_YESNO_EN}",
            "Legal en passant",
        ),
    )


def _gen_draw_conditions(board, rng):
    flags = bq.draw_conditions(board)
    key = rng.choice(list(flags))
    labels = {
        "ahogado": ("ahogado", "stalemate"),
        "material_insuficiente": ("material insuficiente", "insufficient material"),
        "repeticion_triple": ("triple repetición reclamable", "a claimable threefold repetition"),
        "repeticion_quintuple": ("repetición quíntuple", "fivefold repetition"),
        "regla_50_movimientos": ("la regla de 50 movimientos reclamable", "a claimable fifty-move rule"),
        "regla_75_movimientos": ("la regla de 75 movimientos", "the seventy-five-move rule"),
    }
    es, en = labels[key]
    return _inst(
        "draw_conditions",
        f"¿Hay {es} en esta posición? {_YESNO}",
        f"Tablas: {es}",
        flags[key],
        "boolean",
        en=(f"Is there {en} in this position? {_YESNO_EN}", f"Draw: {en}"),
    )


def _gen_king_square(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    if board.king(color) is None:
        return None
    return _inst(
        "king_square",
        f"¿En qué casilla está el rey de las {_color_es(color)}? "
        "(una casilla, p. ej. e1)",
        f"Casilla del rey {_color_es(color)}",
        bq.king_square(board, color),
        "square",
        en=(
            f"Which square is the {_color_en(color)} king on? (one square, e.g. e1)",
            f"{_color_en(color)} king square",
        ),
    )


def _gen_piece_at_square(board, rng):
    names = _occupied(board) or _sq_names()
    sq = rng.choice(names)
    piece = bq.piece_at(board, sq)
    return _inst(
        "piece_at_square",
        f"¿Qué pieza hay en {sq}? Usa el símbolo FEN (KQRBNPkqrbnp). "
        "Si está vacía, deja la respuesta vacía.",
        f"Pieza en {sq}",
        piece,
        "piece_symbol",
        en=(
            f"What piece is on {sq}? Use the FEN symbol (KQRBNPkqrbnp). "
            "If empty, leave the answer empty.",
            f"Piece on {sq}",
        ),
    )


def _gen_square_color(board, rng):
    sq = rng.choice(_sq_names())
    return _inst(
        "square_color",
        f"¿De qué color es la casilla {sq}? Responde clara u oscura.",
        f"Color de {sq}",
        bq.square_color(sq),
        "piece_symbol",
        en=(f"What colour is square {sq}? Answer light or dark.", f"Colour of {sq}"),
    )


def _gen_alignment(board, rng):
    a, b = rng.choice(_sq_names()), rng.choice(_sq_names())
    if a == b:
        b = "h8" if a != "h8" else "a1"
    return _inst(
        "alignment",
        f"¿En qué líneas coinciden {a} y {b}? "
        f"Lista fila, columna y/o diagonal. {_LIST_HINT}",
        f"Alineación {a}-{b}",
        bq.alignment(a, b),
        "square_list",
        en=(
            f"Which lines do {a} and {b} share? "
            f"List rank, file and/or diagonal. {_LIST_HINT_EN}",
            f"Alignment {a}-{b}",
        ),
    )


def _gen_square_distance(board, rng):
    a, b = rng.choice(_sq_names()), rng.choice(_sq_names())
    return _inst(
        "square_distance",
        f"¿Cuál es la distancia de rey (número de pasos) entre {a} y {b}?",
        f"Distancia {a}-{b}",
        bq.square_distance(a, b),
        "number",
        en=(
            f"What is the king-move distance (number of steps) between {a} and {b}?",
            f"Distance {a}-{b}",
        ),
    )


def _gen_most_advanced(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    sq = bq.most_advanced_piece(board, color)
    if sq is None:
        return None
    return _inst(
        "most_advanced_piece",
        f"¿En qué casilla está la pieza (no rey) más avanzada de las {_color_es(color)}?",
        f"Pieza más avanzada {_color_es(color)}",
        sq,
        "square",
        en=(
            f"Which square has {_color_en_s(color)} most advanced non-king piece?",
            f"Most advanced {_color_en(color)} piece",
        ),
    )


def _gen_legal_move_count(board, rng):
    return _inst(
        "legal_move_count",
        "¿Cuántos movimientos legales tiene el bando que mueve ahora?",
        "Movimientos legales (bando en turno)",
        bq.legal_move_count(board),
        "number",
        turn_dependent=True,
        en=("How many legal moves does the side to move have?", "Legal moves (side to move)"),
    )


def _gen_legal_moves_for_piece(board, rng):
    names = _occupied(board)
    if not names:
        return None
    sq = rng.choice(names)
    # legal_moves is empty for the side that does not move → answer 0
    n = len(bq.legal_moves_for_piece(board, sq))
    return _inst(
        "legal_moves_for_piece",
        f"¿Cuántos movimientos legales tiene la pieza en {sq}? "
        "(si esa pieza no es del bando que mueve ahora, la respuesta es 0)",
        f"Movimientos legales en {sq}",
        n,
        "number",
        turn_dependent=True,
        en=(
            f"How many legal moves does the piece on {sq} have? "
            "(if that piece is not the side to move's, the answer is 0)",
            f"Legal moves from {sq}",
        ),
    )


def _gen_can_reach(board, rng):
    names = _occupied(board)
    if not names:
        return None
    frm = rng.choice(names)
    dests = bq.legal_moves_for_piece(board, frm)
    to = (
        rng.choice(dests)
        if dests and rng.choice([True, False])
        else rng.choice(_sq_names())
    )
    ok = bq.can_reach(board, frm, to)
    return _inst(
        "can_reach",
        f"¿Puede la pieza en {frm} llegar a {to} en un movimiento legal? "
        f"(si esa pieza no es del bando que mueve ahora, la respuesta es no). {_YESNO}",
        f"¿{frm} puede a {to}?",
        ok,
        "boolean",
        turn_dependent=True,
        en=(
            f"Can the piece on {frm} reach {to} in one legal move? "
            f"(if that piece is not the side to move's, the answer is no). {_YESNO_EN}",
            f"Can {frm} reach {to}?",
        ),
    )


def _gen_squares_attacked_by(board, rng):
    names = _occupied(board)
    if not names:
        return None
    sq = rng.choice(names)
    return _inst(
        "squares_attacked_by",
        f"¿Cuántas casillas ataca geométricamente la pieza en {sq} "
        "(sin exigir que el movimiento sea legal por jaque)?",
        f"Casillas atacadas desde {sq}",
        bq.squares_attacked_by(board, sq),
        "number",
        en=(
            f"How many squares does the piece on {sq} attack geometrically "
            "(not requiring the move to be legal regarding check)?",
            f"Squares attacked from {sq}",
        ),
    )


def _gen_who_controls(board, rng):
    sq = rng.choice(_sq_names())
    color = rng.choice([chess.WHITE, chess.BLACK])
    n = bq.who_controls(board, sq)["blancas" if color == chess.WHITE else "negras"]
    return _inst(
        "who_controls_square",
        f"¿Cuántas piezas {_color_es(color)} controlan {sq}?",
        f"Control {_color_es(color)} de {sq}",
        n,
        "number",
        en=(
            f"How many {_color_en(color)} pieces control {sq}?",
            f"{_color_en(color)} control of {sq}",
        ),
    )


def _gen_king_escape(board, rng):
    color = board.turn
    if board.king(color) is None:
        return None
    return _inst(
        "king_escape_squares",
        "¿Cuántas casillas de escape sin captura tiene el rey del bando en turno?",
        "Escapes del rey en turno",
        bq.king_escape_squares(board, color),
        "number",
        turn_dependent=True,
        en=(
            "How many capture-free escape squares does the side to move's king have?",
            "King escapes for the side to move",
        ),
    )


def _gen_hanging(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "hanging_pieces",
        f"¿Qué casillas tienen piezas colgadas de las {_color_es(color)} ahora mismo? "
        f"{_LIST_HINT}",
        f"Piezas colgadas {_color_es(color)}",
        bq.hanging_pieces(board, color),
        "square_list",
        en=(
            f"Which squares have hanging {_color_en(color)} pieces right now? {_LIST_HINT_EN}",
            f"Hanging {_color_en(color)} pieces",
        ),
    )


def _gen_pinned(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "pinned_pieces",
        f"¿En qué casillas hay piezas clavadas de las {_color_es(color)}? {_LIST_HINT}",
        f"Piezas clavadas {_color_es(color)}",
        bq.pinned_pieces(board, color),
        "square_list",
        en=(
            f"On which squares are {_color_en_s(color)} pinned pieces? {_LIST_HINT_EN}",
            f"Pinned {_color_en(color)} pieces",
        ),
    )


def _gen_defenders(board, rng):
    names = _occupied(board)
    if not names:
        return None
    sq = rng.choice(names)
    return _inst(
        "defenders_count",
        f"¿Cuántas piezas propias (del bando de la pieza en {sq}) defienden {sq}?",
        f"Defensores de {sq}",
        bq.defenders_count(board, sq),
        "number",
        en=(
            f"How many friendly pieces (of the side that owns the piece on {sq}) defend {sq}?",
            f"Defenders of {sq}",
        ),
    )


def _gen_least_valuable(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    sq = bq.least_valuable_attacked_piece(board, color)
    if sq is None:
        return None
    return _inst(
        "least_valuable_attacked_piece",
        f"¿En qué casilla está la pieza atacada de menor valor de las {_color_es(color)}?",
        f"Pieza atacada menor valor {_color_es(color)}",
        sq,
        "square",
        en=(
            f"On which square is {_color_en_s(color)} lowest-value attacked piece?",
            f"Lowest-value attacked {_color_en(color)} piece",
        ),
    )


def _gen_attackers(board, rng):
    sq = rng.choice(_sq_names())
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "attackers_count",
        f"¿Cuántas piezas {_color_es(color)} atacan {sq}?",
        f"Atacantes {_color_es(color)} de {sq}",
        bq.attackers_count(board, sq, color),
        "number",
        en=(
            f"How many {_color_en(color)} pieces attack {sq}?",
            f"{_color_en(color)} attackers of {sq}",
        ),
    )


def _gen_discovered_check(board, rng):
    return _inst(
        "discovered_check",
        "¿Cuántas jugadas legales del bando en turno dan jaque a la descubierta?",
        "Jaques a la descubierta",
        len(bq.discovered_check_moves(board)),
        "number",
        turn_dependent=True,
        en=(
            "How many legal moves by the side to move give discovered check?",
            "Discovered checks",
        ),
    )


def _gen_passed_pawns(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "passed_pawns",
        f"¿En qué casillas hay peones pasados de las {_color_es(color)}? {_LIST_HINT}",
        f"Peones pasados {_color_es(color)}",
        bq.passed_pawns(board, color),
        "square_list",
        en=(
            f"On which squares are {_color_en_s(color)} passed pawns? {_LIST_HINT_EN}",
            f"Passed {_color_en(color)} pawns",
        ),
    )


def _gen_doubled_pawns(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "doubled_pawns",
        f"¿En qué columnas tienen peones doblados las {_color_es(color)}? "
        f"Lista letras de columna. {_LIST_HINT}",
        f"Peones doblados {_color_es(color)}",
        bq.doubled_pawns(board, color),
        "square_list",
        en=(
            f"On which files do {_color_en(color)} have doubled pawns? "
            f"List file letters. {_LIST_HINT_EN}",
            f"Doubled {_color_en(color)} pawns",
        ),
    )


def _gen_isolated_pawns(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    return _inst(
        "isolated_pawns",
        f"¿En qué casillas hay peones aislados de las {_color_es(color)}? {_LIST_HINT}",
        f"Peones aislados {_color_es(color)}",
        bq.isolated_pawns(board, color),
        "square_list",
        en=(
            f"On which squares are {_color_en_s(color)} isolated pawns? {_LIST_HINT_EN}",
            f"Isolated {_color_en(color)} pawns",
        ),
    )


def _gen_pawns_on_file(board, rng):
    color = rng.choice([chess.WHITE, chess.BLACK])
    file_letter = rng.choice(list(chess.FILE_NAMES))
    return _inst(
        "pawns_on_file",
        f"¿Cuántos peones tienen las {_color_es(color)} en la columna {file_letter}?",
        f"Peones {_color_es(color)} en {file_letter}",
        bq.pawns_on_file(board, color, file_letter),
        "number",
        en=(
            f"How many {_color_en(color)} pawns are on the {file_letter}-file?",
            f"{_color_en(color)} pawns on {file_letter}",
        ),
    )


REGISTRY = {
    "captures_available": _gen_captures,
    "checks_available": _gen_checks,
    "in_check": _gen_in_check,
    "side_to_move": _gen_side_to_move,
    "total_piece_count": _gen_total_piece_count,
    "material_balance": _gen_material_balance,
    "castling_rights": _gen_castling_rights,
    "en_passant_available": _gen_en_passant,
    "draw_conditions": _gen_draw_conditions,
    "king_square": _gen_king_square,
    "piece_at_square": _gen_piece_at_square,
    "square_color": _gen_square_color,
    "alignment": _gen_alignment,
    "square_distance": _gen_square_distance,
    "most_advanced_piece": _gen_most_advanced,
    "legal_move_count": _gen_legal_move_count,
    "legal_moves_for_piece": _gen_legal_moves_for_piece,
    "can_reach": _gen_can_reach,
    "squares_attacked_by": _gen_squares_attacked_by,
    "who_controls_square": _gen_who_controls,
    "king_escape_squares": _gen_king_escape,
    "hanging_pieces": _gen_hanging,
    "pinned_pieces": _gen_pinned,
    "defenders_count": _gen_defenders,
    "least_valuable_attacked_piece": _gen_least_valuable,
    "attackers_count": _gen_attackers,
    "discovered_check": _gen_discovered_check,
    "passed_pawns": _gen_passed_pawns,
    "doubled_pawns": _gen_doubled_pawns,
    "isolated_pawns": _gen_isolated_pawns,
    "pawns_on_file": _gen_pawns_on_file,
}

DEFAULT_ENABLED = list(REGISTRY)


def generate_question(board, kind=None, rng=random, enabled=None):
    # ponytail: kind= pins a type for tests; production omits it
    if kind is None:
        pool = [k for k in (enabled or KINDS) if _canon(k) in REGISTRY]
        if not pool:
            return None
        kind = rng.choice(pool)
    fn = REGISTRY.get(_canon(kind))
    if fn is None:
        return None
    inst = fn(board, rng)
    if inst is None:
        return None
    inst = dict(inst)
    inst["type"] = kind
    return inst


def generate_batch(board, enabled=None, n=3, last_ids=(), rng=random):
    # ponytail: shrink instead of repeating a type inside the batch
    pool, seen = [], set()
    kinds = DEFAULT_ENABLED if enabled is None else enabled
    if not kinds:
        return []
    for k in kinds:
        c = _canon(k)
        if c not in REGISTRY or c in seen:
            continue
        seen.add(c)
        pool.append(k)
    order = list(pool)
    shuf = getattr(rng, "shuffle", None)
    if callable(shuf):
        shuf(order)
    if last_ids and len(order) > 1 and _canon(order[0]) == _canon(last_ids[-1]):
        order.append(order.pop(0))
    out, used = [], set()
    for k in order:
        c = _canon(k)
        if c in used:
            continue
        if board.fullmove_number < MIN_MOVE.get(c, 1):
            continue
        inst = generate_question(board, kind=k, rng=rng)
        if inst is None:
            continue
        out.append(inst)
        used.add(c)
        if len(out) >= n:
            break
    # ponytail: one fallback via _inst, never pad remaining slots
    if not out and n > 0:
        out.append(
            _inst(
                "no_more_questions",
                FALLBACK_PROMPT,
                "Sin más preguntas",
                "",
                "square_list",
                en=(FALLBACK_PROMPT_EN, "No more questions"),
            )
        )
    return out


def evaluate(instance, user_answer) -> bool:
    expected = instance["expectedAnswerType"]
    frozen = instance["answer"]
    raw = str(user_answer).strip()
    low = raw.lower()
    if expected == "number":
        try:
            return int(raw) == int(frozen)
        except (TypeError, ValueError):
            return False
    if expected == "boolean":
        if low in ("sí", "si", "true", "1", "yes"):
            return frozen is True
        if low in ("no", "false", "0"):
            return frozen is False
        return False
    if expected == "square":
        if frozen is None:
            return low in ("", "ninguna", "none", "-", "empty")
        return low == str(frozen).lower()
    if expected == "square_list":
        want = {str(x).lower() for x in (frozen or [])}
        if low in ("", "ninguna", "none", "0"):
            got = set()
        else:
            got = {_alias(p.strip().lower()) for p in raw.replace(",", " ").split() if p.strip()}
        return got == want
    if frozen is None:
        return low in ("", "ninguna", "none", "-", "vacía", "vacia", "empty")
    return _alias(low) == str(frozen).lower()
