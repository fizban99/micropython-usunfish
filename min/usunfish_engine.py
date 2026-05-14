from random import randint,seed
from binascii import crc32
from usunfish_common import monotonic
try:import micropython
except ImportError:
	class _MicroPythonFallback:
		@staticmethod
		def native(func):return func
	micropython=_MicroPythonFallback()
	def const(x):return x
seed(monotonic())
import gc
from usunfish_common import*
import usunfish_gmv
from usunfish_gmv import parse_sibl,makes_check,gen_moves,value
import usunfish_gmv as ugmv
gc.collect()
BASE_SEED=randint(0,1073741823)
_OP_IND2=const(0)
_OP_IND=const(1)
_MAX_HIST=const(10)
gm_buf=[0]*800
history=list()
_A1=const(56)
_H1=const(63)
_A8=const(0)
_H8=const(7)
_NO=const(-8)
_S=const(8)
_P=const(0)
_R=const(3)
_K=const(5)
_BP=const(8)
_MT_LW=const(12680)
_MT_UP=const(16383)
_CANCEL=const(16384)
_NCANCEL=const(0)
_QS=const(16)
_QS_A=const(37)
_FUT=const(10)
_EVAL_ROUGHNESS=const(4)
_MAX_DEPTH=const(15)
_MAX_QS=const(8)
PVALUES=b'\x00\x03\x03\x05\t'
max_qs=_MAX_QS
max_nodes=8000
max_time=None
t_kll=[0]*_MAX_DEPTH
_T_SZS=const(128)
T_SLOTS=16
t_szs=[0]*T_SLOTS
tp_scoreh=[[0]*_T_SZS for _ in range(T_SLOTS)]
tp_scored=[[0]*(_T_SZS*2)for _ in range(T_SLOTS)]
max_d_sc=[0]*T_SLOTS
nodes=0
op_mode=1
op_ind=_OP_IND
last_mv=-1
ply=0
req_d=0
iter=0
h_mv=[0]*64,[0]*64
h_va=[0]*64,[0]*64
max_h_mv=[0,0]
eg=0
position=[[11,9,10,12,13,10,9,11,8,8,8,8,8,8,8,8,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,0,0,0,0,0,0,0,0,3,1,2,4,5,2,1,3],60|4<<8,1015936,0,0,0]
@micropython.native
def hash_piece(pc,i,base_seed=BASE_SEED):index=pc<<6|i;x=base_seed^index;x^=x>>16;x=x*2146121005;x^=x>>15;x=x*2221713035;x^=x>>16;return x&1073741823
@micropython.native
def norm_wb_ek(wb_ek,turn):
	if turn:ep=wb_ek>>8&255;kp=wb_ek&255;wb_ek=(wb_ek&196608)<<2|(wb_ek&786432)>>2|(ep^63 if ep!=128 else 128)<<8|(kp^63 if kp!=128 else 128)
	return wb_ek&1048575
@micropython.native
def hash_state(wb_ek,turn):return hash_piece(0,norm_wb_ek(wb_ek,turn))
@micropython.native
def hash_state_swap(wb_ek,wb_ek2,turn):
	wb_ek=norm_wb_ek(wb_ek,turn^1);wb_ek2=norm_wb_ek(wb_ek2,turn)
	if wb_ek!=wb_ek2:return hash_piece(0,wb_ek)^hash_piece(0,wb_ek2)
	else:return 0
def hash_board():
	pos=position;board,_,wc_bc_ep_kp,_,_,_=pos;turn=wc_bc_ep_kp>>20;h=hash_state(pos[2],turn)
	if turn:
		for(i,p)in enumerate(board):
			if p&7<6:p^=8;h^=hash_piece(p,63^i)
		h=-h
	else:
		for(i,p)in enumerate(board):
			if p&7<6:h^=hash_piece(p,i)
	pos[5]=h;return h
hash_board()
@micropython.native
def restore(mv,dif):
	pos=position;board,ksq,_,_,_,_=pos;board[mv>>8&255]=dif>>4&15;board[mv&63]=dif&15
	if dif>65535:i=dif>>16&255;board[dif>>8&255]=board[i];board[i]=_R
	elif dif>255:board[dif>>8&255]=_BP
	if board[mv>>8&255]==_K:pos[1]=ksq&65280|mv>>8
