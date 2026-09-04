from pathlib import Path
import sys, os

sys.path.append(str(Path(__file__).resolve().parent.parent))

import chess.pgn
import usunfish_engine as usunfish
from usunfish_engine import g_m, rotate, value, parse, move, position


MAX_OP_D = 11
MAX_VARIATIONS = 7
max_children = 0
tree = {}
exceeds_variations  = 0
prev_variations = 0
for book in ["SuperGM_4mvs.pgn", "400Book.pgn" ]:
    openings = []
    openings2 = []
    moves = []
    moves2 = []    
    print(f"######### {book} #########")
    initial = position[0][:]
    with open(Path(__file__).resolve().parent / book) as pgn_file:
        while True:
            # Read the next game from the PGN file
            game = chess.pgn.read_game(pgn_file)
            usunfish.position = [
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
            if game is None:
                break  # No more games in the file
            #iterate through the games
            moves = []
            moves2 = []
            for i, mv in enumerate(game.mainline_moves()):
                if i >MAX_OP_D:
                    break

                if book == "400Book.pgn" and mv.uci().lower() in ("c2c4", "d2d4", "e2e4","g1f3", "f2f4","g2g3","b2b3","b1c3"):
                     continue
                gmoves = [(mv>>14, mv&0x3FFF) for mv in g_m()]
                if i % 2 == 0:
                    gmoves =  [(v, (m.to_bytes(2,"big")[0], m.to_bytes(2,"big")[1])) for v,m in gmoves]
                else:
                    gmoves = [(v, (63-m.to_bytes(2,"big")[0], 63-m.to_bytes(2,"big")[1])) for v,m in gmoves]
                gmoves_orig = [m for v, m in gmoves[-len(gmoves):]] 
                gmoves_orig.reverse()
                gmoves = [m for v, m in gmoves[-41:]]  
                # gmoves.reverse()                       
                imv = (parse(mv.uci()[0:2]), parse(mv.uci()[2:4]))
                try:
                    index = len(gmoves)-gmoves.index(imv)-1
                except ValueError:
                    o_ind = gmoves_orig.index(imv)
                    print("Not found",i,mv.uci(), o_ind ) 
                    if o_ind < 26 :
                        pass
                    break
                moves.append(mv.uci())
                moves2.append(index)
                if i % 2 == 0:
                    pos = move((imv[0]<<8)|(imv[1]), None, usunfish.position)
                else:
                    pos = move( (((63-imv[0])<<8)|(63-imv[1])), None, usunfish.position)
            openings.append(moves)
            openings2.append(moves2)
        print(f"Number of openings in {book}: {len(openings)}")          

# build a tree of the openings

        for opening, opening2 in zip(openings, openings2):
            current = tree
            for i, (move1, move2) in enumerate(zip(opening, opening2)):
                if len(opening) ==1:
                    break
                move1 = str(i) + ":" + move1 + "-" + str(move2)
                # limit variations to 4 + 16
                if len(current)< MAX_VARIATIONS or (move1[0]=="0" and len(current)<19):
                    if move1 not in current:
                        current[move1] = {}
                    current = current[move1]
                else:
                    exceeds_variations += 1
                    break
        print(f"Number of initial variations in {book}: {len(tree)-prev_variations}")          
        prev_variations = len(tree)

# Function to print the tree
openings_comp = []
node_num = 0
def print_tree(node, indent=0, f=None):
    global node_num, max_children
    for mv, subtree in node.items():
        node_num +=1
        move_num = int(mv.split("-")[1])
        move_depth = int(mv.split(":")[0])
        if move_num < 14 :
            openings_comp.append(move_num)
        elif move_num < 25:
            openings_comp.append(14)
            openings_comp.append(move_num-14 + 4)
        else:
            openings_comp.append(14)
            openings_comp.append(15)
            openings_comp.append(move_num-14-15 + 4)

        mv = mv + "(" + str(len(subtree)) + ")" if len(subtree) > 1 else mv + "-" if len(subtree) == 0 else mv
        
        if len(subtree) > 1 and move_depth <  MAX_OP_D:
            openings_comp.append(14)
            assert len(subtree) < 20
            if len(subtree) > max_children:
                max_children = len(subtree)
            if len(subtree) < 4:
                openings_comp.append(len(subtree)-2)
            else:
                openings_comp.append(3)
                openings_comp.append(len(subtree)-4)
        elif len(subtree) == 0 and move_depth <  MAX_OP_D:
            openings_comp.append(15)

        print('    ' * indent + mv + ' ' + str(len(openings_comp)), file=f)
        print_tree(subtree, indent+1, f=f)

openings_comp.append(14)
if len(tree) < 4:
    openings_comp.append(len(tree)-2)
else:
    openings_comp.append(3)
    openings_comp.append(len(tree)-4)
with open(f"openings_comp.txt","w") as f:
    print_tree(tree, f=f)
if len(openings_comp) % 2==1:
    openings_comp.insert(0,0)
    op_ind = 1
else:
    op_ind = 0
print(f"Excess of variations: {exceeds_variations}")
# Print the opening tree
print(f"Initial variation length: {len(tree)}")
print("OP_IND = ", op_ind)
print(f"Max plies: {node_num}. Max moves: {node_num // 2}")
print(f"Nibbles: {len(openings_comp)}. Bytes: {len(openings_comp)>>1}")
print(openings_comp)
openings_comp = bytes((openings_comp[i]  << 4) | (openings_comp[i+1] ) for i in range(0,len(openings_comp),2))
print(openings_comp)

                


