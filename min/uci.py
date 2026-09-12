import os,usunfish_engine as u
from usunfish_engine import render_mv,parse_move
from random import seed
import sys
platform=sys.platform
from usunfish_common import monotonic
try:import micropython;runtime=' - micropython'
except ImportError:
	def const(x):return x
	runtime=' - python'
version='uSunfish 1.4'
year='2026'
_MT_LW=const(12680)
_OP_IND=1 if u.op[0]>>4==0 else 0
_MAX_QS=const(8)
_PAWN=const(22)
LEVEL=7
limit_strength=False
for arg in sys.argv[1:]:
	if arg.startswith('--level='):LEVEL=int(arg.split('=',1)[1]);limit_strength=True
startpos=u.position[:]
startpos[0]=startpos[0][:]
last_startpos_moves=None
last_startpos_count=0
_P=0
_N=1
_B=2
_R=3
_Q=4
_K=5
PIECES='PNBRQK.pnbrqk'
VALUES=[_P,_N,_B,_R,_Q,_K,6,_P|8,_N|8,_B|8,_R|8,_Q|8,_K|8]
ENCODE={A:B for(A,B)in zip(PIECES,VALUES)}
PVALUES=b'\x00\x03\x03\x05\t'
def encode_fen_board(fen_board):
	B=[]
	for A in fen_board:
		if A=='/':continue
		elif A.isdigit():B.extend([6]*int(A))
		else:B.append(ENCODE[A])
	return B
def castle_bits(castling):A=castling;B=('Q'in A)<<1|('K'in A);C=('k'in A)<<1|('q'in A);return B<<2|C
def from_fen(board,color,castling,enpas):
	B=enpas;A=board;A=encode_fen_board(A);D=u.parse(B)if B!='-'else 128;E=castle_bits(castling)<<16|D<<8|128;C=u.get_phase(A);u.eg=C;F=u.recalc_sc(A,C,0);G=A.index(_K|8)<<8|A.index(_K);u.position=[A,G,E,F,0,0]
	if color!='w':u.rotate()
	u.hash_board();return u.position
def cp_pos(position):A=position[:];A[0]=A[0][:];return A
def can_kill_king(position):
	A=position;C,D=A[1:3];u.position=A
	if u.makes_check(C>>8,0,A):return True
	B=D&255
	if B==128:return False
	return any(u.makes_check(B+C,0,A)for C in(-1,0,1))
def perft(depth):
	B=cp_pos(u.position)
	def C(position):u.position=cp_pos(position);u.hash_board()
	def E(position,depth):
		D=depth;B=position
		if can_kill_king(B):return 0
		if D==0:return 1
		F=0;G=cp_pos(B);H=u.g_m()
		for A in H:I=(A>>14)-512;A=A&16383;u.move(A,I,u.position);F+=E(u.position,D-1);C(G)
		return F
	F=0;C(B);G=u.g_m()
	for A in G:
		H=(A>>14)-512;A=A&16383;I=render_mv(A,B[2]>>20);u.move(A,H,u.position);D=E(u.position,depth-1)
		if D:print(f"{I}: {D}");F+=D
		C(B)
	print();print('Nodes searched:',F)
def parse_go(args):
	C=args;B={'wtime':None,'btime':None,'winc':0,'binc':0,'movestogo':None,'depth':None,'nodes':None,'mate':None,'movetime':None,'infinite':False};A=1;E=len(C)
	while A<E:
		D=C[A]
		if D=='infinite':B['infinite']=True;A+=1
		elif D in B.keys():B[D]=int(C[A+1]);A+=2
		else:A+=1
	return B
def send(*A):
	sys.stdout.write(' '.join(str(A)for A in A));sys.stdout.write('\n')
	try:sys.stdout.flush()
	except:pass
def get_turn():return u.position[2]>>20
def reset_pos():
	if own_book:u.op_mode=1
	else:u.op_mode=0
	u.eg=0;u.last_mv=-1;u.ply=0;u.op_ind=_OP_IND;u.max_qs=_MAX_QS;u.history.clear();u.position[:]=hist[-1][:];u.position[0]=hist[-1][0][:];u.history.append(u.position[5])
def startpos_is_extension(new_moves):
	A=new_moves
	if last_startpos_moves is None:return False
	if not last_startpos_moves:return True
	return A==last_startpos_moves or len(A)>len(last_startpos_moves)and A.startswith(last_startpos_moves)and A[len(last_startpos_moves)]==' '
