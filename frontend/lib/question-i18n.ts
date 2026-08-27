const YES = "Answer yes or no.";
const LIST =
  'Separate them with commas (e.g. a3, f6). If there are none, leave the answer empty — do not write a dash or "none".';

const CANON: Record<string, string> = {
  captures: "captures_available",
  checks: "checks_available",
};

const DRAW: [RegExp, string][] = [
  [/material insuficiente/i, "insufficient material"],
  [/triple repetici[oó]n/i, "a claimable threefold repetition"],
  [/repetici[oó]n qu[ií]ntuple/i, "fivefold repetition"],
  [/regla de 50/i, "a claimable fifty-move rule"],
  [/regla de 75/i, "the seventy-five-move rule"],
  [/ahogado/i, "stalemate"],
];

function sqs(s: string): string[] {
  return s.toLowerCase().match(/\b[a-h][1-8]\b/g) ?? [];
}

function color(s: string): "White" | "Black" {
  return /negras/i.test(s) ? "Black" : "White";
}

function poss(s: string): "White's" | "Black's" {
  return color(s) === "Black" ? "Black's" : "White's";
}

function fileLetter(s: string): string | undefined {
  return s.toLowerCase().match(/\bcolumna\s+([a-h])\b/)?.[1];
}

function castleSide(s: string): "kingside" | "queenside" {
  return /largo/i.test(s) ? "queenside" : "kingside";
}

function drawLabel(s: string): string {
  for (const [re, en] of DRAW) if (re.test(s)) return en;
  return "a draw";
}

const STATIC: Record<string, { long: string; short: string }> = {
  captures_available: {
    long: "How many legal captures does the side to move have?",
    short: "Legal captures by the side to move",
  },
  checks_available: {
    long: "How many legal moves by the side to move give check in this position?",
    short: "Legal checks by the side to move",
  },
  in_check: {
    long: "Is the side to move's king currently in check? Answer yes or no.",
    short: "Side to move in check",
  },
  side_to_move: {
    long: `Is it White's turn to move? ${YES}`,
    short: "White to move",
  },
  total_piece_count: {
    long: "How many pieces are on the board in total (White and Black)?",
    short: "Total pieces",
  },
  material_balance: {
    long: "What is the material balance (positive favours White, negative favours Black)?",
    short: "Material balance",
  },
  en_passant_available: {
    long: `Is there a legal en passant capture for the side to move right now? ${YES}`,
    short: "Legal en passant",
  },
  legal_move_count: {
    long: "How many legal moves does the side to move have?",
    short: "Legal moves (side to move)",
  },
  king_escape_squares: {
    long: "How many capture-free escape squares does the side to move's king have?",
    short: "King escapes for the side to move",
  },
  discovered_check: {
    long: "How many legal moves by the side to move give discovered check?",
    short: "Discovered checks",
  },
  no_more_questions: {
    long: "No more questions left for this kind of position",
    short: "No more questions",
  },
};

type Q = { type: string; prompt: string; promptEn?: string; promptShort?: string; promptShortEn?: string };