@micropython.native
def reverse():
	pos=position;board,ksq,wc_bc_ep_kp,pscore,mob,_=pos
	for i in range(32):board[i],board[63^i]=board[63^i]^8,board[i]^8
	pos[1]=ksq>>8^63|(ksq&255^63)<<8
@micropython.native
def rotate_and_set(score,wc,bc,ep,kp,turn,nullmove,mob):pos=position;reverse();turn=turn^1;pos[3]=-score;pos[2]=turn<<20|bc<<18|wc<<16|(ep^63 if ep!=128 and not nullmove else 128)<<8|(kp^63 if kp!=128 and not nullmove else 128);pos[4]=-mob;pos[5]=-pos[5]
@micropython.native
def rotate(nullmove=False):board,ksq,wc_bc_ep_kp,pscore,mob,_=position;turn=wc_bc_ep_kp>>20;wc=wc_bc_ep_kp>>18&3;bc=wc_bc_ep_kp>>16&3;ep=wc_bc_ep_kp>>8&255;kp=wc_bc_ep_kp&255;rotate_and_set(pscore,wc,bc,ep,kp,turn,nullmove,mob)
@micropython.native
def move(mv,val,pos):
	board,ksq,wc_bc_ep_kp,pscore,mob,h=pos;i,j,prom,turn=mv>>8,mv&63,((mv&255)>>6)+1,wc_bc_ep_kp>>20;xor=turn*7;pxor=turn<<3;p=board[i];h=abs(h)
	if turn:ii,jj,pc=63^i,63^j,p^8
	else:ii,jj,pc=i,j,p
	wc,bc,ep,kp=wc_bc_ep_kp>>18&3,wc_bc_ep_kp>>16&3,wc_bc_ep_kp>>8&255,wc_bc_ep_kp&255;q=board[j]
	if q&7<6:h^=hash_piece(q^pxor,jj)
	pp=p&7;t=pp if not eg or op_mode else pp+6;val=value(pst,i,j,prom,p,q,xor,eg,kp,ep,t)if val is None else val;ep,kp=128,128;score=pscore+val;dif=board[i]<<4|board[j];board[j]=p;board[i]=6|turn<<3;h^=hash_piece(pc,ii);wc=wc&1 if i==_A1 else wc&2 if i==_H1 else wc;bc=bc&2 if j==_A8 else bc&1 if j==_H8 else bc
	if p==_K:
		wc=0;h^=hash_piece(pc,jj)
		if abs(j-i)==2:kp=(i+j)//2;k=_A1 if j<i else _H1;dif=k<<16|kp<<8|dif;board[k]=6|turn<<3;h^=hash_piece(_R^pxor,63^k if turn else k);board[kp]=_R;h^=hash_piece(_R^pxor,63^kp if turn else kp)
		ksq=ksq&65280|j
	elif p==_P:
		if _A8<=j<=_H8:board[j]=prom;h^=hash_piece(prom^pxor,jj)
		else:h^=hash_piece(pc,jj)
		if j-i==2*_NO:ep=i+_NO
		if j==wc_bc_ep_kp>>8&255:board[j+_S]=6|turn<<3;h^=hash_piece(_P^pxor,63^j+_S if turn else j+_S);dif=j+_S<<8|dif
	else:h^=hash_piece(pc,jj)
	pos[1]=ksq;rotate_and_set(score,wc,bc,ep,kp,turn,False,mob);hash_state_swap(wc_bc_ep_kp,pos[2],turn);turn^=1;pos[5]=-h if turn else h;return dif
@micropython.native
def s_sc(tscd,tsch,i,mv,dr,best,h,fh,od):tscd[i<<1]=mv;tscd[(i<<1)+1]=fh|best+16384|dr<<16|od+16<<20|iter<<25;tsch[i]=h
@micropython.native
def s_hmv(h_mv,h_va,mv,max_h_mv,w):
	i=0;i=get_index(mv,h_mv,0,max_h_mv)
	if i<0:
		if max_h_mv<len(h_va):i=max_h_mv;max_h_mv+=1
		else:
			min_i=0;min_v=h_va[0]
			for j in range(1,len(h_va)):
				v=h_va[j]
				if v<min_v:min_v=v;min_i=j
			i=min_i;h_va[i]=0
	h_mv[i]=mv;v=h_va[i]+w;h_va[i]=40 if v>40 else 1 if v<1 else v;return max_h_mv
