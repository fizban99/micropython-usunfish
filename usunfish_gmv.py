from usunfish_common import *
from random import randint

##############################################################################
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
_E = const(1)
_S = const(8)
_W = const(-1)
_P = const(0)
_N = const(1)
_B = const(2)
_R = const(3)
_Q = const(4)
_K = const(5)
_BP = const(8)

_PHLX = const(0)
_CTPA = const(1)
_MXEPA = const(2) 
_MXOPA = const(3)
_RRPA = const(4)
_PHPA = const(5)
_PPPA = const(6)
_BSHP = const(7)
_OPNR = const(8)
_OPNQ = const(9)
_SOPNR = const(10)
_SOPNQ = const(11)
_PB = const(12)
_OPB = const(13)
_ATT = const(1)
_KRC = const(2)
_MBT = const(3)
_SOPN = const(4)
_OPN = const(5)
# In the original sunfish, mate value must be greater than 8*queen + 2*(rook+knight+bishop)
# King value is set to twice this value such that if the opponent is
# 8 queens up, but we got the king, we still exceed MATE_VALUE.
# When a MATE was detected, the score was set to MATE_UPPER
# In uSunfish mate is explicitely detected, so no need to have a high value for the king
# we can use constants that are close to the original, but fit in 14 bits.
# This will allow efficient usage of 30 bit positive integers in micropython
# Constants for tuning search
_QS = 16
# limit depth for opening book
_MAX_OP_D = const(11)
draw = False
_buff = [0] * 9  # kingring squares and black pawns

def op_get(i, op):
        if i >> 1 >= len(op):
            return 0
        return (op[i >> 1] >> ((i & 1) ^ 1) * 4) & 0xF

def read_node(c_ind, op):
    first = op_get(c_ind, op)

    if first < 14:
        return first, c_ind + 1

    second = op_get(c_ind + 1, op)

    if second < 15:
        # second must be 4..14 here
        return second + 10, c_ind + 2

    # [14,15,x]
    return 25 + op_get(c_ind + 2, op), c_ind + 3

def parse_sibl(c_ind, d, op):
    if d > _MAX_OP_D:
        return [], c_ind    
    sibl = []
    n_sibl = op_get(c_ind, op)
    # read number of siblings
    if n_sibl == 14 and op_get(c_ind + 1, op) < 3:
        n_sibl = op_get(c_ind + 1, op)+2
        c_ind += 2
    elif n_sibl == 15:
        n_sibl = 0
        c_ind += 1
    elif n_sibl == 14 and op_get(c_ind + 1, op) == 3:
        n_sibl = op_get(c_ind + 2, op)+4
        c_ind += 3
    else:
        n_sibl = 1
    for _ in range(n_sibl):
        # read node value
        node, c_ind = read_node(c_ind, op)
        sibl.append((node, c_ind))
        # Recursively parse children
        _, c_ind = parse_sibl(c_ind , d+1, op)
    
    return sibl, c_ind


###############################################################################
# Chess logic
###############################################################################
@micropython.native
def makes_check(ksq, bbit, position):
    """
    Return True if the square king_sq is attacked by the side 'by_white'.
    - by_white == True  -> look for white attackers
    - by_white == False -> look for black attackers
    Uses board[] and your piece encoding:
      white: 0..5, black: 8..13, empty: 6 or 14.
    """
    b = position[0]
    wc_bc_ep_kp = position[2]
    rk = ksq >> 3  # rank 0..7 (0 = 8th rank)
    fk = ksq & 7  # file 0..7 (0 = 'a')
    # --- piece codes for the attacking side ---
    P = _P | bbit
    N = _N | bbit
    B = _B | bbit
    R = _R | bbit
    Q = _Q | bbit
    K = _K | bbit
    # Edge case when the square to validate is already occupied
    # by same color
    p0 = b[ksq]
    if p0 == N or p0 == K or p0 == R or p0 == B or p0 == P:
        return True

    # ------------------------------------------------
    # 1) Pawn attacks
    # ------------------------------------------------
    # pawn attacks
    r = rk + 1 if not bbit else rk - 1
    if 0 <= r < 8:
        i = r * 8
        c = fk - 1
        if not (c & ~7) and b[i + c] == P:
            return True
        c = fk + 1
        if not (c & ~7) and b[i + c] == P:
            return True

    empt = 6 | ((wc_bc_ep_kp >> 20) << 3)
    for p in (N, K, R, B):
        dir = directions[p & 7]
        for dn in range(0, len(dir) - 1, 2):
            dc, d = dir[dn] - 2, dir[dn + 1] - 17
            # calculate column for detecting out of bounds
            c = fk
            j = ksq
            while True:
                j += d
                c += dc
                if (c & ~7) | (j & ~63):
                    break
                q = b[j]
                if p == N or p == K:
                    if q == p:
                        return True
                    break

                if q == empt:
                    continue
                # first non-empty square on this ray
                if q == p or q == Q:
                    return True
                break  # blocked by some piece
    return False


