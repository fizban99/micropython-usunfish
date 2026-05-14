import os
import usunfish_engine as u
from usunfish_engine import render_mv, parse_move
from random import seed
import sys
platform = sys.platform
from usunfish_common import monotonic
try:
    import micropython
    runtime = " - micropython"
except ImportError:
    def const(x):
        return x
    runtime = " - python"

version = "uSunfish 1.1" 
year = "2026"
_MT_LW = const(12680)
_OP_IND = const(1)
_MAX_QS = const(8)
_PAWN = const(22)

LEVEL = 7
limit_strength = False
for arg in sys.argv[1:]:
    if arg.startswith("--level="):
        LEVEL = int(arg.split("=", 1)[1])
        limit_strength = True


startpos = u.position[:]
startpos[0] = startpos[0][:]

_P = 0
_N = 1
_B = 2
_R = 3
_Q = 4
_K = 5
PIECES = "PNBRQK.pnbrqk"
VALUES = [_P, _N, _B, _R, _Q, _K, 6,
          _P | 8, _N | 8, _B | 8, _R | 8, _Q | 8, _K | 8]

ENCODE = {p: v for p, v in zip(PIECES, VALUES)}
PVALUES = b"\x00\x03\x03\x05\x09"


def encode_fen_board(fen_board):
    board = []

    for ch in fen_board:
        if ch == "/":
            continue
        elif ch.isdigit():
            board.extend([6] * int(ch))
        else:
            board.append(ENCODE[ch])

    return board


def castle_bits(castling):
    wc = (("Q" in castling) << 1) | ("K" in castling)
    bc = (("k" in castling) << 1) | ("q" in castling)
    return (wc << 2) | bc


def from_fen(board, color, castling, enpas):
    board = encode_fen_board(board)

    ep = u.parse(enpas) if enpas != "-" else 128
    wc_bc_ep_kp = (castle_bits(castling) << 16) | (ep << 8) | 0x80

    eg = u.is_endgame(board)
    u.eg = eg

    score = u.recalc_sc(board, eg)
    ksq = (board.index(_K | 8) << 8) | board.index(_K)

    u.position = [board, ksq, wc_bc_ep_kp, score, 0, 0]

    if color != "w":
        u.rotate()

    u.hash_board()
    return u.position



def cp_pos(position):
    copy = position[:]
    copy[0]=copy[0][:]
    return copy

def can_kill_king(position):
    # If we just checked for opponent moves capturing the king, we would miss
    # captures in case of illegal castling.
    ksq, wc_bc_ep_kp = position[1:3]
    u.position = position
    if u.makes_check(ksq>>8,  0x00, position ):
        return True
    kp = wc_bc_ep_kp & 0xFF
    if kp == 128:
        return False

    return any(u.makes_check(kp + offset, 0x00, position) for offset in (-1, 0, 1))

def perft(depth):
    root_pos  = cp_pos(u.position)
    def restore_position(position):
        u.position = cp_pos(position)
        u.hash_board()

    def _perft_count(position, depth):
        # Check that we didn't get to an illegal position
        if can_kill_king(position):
            return 0
        if depth == 0:
            return 1
        total = 0
        cp = cp_pos(position)

        gm = u.g_m()
        for move in gm:
            val = (move>>14)-512
            move = move&0x3FFF
            u.move(move, val, u.position)
            total += _perft_count(u.position, depth - 1)
            restore_position(cp)

        return total

    total = 0
    restore_position(root_pos)
    gm = u.g_m() 
    for move in gm:
        val = (move>>14)-512
        move = move&0x3FFF
        move_uci = render_mv(move, root_pos[2]>>20)
        u.move(move, val, u.position)
        cnt = _perft_count(u.position, depth - 1)
        if cnt:
            print(f"{move_uci}: {cnt}")
            total += cnt
        restore_position(root_pos)

    print()
    print("Nodes searched:", total)



def parse_go(args):
    """
    Parse a UCI 'go' command after line.split().

    Example input:
        ["go", "wtime", "8715", "btime", "62973", "binc", "940"]

    Returns a dict with normalized values.
    """
    result = {
        "wtime": None,
        "btime": None,
        "winc": 0,
        "binc": 0,
        "movestogo": None,
        "depth": None,
        "nodes": None,
        "mate": None,
        "movetime": None,
        "infinite": False,
    }

    i = 1
    n = len(args)

    while i < n:
        token = args[i]
        if token == "infinite":
            result["infinite"] = True
            i += 1
        elif token in result.keys():
            result[token] = int(args[i + 1])
            i += 2
        else:
            i += 1
    return result


def send(*parts):
    sys.stdout.write(" ".join(str(part) for part in parts))
    sys.stdout.write("\n")
    try:
        sys.stdout.flush()
    except:
        pass

def get_turn():
    return u.position[2] >> 20


def reset_pos():
    if own_book:
        u.op_mode = 1
    else:
        u.op_mode = 0
    u.eg = 0
    u.last_mv = -1
    u.ply = 0
    u.op_ind = _OP_IND
    u.max_qs = _MAX_QS
    u.history.clear
    u.position[:] = hist[-1][:]
    u.position[0] = hist[-1][0][:] 
    u.history.append(u.position[5])        

_T_SZS = const(128)
def recalc_tp():
    u.t_szs = [0] * u.T_SLOTS
    u.tp_scoreh = [[0] * _T_SZS for _ in range(u.T_SLOTS)]
    # preallocate the score table
    u.tp_scored = [[0] * (_T_SZS * 2) for _ in range(u.T_SLOTS)]
    u.max_d_sc = [0] * u.T_SLOTS    

if platform in ("win32", "linux"):
    u.T_SLOTS = 128
    recalc_tp()