@micropython.native
def s_entry(tp,mv,d):
	m=tp[d];mv1=m&16383;mv2=m>>16&16383
	if mv!=mv1 and mv!=mv2:tp[d]=mv1<<16|mv
@micropython.native
def s_tp(h,mv,best,dr,val,od,fh,mob,incheck):
	global tp_scoreh,tp_scored,max_d_sc,t_szs;global max_h_mv,max_h_mvm;non_capt=position[0][mv&63]|8==14;turn=position[2]>>20
	if fh:
		if val<=_QS and non_capt and dr<_MAX_DEPTH:s_entry(t_kll,mv,dr)
		if val<=_QS and non_capt:
			if od>0:max_h_mv[turn]=s_hmv(h_mv[turn],h_va[turn],mv,max_h_mv[turn],od*od)
	elif val<=_QS and non_capt:
		if od>0:max_h_mv[turn]=s_hmv(h_mv[turn],h_va[turn],mv,max_h_mv[turn],-od*od)
	e=fh|best+16384|dr<<16|od+16<<20|iter<<25;it=iter;mv=mv|mob+512<<14|incheck>>2<<29;hind=h&T_SLOTS-1;new=False;tszs,tsch,tscd,md=t_szs[hind],tp_scoreh[hind],tp_scored[hind],max_d_sc[hind];i=get_index(h,tsch,0,tszs)
	if i>=0:e2=tscd[(i<<1)+1];sod=(e2>>20&31)-16;sdr=e2>>16&15
	else:
		sod=od;sdr=dr
		if tszs<_T_SZS:i=tszs;t_szs[hind]+=1;max_d_sc[hind]=md if md>dr else dr;new=True
		else:
			i=-1;m_it=it-dr*2
			for j in range(1,_T_SZS<<1,2):
				e2=tscd[j];c_iter=e2>>25;sd=e2>>16&15;fh2=e&32768
				if sd>2 and c_iter-sd*2<=m_it:
					m_it=c_iter-sd*2;i=j-1>>1
					if c_iter<=2:break
			if i==-1:return
			max_d_sc[hind]=md if md>dr else dr;new=True
	if not fh:mv=mv&4294950912
	if od>=sod:
		tscd[i<<1]=mv;tscd[(i<<1)+1]=e
		if new:tsch[i]=h
		elif md<dr:max_d_sc[hind]=dr
@micropython.native
def reset_tp_score():
	global tp_scored
	for hind in range(T_SLOTS):
		for i in range(0,t_szs[hind]<<1,2):
			if(tp_scored[hind][i+1]>>15)-16384!=_MT_LW:tp_scored[hind][i+1]=32768|-_MT_UP+16384
def g_kll(pdpth):
	kll=[0,0];kll0=t_kll[pdpth]if pdpth<_MAX_DEPTH else 0
	if kll0:kll[0]=kll0&16383;kll[1]=kll0>>16
	return kll
@micropython.native
def g_sc(h,dr,od,board):
	global tp_scoreh,tp_scored;hind=h&T_SLOTS-1;tscd=tp_scored[hind]
	if dr>max_d_sc[hind]:return 0,-_MT_UP,32768,0,0
	i=get_index(h,tp_scoreh[hind],0,t_szs[hind])
	if i>=0:e=tscd[(i<<1)+1];tscd[(i<<1)+1]=e&33554431|iter<<25;mv=tscd[i<<1];position[4]=((mv>>14&1023)-512)*4-2;incheck=mv>>29<<2;mv=mv&16383
	else:return 0,-_MT_UP,32768,0,0
	sod=(e>>20&31)-16
	if board[mv>>8]>5 or board[mv&63]<6 or board[mv>>8]==_P and mv>>8<mv&63:return 0,_MT_UP,0,0,0
	if sod<od:return mv,-_MT_UP,32768,-1,incheck
	fh=e&32768;best=(e&32767)-16384;return mv,best,fh,1,incheck
def reset_pos(omv,sc,lwc_bc_ep_kp,dif,omb,h):
	pos=position;pos[3]=sc;pos[2]=lwc_bc_ep_kp;pos[4]=omb;pos[5]=h
	if not omv:return
	reverse();restore(omv,dif)