@micropython.native
def ma(moves, ind, mv, val, lvalue, kll, h_va, max_h_mv, h_mv, p, q, prom, empt, op_mode):
    """Move sorting logic
    A virtual bonus is added to the score for sorting
    and later substracted for stability of the sunfish scoring logic
    """

    if (lvalue >= _QS and prom < 3):
        # in quiet search, disregard non-Q promotions
        # ma is passed prom = 4 for non-promotion moves
        return ind

    if p == _P and prom < 3:
        order = 0
        # under promotions at the end (order 0)
    # non-quiet moves first
    elif q != empt or prom == 3:
        # mvv-lva
        # promotions with capture are considered
        # as if the capture was the promotion, for sorting
        if p == _P and prom == 3:
            q = 4
        # Captures are sorted into 43..63:
        # q&7 is 0..4 because kings are never captured/generated as normal captures.
        # p is 0..4 for the moving piece in generated white moves.
        # This keeps captures above killers/history without extra fields.
        order = ((q & 7) << 2) + (47 - p)
    elif kll and (mv in kll):
        # killer moves
        if mv == kll[0]:
            order = 42
        else:
            order = 41
    elif val >= _QS:
        # other moves above threshold
        # (tactical moves?)
        # order overlaps with history, but val will always be higher
        # since val >= QS
        order = 40
    elif max_h_mv:
        # rest of moves ordered by history heuristics (1-40)
        i = get_index(mv, h_mv, 0, max_h_mv)
        if i >= 0:
            order = h_va[i]
        else:
            # lastly moves not in history
            order = 0
    else:
        order = 0

    if ind < len(moves) and (val >= lvalue or  order > 40):
        if op_mode:
            order = 0
        moves[ind] = (mv | ((val + 512) << 14)) | (order << 24)
        ind += 1

    return ind


@micropython.native
def value(lpst, i, j, prom, p0, q, xor, eg, kp, ep, p):
    # base PST delta
    score = lpst[p][j ^ xor] - lpst[p][i ^ xor]

    # capture of enemy piece
    if 8 <= q < 14:
        ind = j ^ 63
        q1 = (q & 7)
        score += lpst[q1][ind ^ xor ^ 7]
        # No need to check for king capture, since it is
        # checked with makes_check
        # if (q & 7) == _K:
        #     score = 511

    # castling check detection
    if abs(j - (kp)) < 2:
        ind = j ^ 63
        score += lpst[p][ind ^ xor ^ 7] + 14975

    # king castling rook PST adjustment
    if p0 == _K and abs(i - j) == 2:
        r_from = _A1 if j < i else _H1
        p1 = _R 
        score += lpst[p1][((i + j) >> 1) ^ xor] - lpst[p1][r_from ^ xor]

    # pawn specials: ep capture / promotion
    elif p0 == _P:
        if j == (ep):  # ep square
            score += lpst[p][((j + _S) ^ 56) ^ xor]
        elif _A8 <= j <= _H8:  # promotion.
            # No need to substract pst of last row, since it is 0
            prom = prom 
            score += lpst[prom][j ^ xor]

    return score