def append_hist():hist.append((u.position[0][:],u.position[1],u.position[2],u.position[3],u.position[4],u.position[5]))
_T_SZS=const(128)
def recalc_tp():u.t_szs=[0]*u.T_SLOTS;u.tp_scoreh=[[0]*_T_SZS for A in range(u.T_SLOTS)];u.tp_scored=[[0]*(_T_SZS*2)for A in range(u.T_SLOTS)];u.max_d_sc=[0]*u.T_SLOTS
def clear_search_state(clear_history=False):
	u.max_qs=_MAX_QS;u.soft_time=None;u.max_time=None;u.max_h_mv[0],u.max_h_mv[1]=0,0
	for A in range(len(u.t_kll)):u.t_kll[A]=0
	for A in range(u.T_SLOTS):u.t_szs[A]=0;u.max_d_sc[A]=0
	if clear_history:u.history.clear()
def reset_game(root,book=True):u.position[:]=root[:];u.position[0]=root[0][:];u.op_mode=1 if book else 0;u.op_ind=_OP_IND;u.last_mv=-1;u.ply=0;u.eg=0;u.hash_board();u.history.clear();u.history.append(u.position[5]);clear_search_state()
def reset_new_game():global hist,last_startpos_moves,last_startpos_count;last_startpos_moves=None;last_startpos_count=0;reset_game(startpos,own_book);hist=[cp_pos(u.position)]
def send_info(depth,score,move_code):global best_move;best_move=render_mv(move_code,wc_bc_ep_kp>>20);A=max(1,monotonic()-start);B=sum(u.t_szs)*1000//(u.T_SLOTS*_T_SZS);send('info depth',depth,'score cp',score*100//_PAWN,'nodes',u.nodes,'nps',u.nodes*1000//A,'hashfull',B,'pv',best_move)
_BENCH_SEED=const(0)
_BENCH1_NODES=const(64000)
_BENCH2_DEPTH=const(8)
def prepare_bench():
	global hist
	if u.ply==0:hist=[startpos];reset_pos()
	u.position[:]=hist[-1][:];u.position[0]=hist[-1][0][:];seed(_BENCH_SEED);u.BASE_SEED=_BENCH_SEED;u.op_mode=0;u.hash_board();clear_search_state(True)
def run_bench1():
	global start,best_move,wc_bc_ep_kp;prepare_bench();start=monotonic();best_move=0;A=0;D=u.position[3];wc_bc_ep_kp=u.position[2];u.max_nodes=_BENCH1_NODES;G=u.g_mv();E=[A&16383 for A in G];B=0
	for(B,H,C,F)in u.search(G):
		if C>=H and F:A=F;D=C;send_info(B,C,F)
		if u.nodes>_BENCH1_NODES and D>0 or C==_MT_LW and B>=7 or 10*u.nodes>15*_BENCH1_NODES:break
	if A==0 or A not in E:
		if E:A=E[-1]
	send_info(B,D,A);send('bestmove',render_mv(A,wc_bc_ep_kp>>20)if A&16191 else'(none)');print('Bench1 time:',(monotonic()-start)/1000)
def run_bench2(target_depth):
	B=target_depth;global start,best_move,wc_bc_ep_kp
	if B<1 or B>20:send('info string bench2 depth must be between 1 and',20);return
	prepare_bench();start=monotonic();best_move=0;A=0;G=u.position[3];wc_bc_ep_kp=u.position[2];u.max_nodes=100000000;u.max_time=None;u.soft_time=None;H=u.g_mv();C=[A&16383 for A in H];D=0;I=monotonic()
	for(D,J,E,F)in u.search(H,B):
		if E>=J and F:A=F;G=E;send_info(D,E,F);print(monotonic()-I);I=monotonic()
	if A==0 or A not in C:
		if C:A=C[-1]
	send_info(D,G,A);send('bestmove',render_mv(A,wc_bc_ep_kp>>20)if A&16191 else'(none)');print('Bench2 time:',(monotonic()-start)/1000)
