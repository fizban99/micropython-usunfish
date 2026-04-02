import os
import usunfish_engine as u
from time import time as monotonic
import sys

_A1 = const(56)
_P = const(0)
_MAX_HIST = const(10)
_MT_LW = const(12680)
_OP_IND = const(1)
_MAX_QS = const(8)

LEVEL = 7
for arg in sys.argv[1:]:
    if arg.startswith("--level="):
        LEVEL = int(arg.split("=", 1)[1])

startpos = u.position[:]
startpos[0] = u.position[0][:]
def get_turn():
    return u.position[2] >> 20


def render(i):
    rank, fil = divmod(i - _A1, 8)
    return chr(fil + ord('a')) + str(-rank + 1)


def parse(c):
    fil, rank = ord(c[0]) - ord('a'), int(c[1]) - 1
    return _A1 + fil - 8*rank


def parse_move(move_str, white_pov):
    mapping = "NBRQ"
    i, j, prom = parse(move_str[:2]), parse(
        move_str[2:4]), move_str[4:].upper()
    if not white_pov:
        i, j = 63 - i, 63 - j
    mv = i << 8 | j | mapping.index(prom) << 6
    return mv


def render_mv(mv, turn=0):
    if mv == 0:
        return ""
    i, j = mv >> 8, mv & 0x3F
    prom = ""
    if j < 8 and u.position[0][i] | 8 == _P+8:
        prom = mapping[((mv >> 6) & 3)+1].lower()
    if turn == 1:
        i, j = 63 - i, 63 - j
    return render(i) + render(j) + prom


mapping = 'PNBRQK. pnbrqk. '    
version = f"uSunfish 2026.1 level {LEVEL}"

while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    args = line.split()
    if args[0] == "uci":
        print("id name", version)
        print("option name Skill_Level type spin default 7 min 0 max 7")
        print("uciok")

    elif args[0] == "isready":
        print("readyok")

    elif args[0] == "quit":
        break

    elif args[0].strip().lower()[:32] == "setoption name skill_level value":
        LEVEL = args[0].strip.lower()[-1]

    elif args[:2] == ["position", "startpos"]:
        u.op_mode = 1
        u.eg = 0
        u.last_mv = -1
        u.ply = 0
        u.op_ind = _OP_IND
        u.max_qs = _MAX_QS
        hist = [startpos]
        for mv in args[3:]:
            u.position[:] = hist[-1][:]
            u.position[0] = hist[-1][0][:]
            move_code = parse_move(mv, 1-(u.position[2]>>20))
            
            u.mk_mv(move_code)
            u.history.append(u.ghash())
            u.history = u.history[-_MAX_HIST:]
            hist.append((u.position[0][:], u.position[1], u.position[2], u.position[3], u.position[4]))

    elif args[0] == "go":

        start = monotonic()
        move_str = None
        best_move = 0
        best_move_code = 0
        u.eg = 0
        board, pscore, wc_bc_ep_kp, ksq, mob = hist[-1]
        board = board[:]
        gmv = u.g_mv()
        gm = [m&0x3FFF for m in gmv]
        lvl = LEVEL
        lvl = int(lvl)-1
        best = 0
        u.position[:] = hist[-1][:]
        u.max_nodes = 125 if lvl<0 else 125*(1<<lvl)
        if len(gmv)==1:
            best_move_code = gmv[0]&0x3FFF
            best_move = render_mv(best_move_code, wc_bc_ep_kp>>20 )
            print("bestmove", best_move)
            continue

        for depth, gamma, score, mv in u.search(gmv):

            if score >= gamma and mv:
                best_move = render_mv(mv, wc_bc_ep_kp>>20 )
                best_move_code = mv
                print("info depth", depth, "score cp", score, "nodes", u.nodes, "pv", best_move)

            if  (lvl == -1 and (best_move_code or u.nodes > 125)) or (lvl > -1 and u.nodes > 125*(1<<lvl)) or (score== _MT_LW and depth>=3):
                break

        if best_move_code ==0 or best_move_code not in gm:
            if gm:
                gm = [m&0x3FFF for m in gmv]
                best_move_code = gm[-1]

        best_move = render_mv(best_move_code, wc_bc_ep_kp>>20 )
        print("bestmove", best_move if best_move_code&0x3F3F!=0 else "(none)")