@micropython.native
def king_ring(k, buff):
    r, f = k >> 3, k & 7
    i = 0
    for dr in b"\x00\x01\x02":
        rr = r + dr - 1
        if 0 <= rr <= 7:
            base = rr << 3
            for df in b"\x00\x01\x02":
                ff = f + df - 1
                if 0 <= ff <= 7:
                    buff[i] = base + ff
                    i += 1
    return buff[:i]


@micropython.native
def rq_mobility(r_file, q_file, enemy_pawns, own_pawns, pf2, sop_r, sop_q, op_r, op_q, pc4=PC4):
    pf1 = enemy_pawns & (0xFF ^ own_pawns)
    a = r_file & pf1
    b = r_file & pf2
    c = q_file & pf1
    d = q_file & pf2
    return (
        (pc4[a & 15] + pc4[a >> 4]) * sop_r
        + (pc4[b & 15] + pc4[b >> 4]) * op_r
        + (pc4[c & 15] + pc4[c >> 4]) * sop_q
        + (pc4[d & 15] + pc4[d >> 4]) * op_q
    )


@micropython.native
def gen_moves(gm, ind, pos, lvalue, kll, hva, mhva, hmv, eg, op_mode, base_seed, dpth, lbuff=_buff):
    """A state of a chess game contains:
    board -- a 64 integer list representation of the board
    ksq_b_w -- the king square black and white
    wc -- the castling rights, [west/queen side, east/king side] as the bits 2 and 3 of a byte
    bc -- the opponent castling rights, [west/king side, east/queen side] as the bits 0 and 1 of the same previous byte
    ep - the en passant square as a square number or 128 if there is no en passant square
    kp - the king passant square as a square number or 128 if there is no king passant square
    score -- the board evaluation in two bytes with an offset of 16384
    """
    # For each of our pieces, iterate through each possible 'ray' of moves,
    # as defined in the 'directions' map. The rays are broken e.g. by
    # captures or immediately in case of pieces such as knights.
    global draw 
    draw = False
    b, ksq, wcek, pscore, _, _ = pos
    if op_mode:
        lpst = pst[0]
    else:
        lpst = pst[eg]
    l = ind
    # unpack packed status
    ep = (wcek >> 8) & 0xFF  # en passant square
    kp = wcek & 0xFF  # king passant square
    cwq = (wcek >> 18) & 2  # our queenside castling right
    cke = (wcek >> 18) & 1  # our kingside castling right
    bk = ksq >> 8
    wk = ksq & 0xFF
    xor = wcek >> 20
    empt = 6 | (xor << 3)
    xor = xor * 7
    bkr, bkf, wkr, wkf = bk >> 3, bk & 7, wk >> 3, wk & 7
    bk_ring = king_ring(bk, lbuff)
    wk_ring = king_ring(wk, lbuff)
    bpi = 0  # black pawn index
    wp_files = [0] * 8  # both pieces and attacks
    bp_files = [0] * 8  # both pieces and attacks
    i = -1
    bshp = [0, 0]
    mob = [0, 0]
    attc = [0, 0]
    att = mob_ex[eg][_ATT]
    krc = mob_ex[eg][_KRC]
    mbt = mob_ex[eg][_MBT]
    sopn = mob_ex[eg][_SOPN]
    opn = mob_ex[eg][_OPN]
    mob_t = mob_ex[eg][0]
    RQ_files = [0, 0, 0, 0]
    P_files = [0, 0]
    draw_material = 0
    for p in b:
        i += 1

        if p == empt:  # Skip empty squares and opponent's pieces
            continue
        bbit = p & 8  # is black piece
        pp = p & 7  # piece type
        if eg == 2:
            draw_material += PVALUES[pp]
        p16 = pp << 4  # piece type times 16 for mobility table
        wb = 1 if bbit else 0  # white or black to index mobility

        fi = i & 7  # calculate file for detecting out of bounds
        t = pp 
        ring = wk_ring if bbit else bk_ring  # squares around enemy king
        if pp == _P:
            r = i >> 3
            P_files[wb] = P_files[wb] | (1 << fi)
            if bbit:
                # for black pawns, evaluate captures and store pawn positions
                dir = BPDIR
                lbuff[bpi] = i
                bpi += 1
                bp_files[fi] = bp_files[fi] | (1 << r)

            else:
                phlx = 0
                ppawn = 0
                if fi > 0:
                    if b[i - 1] == _P:
                        phlx += 1
                        mob[0] += mob_t[_PHLX]-99
                    if b[i + 7] == _P:
                        ppawn += 1
                if fi < 7:
                    if b[i + 9] == _P and not ppawn:
                        ppawn += 1
                # the scan of black pawns above the current white pawn has been performed, so we caculate bonus for non-blocked pawns
                if r < 5 + (eg==2):
                    # passed pawn bonus from rank 3 onwards (7-5 =2 based 0 is rank)
                    # if not any( (bc>>3)<=rr and (bc&7)==f  for lst in (lbuff[24:bci], lbuff[40:bpi]) for bc in lst):
                    if (bp_files[fi]) == 0:
                        # mob[0] += 3 + ( (((4-rr))*max(bkr, abs(f - bkf)))>>(1-eg)) # bonus for non-blocked pawn by enemy pawns or attacks of pawns
                        mxe = max(abs(r - 1 - bkr), abs(fi - bkf))
                        mxo = max(abs(r - 1 - wkr), abs(fi - wkf))
                        mob[0] += (mob_t[_CTPA]-99
                                + (mob_t[_MXEPA]-99) * mxe * (5 - r)
                                + (mob_t[_MXOPA]-99) * mxo * (5 - r)
                                + (mob_t[_RRPA]-99) * (5 - r)
                                + (mob_t[_PHPA]-99) * phlx
                                + (mob_t[_PPPA]-99) * ppawn
                            )  # bonus for non-blocked pawn by enemy pawns or attacks of pawns
                        # bonus for distance to promotion and distance of enemy king to square just in front
                        # the closer the enemy king, the less the bonus
                dir = directions[pp]
                wp_files[fi] = wp_files[fi] | (
                    1 << (i >> 3)
                )  # store the white pawns pieces and attacks
        else:
            dir = directions[pp]
            if pp == _B:
                if bshp[wb] == 1:
                    mob[wb] += mob_t[_BSHP]-99
                bshp[wb] += 1
            elif pp == _R:
                RQ_files[wb] = RQ_files[wb] | (1 << fi)
            elif pp == _Q:
                RQ_files[wb + 2] = RQ_files[wb + 2] | (1 << fi)
        opf = 0
        for dn in range(0, len(dir) - 1, 2):
            df = dir[dn] - 2
            d = dir[dn + 1] - 17
            j = i
            f = fi
            while True:
                j += d
                f += df

                # Stay inside the board
                # equivalent to if c<0 or c>7 or j<0 or j>63:
                if (f & ~7) | (j & ~63):
                    if df == 0:
                        opf += 1
                        if opf == 2:  # ((pp==_R and not eg) or (pp==_Q and eg)):
                            # open files
                            if pp == _R:
                                mob[wb] += mob_t[_OPNR]-99
                            elif pp == _Q:
                                mob[wb] += mob_t[_OPNQ]-99
                    break

                r = j >> 3
                # king safety bonus for attacking the inner ring of the
                # enemy king
                if pp != _P and pp != _K:
                    if j in ring:
                        if j != (wk if bbit else bk):
                            mob[wb] += att[pp - 1]-99 + krc[attc[wb]]-99
                            attc[wb] += 1 if attc[wb] < 3 else 0

                q = b[j]
                # q normalized according to p
                # so friendly is white enemy is black
                qn = q ^ bbit

                if pp == _P and (d == _NO or d == -_NO):
                    # single forward move
                    if q != empt:
                        # non-capture single move up blocked
                        mob[wb] += mbt[96 + qn] - 99
                        break

                if qn < 6:
                    # friendly piece, stop here, but calculate mobility for all
                    # and for pawns if capture move (df!=0).
                    if df or pp != _P:
                        if (
                            df == 0 and qn == _P and (pp == _R or pp == _Q)
                        ):  # ((pp==_R and not eg) or (pp==_Q and eg)):
                            # naive pawns ahead of the rook or queen bonus (pseudo-semi-open)
                            if pp == _R:
                                mob[wb] += mob_t[_SOPNR]-99
                            else:
                                mob[wb] += mob_t[_SOPNQ]-99
                        elif pp == _K and (
                            (wb == 0 and (d > 2 or r < 6))
                            or (wb == 1 and (d < -2 or r > 1))
                        ):
                            # blocking below or next to king  or king not in rank 0-1
                            if qn == _P:
                                # king safety: pawns below king are
                                # less useful than 6
                                mob[wb] += mob_t[_PB]-99
                            elif qn < 5:
                                # other own pieces are also good above so malus for below
                                mob[wb] += mob_t[_OPB]-99
                            # king blocking king is not possible so no need to check
                        else:
                            if p == _P:
                                wp_files[f] = wp_files[f] | (1 << r)
                            elif p == _BP:
                                bp_files[f] = bp_files[f] | (1 << r)
                            mob[wb] += mbt[p16 + qn] - 99

                    break

                # pawn logic (single/double, capture, ep, promotion)
                if p == _P:
                    # White: we calculate the moves

                    if d == _NO + _NO and (
                        i < _A1 + _NO or (b[i + _NO]) != empt or q != empt
                    ):
                        break
                    if df:
                        # capture move, since delta file not zero
                        # store the attacked square for black pawns
                        wp_files[f] = wp_files[f] | (1 << r)
                        if (
                            (q == empt)
                            and j != kp
                            and j != ep
                            and j != kp - 1
                            and j != kp + 1
                        ):
                            break
                        if q != empt:
                            mob[0] += mbt[p16 + qn] - 99

                    # If we move to the last row, we can be anything but a pawn and a king
                    # so we can store the promotion in the move as the upper 2 bits
                    if p == _P and _A8 <= j <= _H8:  # promotion
                        for prom in range(1, 5):  # NBRQ
                            v = value(lpst, i, j, prom, p, q, xor, eg, kp, ep, t)
                            ind = ma(gm, ind, (i << 8) | j | (
                                (prom - 1) << 6), v, lvalue, kll, hva, mhva, hmv, p, q, prom-1, empt, op_mode)
                        break
                elif p == _BP:
                    if df:
                        if q != empt:
                            # capture move
                            mob[1] += mbt[p16 + qn] - 99
                        bp_files[f] = bp_files[f] | (1 << r)
                    # normal mobility is 0 if not blocked
                    # we can break
                    break
                else:
                    # not a pawn, calculate mobility directly
                    mob[wb] += mbt[p16 + qn] - 99

                # Move it if white
                if not bbit:
                    v = value(lpst, i, j, 0, p, q, xor, eg, kp, ep, t)
                    ind = ma(gm, ind, (i << 8) | j, v, lvalue,
                            kll, hva, mhva, hmv, p, q, 4, empt, op_mode)

                # stop crawlers (P,N,K) and after any capture
                if ((qn ^ 0x8) < 6) or pp == _P or pp == _K or pp == _N:
                    break

                # no more calculations for black
                if bbit:
                    continue
                # castling by sliding the rook next to the king
                if i == _A1 and cwq and j < 63 and b[j + _E] == _K:
                    it = j + _E
                    jt = j + _W
                    tt = _K 
                    v = value(lpst, it, jt, 0, _K, 6, xor, eg, kp, ep, tt)
                    ind = ma(gm, ind, (it << 8) | jt, v, lvalue,
                             kll, hva, mhva, hmv, p, q, 4, empt, op_mode)
                    # break since we can't slide beyond the king
                    break
                if i == _H1 and cke and j > 0 and b[j + _W] == _K:
                    it = j + _W
                    jt = j + _E
                    tt = _K 
                    v = value(lpst, it, jt, 0, _K, 6, xor, eg, kp, ep, tt)
                    ind = ma(gm, ind, (it << 8) | jt, v, lvalue,
                             kll, hva, mhva, hmv, p, q, 4, empt, op_mode)
                    # break since we can't slide beyond the king
                    break
    l = ind - l
    if l:
        moves = gm[ind - l : ind]
        moves.sort()
        if base_seed and not op_mode:
            # Slightly randomize ordering between moves with identical scores+bonus
            # to introduce some variation in play without affecting evaluation.
            l = len(moves)
            for k in range(1, min(randint(0, 3) + 1, l)):
                if (moves[-k] >> 14) == (moves[-k - 1] >> 14):
                    moves[-k], moves[-k - 1] = moves[-k - 1], moves[-k]
        gm[ind - l : ind] = moves

    pf2 = 0xFF ^ (P_files[1] | P_files[0])  # neither enemy or own
    # for white
    if RQ_files[0] or RQ_files[2]:
        mob[0] += rq_mobility(RQ_files[0], RQ_files[2], P_files[1], P_files[0], pf2, sopn[0]-99, sopn[1]-99, opn[0]-99, opn[1]-99) # fmt: skip
    # for black
    if RQ_files[1] or RQ_files[3]:
        mob[1] += rq_mobility(RQ_files[1], RQ_files[3], P_files[0], P_files[1], pf2, sopn[0]-99, sopn[1]-99, opn[0]-99, opn[1]-99) # fmt: skip
    for i in lbuff[0:bpi]:
        r = i >> 3
        f = i & 7
        phlx = 0
        ppawn = 0
        if f > 0:
            if b[i - 1] == _BP:
                phlx += 1
                mob[1] += mob_t[_PHLX]-99
            if b[i - 9] == _BP and not ppawn:
                ppawn += 1
        if r > 2 - (eg==2):
            if f < 7:
                if b[i - 7] == _BP:
                    ppawn += 1
            ahead = 0xFF ^ ((1 << r) - 1)
            if (wp_files[f] & ahead) == 0:
                # mob[1] += 3 +((((r-3)) * (max(7-wkr, abs(f - wkf))))>>(1-eg))  # bonus for non blocked pawns
                mxe = max(abs(r + 1 - wkr), abs(f - wkf))
                mxo = max(abs(r + 1 - bkr), abs(f - bkf))
                mob[1] += (
                    (mob_t[_CTPA]-99)
                    + (mob_t[_MXEPA]-99) * mxe * (r - 2)
                    + (mob_t[_MXOPA]-99) * mxo * (r - 2)
                    + (mob_t[_RRPA]-99) * (r - 2)
                    + (mob_t[_PHPA]-99) * phlx
                    + (mob_t[_PPPA]-99) * ppawn
                )  # bonus for non blocked pawns


    # Pawnless late-endgame handling.  Reuse the same 3/3/5/9 material
    # scale as get_phase(): K vs K and K+minor vs K are simple draws.
    if eg == 2 and l and not (P_files[0] | P_files[1]):
        if draw_material <= 3:
            draw = True
            return l

        king_dist14 = (14 - abs(bkr - wkr) - abs(bkf - wkf))
        # Raw value of the last (highest sorted) move.  Value is packed in
        # bits 14..23 with a +512 offset; ordering bonus starts at bit 24
        if pscore > 80:
            mh_d = (
                abs((bkr << 1) - 7)
                + abs((bkf << 1) - 7) - 2
            ) 
            mob[0] += (mh_d * mh_d + king_dist14) >> 3

        elif pscore < -80:
            mh_d = (
                abs((wkr << 1) - 7)
                + abs((wkf << 1) - 7) - 2
            ) 
            mob[1] += (mh_d * mh_d + king_dist14) >> 3

    # Store the mobility in the position list
    pos[4] = mob[0] - mob[1]
    return l