@micropython.native
def bound(pos,g,od,cn,omv,val,gm,ind,gmv,incheck,pdpth,gm_buf,req_d,max_time):
	global max_qs,nodes;board,ksq,wc_bc_ep_kp,sc,mob,h=pos;mqs=max_qs;lmr=0;osc=sc;omb=mob;oh=h;lwc_bc_ep_kp=wc_bc_ep_kp
	if omv:dif=move(omv,val,pos);board,ksq,wc_bc_ep_kp,sc,mob,h=pos
	else:dif=None
	mob=mob+2>>2;ret=0;best_mv=0;turn=wc_bc_ep_kp>>20
	while True:
		if makes_check(ksq>>8,0,pos):ret,best=1,_MT_UP;break
		kp=wc_bc_ep_kp&255
		if kp!=128:
			for i in range(-1,2):
				if makes_check(kp+i,0,pos):ret,best=1,_MT_UP;break
			if ret:break
		nodes+=1
		if 10*nodes>15*max_nodes or max_time and monotonic()-max_time>0:ret,best=1,_CANCEL;break
		entry=None;hmove,e,fh,match,ret=g_sc(h,pdpth,od,board)
		if fh:
			if e>=g:ret,best,best_mv=1,e,hmove;break
			elif match>0:hbest=e;best=e
		elif e<g:ret,best=1,e;break
		if match:
			if match>0:ohmove=hmove
			mb=(pos[4]+2>>2)-mob+1
		else:mb=1
		d=od if od>0 else 0
		if cn and d>0 and h in history:ret,best=1,0;break
		incheck=incheck>>1
		if match:incheck=ret|incheck
		elif makes_check(ksq&255,8,pos):incheck=incheck|4
		if od<-mqs and not incheck&4:ret,best=1,sc+mb;break
		best=-_MT_UP;ret=0;break
	if not ret:
		while True:
			if not incheck and d>2 and cn and abs(sc)<125 and any(c in board for c in b'\x01\x02\x03\x04'):
				lwc=wc_bc_ep_kp;rotate(True);res=bound(pos,1-g,d-3,False,0,mb,gm,ind,gmv,incheck,pdpth+1,gm_buf,req_d,max_time);rotate();res=-((res&65535)-16384);pos[2]=lwc;best=res if res>best else best
				if res>=g:best_mv=0;break
				if not match:mob=pos[4]+2>>2
			if(incheck&4 or req_d==1)and mqs<2*_MAX_QS:max_qs+=1
			if d==0 and not incheck&4:
				best=sc+mb if sc+mb>best else best
				if sc+mb>=g:best_mv=0;break
			if not hmove and d>2:hmove=bound(pos,g,d-2,False,0,0,gm,ind,gmv,incheck,pdpth,gm_buf,req_d,max_time);hmove=hmove>>16
			val_lower=_QS-(d+(int(incheck>0)<<2))*_QS_A
			if incheck&4:lmr=-1
			if hmove!=0:
				p=board[hmove>>8];t=p&7 if not eg or op_mode else(p&7)+6;val=value(pst,hmove>>8,hmove&63,((hmove&255)>>6)+1,p,board[hmove&63],(wc_bc_ep_kp>>20)*7,eg,kp,wc_bc_ep_kp>>8&255,t)
				if val>=val_lower:
					res=bound(pos,1-g,od-1-lmr,True,hmove,val+mb,gm,ind,None,incheck,pdpth+1,gm_buf,req_d,max_time);res=-((res&65535)-16384);best=res if res>best else best
					if res>=g:best_mv=hmove;break
					if incheck&4 or match>0 and res>hbest+4:match=0
				else:match=0
			else:match=0
			if gmv:gm=[m for m in gmv if((m&16777215)>>14)-512>=val_lower];l=len(gm);gm_buf[:l]=gm;gm=gm_buf
			else:l=gen_moves(gm,ind,pos,val_lower,g_kll(pdpth),h_va[turn],max_h_mv[turn],h_mv[turn],eg,op_mode)
			if omv==0:omb=pos[4];mb=1
			else:mb=(pos[4]+2>>2)-mob+1
			lmax=l
			while l:
				l-=1;mvv=gm[ind+l]&16777215;val=(mvv>>14)-512;best_mv=mvv&16383
				if match>0:
					if ohmove!=best_mv:continue
					else:match=0
				if best_mv==hmove:continue
				res=sc+val+mb
				if od<0 and res+abs(val)<g or od<=-max_qs:best=res if res>best else best;break
				j=best_mv&63;i=best_mv>>8
				if(j>7 or board[i]!=_P)and board[j]&7==6 and(not incheck&4 and d>2 and d<7 and pdpth>2 and res+(abs(val)+_FUT)<g):best=res if res>best else best;break
				if not lmr and not incheck&4 and(lmax-l>4 and d>3 and pdpth>2):lmr=2
				res=bound(pos,1-g,od-1-lmr,True,best_mv,val+mb,gm,ind+l,None,incheck,pdpth+1,gm_buf,req_d,max_time);res=-((res&65535)-16384);best=res if res>best else best
				if best>=g:break
			break
		if best==-_MT_UP:best_mv=0;best=-_MT_LW if incheck&4 else 0
		if best>=g and(od>=-16 and best_mv!=0):s_tp(h,best_mv,best,pdpth,val,od,32768,pos[4]+2>>2,incheck)
		if best<g and not best_mv and fh and hmove and od>=-16:s_tp(h,hmove,best,pdpth,val,od,0,pos[4]+2>>2,incheck)
		max_qs=mqs
	reset_pos(omv,osc,lwc_bc_ep_kp,dif,omb,oh)
	if best==_CANCEL:return _NCANCEL
	return best+16384|best_mv<<16
