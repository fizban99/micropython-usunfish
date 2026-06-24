from random import randint, seed
from binascii import crc32
from usunfish_common import *

seed(monotonic())

import gc
from usunfish_common import *
import usunfish_gmv
from usunfish_gmv import parse_sibl, makes_check, gen_moves, value
import usunfish_gmv as ugmv

gc.collect()

BASE_SEED = randint(0, 0x3FFFFFFF)
# initial bytes of the opening tables
_OP_IND2 = const(0)
_OP_IND = const(0)
# Maximum number of moves to keep in the history
_MAX_HIST = const(10)
# Memory allocation for the move buffer
gm_buf = [0] * 800
history = list()
###############################################################################
# Global constants
###############################################################################
# in micropython, const makes the variable a constant, saving memory
# By prepending an underscore to the variable name saves a little bit more memory
# https://docs.micropython.org/en/latest/develop/optimizations.html

_A1 = const(56)
_H1 = const(63)
_A8 = const(0)
_H8 = const(7)

_NO = const(-8)
_S = const(8)
_P = const(0)
_R = const(3)
_K = const(5)
_BP = const(8)

# In the original sunfish, mate value must be greater than 8*queen + 2*(rook+knight+bishop)
# King value is set to twice this value such that if the opponent is
# 8 queens up, but we got the king, we still exceed MATE_VALUE.
# When a MATE was detected, the score was set to MATE_UPPER
# In uSunfish mate is explicitely detected, so no need to have a high value for the king
# we can use constants that are close to the original, but fit in 14 bits.
# This will allow efficient usage of 30 bit positive integers in micropython
_MT_LW = const(12680)
_MT_UP = const(16383)
_CANCEL = const(16384)
_NCANCEL = const(0)
# Constants for tuning search
_QS = const(16)
_QS_A = const(38)
_FUT = const(10)
_EVAL_ROUGHNESS = const(4)
_MAX_DEPTH = const(20)
# limit depth for quiescence search
_MAX_QS = const(8)
PVALUES = b"\x00\x03\x03\x05\x09\x00\x00"

max_qs = _MAX_QS
max_nodes = 8000
max_time = None
# killer heuristic table
t_kll = [0] * (_MAX_DEPTH)

# Transposition tables
# with a replacement strategy based on age
# useful for the hash move
_T_SZS = const(128)
T_SLOTS = 16
t_szs = [0] * T_SLOTS
tp_scoreh = [[0] * _T_SZS for _ in range(T_SLOTS)]
# preallocate the score table
tp_scored = [[0] * (_T_SZS * 2) for _ in range(T_SLOTS)]
max_d_sc = [0] * T_SLOTS
nodes = 0
op_mode = 1  # indicates whether in opening mode or not
op_ind = _OP_IND  # initial byte of the opening table

last_mv = -1
ply = 0  # which ply move we are in
req_d = 0  # what is the requested depth of the current iteration
iter = 0  # iteration counter for the transposition table age tracking
h_mv = ([0] * 64, [0] * 64)  # move history heuristic table for moves white and black
h_va = ([0] * 64, [0] * 64)  # move history heuristic table for values white and black
max_h_mv = [0, 0]  # upper index of the history heuristic
eg = 0  # whether we are in end game mode or not (switch psts in end game)

# Our board is represented as a list of 64 integers. Each element represents a square.
# There is no padding, so this diverges from the original sunfish implementation
# each integer is a piece, even numbers for white pieces, odd numbers for black pieces
# The space is 6 or 14 indistinctly (6 when it's white's turn, 14 when it's black's turn)
# The initial board state, encoded in base64 to save space
# fmt: off
position = [
    [11, 9, 10, 12, 13, 10, 9, 11,  # board
     8, 8, 8, 8, 8, 8, 8, 8,
     6, 6, 6, 6, 6, 6, 6, 6,
     6, 6, 6, 6, 6, 6, 6, 6,
     6, 6, 6, 6, 6, 6, 6, 6,
     6, 6, 6, 6, 6, 6, 6, 6,
     0, 0, 0, 0, 0, 0, 0, 0,
     3, 1, 2, 4, 5, 2, 1, 3],
    60 | (4 << 8),  # ksq
    1015936,  # wc_bc_ep_kp
    0,  # pscore
    0,  # mobility
    0,  # hash
]
# fmt: on

# https://github.com/skeeto/hash-prospector
@micropython.native
def hash_piece(pc, i, base_seed):
    index = pc << 6 | i
    x = base_seed ^ index
    x ^= x >> 16
    x = x * 0x7FEB352D
    x ^= x >> 15
    x = x * 0x846CA68B
    x ^= x >> 16
    return x & 0x3FFFFFFF


@micropython.native
def norm_wb_ek(wb_ek, turn):
    if turn:
        ep = (wb_ek >> 8) & 0xFF
        kp = wb_ek & 0xFF
        wb_ek = (
            ((wb_ek & 0x30000) << 2)
            | ((wb_ek & 0xC0000) >> 2)
            | (ep ^ 63 if ep != 128 else 128) << 8
            | (kp ^ 63 if kp != 128 else 128)
        )
    return wb_ek & 0xFFFFF


@micropython.native
def hash_state(wb_ek, turn, base_seed):
    return hash_piece(0, norm_wb_ek(wb_ek, turn), base_seed)


@micropython.native
def hash_state_swap(wb_ek, wb_ek2, turn, base_seed):
    wb_ek = norm_wb_ek(wb_ek, turn)
    wb_ek2 = norm_wb_ek(wb_ek2, turn ^ 1)
    if wb_ek != wb_ek2:
        return hash_piece(0, wb_ek, base_seed) ^ hash_piece(0, wb_ek2, base_seed)
    else:
        return 0


