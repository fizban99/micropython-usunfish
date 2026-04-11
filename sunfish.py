from time import time as monotonic
import usunfish_engine as u
import gc
import sys
if sys.implementation.name != "micropython" or sys.platform == "win32":
    def const(x):
        return x
    
gc.collect()
_A1 = const(56)
# level from 0 to 7 
# level 0 will make really dumm moves
# default 2 is around 2 seconds thinking
# every step increase will double the thinking time
LEVEL = 2
mapping = "PNBRQK  pnbrqk  "
_PROM = "NBRQ"
_MT_LW = const(12680)
_MT_UP = const(16383)
_CHECK = const(1)
_MATE = const(2)
_STALEMATE = const(3)
_DRAW = const(4)
_P = const(0)
_OP_IND = const(1)
_MAX_QS = const(8)
_START_POS = b'\x0b\t\n\x0c\r\n\t\x0b\x08\x08\x08\x08\x08\x08\x08\x08\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x06\x00\x00\x00\x00\x00\x00\x00\x00\x03\x01\x02\x04\x05\x02\x01\x03'
MESSAGES = ("\n", "Check!", "Checkmate!", "Stalemate!", "Draw-rep")


def threefold():
    return u.history.count(u.ghash()) >= 3

def render(i):
    r, f = divmod(i - _A1, 8)
    return chr(97 + f) + str(1 - r)

def parse(s):
    return _A1 + ord(s[0]) - 97 - 8 * (int(s[1]) - 1)

def parse_move(s, white_pov):
    i, j = parse(s[:2]), parse(s[2:4])
    if not white_pov:
        i, j = 63 - i, 63 - j
    return i << 8 | j | _PROM.index(s[4:].upper()) << 6

def render_mv(mv, turn=0):
    if not mv:
        return ""
    i, j = mv >> 8, mv & 63
    if turn:
        i, j = 63 - i, 63 - j
    p = mapping[(mv >> 6 & 3) + 1].lower() if j < 8 and u.position[0][i] | 8 == _P + 8 else ""
    return render(i) + render(j) + p

def print_pos():
    for a in range(8):
        print(" ", 8 - a, " ".join(mapping[u.position[0][a * 8 + b]].replace(" ",".") for b in range(8)))
    print("    a b c d e f g h ")

u.history = []


def g_gm1():
    global gm
    # unique start square
    gm = list(set([(m&0x3FFF)>>8 for m in u.g_mv()]))
    gm.sort()


def is_end_game():
    global gm

    if u.can_kill_king(0, ccheck=False):
        g_gm1()
        if not gm:
            return _MATE
        else:
            return _CHECK
    else:
        g_gm1()
        if not gm:
            return _STALEMATE

    if threefold():
        gm = []
        return _DRAW
    return 0


###############################################################################
# User interface
###############################################################################

def main():
    best_move = None
    while True:
        mv = None
        gm = [x & 16383 for x in u.g_mv()]
        if best_move:
            print("My move:", best_move)
            is_end = is_end_game()
            print(MESSAGES[is_end])     
            if is_end:
                break             

        best_move = None
        print_pos()

        # We query the user until she enters a (pseudo) legal move.
        while mv not in gm:
            s = input("Your move: ")
            if len(s)==4 and "a"<=s[0]<="h" and "1"<=s[1]<="8" and "a"<=s[2]<="h" and "1"<=s[3]<="8":
                mv = parse(s[:2]) << 8 | parse(s[2:4]) 
            else:
                print("Please enter a move like g8f6")
                
        if mv&63<8 and u.position[0][mv>>8]==_P:
            mv = mv | 0xC0  # assume queen promotion
        u.mk_mv(mv)
        u.rotate(); print_pos(); u.rotate()
        is_end = is_end_game()
        print(MESSAGES[is_end])
        if is_end > _CHECK:
            break

        lvl = LEVEL-1
        bmv = 0
        u.max_nodes = 125 if lvl<0 else 125*(1<<lvl)
        gmvs = u.g_mv()
        gm = [x & 16383 for x in gmvs]

        for depth, gamma, score, mv in u.search(gmvs):
            if mv is not None:
                print(u.nodes, end="\r")
            if score >= gamma and mv:
                bmv = mv
            if  (lvl == -1 and (bmv or u.nodes > 125)) or (lvl > -1 and u.nodes > 125*(1<<lvl)) or (score== _MT_LW and depth>=3):
                break            

        if not bmv and gm:
            bmv = gm[-1]

        best_move = render_mv(bmv, u.position[2] >> 20)
        
        u.mk_mv(bmv)


###############################################################################
# API
###############################################################################

def game(iboard=None):
    u.eg = 0
    u.op_mode = 1    
    u.op_ind = _OP_IND 
    u.max_qs = _MAX_QS 
    if iboard:
        u.last_mv = 15
        u.ply=2        
        u.position = [make_board(iboard), 1084, 1015936, 3, 2]        
    else:
        u.last_mv = -1
        u.ply=0
        u.position = [list(_START_POS),
                      60 | (4 << 8),  # ksq
                      1015936,  # wc_bc_ep_kp
                      0, # pscore
                      0, # mobility 
                        ] 
        
    best_move = None
    amove = None
    is_end = False
    while True:
        gc.collect()
        if best_move:
            is_end = is_end_game()

        # Yield current board state and last black move (if any)
        amove = yield u.position[0], best_move  # Await a move
        if is_end > _CHECK:
            print(MESSAGES[is_end])   
            return False # StopIteration: player lost

        best_move = None
        gm = [x & 16383 for x in u.g_mv()]
        move = None
        while move not in gm: 
            if move:
                amove = yield  # A None reponse prompts user to try again     
            if len(amove)==4 and "a"<=amove[0]<="h" and "1"<=amove[1]<="8" and "a"<=amove[2]<="h" and "1"<=amove[3]<="8":
                move = parse(amove[:2]) << 8 | parse(amove[2:4]) 
        
        if move&63<8 and u.position[0][move>>8]==_P:
            move = move | 0xC0  # assume queen promotion
        u.mk_mv(move)
        # After our move we rotate the board and print it again.
        # This allows us to see the effect of our move.
        u.rotate()
        yield u.position[0] # print the board
        u.rotate()
        is_end = is_end_game()
        if is_end > _CHECK:
            print(MESSAGES[is_end])  
            return True  # Player won

        lvl = LEVEL-1
        bmv = 0
        u.max_nodes = 125 if lvl<0 else 125*(1<<lvl)
        gmvs = u.g_mv()
        gm = [x & 16383 for x in gmvs]

        for depth, gamma, score, mv in u.search(gmvs):
            if score >= gamma and mv:
                bmv = mv
            if  (lvl == -1 and (bmv or u.nodes > 125)) or (lvl > -1 and u.nodes > 125*(1<<lvl)) or (score== _MT_LW and depth>=3):
                break            

        if not bmv and gm:
            bmv = gm[-1]

        best_move = render_mv(bmv, u.position[2] >> 20)
        
        u.mk_mv(bmv)




# Return contents of board in left to right, top to bottom order.
def get_board(board):
    for cell in board:
        yield mapping[cell].strip()

# Convert a board bytes object to a uSunfish compatible board. Enable arbitrary start positions.
# The bytes object has length 64 and represents a board in alphabetic form.
def make_board(b):
    for i, cell in enumerate(b):
        u.position[0][i] = mapping.index(chr(cell))
    return u.position[0]


if __name__ == "__main__":
    main()

