"use client";

import dynamic from "next/dynamic";

const Chessboard = dynamic(
  () => import("react-chessboard").then((m) => m.Chessboard),
  { ssr: false },
);

export function ChessBoardView({
  fen,
  orientation,
}: {
  fen: string;
  orientation: "white" | "black";
}) {
  return (
    <div className="board-wrap">
      <Chessboard
        options={{
          position: fen,
          allowDragging: false,
          boardOrientation: orientation,
          darkSquareStyle: { backgroundColor: "#1e5c3a" },
          lightSquareStyle: { backgroundColor: "#f3ead8" },
        }}
      />
    </div>
  );
}