def hash_board():
    pos = position
    board, _, wc_bc_ep_kp, _, _, _ = pos
    turn = wc_bc_ep_kp >> 20
    base_seed = BASE_SEED
    h = hash_state(pos[2], turn, base_seed)

    if turn:
        for i, p in enumerate(board):
            if p & 7 < 6:
                # piece colors are inverted
                p ^= 8
                # board is inverted for black to move
                h ^= hash_piece(p, 63 ^ i, base_seed)
        h = -h
    else:
        for i, p in enumerate(board):
            if p & 7 < 6:
                h ^= hash_piece(p, i, base_seed)

    pos[5] = h
    return h


hash_board()


###############################################################################
# Board functions
###############################################################################
@micropython.native
def restore(mv, dif):
    """Restore a board from a difference"""
    pos = position
    board, ksq, _, _, _, _ = pos

    board[(mv >> 8) & 0xFF] = (dif >> 4) & 0x0F
    board[mv & 0x3F] = dif & 0x0F
    if dif > 0xFFFF:
        # castling
        i = (dif >> 16) & 0xFF
        board[(dif >> 8) & 0xFF] = board[i]
        board[i] = _R
    elif dif > 0xFF:
        # en passant
        board[(dif >> 8) & 0xFF] = _BP

    if board[(mv >> 8) & 0xFF] == _K:
        pos[1] = (ksq & 0xFF00) | (mv >> 8)


@micropython.native
def reverse():
    """Swap white and black pieces just by flipping
    the highest bit of each nibble and reverse the board"""
    pos = position
    board, ksq, wc_bc_ep_kp, pscore, mob, _ = pos

    for i in range(32):
        board[i], board[63 ^ i] = board[63 ^ i] ^ 8, board[i] ^ 8
    pos[1] = ((ksq >> 8) ^ 63) | (((ksq & 0xFF) ^ 63) << 8)


@micropython.native
def rotate_and_set(score, wc, bc, ep, kp, turn, nullmove, mob):
    """Rotates the board and sets new values"""
    # board, ksq, wc_bc_ep_kp, pscore = position
    pos = position
    reverse()
    # h = abs(pos[5])^pos[2]
    turn = turn ^ 1
    pos[3] = -score
    pos[2] = (
        (turn << 20)
        | (bc << 18)
        | (wc << 16)
        | (ep ^ 63 if ep != 128 and not nullmove else 128) << 8
        | (kp ^ 63 if kp != 128 and not nullmove else 128)
    )
    pos[4] = -mob
    # h = h^pos[2]
    pos[5] = -pos[5]


@micropython.native
def rotate(nullmove=False):
    """Rotates the board, preserving enpassant, unless nullmove"""
    board, ksq, wc_bc_ep_kp, pscore, mob, _ = position

    turn = wc_bc_ep_kp >> 20
    wc = (wc_bc_ep_kp >> 18) & 3
    bc = (wc_bc_ep_kp >> 16) & 3
    ep = (wc_bc_ep_kp >> 8) & 0xFF
    kp = wc_bc_ep_kp & 0xFF
    rotate_and_set(pscore, wc, bc, ep, kp, turn, nullmove, mob)


@micropython.native
def move(mv, val, pos):
    board, ksq, wc_bc_ep_kp, pscore, mob, h = pos

    i, j, prom, turn = mv >> 8, mv & 63, ((mv & 0xFF) >> 6) + 1, wc_bc_ep_kp >> 20
    xor = turn * 7
    pxor = turn << 3
    p = board[i]
    h = abs(h)
    base_seed = BASE_SEED
    if turn:
        ii, jj, pc = 63 ^ i, 63 ^ j, p ^ 8
    else:
        ii, jj, pc = i, j, p

    # Copy variables
    wc, bc, ep, kp = (
        (wc_bc_ep_kp >> 18) & 3,
        (wc_bc_ep_kp >> 16) & 3,
        (wc_bc_ep_kp >> 8) & 0xFF,
        wc_bc_ep_kp & 0xFF,
    )
    q = board[j]
    if q & 7 < 6:
        h ^= hash_piece(q ^ pxor, jj, base_seed)
    pp = p & 7
    t = pp 
    tpst=pst[eg]
    val = value(tpst, i, j, prom, p, q, xor, eg, kp, ep, t) if val is None else (val)
    # reset ep and kp
    ep, kp = 128, 128
    score = pscore + val
    # Actual move
    dif = (board[i] << 4) | board[j]
    board[j] = p

    board[i] = 6 | (turn << 3)
    # xor out the piece
    h ^= hash_piece(pc, ii, base_seed)
    # Castling rights, we move the rook or capture the opponent's
    wc = wc & 1 if i == _A1 else wc & 2 if i == _H1 else wc
    # Black castling rights are inverted
    bc = bc & 2 if j == _A8 else bc & 1 if j == _H8 else bc
    # Castling
    if p == _K:
        wc = 0
        # xor in the king
        h ^= hash_piece(pc, jj, base_seed)
        if abs(j - i) == 2:
            kp = (i + j) // 2
            k = _A1 if j < i else _H1
            dif = (k << 16) | (kp << 8) | dif
            board[k] = 6 | (turn << 3)
            # xor out the rook
            h ^= hash_piece(_R ^ pxor, 63 ^ k if turn else k, base_seed)
            board[kp] = _R
            h ^= hash_piece(_R ^ pxor, 63 ^ kp if turn else kp, base_seed)
        ksq = (ksq & 0xFF00) | j
    # Pawn promotion, double move and en passant capture
    elif p == _P:
        if _A8 <= j <= _H8:
            board[j] = prom
            # xor in the queen
            h ^= hash_piece(prom ^ pxor, jj, base_seed)
        else:
            # xor in the pawn
            h ^= hash_piece(pc, jj, base_seed)
        if j - i == 2 * _NO:
            ep = i + _NO
        if j == (wc_bc_ep_kp >> 8) & 0xFF:
            board[j + _S] = 6 | (turn << 3)
            # xor out the ep pawn
            h ^= hash_piece(_P ^ pxor, 63 ^ (j + _S) if turn else j + _S, base_seed)
            dif = ((j + _S) << 8) | dif
    else:
        # xor in the piece if not a king or a pawn
        h ^= hash_piece(pc, jj, base_seed)

    pos[1] = ksq

    # We rotate the returned position, so it's ready for the next player
    rotate_and_set(score, wc, bc, ep, kp, turn, False, mob)
    # xor in the state
    h ^= hash_state_swap(wc_bc_ep_kp, pos[2], turn, base_seed)
    turn ^= 1
    pos[5] = -h if turn else h

    return dif


