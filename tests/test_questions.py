import chess
import pytest

from backend.questions import (
    DEFAULT_ENABLED,
    PROMPTS,
    REGISTRY,
    evaluate,
    generate_batch,
    generate_question,
)

ITALIAN = chess.Board(
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
)


def test_captures_start_is_zero():
    q = generate_question(chess.Board(), kind="captures")
    assert q["type"] == "captures"
    assert q["prompt"] == PROMPTS["captures"]
    assert q["answer"] == 0
    assert q["expectedAnswerType"] == "number"


def test_captures_and_checks_after_e4_d5():
    board = chess.Board()
    board.push_san("e4")
    board.push_san("d5")
    caps = generate_question(board, kind="captures")
    chks = generate_question(board, kind="checks")
    assert caps["answer"] == 1
    assert chks["type"] == "checks"
    assert chks["prompt"] == PROMPTS["checks"]
    assert chks["answer"] == 1


def test_exd5_has_capture_but_no_check():
    board = chess.Board()
    for san in ("e4", "d5", "exd5"):
        board.push_san(san)
    assert generate_question(board, kind="captures")["answer"] == 1
    assert generate_question(board, kind="checks")["answer"] == 0


def test_in_check_start_is_false():
    q = generate_question(chess.Board(), kind="in_check")
    assert q["prompt"] == PROMPTS["in_check"]
    assert q["answer"] is False
    assert q["expectedAnswerType"] == "boolean"


def test_scholar_mate_terminal():
    board = chess.Board()
    for san in ("e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"):
        board.push_san(san)
    assert generate_question(board, kind="captures")["answer"] == 0
    assert generate_question(board, kind="checks")["answer"] == 0
    assert generate_question(board, kind="in_check")["answer"] is True


def test_omitting_kind_picks_among_enabled():
    class Rec:
        def choice(self, seq):
            self.seen = list(seq)
            return seq[0]

    rng = Rec()
    q = generate_question(chess.Board(), rng=rng, enabled=["captures", "checks", "in_check"])
    assert set(rng.seen) == {"captures", "checks", "in_check"}
    assert q["type"] == "captures"


@pytest.mark.parametrize("kind", list(REGISTRY))
def test_every_catalogue_kind_generates_on_italian(kind):
    rng = __import__("random").Random(0)
    q = generate_question(ITALIAN, kind=kind, rng=rng)
    if q is None:
        q = generate_question(
            chess.Board("rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 1 2"),
            kind=kind,
            rng=__import__("random").Random(1),
        )
    assert q is not None
    assert q["type"] == kind
    assert q["prompt"]
    assert q["expectedAnswerType"] in ("number", "boolean", "square", "square_list", "piece_symbol")
    if q["expectedAnswerType"] == "square_list":
        user = " ".join(q["answer"] or [])
    else:
        user = q["answer"]
    assert evaluate(q, user)


def test_generate_batch_no_repeat_and_shrinks():
    rng = __import__("random").Random(0)
    batch = generate_batch(ITALIAN, enabled=list(REGISTRY), n=3, rng=rng)
    assert len(batch) == 3
    types = [q["type"] for q in batch]
    assert len(types) == len(set(types))
    tiny = generate_batch(ITALIAN, enabled=["in_check", "side_to_move"], n=5, rng=rng)
    assert len(tiny) == 2
    assert {q["type"] for q in tiny} == {"in_check", "side_to_move"}


def test_generate_batch_skips_unknown_and_aliases_dedupe():
    batch = generate_batch(
        ITALIAN,
        enabled=["captures", "captures_available", "not_a_kind", "in_check"],
        n=5,
        rng=__import__("random").Random(0),
    )
    types = [_canon_type(q["type"]) for q in batch]
    assert types.count("captures_available") <= 1
    assert "not_a_kind" not in [q["type"] for q in batch]


def _canon_type(t):
    return {"captures": "captures_available", "checks": "checks_available"}.get(t, t)


def test_evaluate_square_list_is_a_set():
    q = {
        "type": "hanging_pieces",
        "prompt": "x",
        "answer": ["e5", "a4"],
        "expectedAnswerType": "square_list",
    }
    assert evaluate(q, "a4, e5")
    assert evaluate(q, "e5 a4")
    assert not evaluate(q, "e5")
    assert evaluate({"type": "h", "prompt": "x", "answer": [], "expectedAnswerType": "square_list"}, "ninguna")


def test_evaluate_boolean_aliases():
    q = generate_question(chess.Board(), kind="in_check")
    assert evaluate(q, "no")
    assert evaluate(q, "false")
    assert not evaluate(q, "sí")


def test_captures_available_alias_matches_captures():
    board = chess.Board()
    a = generate_question(board, kind="captures")
    b = generate_question(board, kind="captures_available")
    assert a["answer"] == b["answer"]
    assert a["expectedAnswerType"] == "number"


