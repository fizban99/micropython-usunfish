# micropython-uSunfish

MicroPython uSunfish Chess Engine

This is an unofficial MicroPython port/derivative of [Sunfish](https://github.com/thomasahle/sunfish/tree/83d675df2f51cd2c66cc765919da7425500a29b6) Chess Engine.

It is tested with MicroPython V1.27.0 on ESP32-S3, but it is not memory-intensive so it should work on a plain ESP32.

  [sunfish_github]: https://github.com/thomasahle/sunfish

- Ported by: fizban99
- License: GNU GPL v3 (the same as Sunfish)

# fizban99 fork

This fork has the following enhancements:
- Reduced memory footprint by extensively using some micropython features such as string interning and 31-bit smallints and removing the object-oriented approach of the original Sunfish.
- It uses a small hash table to reduce node traversal time during sequential iterations of the iterative deepening MTD-bi search. The table stores only fail-high moves and employs a simple age-based replacement algorithm.
- It includes a small opening book of 1,768 plies derived from the Balsa_270423.pgn and Unique v110225 openings files.
- As a reply of non-common openings, it has 5 different answers to non-common starting positions using the 400 moves.pgn file from https://www.scacchi64.com/downloads.html
- The strength is set through the number of nodes evaluated. From level 1 (125 nodes) to level 7 (8000). At level 7 it is calibrated to just below 2100 Elo when playing against the Stockfish engine configured to simulate that rating and it takes around 60 seconds per move on a standard ESP32. Setting it to level 0, it plays at an extremely easy level. The level can be set in the `sunfish.py` file.
- This version incorporates 
    - Additional mobility evaluation, including double bishops, open/semiopen files, king safety and advanced pawns.
    - Enhanced but basic move ordering with
        - Promotions and captures first, following a simplified MVV-LVA (Most Valueable Victim - Least Valuable Aggressor)
        - Killer moves second
        - History heuristic third
        - Under promotions and non-history quiets last
    - Basic Late Move Reduction (LMR) 
    - Agressive forward and reverse futility pruning.
- The pst and mobility tables have been tuned using the quiet-labeled.v7.epd positions file using the L-BFGS-B algorithm of the scipy library.
- Instead of a string, the board is a 64-item list that is part of the global position. Although a list to store the board is memory-hungry, its updatable and faster for restoring the difference when returning from a recursive call.
- Besides the original [Sunfish](https://github.com/thomasahle/sunfish), this engine also draws inspiration on [MinimalChess](https://github.com/lithander/MinimalChessEngine),  [4ku](https://github.com/kz04px/4ku) and [MadChess](https://www.madchess.net/)

# Installation

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
[miropython-touch](https://github.com/peterhinch/micropython-touch/tree/master). An example graphical
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

The file uci.py implements a simple UCI interface that can be used with any UCI-compatible user interface. It currently only supports the `Skill_Level` option and `OwnBook` and does not include any time management, always playing at the specified skill level. 
The Windows executable is just the micropython runtime with the micropython code frozen and autolaunching. It is compatible with [cutechess](https://cutechess.com/), [arena](http://www.playwitharena.de/) and [lucaschess](https://lucaschess.pythonanywhere.com/).
You can also play on lichess at [level 0](https://lichess.org/@/uSunfish-l0), [level 1](https://lichess.org/@/uSunfish-l1) or [level 7](https://lichess.org/@/uSunfish-l7).