###############################################################################
# Search logic
###############################################################################


@micropython.native
def s_sc(tscd, tsch, i, mv, dr, best, h, fh, od):
    """Set move score in the hash table"""
    tscd[i << 1] = mv
    tscd[(i << 1) + 1] = (
        fh | (best + 16384) | (dr << 16) | ((od + 16) << 20) | (iter << 25)
    )
    tsch[i] = h


@micropython.native
def s_hmv(h_mv, h_va, mv, max_h_mv, w):
    # search for existing mv in current range
    # of history heuristics list
    i = 0
    i = get_index(mv, h_mv, 0, max_h_mv)
    if i < 0:
        if max_h_mv < len(h_va):
            i = max_h_mv
            max_h_mv += 1  # use next free slot
        else:
            # replace least-used slot (single pass)
            min_i = 0
            min_v = h_va[0]
            for j in range(1, len(h_va)):
                v = h_va[j]
                if v < min_v:
                    min_v = v
                    min_i = j
            i = min_i
            h_va[i] = 0  # reset its value

    h_mv[i] = mv
    v = h_va[i] + w
    h_va[i] = 40 if v > 40 else 1 if v < 1 else v
    return max_h_mv


@micropython.native
def s_entry(tp, mv, d):
    """Store a move in the heuristics table"""
    m = tp[d]
    mv1 = m & 0x3FFF
    mv2 = (m >> 16) & 0x3FFF
    if mv != mv1 and mv != mv2:
        tp[d] = (mv1 << 16) | mv


@micropython.native
def s_tp(h, mv, best, dr, val, od, fh, mob, incheck):
    """Store a chunk of data in a hash table
    The hash table has an index list with the 30-bit hashes (smallints),
    the data table has
    tp_score:  ply-depth +best_mv, score,gamma. The depth is stored as 4 bits,
    the mv as 14 bits, score,gamma are stored as 2-byte integers. Depth is stored so that nodes closer to the main are
    preferred, and the moves are stored in the order they were found.
    If a new move is stored in the same hash, is is replaced
    """
    global tp_scoreh, tp_scored, max_d_sc, t_szs
    global max_h_mv, max_h_mvm

    non_capt = position[0][mv & 63] | 8 == 14
    turn = position[2] >> 20
    if fh:
        if val <= _QS and non_capt and dr < _MAX_DEPTH:
            s_entry(t_kll, mv, dr)  # quiet move, store in killer table
        if val <= _QS and non_capt:  # quiet move, we use a history heuristics
            if od > 0:
                max_h_mv[turn] = s_hmv(
                    h_mv[turn], h_va[turn], mv, max_h_mv[turn], od * od
                )
    elif val <= _QS and non_capt:  # quiet move that fail low update history heuristics
        if od > 0:
            max_h_mv[turn] = s_hmv(h_mv[turn], h_va[turn], mv, max_h_mv[turn], -od * od)

    e = fh | (best + 16384) | (dr << 16) | ((od + 16) << 20) | (iter << 25)
    it = iter
    mv = mv | ((mob + 512) << 14) | ((incheck >> 2) << 29)
    # if dr < _T_SZS2:
    #     h, tp_scoreh2[dr] = tp_scoreh2[dr], h
    #     mv, tp_scored2[dr<<1] = tp_scored2[dr<<1], mv
    #     e, tp_scored2[(dr<<1)+1] = tp_scored2[(dr<<1)+1], e
    #     it = e >> 25 # local iter
    #     if h == 0 or h==tp_scoreh2[dr]:
    #         return
    hind = (h) & (T_SLOTS - 1)
    new = False
    tszs, tsch, tscd, md = t_szs[hind], tp_scoreh[hind], tp_scored[hind], max_d_sc[hind]
    i = get_index(h, tsch, 0, tszs)
    if i >= 0:
        e2 = tscd[(i << 1) + 1]
        sod = ((e2 >> 20) & 0x1F) - 16
        sdr = (e2 >> 16) & 0xF
    else:
        sod = od
        sdr = dr
        if tszs < _T_SZS:  # within main range
            i = tszs
            t_szs[hind] += 1
            max_d_sc[hind] = md if md > dr else dr
            new = True
        else:
            i = -1
            # find another first
            m_it = it - dr * 2
            for j in range(1, _T_SZS << 1, 2):
                e2 = tscd[j]
                c_iter = e2 >> 25
                sd = (e2 >> 16) & 0xF
                fh2 = e & 0x8000
                if sd > 2 and c_iter - sd * 2 <= m_it:
                    m_it = c_iter - sd * 2
                    i = (j - 1) >> 1
                    if c_iter <= 2:
                        break
            if i == -1:
                # not found anything older, return
                i =  _T_SZS-((h>>16)&0x3F)-1

            max_d_sc[hind] = md if md > dr else dr
            new = True

    if not fh:
        mv = mv & 0xFFFFC000  # set the move to 0, keeping the mobility
    # store the move and the original move only if od>sod
    if od >= sod:
        tscd[i << 1] = mv
        tscd[(i << 1) + 1] = e
        if new:
            tsch[i] = h
        elif md < dr:
            max_d_sc[hind] = dr