def mk_mv(mv):
	global last_mv,op_mode,op_ind,ply;ply+=1
	if op_mode==1:
		gm=g_m();gm=[m&16383 for m in gm];gm.reverse();mv=mv&16191;last_mv=gm.index(mv);mvs,_=parse_sibl(op_ind,ply-1,op);i=[i for(i,(mv,_))in enumerate(mvs)if mv==last_mv]
		if i:op_ind=mvs[i[0]][1]
		else:
			op_mode=0
			if ply==1:
				mvs,_=parse_sibl(_OP_IND2,ply-1,op2);i=[i for(i,(mv,_))in enumerate(mvs)if mv==last_mv]
				if i:op_ind=mvs[i[0]][1];op_mode=2
	if len(history)>_MAX_HIST:history.pop(0)
	dif=move(mv,None,position);history.append(position[5]);return dif
def g_next_move(op):
	global op_ind,last_mv,op_mode,ply;i=op_ind;mvs,_=parse_sibl(i,ply,op)
	if not mvs:op_mode=0;return 0
	mv,_=mvs[randint(0,len(mvs)-1)];gm=g_m();mv=gm[-mv-1]&16383;return mv
def search(gmv):
	global nodes,req_d,tp_scored,tp_scoreh,max_d_sc,t_szs,op_ind,iter;global eg,max_qs,req_d,start_time,b_overflow;_,_,_,pscore,_,_=position;nodes=0;usunfish_gmv.b_overflow=0
	if not gmv:gmv=g_mv()
	if op_mode==1:
		last_mv=g_next_move(op)
		if last_mv!=0:yield(0,pscore-4,pscore,last_mv);return
	elif op_mode==2 and ply==1:
		last_mv=g_next_move(op2)
		if last_mv!=0:yield(0,pscore-4,pscore,last_mv);return
	g=0;iter=0
	for req_d in range(1,_MAX_DEPTH+1):
		lower,upper=-_MT_LW,_MT_LW;eval_dist=upper-lower
		while eval_dist>_EVAL_ROUGHNESS+max(0,(req_d-4)*2):
			res=bound(position,g,req_d,False,0,0,gm_buf,0,gmv,0,0,gm_buf,req_d,max_time)
			if res==_NCANCEL:yield(req_d,g,_NCANCEL,0);return
			score,best_mv=(res&65535)-16384,res>>16
			if score>=g:lower=score
			else:upper=score
			eval_dist=upper-lower;yield(req_d,g,score,best_mv);g=(lower+upper+1)//2;iter=(iter+1)%64
def g_m():turn=position[2]>>20;gm=gm_buf;l=gen_moves(gm,0,position,-_MT_LW,0,h_va[turn],max_h_mv[turn],h_mv[turn],eg,op_mode);gm=gm[:l];return gm
@micropython.native
def is_endgame(board):material=sum(PVALUES[p&7]for p in board if p&7<5);pawns=sum(1 for p in board if p&7==0);return material<13 or pawns<8
@micropython.native
def recalc_sc(board,eg):
	score=0
	for(i,c)in enumerate(board):
		piece=c&7
		if piece>=6:continue
		table=piece+6 if eg else piece
		if c&8:score-=pst[table][i^56]
		else:score+=pst[table][i]
	return score