def test_default_enabled_is_full_catalogue():
    assert set(DEFAULT_ENABLED) == set(REGISTRY)
    assert "discovered_check" in REGISTRY
    assert "side_to_move" in REGISTRY


MIN_MOVE_OVERRIDES = {
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
ALLOW_EMPTY_KINDS = {
    "hanging_pieces",
    "pinned_pieces",
    "passed_pawns",
    "doubled_pawns",
    "isolated_pawns",
    "alignment",
}


@pytest.mark.parametrize("kind,n", list(MIN_MOVE_OVERRIDES.items()))
def test_min_move_number_overrides(kind, n):
    q = generate_question(ITALIAN, kind=kind, rng=__import__("random").Random(0))
    if q is None:
        pytest.skip("kind not applicable on Italian")
    assert q["minMoveNumber"] == n


def test_default_min_move_number_is_one():
    q = generate_question(chess.Board(), kind="in_check")
    assert q["minMoveNumber"] == 1
    assert q["allowsEmptyAnswer"] is False


@pytest.mark.parametrize("kind", list(ALLOW_EMPTY_KINDS))
def test_list_kinds_allow_empty_answer(kind):
    q = generate_question(ITALIAN, kind=kind, rng=__import__("random").Random(0))
    assert q is not None
    assert q["allowsEmptyAnswer"] is True


def test_evaluate_empty_string_against_empty_list():
    q = {
        "type": "pinned_pieces",
        "prompt": "x",
        "answer": [],
        "expectedAnswerType": "square_list",
    }
    assert evaluate(q, "")
    assert evaluate(q, "   ")
    assert not evaluate(
        {"type": "pinned_pieces", "prompt": "x", "answer": ["c6"], "expectedAnswerType": "square_list"},
        "",
    )


FALLBACK_PROMPT = "No quedan más preguntas por hacer en este tipo de posición"


def test_generate_batch_start_excludes_gated_kinds():
    rng = __import__("random").Random(0)
    batch = generate_batch(chess.Board(), enabled=list(REGISTRY), n=10, rng=rng)
    assert len(batch) == 10
    types = {q["type"] for q in batch}
    assert types.isdisjoint(MIN_MOVE_OVERRIDES)
    assert "no_more_questions" not in types


def test_generate_batch_empty_pool_emits_one_fallback():
    batch = generate_batch(
        chess.Board(), enabled=["pinned_pieces"], n=3, rng=__import__("random").Random(0)
    )
    assert len(batch) == 1
    inst = batch[0]
    assert inst["type"] == "no_more_questions"
    assert inst["prompt"] == FALLBACK_PROMPT
    assert inst["promptEn"] == "No more questions left for this kind of position"
    assert evaluate(inst, "")


def test_generate_batch_pinned_after_min_move():
    assert ITALIAN.fullmove_number >= 3
    batch = generate_batch(
        ITALIAN, enabled=["pinned_pieces"], n=3, rng=__import__("random").Random(0)
    )
    assert len(batch) == 1
    assert batch[0]["type"] == "pinned_pieces"


def test_generate_batch_shrinks_without_fallback_on_start():
    batch = generate_batch(
        chess.Board(),
        enabled=["in_check", "side_to_move"],
        n=5,
        rng=__import__("random").Random(0),
    )
    assert len(batch) == 2
    assert {q["type"] for q in batch} == {"in_check", "side_to_move"}
    assert all(q["type"] != "no_more_questions" for q in batch)


def test_generate_batch_empty_enabled_is_empty():
    # ponytail: [] kinds is the off switch — no fallback, no block
    batch = generate_batch(chess.Board(), enabled=[], n=3)
    assert batch == []


@pytest.mark.parametrize("kind", list(REGISTRY))
def test_every_catalogue_kind_has_english_prompt(kind):
    rng = __import__("random").Random(0)
    q = generate_question(ITALIAN, kind=kind, rng=rng)
    if q is None:
        q = generate_question(
            chess.Board("rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 1 2"),
            kind=kind,
            rng=__import__("random").Random(1),
        )
    assert q is not None
    assert q["promptEn"]
    assert not q["promptEn"].startswith("¿")
    assert q["promptShortEn"]
    assert q["promptEn"] != q["prompt"]


def test_evaluate_accepts_english_colour_and_line_words():
    colour = {
        "type": "square_color",
        "prompt": "x",
        "answer": "clara",
        "expectedAnswerType": "piece_symbol",
    }
    assert evaluate(colour, "light")
    assert evaluate(colour, "clara")
    assert not evaluate(colour, "dark")
    lines = {
        "type": "alignment",
        "prompt": "x",
        "answer": ["fila", "diagonal"],
        "expectedAnswerType": "square_list",
    }
    assert evaluate(lines, "rank, diagonal")
    assert evaluate(lines, "fila diagonal")


def test_evaluate_boolean_yes():
    q = generate_question(chess.Board(), kind="in_check")
    assert q["answer"] is False
    assert not evaluate(q, "yes")
    q["answer"] = True
    assert evaluate(q, "yes")