@micropython.native
def reset_tp_score():
    global tp_scored
    for hind in range(T_SLOTS):
        for i in range(0, t_szs[hind] << 1, 2):
            if (tp_scored[hind][i + 1] >> 15) - 16384 != _MT_LW:  # mate is a mate
                tp_scored[hind][i + 1] = 0x8000 | (-_MT_UP + 16384)


def g_kll(pdpth):
    """Look up the tp for killers at the same distance from root"""

    kll = [0, 0]
    kll0 = t_kll[pdpth] if pdpth < (_MAX_DEPTH) else 0
    if kll0:
        kll[0] = kll0 & 0x3FFF  # latest stored is 0
        kll[1] = kll0 >> 16
    return kll


# hits = [dict(),dict(),dict(),dict()]
# hits_i = [dict(),dict(),dict(),dict()]


@micropython.native
def g_sc(h, dr, od, board):
    """Get a score from the score table"""
    global tp_scoreh, tp_scored

    # if dr<_T_SZS2 and h==tp_scoreh2[dr]:
    #     e = tp_scored2[(dr << 1)+1]
    #     tp_scored2[(dr << 1)+1] = (e & 0x1FFFFFF) | (iter << 25)
    #     mv = tp_scored2[dr << 1]
    #     position[4] = (mv >> 14)-512 # mobility
    #     mv = mv & 0x03FFF
    # else:
    hind = (h) & (T_SLOTS - 1)
    tscd = tp_scored[hind]
    if dr > max_d_sc[hind]:
        return 0, -_MT_UP, 0x8000, 0, 0  # impossible fail high e < g always
    i = get_index(h, tp_scoreh[hind], 0, t_szs[hind])
    if i >= 0:
        # hits[hind][i]=hits[hind].get(i,0)+1
        e = tscd[(i << 1) + 1]
        # hits_i[hind][iter-c_iter]=hits_i[hind].get(iter-c_iter,0)+1
        tscd[(i << 1) + 1] = (e & 0x1FFFFFF) | (iter << 25)
        mv = tscd[i << 1]
        position[4] = (((mv >> 14) & 0x3FF) - 512) * 4 - 2  # mobility
        incheck = (mv >> 29) << 2  # to return 0x04 if incheck we shift 27 instead of 29
        mv = mv & 0x03FFF

    else:
        return 0, -_MT_UP, 0x8000, 0, 0  # impossible fail high e < g always

    # sd = (e >> 16) & 0xF
    sod = ((e >> 20) & 0x1F) - 16

    # try to prevent hash collision
    # by checking if the move starts with a white piece
    # and does not end with a white piece

    if (
        (board[mv >> 8] > 5)
        or (board[mv & 63] < 6)
        or (board[mv >> 8] == _P and (mv >> 8) < (mv & 63))
    ):
        return 0, _MT_UP, 0, 0, 0
    # We need to be sure, that the stored search for the score was over the same
    # nodes as the current search, so the evaluation depth has to be the same or greater
    if sod < od:
        return mv, -_MT_UP, 0x8000, -1, incheck
    fh = e & 0x8000
    best = (e & 0x7FFF) - 16384
    return mv, best, fh, 1, incheck


def reset_pos(omv, sc, lwc_bc_ep_kp, dif, omb, h):
    # board, ksq, wc_bc_ep_kp, pscore = position
    pos = position
    # if there wasn't a move no need to reset
    pos[3] = sc
    pos[2] = lwc_bc_ep_kp
    pos[4] = omb
    pos[5] = h
    if not omv:
        return
    reverse()
    restore(omv, dif)


