<p align="center">
  <img src="./img/uSunfish_logo_128.png" />
</p>

# micropython-uSunfish

MicroPython uSunfish Chess Engine

This is an unofficial MicroPython port/derivative of [Sunfish](https://github.com/thomasahle/sunfish/tree/83d675df2f51cd2c66cc765919da7425500a29b6) Chess Engine.

It is tested with MicroPython V1.27.0 on ESP32-S3, but it is not memory-intensive so it should work on a plain ESP32.

  [sunfish_github]: https://github.com/thomasahle/sunfish

- Ported by: fizban99
- License: GNU GPL v3 (the same as Sunfish)

# fizban99 fork

This fork has the following enhancements:
## Features

These are some technical details about the features implemented in this Sunfish-based engine.

- **Sunfish-derived compact chess engine**
  - Based on the original [Sunfish](https://github.com/thomasahle/sunfish) chess engine.
  - Iterative deepening with MTD-bi / null-window search.
  - Sunfish-style pseudo-legal move generation.
  - Null-move pruning.
  - Reworks the implementation heavily for MicroPython and constrained-memory devices.

- **MicroPython-oriented implementation**
  - Reduced memory footprint using MicroPython features such as `const` and small-integer-friendly encodings.
  - Evaluation scores are scaled down to fit within MicroPython integer constraints.
  - The object-oriented position structure of the original Sunfish was removed.
  - Memory allocation is minimized to reduce garbage-collection pressure.
  - A preallocated global move buffer is used to place move lists at different ply depths, avoiding repeated allocation during search.
  - Yielding and other allocation-heavy patterns from the original design are avoided where possible.

- **64-square piece-array board representation**
  - Uses a mutable 64-item integer list instead of Sunfish’s string board. Although a list is relatively memory-hungry, it allows faster make/restore by updating only the changed squares.
  - No mailbox padding. Instead, out-of-bounds detection is handled through rank/file checks.
  - The side-to-move rotated-board idea from Sunfish is retained.

- **Explicit king-attack handling**
  - Move generation remains pseudo-legal, but the engine no longer relies on playing all the way to an actual king-capture position.
  - A `makes_check()` function detects whether a given king is under attack, so if the side to move can capture the opponent king, the search returns a mate score immediately.
  - Illegal castling-through-check cases are also handled through the king-passant square, as in the original Sunfish.
  - This, plus a score scaled down by dividing it by 4, allows smaller PST constants, which helps keep scores compatible with MicroPython integer limits.

- **Hand-crafted pseudo-tapered evaluation**
  - Uses piece-square tables and additional hand-crafted positional terms.
  - Uses three evaluation phases:
    - opening/middlegame
    - blended middle phase, implemented as a weighted average of the other two phases.
    - endgame
  - PST and mobility tables were tuned using the `quiet-labeled.v7.epd` positions file with the L-BFGS-B algorithm from SciPy.

- **Integrated mobility evaluation**
  - Contains a compact MinimalChess-style mobility table, separate from the piece-square tables.
  - Mobility is calculated during move generation, while the engine is already scanning moves, rays, pawn files, attacks, and king-ring squares, which avoids a separate full-board mobility pass.
  - Mobility is applied as a second-stage evaluation correction after the PST-based move scoring and ordering. Even though mobility is calculated at this second stage, it still appears to increase Elo significantly.
  - Mobility-related evaluation includes:
    - piece mobility by target-square content
    - bishop pair
    - open and semi-open files
    - rook and queen file activity
    - king safety / king-ring pressure
    - advanced pawns
    - passed-pawn-style terms
    - connected/protected pawn-style terms

- **Move ordering**
  - Hash move is tried first.
  - Captures and queen promotions are ordered using a simplified MVV-LVA scheme.
  - A separate quiet killer-move table is used; this is distinct from the original Sunfish terminology, where the hash move was referred to as a killer move.
  - History heuristic is used for quiet moves.
  - Underpromotions and quiet moves without history are searched last.
  - Positions with the same order and score can be resorted, adding a small amount of non-determinism and play variety.

- **Search enhancements over original Sunfish**
  - Late Move Reduction.
  - Aggressive futility pruning.
  - Check extensions.
  - Separate quiet killer-move heuristic.
  - History heuristic.
  - Bounded node-based strength control.

- **Interruptible time management**
  - The search can stop inside the recursive search when the allocated time runs out. This differs from original Sunfish, which only stopped after completing an iterative-deepening iteration, and reduces the risk of losing on time when a deeper iteration unexpectedly takes too long.

- **Small bounded transposition table**
  - Replaces the original Sunfish approach based on an effectively unbounded Python dictionary.
  - Designed for constrained memory.
  - Uses a small fixed-size table with compact entries.
  - Uses an age-based replacement policy.
  - Stores useful hash moves, especially fail-high moves.
  - Uses a computed compact Zobrist-like [integer hash function](https://github.com/skeeto/hash-prospector) instead of storing a large precomputed hash-key table.
  - Hash generation includes startup randomness, adding a bit of non-determinism.

- **Compact hardcoded opening book**
  - Original Sunfish did not include hardcoded openings. This version includes a compact nibble-encoded opening book. The main book contains about 1,768 plies derived from `Balsa_270423.pgn` and `Unique v110225`.
  - A secondary reply book provides answers to uncommon first moves using the [`400 moves.pgn`](https://www.scacchi64.com/downloads.html) file.

- **Strength control**
  - Playing strength is controlled by the number of evaluated nodes.
  - Level 0 is an extremely easy level.
  - Levels 1–7 range from 125 nodes to 8000 nodes.
  - On a standard ESP32, level 7 takes around 60 seconds per move.

- **UCI compatibility**
  - Supports UCI operation.
  - Provides configurable options including:
    - `Skill Level`
    - `OwnBook`
    - `UCI_LimitStrength`
    - `Hash Slots`
  - Supports FEN setup.
  - Includes `go`, and `go perft`.

- **External inspiration**
  - Besides the original Sunfish, this engine also draws inspiration from:
    - [MinimalChess](https://github.com/lithander/MinimalChessEngine)
    - [4ku](https://github.com/kz04px/4ku) 
    - [MadChess](https://www.madchess.net/)


# Installation on a MicroPython-compatible board

The file may be installed on target hardware with `mpremote`:
```bash
$ mpremote mip install github:fizban99/micropython-usunfish
```

It is also compatible with cpython, although it is actually optimized for micropython.

# Gameplay

Running `import sunfish` and then `sunfish.main()` starts a terminal-based textual chess game. The human player is White,
and the machine is Black. White pieces are denoted by upper case letters, and Black by lower. Blank
squares are marked with a `.`character. The appearance of the board is as follows:
```
  8 r n b q k b n r
  7 p p p p . p p p
  6 . . . . . . . .
  5 . . . . p . . .
  4 . . . . P . . .
  3 . . . . . . . .
  2 P P P P . P P P
  1 R N B Q K B N R
    a b c d e f g h
```
Moves are input and displayed in "algebraic" notation, for example `b1c3` to move a white Knight.
Castling is done by moving the King, e.g. `e1g1` to castle on the King side - the Rook moves
automatically. Pawn promotion - always to Queen - occurs automatically. The machine can do _en passant_
captures. 
If an invalid move is entered, the engine prompts the user to try again.

## Limitations

The engine does not allow you to play as Black (although with a suitable graphical front-end this can
be remedied).

# Using the API

This allows Sunfish to work with a graphical front-end such as
[micropython-touch](https://github.com/peterhinch/micropython-touch/tree/master). An example graphical
game demo [is here](https://github.com/peterhinch/micropython-touch/blob/master/optional/chess/chess_game.py).
It is intended that the API could be adapted to other chess engines to enable engines and front-ends
to be ported.

The API comprises two generators, `game` and `get_board` and a function `make_board`. With suitable
front-end code the user can play as Black or White.

## The game generator

This runs for the duration of a game. The end of a game is flagged by a `StopIteration` exception,
with the exception value indicating win, lose or (potentially) draw. (Sunfish cannot detect draws).
The following describes one iteration of the generator.

By default, with no passed argument, the generator starts with a standard chessboard with the human
playing White. Before starting the loop, the GUI calls `next()` to retrieve a representation of the
board state. The GUI passes this to the `get_board` generator to populate the visual representation
of the board. The player then enters a move. If an invalid move is entered, it is ignored: the
generator yields `None`. This prompts the GUI to ignore any bad move. When a valid move is entered,
the generator returns a representation of the new board state. The GUI passes that to the `get_board`
generator to refresh the board on screen.

After a brief delay for the player to evaluate the board, the GUI issues `next()` which prompts the
game generator to calculate its move. This `next()` call returns the new board state and the latest
move (in "a2a4" format). The GUI briefly highlights the squares of the move. The next pass refreshes
the screen as before.

Note that moves passed from the GUI to the generator must be lexically valid (no "a8a9"), but the
engine checks for a valid chess move. Special moves such as castling are handled as described above
in the text game.

The following is an example of the generator in use
```py
    async def play_game(self):
        game_over = False
        # Set up the board
        game = sunfish.game(iblack) if self.invert else sf.game()
        board, _ = next(game)  # Start generator, get initial position
        while not game_over:
            try:
                self.populate(board)  # Fill the board grid with the current position using get_board
                await asyncio.sleep(0)
                board = None
                while board is None:  # Acquire valid move
                    await self.moved.wait()  # Wait for player/GUI to update self.move
                    board = game.send(self.move)  # Get position after move
                self.populate(board)  # Use the Position instance to redraw the board
                await asyncio.sleep(1)  # Ensure refresh, allow time to view.
                board, mvblack = next(game)  # Sunfish calculates its move. Yields the new board state and its move
                self.flash(*rc(mvblack[:2]), WHITE)  # Flash the squares to make the forthcoming move obvious
                self.flash(*rc(mvblack[2:]), WHITE)
                await asyncio.sleep_ms(700)  # Let user see forthcoming move
            except StopIteration as e:
                game_over = True
                print(f"Game over: you {'won' if (e ^ self.invert) else 'lost'}")
```
Note that generator iterations return a `board` instance. From the point of view of the GUI code
this is an opaque object whose only use is to be passed to the `get_board` generator. In general a
`board` is some object which contains information on the current board state.


## The get_board generator

This is instantiated with a `board` object, as returned by the `game` generator, and yields the
alphabetic character associated with each square in turn. Order is left to right, then top to bottom.
In the board illustrated above, initial successive calls would yield "rnbqkbnrpppp.ppp." The following is
a code fragment illustrating its use to populate a grid with the current board state.
```py
# Return state of each square in turn.
def get(board, invert):
    dic = {}
    gen = sunfish.get_board(board)  # Instantiate Sunfish generator
    n = 0
    while True:
        r = next(gen)  # Get chesspiece character
        dic["text"] = lut[r.upper()]  # Convert to chess glyph
        dic["fgcolor"] = WHITE if (r.isupper() ^ invert) else RED
        dic["bgcolor"] = BLACK if ((n ^ (n >> 3)) & 1) else PALE_GREY
        yield dic
        n += 1
```
# Implementing the API

This describes the process of adding the API to an existing chess engine, enabling engines to readily be
changed in a graphical game. The following must be implemented.

## The game generator

The generator function takes a single optional argument, a 64 element `bytes` object comprising the initial
board state. Reduced to its essentials it has the following structure:
```py
def game(iboard=None):
    # If an initial board is passed, convert it to the engine's native format and initialise the engine
    # engine.start(make_board(iboard))
    engine_move = None  # Machine's last move in "a2a4" format
    while True:
        if engine.player_has_lost():
            return False  # StopIteration: player lost
        elif engine.drawn_game():
            return None

        # Yield current board state and last black move (if any)
        move = yield current_board_state, engine_move  # Await a move in "a2a4" format
        # The GUI guarantees these are lexically valid. Engine checks for chess validity.
        while not legal_move(move):
            move = yield  # A None reponse prompts user to try again

        engine.user_move(move)  # Pass vaild "a2a4" user move to engine
        if engine.player_has_won():
            return True  # Player won

        # Fire up the engine to look for a move.
        move = engine.calculate_move()
        if engine.player_has_lost():
            return False  # Player lost
        elif engine.drawn_game():
            return None

        # The black player moves from a rotated position, so we have to
        # 'back rotate' the move before printing it.
        engine_move = convert_engine_move_format_to_text()  # "a2a4" format
```
The engine may optionally add a fifth character to moves it returns, with "+" denoting chack and "#"
denoting checkmate. Sunfish does not do this.

## The get_board generator

This converts the engine's internal representation of a board into alphanumeric format, with pieces
at the top of the board being lowercase and those at the bottom being uppercase. Empty squares should
yield "". The generator should yield exactly 64 characters in turn, sarting at the top left of the
board, progressing left to right then by row downwards.

## The make_board function

This takes a 64 element `bytes` object and returns the engine's internal representation of a board.
The format of the `bytes` object is described above in "inverted play".

# The UCI interface

The file uci.py implements a simple UCI interface that can be used with any UCI-compatible user interface. It currently supports the following options
- `Skill_Level` only active if `UCI_LimitStrength` set to true.
- `OwnBook`. Whether to use its internal opening book or not.
- `Hash Slots`. Each slot requires approximately 1500 bytes. The default is 8 on ESP32 and 128 on Windows/Linux MicroPython, and 256 when using PyPy.

The uci commands implemented are basically `position startpos [moves]`, `position fen`, `go perft <n>` and `go [wtime] [btime] [winc] [binc] [movetime]`

# Windows version

The Windows executable is just the micropython runtime with the micropython code frozen and autolaunching the UCI interface using [my fork of MicroPython](https://github.com/fizban99/micropython_windows/tree/windows-msvc-native-v128). It is compatible with [cutechess](https://cutechess.com/), [arena](http://www.playwitharena.de/) and [lucaschess](https://lucaschess.pythonanywhere.com/) and it is only around 900KB.
You can also play on lichess at [level 0](https://lichess.org/@/uSunfish-l0), [level 1](https://lichess.org/@/uSunfish-l1) or [level 7](https://lichess.org/@/uSunfish-l7).

Besides the MicroPython version, the release includes an `.exe` launcher that starts the UCI interface using the bundled, abridged PyPy package. The latest releases bundle the launcher, the PyPy package and the python source code into a single executable by means of the [Enigma Virtual Box](https://enigmaprotector.com/en/aboutvb.html) software. The MicroPython version uses about **2.6 MB** of memory, while the PyPy version uses about **50 MB**. By comparison, the original Sunfish did not impose a fixed hash-table limit and could easily grow to several gigabytes of memory usage.

Based on my own CCRL-like testing, I estimate the MicroPython version to be **1330-1380 Elo** on the [CCRL Blitz](https://computerchess.org.uk/404/) scale. The PyPy version is estimated to be about **250 Elo stronger**, at **1580-1650 Elo**.

This is probably one of the strongest HCE chess engines written in "pure" Python, and very likely the strongest written for MicroPython. Note that there are stronger Python engines, like [Antares](https://github.com/Alex2262/Antares), which uses Numba; [Chessidle](https://github.com/alvinypeng/chessidle) and [D-House](https://github.com/alvinypeng/d-house/tree/main), which are "pure" Python, but use NNE; [Habu](https://github.com/radiantcat/habu/blob/main/habu.py) uses a compiled code for NNUE; or [Dinora](https://github.com/Saegl/dinora), which uses Pytorch. The PyPy version of uSunfish is estimated to have a similar performance as [Numbfish](https://github.com/dimdano/numbfish), which actually uses an NNE approach.
