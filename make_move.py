"""
Chess bot for GitHub Profile
Triggered by GitHub Actions when an issue is opened with title "chess: <move>"
"""

import sys, json, os, re, chess, chess.svg
from datetime import datetime

REPO       = "rifani890/rifani890"
FEN_FILE   = "chess/game.fen"
SVG_FILE   = "chess/board.svg"
MOVES_FILE = "chess/moves.json"
README     = "README.md"

# ── SVG board colors ──────────────────────────────────────────────────────────
COLORS = {
    "square light":          "#f0d9b5",
    "square dark":           "#b58863",
    "square light lastmove": "#cdd26a",
    "square dark lastmove":  "#aaa23a",
    "margin":                "#1a1510",
    "coord":                 "#d4af37",
}

# ── State helpers ─────────────────────────────────────────────────────────────

def load_fen():
    if os.path.exists(FEN_FILE):
        with open(FEN_FILE) as f:
            return f.read().strip()
    return chess.STARTING_FEN

def save_fen(fen):
    os.makedirs("chess", exist_ok=True)
    with open(FEN_FILE, "w") as f:
        f.write(fen)

def save_svg(board, last_move=None):
    os.makedirs("chess", exist_ok=True)
    arrows = []
    if last_move:
        arrows = [chess.svg.Arrow(
            last_move.from_square, last_move.to_square, color="#d4af37"
        )]
    svg = chess.svg.board(
        board, size=480,
        arrows=arrows,
        colors=COLORS,
        coordinates=True,
    )
    with open(SVG_FILE, "w") as f:
        f.write(svg)

def load_moves():
    if os.path.exists(MOVES_FILE):
        with open(MOVES_FILE) as f:
            return json.load(f)
    return []

def save_moves(moves):
    os.makedirs("chess", exist_ok=True)
    with open(MOVES_FILE, "w") as f:
        json.dump(moves, f, indent=2)

# ── Move link generator ───────────────────────────────────────────────────────

def issue_url(uci):
    title = f"chess: {uci}"
    return (
        f"https://github.com/{REPO}/issues/new"
        f"?title={title.replace(' ', '+')}"
        f"&labels=chess-move"
        f"&body=Making+my+move%3A+{uci}"
    )

def move_table(board):
    """Return markdown table of legal moves as issue links, grouped by piece."""
    legal = list(board.legal_moves)
    if not legal:
        return ""

    by_piece: dict[str, list] = {}
    for mv in legal:
        piece = board.piece_at(mv.from_square)
        key   = piece.symbol().upper()
        by_piece.setdefault(key, []).append(mv)

    rows = []
    order = ["K", "Q", "R", "B", "N", "P"]
    labels = {"K": "♔ King", "Q": "♕ Queen", "R": "♖ Rook",
              "B": "♗ Bishop", "N": "♘ Knight", "P": "♙ Pawn"}
    for pt in order:
        mvs = by_piece.get(pt, [])
        if not mvs:
            continue
        links = " ".join(
            f"[`{board.san(m)}`]({issue_url(m.uci())})"
            for m in sorted(mvs, key=lambda x: board.san(x))
        )
        rows.append(f"| {labels[pt]} | {links} |")

    header = "| Piece | Moves |\n|-------|-------|"
    return header + "\n" + "\n".join(rows)

# ── README updater ────────────────────────────────────────────────────────────

def update_readme(board, last_player=""):
    with open(README) as f:
        content = f.read()

    turn = "White ♔" if board.turn == chess.WHITE else "Black ♚"

    if board.is_checkmate():
        winner = "Black ♚" if board.turn == chess.WHITE else "White ♔"
        status  = f"🏆 **Checkmate! {winner} wins!**"
        moves   = f"[🔄 Start a New Game]({issue_url('reset')})"
    elif board.is_stalemate():
        status  = "🤝 **Stalemate! It's a draw.**"
        moves   = f"[🔄 Start a New Game]({issue_url('reset')})"
    elif board.is_check():
        status  = f"⚠️ **{turn} to move — IN CHECK!**"
        moves   = move_table(board)
    else:
        by_line = f" &nbsp;·&nbsp; last move by **@{last_player}**" if last_player else ""
        status  = f"**{turn} to move**{by_line}"
        moves   = move_table(board)

    raw_svg = f"https://raw.githubusercontent.com/{REPO}/main/chess/board.svg"

    section = f"""<!-- CHESS_START -->
---

<h3 align="center">♟ Chess — Play Against the World!</h3>

<div align="center">

> Make your move by clicking a link below — a bot will update the board automatically!

<img src="{raw_svg}" width="420" alt="Chess board" />

{status}

</div>

{moves}

<details>
<summary>📖 How to play</summary>

1. Click any move link in the table above
2. Submit the pre-filled GitHub Issue *(don't change the title)*
3. The bot applies your move and updates the board within seconds ♟

> Anyone can play — one move per person per turn, first come first served!

</details>
<!-- CHESS_END -->"""

    pattern = r"<!-- CHESS_START -->.*?<!-- CHESS_END -->"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, section, content, flags=re.DOTALL)
    else:
        content = content.rstrip() + "\n\n" + section + "\n"

    with open(README, "w") as f:
        f.write(content)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python make_move.py '<issue_title>' [username]")
        sys.exit(1)

    issue_title = sys.argv[1]
    username    = sys.argv[2] if len(sys.argv) > 2 else ""

    if not issue_title.lower().startswith("chess:"):
        print("Not a chess issue — skipping.")
        sys.exit(0)

    move_str = issue_title[6:].strip()

    # Load board
    board = chess.Board(load_fen())
    moves = load_moves()

    # ── Reset ──
    if move_str.lower() in ("reset", "new", "restart"):
        board = chess.Board()
        moves = []
        save_fen(board.fen())
        save_svg(board)
        save_moves(moves)
        update_readme(board, username)
        print("✅ Game reset to starting position.")
        return

    # ── Parse move ──
    move = None
    for parser in [chess.Move.from_uci, board.parse_san]:
        try:
            candidate = parser(move_str)
            if candidate in board.legal_moves:
                move = candidate
                break
        except Exception:
            continue

    if move is None:
        print(f"❌ Invalid or illegal move: '{move_str}'")
        sys.exit(1)

    san = board.san(move)
    board.push(move)

    moves.append({
        "san":       san,
        "uci":       move_str,
        "player":    username,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

    save_fen(board.fen())
    save_svg(board, move)
    save_moves(moves)
    update_readme(board, username)

    print(f"✅ Move '{san}' by @{username} applied.")

if __name__ == "__main__":
    main()