@micropython.native
def bound(
    pos, g, od, cn, omv, val, gm, ind, gmv, incheck, pdpth, gm_buf, req_d, max_time
):
    """Receives a position, the gamma,depth,can_null, qs and returns the best score for the position
    Let s* be the "true" score of the sub-tree we are searching.
    The method returns r, where
    if gamma >  s* then s* <= r < gamma  (A better upper bound)
    if gamma <= s* then gamma <= r <= s* (A better lower bound)"""
    global max_qs, nodes
    board, ksq, wc_bc_ep_kp, sc, mob, h = pos
    mqs = max_qs
    red = 0

    # Make the move
    osc = sc  # original score
    omb = mob  # original mobility
    oh = h  # original hash
    lwc_bc_ep_kp = wc_bc_ep_kp  # local flags
    if omv:
        dif = move(omv, val, pos)
        board, ksq, wc_bc_ep_kp, sc, mob, h = pos
    else:
        dif = None
    mob = (mob + 2) >> 2
    ret = 0
    best_mv = 0
    turn = wc_bc_ep_kp >> 20
    while True:
        """Calculate early returns
        The while is just to be able to break
        """

        # Sunfish is a king-capture engine, so we should always check if we
        # still have a king. Notice since this is the only termination check,
        # the remaining code has to be comfortable with being mated, stalemated
        # or able to capture the opponent king.
        # If the move ends with a king capture, we can stop the search
        # and return the mate score
        if makes_check(ksq >> 8, 0, pos):
            ret, best = 1, _MT_UP
            break
        # king moved through check, return a mate score
        kp = wc_bc_ep_kp & 0xFF
        if kp != 128:
            for i in range(-1, 2):
                if makes_check(kp + i, 0, pos):
                    ret, best = 1, _MT_UP
                    break
            if ret:
                break

        nodes += 1
        # kill switch if we are 50% more than the allowed nodes or after max_time
        if 10 * nodes > 15 * max_nodes or (max_time and (monotonic() - max_time) > 0):
            ret, best = 1, _CANCEL
            break

        entry = None
        # Look for the strongest move from last time, the hash-move.
        # and look in the table if we have already searched this position before.
        hmove, e, fh, match, ret = g_sc(h, pdpth, od, board)
        if fh:  # it was a fail high
            if e >= g:
                ret, best, best_mv = 1, e, hmove
                break
            elif match > 0:
                hbest = e
                best = e
            # if e!=-_MT_UP: hits[0][req]=hits[0].get(req,0)+1
        elif e < g:  # it was a fail low
            ret, best = 1, e
            break
        if match:
            # positive match means full match
            # negative match means only mobility and incheck
            if match > 0:
                ohmove = hmove
            mb = ((pos[4] + 2) >> 2) - mob + 1
        else:
            mb = 1  # turn bonus
        # Depth <= 0 is QSearch. Here any position is searched as deeply as defined by _MAX_QS
        d = od if od > 0 else 0
        # Let's not repeat positions. We don't check for repetitions:
        # - at the root (can_null=False) since it is in history, but not a draw.
        # - at depth=0, since it would be expensive and break "futility pruning".
        if cn and d > 0 and h in history:
            ret, best = 1, 0
            break

        # in check?
        # keep track of incheck, counter-incheck, just moved out of check
        # incheck&4: currently in check
        # incheck&2: the enemy just moved out of check
        # incheck&1: in my previous move I moved out of check
        incheck = incheck >> 1
        if match:
            incheck = ret | incheck
        elif makes_check(ksq & 0xFF, 0x08, pos):
            incheck = incheck | 4

        # if we reached the maximum depth in quiescent search and not in check, return the score
        if od < -mqs and not incheck & 4:
            ret, best = 1, sc + mb
            break

        # Pre-generation deep futility pruning.
        # gen_moves() is expensive because it also computes mobility/eval terms.
        # If we are far below gamma even after a queen-sized margin,
        # skip move generation at medium depths outside checks.
        # if  (not incheck&5 and d > 2 and d<7 and pdpth>2 and
        #                 ((sc + mb + PC_VAL[4] )) < g ) :
        #     ret, best = 1, sc + mb
        #     break

        best = -_MT_UP
        ret = 0
        break

    if not ret:
        # Run through the moves, shortcutting when possible
        while True:
            # First we try not moving at all. We only do this if there is at least one major
            # piece left on the board, since otherwise zugzwangs are too dangerous.
            # FIXME: We also can't null move if we can capture the opponent king.
            # Since if we do, we won't spot illegal moves that could lead to stalemate.
            # For now we just solve this by not using null-move in very unbalanced positions.
            # TODO: We could actually use null-move in QS as well. Not sure it would be very useful.
            # But still.... We just have to move stand-pat to be before null-move.
            # if depth > 2 and can_null and any(c in pos.board for c in "RBNQ"):
            # if depth > 2 and can_null and any(c in pos.board for c in "RBNQ") and abs(pos.score) < 500:
            if (
                not incheck
                and d > 2
                and cn
                and abs(sc) < 125
                and any(0 < (p & 7) < 5 for p in board if not (p & 8))
                and pdpth > 0
            ):
                lwc = wc_bc_ep_kp
                rotate(True)
                res = bound(pos, 1-g, d-3 , False, 0, mb, gm, ind, gmv, incheck, pdpth+1, gm_buf, req_d, max_time) # fmt: skip
                rotate()
                res = -((res & 0xFFFF) - 16384)
                pos[2] = lwc
                best = res if res > best else best
                if res >= g:
                    best_mv = 0
                    break
                if not match:
                    mob = (pos[4] + 2) >> 2

            # Increase the quiescent search depth if in-check and in first iteration
            # if (incheck&4 or (req_d == 1)) and mqs < 2*_MAX_QS:
            #     max_qs += 1

            if d == 0 and not incheck & 4:
                best = sc + mb if sc + mb > best else best
                # For QSearch we have a different kind of null-move, namely we can just stop
                # and not capture anything else.
                if sc + mb >= g:
                    best_mv = 0
                    break
            # Is there is no killer move in the kpv
            # try to find one with a more shallow search.
            # This is known as Internal Iterative Deepening (IID).
            # can_null=False, since we want to make sure we actually find a move.
            if not hmove and d > 2:
                hmove = bound(pos, g, d - 2, False, 0, 0, gm, ind, gmv, incheck, pdpth, gm_buf, req_d, max_time) # fmt: skip
                hmove = hmove >> 16

            # If depth == 0 we only try moves with high intrinsic score (captures and
            # promotions). Otherwise we do all moves. This is called quiescent search.
            # If in check or moving out of check, we increase the range.
            val_lower = _QS - (d + (int(incheck > 0) << 2)) * _QS_A

            # Check extension
            if incheck & 4:
                red = -1
            else:
                red = 0
            # Only play the move if it would be included at the current val-limit,
            # since otherwise we'd get search instability.
            # We will skip the hash-move in the main loop below
            # we will research the hash move even with exact match
            # since the gamma is different
            if hmove != 0:
                p = board[hmove >> 8]
                t = (p&7) #if (not eg or op_mode) else (p&7)+6
                if op_mode: 
                    tpst = pst[0]
                else:
                    tpst = pst[eg]
                # fmt: off
                val = value(tpst, hmove >> 8, hmove & 63, ((
                    hmove & 0xFF) >> 6)+1, p, board[hmove & 63], 
                    (wc_bc_ep_kp >> 20) * 7, eg, kp, (wc_bc_ep_kp>>8) & 0xFF,t)
                # fmt: on
                if val >= val_lower:
                    res = bound(pos, 1-g, od-1-red, True, hmove, val+mb, gm, ind, None, incheck, pdpth+1, gm_buf, req_d, max_time) # fmt: skip
                    res = -((res & 0xFFFF)-16384)
                    best = res if res > best else best
                    if res >= g:
                        best_mv = hmove
                        break
                    if incheck & 4 or (match > 0 and res > hbest + 4):
                        # look at previous moves only if the new mobility is at least 4 points greater than the stored one
                        # (simple heuristic that seems to work)
                        match = 0
                else:
                    match = 0
            else:
                # look at previous moves
                match = 0

            if gmv:
                gm = [m for m in gmv if ((m & 0x00FFFFFF) >> 14) - 512 >= val_lower]
                l = len(gm)
                gm_buf[:l] = gm
                gm = gm_buf
            else:
                l = gen_moves(gm, ind, pos, val_lower, g_kll(pdpth), h_va[turn], max_h_mv[turn], h_mv[turn], eg, op_mode, BASE_SEED, d)  # fmt: skip
            if omv == 0:
                omb = pos[4]
                mb = 1
            else:
                mb = ((pos[4] + 2) >> 2) - mob + 1

            # Then all the other moves in the position. We sort them by the value
            # and we take them in reverse order to get the best ones first. We also
            # skip the move if it's the killer move, since we already tried that one.
            # the ones that are below the val_lower limit (Quiescent Search) are already filtered out.
            lmax = l
            while l:
                l -= 1
                mvv = gm[ind + l] & 0x00FFFFFF
                val = (mvv >> 14) - 512
                # prev_res = sc+val
                best_mv = mvv & 0x3FFF
                if match > 0:
                    if ohmove != best_mv:
                        # lmax-=1
                        continue
                    else:
                        match = 0
                if best_mv == hmove:
                    # lmax-=1
                    continue

                # In quiescent search, if the new score is much less than gamma,
                # we can break since it cannot be much better (unless a high exchange)
                # This is known as futility pruning.
                res = sc + val + mb
                mgn = abs(val) + 1
                if (od < 0 and (res + mgn < g)) or od <= -max_qs:
                    best = res if res > best else best
                    break  # inner while

                # Futility pruning (non-qsearch)
                # Only when not in check and not in qsearch
                # If static score is already far below gamma and ply is above 2, accept it
                j = best_mv & 63
                i = best_mv >> 8

                if not (incheck & 4) and omv and od < -_MAX_QS + 2 and j != 63 - (omv & 63):
                    continue

                red = -1 if incheck & 4 else 0  # check extension

                if ( not red and
                    (j > 7 or board[i] != _P)
                    and board[j] & 7 == 6
                    and (
                        d > 2
                        and d < 8
                        and pdpth > 2
                        and (res + (mgn<<2) + (d-3)*(abs(mb)+1)  < g)
                    )
                ):
                    best = res if res > best else best
                    break

                # Simple Late Move Reductions (LMR)
                if (
                    not red
                    and (lmax - l > 4 and d > 3 and pdpth > 0)
                ):
                    if val > 0 or (board[j] & 7) != 6:
                        red = 1
                    else:
                        red = 1 + d // 4 
                res = bound(pos, 1-g, od-1-red, True, best_mv, val + mb, gm, ind+l, None, incheck, pdpth+1, gm_buf, req_d, max_time) # fmt: skip
                res = -((res & 0xFFFF)-16384)
                if red>0 and res >= g + 5:
                    # full depth re-search
                    res = bound(pos, 1-g, od-1, True, best_mv, val + mb, gm, ind+l, None, incheck, pdpth+1, gm_buf, req_d, max_time) # fmt: skip
                    res = -((res & 0xFFFF)-16384) 

                best = res if res > best else best

                if best >= g:
                    break
            break

        # Stalemate checking is a bit tricky: Say we failed low, because
        # we can't (legally) move and so the (real) score is -infty.
        # At the next depth we are allowed to just return r, -infty <= r < gamma,
        # which is normally fine.
        # However, what if gamma = -10 and we don't have any legal moves?
        # Then the score is actually a draw and we should fail high!
        # Thus, if best < gamma and best < 0 we need to double check what we are doing.

        # We will fix this problem another way: We add the requirement to bound, that
        # it always returns MATE_UPPER if the king is capturable. Even if another move
        # was also sufficient to go above gamma. If we see this value we know we are either
        # mate, or stalemate. It then suffices to check whether we're in check.

        # Note that at low depths, this may not actually be true, since maybe we just pruned
        # all the legal moves. So sunfish may report "mate", but then after more search
        # realize it's not a mate after all. That's fair.
        # This is too expensive to test at depth == 0

        if best == -_MT_UP:
            best_mv = 0
            best = -_MT_LW if incheck & 4 else 0

        # for small transposition tables it is better to store the score in the table
        # when the score is better than the gamma so that moves and scores can be stored in the
        # same table. Also when invalidating a previously fh move

        if best >= g and (16 > od >= -16 and (best_mv != 0)) and (cn or pdpth == 0) and pdpth < 16:
            s_tp(h, best_mv, best, pdpth, val, od, 0x8000, (pos[4] + 2) >> 2, incheck)
        if best < g and not best_mv and fh and hmove and (16 > od >= -16) and pdpth < 16:
            s_tp(h, hmove, best, pdpth, val, od, 0, (pos[4] + 2) >> 2, incheck)

        # reset max_qs if modified
        max_qs = mqs

    reset_pos(omv, osc, lwc_bc_ep_kp, dif, omb, oh)
    if best == _CANCEL:
        return _NCANCEL
    # ic(-best,best_mv)

    return (best + 16384) | (best_mv << 16)


