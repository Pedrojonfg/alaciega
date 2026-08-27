import chess

from backend.blindfold_questions import (
    alignment,
    attackers_count,
    can_castle,
    can_reach,
    defenders_count,
    discovered_check_moves,
    doubled_pawns,
    draw_conditions,
    en_passant_available,
    hanging_pieces,
    isolated_pawns,
    king_escape_squares,
    king_square,
    least_valuable_attacked_piece,
    legal_move_count,
    legal_moves_for_piece,
    material_balance,
    most_advanced_piece,
    passed_pawns,
    pawns_on_file,
    piece_at,
    piece_counts_by_type,
    pinned_pieces,
    square_color,
    square_distance,
    squares_attacked_by,
    total_piece_count,
    who_controls,
)

ITALIAN = chess.Board(
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
)


def test_italian_global_position():
    assert total_piece_count(ITALIAN) == 32
    assert material_balance(ITALIAN) == 0
    counts = piece_counts_by_type(ITALIAN, chess.WHITE)
    assert counts == {"peones": 8, "menores": 4, "mayores": 3, "damas": 1}
    castle = can_castle(ITALIAN, chess.WHITE)
    assert castle["corto"] is True
    assert castle["largo"] is False
    assert en_passant_available(ITALIAN) is False
    draws = draw_conditions(ITALIAN)
    assert draws["ahogado"] is False
    assert draws["material_insuficiente"] is False


def test_italian_squares():
    assert king_square(ITALIAN, chess.WHITE) == "e1"
    assert piece_at(ITALIAN, "c4") == "B"
    assert piece_at(ITALIAN, "a3") is None
    assert square_color("e4") == "clara"
    assert square_color("e5") == "oscura"
    assert alignment("c4", "e6") == ["diagonal"]
    assert square_distance("c4", "e6") == 2
    assert most_advanced_piece(ITALIAN, chess.WHITE) == "e4"


def test_italian_mobility():
    assert legal_move_count(ITALIAN) == 33
    assert "e5" in legal_moves_for_piece(ITALIAN, "f3")
    assert can_reach(ITALIAN, "c4", "f7") is True
    assert can_reach(ITALIAN, "c4", "a3") is False
    assert squares_attacked_by(ITALIAN, "c4") == 10
    ctrl = who_controls(ITALIAN, "d5")
    assert ctrl["blancas"] >= 1
    assert king_escape_squares(ITALIAN, chess.WHITE) == 3


def test_hanging_unprotected_pawn():
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 1 2")
    assert hanging_pieces(board, chess.BLACK) == ["e5"]
    least = least_valuable_attacked_piece(board, chess.BLACK)
    assert board.piece_at(chess.parse_square(least)).piece_type == chess.PAWN
    assert attackers_count(board, "e5", chess.WHITE) == 1
    assert defenders_count(board, "e5") == 0


def test_pinned_knight_on_file():
    board = chess.Board("4r3/8/8/8/8/8/4N3/4K3 w - - 0 1")
    assert pinned_pieces(board, chess.WHITE) == ["e2"]


def test_pawn_structure():
    passed = chess.Board("4k3/8/8/4P3/8/8/8/4K3 w - - 0 1")
    assert passed_pawns(passed, chess.WHITE) == ["e5"]
    doubled = chess.Board("4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1")
    assert doubled_pawns(doubled, chess.WHITE) == ["e"]
    isolated = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
    assert isolated_pawns(isolated, chess.WHITE) == ["e4"]
    assert pawns_on_file(ITALIAN, chess.WHITE, "e") == 1
    assert pawns_on_file(ITALIAN, chess.WHITE, "a") == 1
    assert pawns_on_file(ITALIAN, chess.WHITE, "h") == 1


def test_discovered_check_knight_uncovers_bishop():
    board = chess.Board("7k/8/8/8/3N4/8/8/B3K3 w - - 0 1")
    found = discovered_check_moves(board)
    assert found
    assert all(uci.startswith("d4") for uci in found)