if hasattr(sys, "pypy_version_info"):
    u.T_SLOTS = 256
    runtime = " - pypy"
    recalc_tp()


own_book = True
while True:
    line =sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    args = line.split()
    if args[0] == "uci":
        send("id name", version + f" ({platform}{runtime})" )
        send("id author", f"fizban99 ({year})")
        send(f"option name Skill Level type spin default {LEVEL} min 0 max 7")
        send(f"option name OwnBook type check default {str(own_book).lower()}")
        send(f"option name UCI_LimitStrength type check default {str(limit_strength).lower()}")
        send(f"option name Hash Slots type combo default {u.T_SLOTS} var 2 var 4 var 8 var 16 var 32 var 64 var 128 var 256 var 512")
        send("uciok")


    elif args[0] == "isready":
        send("readyok")

    elif args[0] == "quit":
        break

    elif args[0:5] == ["setoption", "name", "Skill", "Level", "value"]:
        LEVEL = args[5].strip().lower()

    elif args[0:4] == ["setoption", "name", "OwnBook", "value"]:
        own_book = True if args[4].lower() == "true" else False

    elif args[0:4] == ["setoption", "name", "UCI_LimitStrength", "value"]:
        limit_strength = True if args[4].lower() == "true" else False

    elif args[0:5] == ["setoption", "name", "Hash", "Slots", "value"]:
        s = int(args[5])    
        if 2 <= s <= 1024 and s & (s - 1) == 0:
            u.T_SLOTS = s
            recalc_tp()


    elif args[:2] == ["position", "startpos"]:
        hist = [startpos]        
        reset_pos()
        for mv in args[3:]:
            move_code = parse_move(mv, 1-(u.position[2]>>20))
            
            u.mk_mv(move_code)
            # print(u.position[5])
            hist.append((u.position[0][:], u.position[1], u.position[2], u.position[3], u.position[4], u.position[5]))

    elif args[:2] == ["position", "fen"]:
            u.op_mode = 0    
            u.eg = 0
            u.max_qs = _MAX_QS
            u.max_h_mv=[0,0]
            u.position = from_fen(*args[2:6])
            u.ply=1
            if u.position[2]>>20 == 0:
                hist = [cp_pos(u.position)]  
            else:
                old_pos = cp_pos(u.position)
                u.rotate()
                hist = [cp_pos(u.position), old_pos]
                u.position = cp_pos(old_pos)


    elif args[:2] == ["go", "perft"]:
        perft(int(args[2]))

    elif args[0] == "go" or args[0] == "bench":
        if u.ply == 0:
            hist = [startpos]
            reset_pos()
        state = parse_go(args)
        start = monotonic()
        move_str = None
        best_move = 0
        best_move_code = 0
        board, pscore, wc_bc_ep_kp, ksq, mob, h = hist[-1]
        turn = "b" if wc_bc_ep_kp>>20 else "w"
        board = board[:]
        
        if args[0] == "bench":
            LEVEL = 10
            seed(0)
            u.BASE_SEED = 0
            u.op_mode = 0
            limit_strength = True
            state[f"{turn}time"] = 6000000
            state["infinite"] = False
        
        gmv = u.g_mv()
        gm = [m&0x3FFF for m in gmv]
        lvl = LEVEL if limit_strength else 100
        lvl = int(lvl)-1
        best = 0
        u.position[:] = hist[-1][:]
        u.max_nodes = 125 if lvl<0 else 125*(1<<lvl)
        if len(gmv)==1:
            best_move_code = gmv[0]&0x3FFF
            best_move = render_mv(best_move_code, wc_bc_ep_kp>>20 )
            send("bestmove", best_move)
            continue

        time_left = state[f"{turn}time"]
        if time_left is None:
            time_left = state["movetime"]
            max_time = (start + time_left)
            u.max_time =  (start + time_left)            
        else:        
            if time_left is None or state["infinite"]:
                u.max_time = None
            else:
                mtg = state["movestogo"]
                if not mtg:
                    if time_left < 10000:
                        mtg = 10
                    elif  u.eg:
                        mtg = 20
                    elif u.ply < 20:
                        mtg = 50
                    else:
                        mtg = 40
                inc = min(time_left // mtg + state[f"{turn}inc"] * 8 // 10, time_left // 4)
                max_time = (start + inc * 8 // 10)
                u.max_time =  (start +  inc *15 //10)

        for depth, gamma, score, mv in u.search(gmv):

            if score >= gamma and mv:
                best_move = render_mv(mv, wc_bc_ep_kp>>20 )
                best_move_code = mv
                hashfull = sum(u.t_szs)*1000//(u.T_SLOTS*_T_SZS)
                elapsed = max(1, monotonic() - start)

                send(
                    "info depth", depth,
                    "score cp", score * 100 // _PAWN,
                    "nodes", u.nodes,
                    "nps", u.nodes * 1000 // elapsed,
                    "hashfull", hashfull,
                    "pv", best_move,
                )
                if u.usunfish_gmv.b_overflow > 0:
                    send(
                        "info string buffer_overflow", u.usunfish_gmv.b_overflow
                    )

            if  ((lvl == -1 and (best_move_code or u.nodes > 125)) 
                 or (lvl > -1 and u.nodes > 125*(1<<lvl)) 
                 or (score == _MT_LW and depth>=7) 
                 or (u.max_time and (monotonic() - max_time) > 0)):
                break

        if best_move_code ==0 or best_move_code not in gm:
            if gm:
                gm = [m&0x3FFF for m in gmv]
                best_move_code = gm[-1]

        best_move = render_mv(best_move_code, wc_bc_ep_kp>>20 )
        send("bestmove", best_move if best_move_code&0x3F3F!=0 else "(none)")
        if args[0] == "bench":
            sys.exit()