def mk_mv(mv):
    global last_mv, op_mode, op_ind, ply

    ply += 1
    if op_mode == 1:
        gm = g_m()

        gm = [m & 0x3FFF for m in gm]
        gm.reverse()
        # remove promotion info for the opening comparison
        mv = mv & 0x3F3F
        last_mv = gm.index(mv)
        # check if the last move
        # is in the list of next moves of the opening
        mvs, _ = parse_sibl(op_ind, ply - 1, op)
        i = [i for i, (mv, _) in enumerate(mvs) if mv == last_mv]
        if i:
            # if it is in the list, update the next move index
            # to the first child of the move
            op_ind = mvs[i[0]][1]
        else:
            op_mode = 0
            if ply == 1:
                # check if the last move
                # is in the list of next moves of the opening
                mvs, _ = parse_sibl(_OP_IND2, ply - 1, op2)
                i = [i for i, (mv, _) in enumerate(mvs) if mv == last_mv]
                if i:
                    # if it is in the list, update the next move index
                    # to the first child of the move
                    op_ind = mvs[i[0]][1]
                    op_mode = 2

    if len(history) > _MAX_HIST:
        history.pop(0)
    dif = move(mv, None, position)
    history.append(position[5])
    return dif


def g_next_move(op):
    global op_ind, last_mv, op_mode, ply
    # choose a move from the children
    i = op_ind
    mvs, _ = parse_sibl(i, ply, op)
    if not mvs:
        op_mode = 0
        return 0
    mv, _ = mvs[randint(0, len(mvs) - 1)]
    gm = g_m()

    mv = gm[-mv - 1] & 0x3FFF
    return mv