@micropython.native
def g_mv():
	global max_qs,eg,pst;global t_szs,max_d_sc;global max_h_mv;pos=position;lbrd,_,wc_bc_ep_kp,pscore,_,_=pos;turn=wc_bc_ep_kp>>20
	if not eg and is_endgame(lbrd):max_qs=_MAX_QS+1;eg=1;xor=(wc_bc_ep_kp>>20)*7;pos[3]=recalc_sc(lbrd,eg)
	ts=[0]*T_SLOTS;d=0
	if ply<2:
		max_h_mv[0],max_h_mv[1]=0,0
		for i in range(_MAX_DEPTH):t_kll[i]=0
		gm=g_m();gm=[m for m in gm if not can_kill_king(m&16383)]
	else:
		t_kll[:-2]=t_kll[2:];t_kll[-2:]=[0,0];lwc_bc_ep_kp=wc_bc_ep_kp;nullmove=True
		for _ in range(2):
			rotate(nullmove);nullmove=False;turn=turn^1;gm=g_m();gm=[m for m in gm if not can_kill_king(m&16383)];gmm={m&16383 for m in gm};i=0
			for j in range(max_h_mv[turn]):
				mv=h_mv[turn][j]
				if mv in gmm:
					v=h_va[turn][j]>>2
					if v>0:h_mv[turn][i]=mv;h_va[turn][i]=v;i+=1
			max_h_mv[turn]=i
		pos[2]=lwc_bc_ep_kp;d=recalc_tp(0,ts)
	max_d_sc=[d]*T_SLOTS;t_szs=ts;return gm
def recalc_tp(d,ts):
	_,_,wc_bc_ep_kp,pscore,mob,h=position;hind=h&T_SLOTS-1;tscd,tsch=tp_scored[hind],tp_scoreh[hind]
	try:i=tsch.index(h,ts[hind],t_szs[hind])
	except ValueError:return d
	e=tscd[(i<<1)+1];mv=tscd[i<<1]&16383;sod=(e>>20&31)-16
	if mv:j=ts[hind];tsch[j]=h;tscd[j<<1]=tscd[i<<1];tscd[(j<<1)+1]=e&4293984255|d<<16;ts[hind]+=1;lwc_bc_ep_kp=wc_bc_ep_kp;tsch[i]=0;dif=move(mv,0,position);d=recalc_tp(d+1,ts);reset_pos(mv,pscore,lwc_bc_ep_kp,dif,mob,h);return d
	else:return d
def can_kill_king(mv,ccheck=True):
	pos=position;lbrd,ksq,wc_bc_ep_kp,pscore,mob,h=pos;res=False;by_black=0;sc=pscore;lwc_bc_ep_kp=wc_bc_ep_kp
	if mv!=0:dif=move(mv,None,pos)
	else:by_black=8
	lbrd,ksq,wc_bc_ep_kp,pscore,_,_=position
	if by_black:king=ksq&255
	else:king=ksq>>8
	if makes_check(king,by_black,pos):res=True
	elif ccheck and mv:
		kp=wc_bc_ep_kp&255
		if kp!=128:
			for i in(-1,0,1):
				if makes_check(kp+i,by_black,pos):res=True;break
	if mv>0:reset_pos(mv,sc,lwc_bc_ep_kp,dif,mob,h)
	return res
def render(i):rank,fil=divmod(i-_A1,8);return chr(fil+ord('a'))+str(-rank+1)
def parse(c):fil,rank=ord(c[0])-ord('a'),int(c[1])-1;return _A1+fil-8*rank
def parse_move(move_str,white_pov):
	mapping='NBRQ';i,j,prom=parse(move_str[:2]),parse(move_str[2:4]),move_str[4:].upper()
	if not white_pov:i,j=63^i,63^j
	mv=i<<8|j|mapping.index(prom)<<6;return mv
def render_mv(mv,turn=0):
	if mv==0:return'(none)'
	i,j=mv>>8,mv&63;prom=''
	if j<8 and position[0][i]|8==_P+8:prom=mapping[(mv>>6&3)+1].lower()
	if turn==1:i,j=63^i,63^j
	return render(i)+render(j)+prom
mapping='PNBRQK. pnbrqk. '