function built(type: string, prompt: string): { long: string; short: string } | null {
  const kind = CANON[type] ?? type;
  const fixed = STATIC[kind];
  if (fixed) return fixed;
  const [a, b] = sqs(prompt);
  const c = color(prompt);
  const p = poss(prompt);
  if (kind === "castling_rights") {
    const side = castleSide(prompt);
    return {
      long: `Can ${c} (side to move) castle ${side}? ${YES}`,
      short: `${side[0].toUpperCase()}${side.slice(1)} castle for the side to move`,
    };
  }
  if (kind === "draw_conditions") {
    const label = drawLabel(prompt);
    return { long: `Is there ${label} in this position? ${YES}`, short: `Draw: ${label}` };
  }
  if (kind === "king_square") {
    return {
      long: `Which square is the ${c} king on? (one square, e.g. e1)`,
      short: `${c} king square`,
    };
  }
  if (kind === "piece_at_square" && a) {
    return {
      long: `What piece is on ${a}? Use the FEN symbol (KQRBNPkqrbnp). If empty, leave the answer empty.`,
      short: `Piece on ${a}`,
    };
  }
  if (kind === "square_color" && a) {
    return { long: `What colour is square ${a}? Answer light or dark.`, short: `Colour of ${a}` };
  }
  if (kind === "alignment" && a && b) {
    return {
      long: `Which lines do ${a} and ${b} share? List rank, file and/or diagonal. ${LIST}`,
      short: `Alignment ${a}-${b}`,
    };
  }
  if (kind === "square_distance" && a && b) {
    return {
      long: `What is the king-move distance (number of steps) between ${a} and ${b}?`,
      short: `Distance ${a}-${b}`,
    };
  }
  if (kind === "most_advanced_piece") {
    return {
      long: `Which square has ${p} most advanced non-king piece?`,
      short: `Most advanced ${c} piece`,
    };
  }
  if (kind === "legal_moves_for_piece" && a) {
    return {
      long: `How many legal moves does the piece on ${a} have? (if that piece is not the side to move's, the answer is 0)`,
      short: `Legal moves from ${a}`,
    };
  }
  if (kind === "can_reach" && a && b) {
    return {
      long: `Can the piece on ${a} reach ${b} in one legal move? (if that piece is not the side to move's, the answer is no). ${YES}`,
      short: `Can ${a} reach ${b}?`,
    };
  }
  if (kind === "squares_attacked_by" && a) {
    return {
      long: `How many squares does the piece on ${a} attack geometrically (not requiring the move to be legal regarding check)?`,
      short: `Squares attacked from ${a}`,
    };
  }
  if (kind === "who_controls_square" && a) {
    return { long: `How many ${c} pieces control ${a}?`, short: `${c} control of ${a}` };
  }
  if (kind === "hanging_pieces") {
    return {
      long: `Which squares have hanging ${c} pieces right now? ${LIST}`,
      short: `Hanging ${c} pieces`,
    };
  }
  if (kind === "pinned_pieces") {
    return {
      long: `On which squares are ${p} pinned pieces? ${LIST}`,
      short: `Pinned ${c} pieces`,
    };
  }
  if (kind === "defenders_count" && a) {
    return {
      long: `How many friendly pieces (of the side that owns the piece on ${a}) defend ${a}?`,
      short: `Defenders of ${a}`,
    };
  }
  if (kind === "least_valuable_attacked_piece") {
    return {
      long: `On which square is ${p} lowest-value attacked piece?`,
      short: `Lowest-value attacked ${c} piece`,
    };
  }
  if (kind === "attackers_count" && a) {
    return { long: `How many ${c} pieces attack ${a}?`, short: `${c} attackers of ${a}` };
  }
  if (kind === "passed_pawns") {
    return {
      long: `On which squares are ${p} passed pawns? ${LIST}`,
      short: `Passed ${c} pawns`,
    };
  }
  if (kind === "doubled_pawns") {
    return {
      long: `On which files do ${c} have doubled pawns? List file letters. ${LIST}`,
      short: `Doubled ${c} pawns`,
    };
  }
  if (kind === "isolated_pawns") {
    return {
      long: `On which squares are ${p} isolated pawns? ${LIST}`,
      short: `Isolated ${c} pawns`,
    };
  }
  const file = fileLetter(prompt);
  if (kind === "pawns_on_file" && file) {
    return {
      long: `How many ${c} pawns are on the ${file}-file?`,
      short: `${c} pawns on ${file}`,
    };
  }
  return null;
}

export function englishPrompt(q: Q): string {
  return q.promptEn ?? built(q.type, q.prompt)?.long ?? q.prompt;
}

export function englishShort(q: Q): string {
  return q.promptShortEn ?? built(q.type, q.prompt)?.short ?? q.promptShort ?? q.prompt;
}