def search(gmv):
    """Iterative deepening MTD-bi search"""
    global nodes, req_d, tp_scored, tp_scoreh, max_d_sc, t_szs, op_ind, iter
    global eg, max_qs, req_d, start_time

    

    nodes = 0
    if not gmv:
        gmv = g_mv()
    _, _, _, pscore, mob, _ = position        
    # Check if we are in opening mode
    if op_mode == 1:
        last_mv = g_next_move(op)
        if last_mv != 0:
            yield 0, pscore - 4, pscore, last_mv
            return
        # Check if we have a move from the 400 moves opening book
    elif op_mode == 2 and ply == 1:
        last_mv = g_next_move(op2)
        if last_mv != 0:
            yield 0, pscore - 4, pscore, last_mv
            return
    
    
    guess = pscore + ((mob+2)>>2) + 1

    iter = 0
    eval_roughness =  _EVAL_ROUGHNESS-1    
    for req_d in range(1, _MAX_DEPTH+1):
        margin = 16 + max(0, req_d-4)*4
        lower = guess - margin
        upper = guess + margin
        if lower < -_MT_LW: lower = -_MT_LW
        if upper > _MT_LW: upper = _MT_LW
        g = guess
        widened = False

        eval_dist = upper - lower
        while eval_dist > eval_roughness:
            res = bound(position, g, req_d, False, 0, 0,
                        gm_buf, 0, gmv, 0, 0, gm_buf, req_d, max_time)

            if res == _NCANCEL:
                yield req_d, g, _NCANCEL, 0
                return

            score, best_mv = ((res & 0xFFFF)-16384), res >> 16

            if score >= g:
                lower = score
                if lower >= upper and not widened:
                    upper = _MT_LW
                    widened = True
            else:
                upper = score
                if upper <= lower and not widened:
                    lower = -_MT_LW
                    widened = True

            eval_dist = upper - lower
            yield req_d, g, score, best_mv
            g = (lower + upper + 1) // 2
            iter = (iter + 1)&31


        guess = (lower + upper + 1) // 2
        depth_roughness = _EVAL_ROUGHNESS + max(0, req_d -4 ) // 4
        eval_roughness = depth_roughness
        if eval_roughness > 6:
            eval_roughness = 6     
        


def g_m():
    turn = position[2] >> 20
    gm = gm_buf
    l = gen_moves(
        gm, 0, position, -_MT_LW, 0, h_va[turn], max_h_mv[turn], h_mv[turn], eg, op_mode, BASE_SEED, 100
    )
    gm = gm[:l]
    return gm


def get_phase(board):
    material = sum(PVALUES[p & 7] for p in board)
    pn = sum(1 for p in board if (p & 7) == 0)
    if material < 13 or pn < 8:
        return 2
    elif material < 33:
        return 1
    else:
        return 0

@micropython.native
def recalc_sc(board, eg, xor):
    score = 0
    tpst = pst[eg]
    for i, c in enumerate(board):
        piece = c & 7

        if piece >= 6:
            continue

        if c & 8:
            score -= tpst[piece][i ^ 56^ xor]
        else:
            score += tpst[piece][i^ xor]

    return score