if platform in('win32','linux'):u.T_SLOTS=256;recalc_tp()
if hasattr(sys,'pypy_version_info'):u.T_SLOTS=2048;runtime=' - pypy';recalc_tp()
own_book=True
reset_new_game()
while True:
	line=sys.stdin.readline()
	if not line:break
	line=line.strip()
	if not line:continue
	args=line.split()
	if args[0]=='uci':send('id name',version+f" ({platform}{runtime})");send('id author',f"fizban99 ({year})");send(f"option name Skill Level type spin default {LEVEL} min 0 max 7");send(f"option name OwnBook type check default {str(own_book).lower()}");send(f"option name UCI_LimitStrength type check default {str(limit_strength).lower()}");send(f"option name Hash Slots type combo default {u.T_SLOTS} var 2 var 4 var 8 var 16 var 32 var 64 var 128 var 256 var 512"+(' var 1024 var 2048'if hasattr(sys,'pypy_version_info')else''));send('uciok')
	elif args[0]=='isready':send('readyok')
	elif args[0]=='quit':break
	elif args[0]=='ucinewgame':reset_new_game()
	elif args[0:5]==['setoption','name','Skill','Level','value']:LEVEL=int(args[5])
	elif args[0:4]==['setoption','name','OwnBook','value']:own_book=True if args[4].lower()=='true'else False;last_startpos_moves=None;last_startpos_count=0
	elif args[0:4]==['setoption','name','UCI_LimitStrength','value']:limit_strength=True if args[4].lower()=='true'else False
	elif args[0:5]==['setoption','name','Hash','Slots','value']:
		s=int(args[5])
		if 2<=s<=(2048 if hasattr(sys,'pypy_version_info')else 512)and s&s-1==0:u.T_SLOTS=s;recalc_tp()
	elif args[:2]==['position','startpos']:
		move_start=3 if len(args)>2 and args[2]=='moves'else len(args);move_count=len(args)-move_start;new_startpos_moves=' '.join(args[move_start:])
		if startpos_is_extension(new_startpos_moves)and move_count>=last_startpos_count:
			u.position[:]=hist[-1][:];u.position[0]=hist[-1][0][:]
			for i in range(last_startpos_count,move_count):mv=args[move_start+i];move_code=parse_move(mv,1-(u.position[2]>>20));u.mk_mv(move_code);append_hist()
		else:
			hist=[startpos];reset_pos()
			for i in range(move_count):mv=args[move_start+i];move_code=parse_move(mv,1-(u.position[2]>>20));u.mk_mv(move_code);append_hist()
		last_startpos_moves=new_startpos_moves;last_startpos_count=move_count
	elif args[:2]==['position','fen']:
		last_startpos_moves=None;last_startpos_count=0;u.op_mode=0;u.eg=0;u.max_qs=_MAX_QS;u.max_h_mv=[0,0];u.position=from_fen(*args[2:6]);u.ply=1
		if u.position[2]>>20==0:hist=[cp_pos(u.position)]
		else:old_pos=cp_pos(u.position);u.rotate();hist=[cp_pos(u.position),old_pos];u.position=cp_pos(old_pos)
	elif args[:2]==['go','perft']:perft(int(args[2]))
	elif args[0]=='bench1':run_bench1();sys.exit()
	elif args[0]=='bench2':depth=int(args[1])if len(args)>1 else _BENCH2_DEPTH;run_bench2(depth);sys.exit()
	elif args[0]=='go':
		if u.ply==0:hist=[startpos];reset_pos()
		state=parse_go(args);start=monotonic();move_str=None;best_move=0;best_move_code=0;board,ksq,wc_bc_ep_kp,pscore,mob,h=hist[-1];turn='b'if wc_bc_ep_kp>>20 else'w';board=board[:];gmv=u.g_mv();gm=[A&16383 for A in gmv];lvl=LEVEL if limit_strength else 100;lvl=int(lvl)-1;best=0;u.position[:]=hist[-1][:];u.max_nodes=125 if lvl<0 else 125*(1<<lvl)if limit_strength else 1<<29
		if len(gmv)==1:best_move_code=gmv[0]&16383;best_move=render_mv(best_move_code,wc_bc_ep_kp>>20);send('bestmove',best_move);continue
		u.soft_time=None;time_left=state[f"{turn}time"]
		if time_left is None:time_left=state['movetime']or 30000;max_time=start+time_left;u.max_time=start+time_left
		elif time_left is None or state['infinite']:u.max_time=None
		else:
			mtg=state['movestogo']
			if not mtg:
				if time_left<10000:mtg=10
				elif u.eg:mtg=40-12*u.eg
				elif u.ply<20:mtg=50
				else:mtg=40
			inc=min(time_left//mtg+state[f"{turn}inc"]*8//10,time_left//4);max_time=start+inc*4//5;u.max_time=start+inc*3//2;u.soft_time=u.max_time
		curr_score=u.position[3];depth=0
		for(depth,gamma,score,mv)in u.search(gmv):
			if score>=gamma and mv:best_move_code=mv;send_info(depth,score,mv);curr_score=score
			if lvl==-1 and(best_move_code or u.nodes>125)or lvl>-1 and u.nodes>u.max_nodes and curr_score>0 or score==_MT_LW and depth>=7 or u.max_time and monotonic()-max_time>0:break
		u.soft_time=None
		if best_move_code==0 or best_move_code not in gm:
			if gm:gm=[A&16383 for A in gmv];best_move_code=gm[-1]
		send_info(depth,curr_score,best_move_code);send('bestmove',render_mv(best_move_code,wc_bc_ep_kp>>20)if best_move_code&16191 else'(none)')