@micropython.native
def g_mv():
    global max_qs, eg, pst
    global t_szs, max_d_sc
    global max_h_mv

    pos = position
    lbrd, _, wc_bc_ep_kp, pscore, _, _ = pos

    turn = wc_bc_ep_kp >> 20
    # detect endgame and adjust score and pst accordingly

    if eg < 2:
        phase = get_phase(lbrd)
        if phase > eg:
            # max_qs = _MAX_QS + 1
            eg = phase
            xor = (wc_bc_ep_kp >> 20) * 7
            # recalculate score
            pos[3] = recalc_sc(lbrd, eg, xor)

    ts = [0,] * T_SLOTS # fmt: skip
    d = 0

    if ply < 2:
        max_h_mv[0], max_h_mv[1] = 0, 0
        for i in range(_MAX_DEPTH):
            t_kll[i] = 0
        gm = g_m()
        gm = [m for m in gm if not can_kill_king(m & 0x3FFF)]
    else:
        # reuse heuristics from previous move
        t_kll[:-2] = t_kll[2:]
        t_kll[-2:] = [0, 0]

        # reuse history heuristics from previous move
        # include only possible moves from current position
        # for both sides
        lwc_bc_ep_kp = wc_bc_ep_kp
        nullmove = True
        for _ in range(2):
            rotate(nullmove)
            nullmove = False
            turn = turn ^ 1
            gm = g_m()
            # print([(((m&0xFFFFFF)>>14)-512, m&0x3FFF, render_mv(m&0x3FFF, pos[2]>>20)) for m in gm])
            gm = [m for m in gm if not can_kill_king(m & 0x3FFF)]
            gmm = {m & 0x3FFF for m in gm}
            i = 0
            for j in range(max_h_mv[turn]):
                mv = h_mv[turn][j]
                if mv in gmm:
                    v = h_va[turn][j] >> 2
                    if v > 0:
                        h_mv[turn][i] = mv
                        h_va[turn][i] = v
                        i += 1
            max_h_mv[turn] = i
        pos[2] = lwc_bc_ep_kp
        # put the previous PV at the beginning
        d = recalc_tp(0, ts)
    for i in range(T_SLOTS):
        max_d_sc[i] = d
    t_szs = ts

    return gm


def recalc_tp(d, ts):
    # move the PV
    # to the beginning
    _, _, wc_bc_ep_kp, pscore, mob, h = position
    hind = (h) & (T_SLOTS - 1)
    tscd, tsch = tp_scored[hind], tp_scoreh[hind]
    try:
        # avoid including the already inserted hashes
        i = tsch.index(h, ts[hind], t_szs[hind])
    except ValueError:
        return d
    # sd = (e >> 16) & 0xF
    e = tscd[(i << 1) + 1]
    mv = tscd[i << 1] & 0x03FFF
    sod = ((e >> 20) & 0x1F) - 16

    # best = (e & 0x7FFF) - 16384
    if mv:  # store it at the beginning
        j = ts[hind]
        tsch[j] = h
        tscd[j << 1] = tscd[i << 1]
        tscd[(j << 1) + 1] = (e & 0xFFF0FFFF) | (d << 16)
        ts[hind] += 1
        lwc_bc_ep_kp = wc_bc_ep_kp
        # empty the matching pos to avoid stack overflow
        tsch[i] = 0
        dif = move(mv, 0, position)
        d = recalc_tp(d + 1, ts)
        reset_pos(mv, pscore, lwc_bc_ep_kp, dif, mob, h)
        return d
    else:
        return d


def can_kill_king(mv, ccheck=True):
    pos = position
    lbrd, ksq, wc_bc_ep_kp, pscore, mob, h = pos
    # If we just checked for opponent moves capturing the king, we would miss
    # captures in case of illegal castling.
    res = False
    by_black = 0
    sc = pscore
    lwc_bc_ep_kp = wc_bc_ep_kp
    if mv != 0:
        dif = move(mv, None, pos)
    else:
        by_black = 0x08

    lbrd, ksq, wc_bc_ep_kp, pscore, _, _ = position
    if by_black:
        king = ksq & 0xFF
    else:
        king = ksq >> 8
    if makes_check(king, by_black, pos):
        res = True
    elif ccheck and mv:
        kp = wc_bc_ep_kp & 0xFF
        if kp != 128:
            for i in (-1, 0, 1):
                if makes_check(kp + i, by_black, pos):
                    res = True
                    break
    if mv > 0:
        reset_pos(mv, sc, lwc_bc_ep_kp, dif, mob, h)
    return res


###############################################################################
# UCI User interface
###############################################################################
mapping = "PNBRQK. pnbrqk. "


def render(i):
    rank, fil = divmod(i - _A1, 8)
    return chr(fil + ord("a")) + str(-rank + 1)


def parse(c):
    fil, rank = ord(c[0]) - ord("a"), int(c[1]) - 1
    return _A1 + fil - 8 * rank


def parse_move(move_str, white_pov):
    mapping = "NBRQ"
    i, j, prom = parse(move_str[:2]), parse(move_str[2:4]), move_str[4:].upper()
    if not white_pov:
        i, j = 63 ^ i, 63 ^ j
    mv = i << 8 | j | mapping.index(prom) << 6
    return mv


def render_mv(mv, turn=0):
    if mv == 0:
        return "(none)"
    i, j = mv >> 8, mv & 0x3F
    prom = ""
    if j < 8 and position[0][i] | 8 == _P + 8:
        prom = mapping[((mv >> 6) & 3) + 1].lower()
    if turn == 1:
        i, j = 63 ^ i, 63 ^ j
    return render(i) + render(j) + prom
