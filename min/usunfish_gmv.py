from usunfish_common import*
from random import randint
_A1=const(56)
_H1=const(63)
_A8=const(0)
_H8=const(7)
_NO=const(-8)
_E=const(1)
_S=const(8)
_W=const(-1)
_P=const(0)
_N=const(1)
_B=const(2)
_R=const(3)
_Q=const(4)
_K=const(5)
_BP=const(8)
_PHLX=const(0)
_CTPA=const(1)
_MXEPA=const(2)
_MXOPA=const(3)
_RRPA=const(4)
_PHPA=const(5)
_PPPA=const(6)
_BSHP=const(7)
_OPNR=const(8)
_OPNQ=const(9)
_SOPNR=const(10)
_SOPNQ=const(11)
_PB=const(12)
_OPB=const(13)
_ATT=const(1)
_KRC=const(2)
_MBT=const(3)
_SOPN=const(4)
_OPN=const(5)
_QS=16
_MAX_OP_D=const(11)
_buff=[0]*9
def parse_sibl(c_ind,d,op):
	def op_get(i,op):
		if i>>1>=len(op):return 0
		return op[i>>1]>>(i&1^1)*4&15
	if d>_MAX_OP_D:return[],c_ind
	sibl=[];n_sibl=op_get(c_ind,op)
	if n_sibl==14 and op_get(c_ind+1,op)<4:n_sibl=op_get(c_ind+1,op)+2;c_ind+=2
	elif n_sibl==15:n_sibl=0;c_ind+=1
	elif n_sibl==14 and op_get(c_ind+1,op)==14 and c_ind==0:n_sibl=16;c_ind+=2
	else:n_sibl=1
	for _ in range(n_sibl):
		node=op_get(c_ind,op)
		if node==14 and op_get(c_ind+1,op)>3:node=node+op_get(c_ind+1,op)-4;c_ind+=1
		c_ind+=1;sibl.append((node,c_ind));_,c_ind=parse_sibl(c_ind,d+1,op)
	return sibl,c_ind
@micropython.native
def makes_check(ksq,bbit,position):
	b=position[0];wc_bc_ep_kp=position[2];rk=ksq>>3;fk=ksq&7;P=_P|bbit;N=_N|bbit;B=_B|bbit;R=_R|bbit;Q=_Q|bbit;K=_K|bbit;p0=b[ksq]
	if p0==N or p0==K or p0==R or p0==B or p0==P:return True
	r=rk+1 if not bbit else rk-1
	if 0<=r<8:
		i=r*8;c=fk-1
		if not c&~7 and b[i+c]==P:return True
		c=fk+1
		if not c&~7 and b[i+c]==P:return True
	empt=6|wc_bc_ep_kp>>20<<3
	for p in(N,K,R,B):
		dir=directions[p&7]
		for dn in range(0,len(dir)-1,2):
			dc,d=dir[dn]-2,dir[dn+1]-17;c=fk;j=ksq
			while True:
				j+=d;c+=dc
				if c&~7|j&~63:break
				q=b[j]
				if p==N or p==K:
					if q==p:return True
					break
				if q==empt:continue
				if q==p or q==Q:return True
				break
	return False
@micropython.native
def ma(moves,ind,mv,val,lvalue,kll,h_va,max_h_mv,h_mv,p,q,prom,empt):
	if lvalue>=_QS and prom<3:return ind
	if p==_P and prom<3:order=0
	elif q!=empt or prom==3:
		if p==_P and prom==3:q=4
		order=((q&7)<<2)+(47-p)
	elif kll and mv in kll:
		if mv==kll[0]:order=42
		else:order=41
	elif val>=_QS:order=40
	elif max_h_mv:
		i=get_index(mv,h_mv,0,max_h_mv)
		if i>=0:order=h_va[i]
		else:order=0
	else:order=0
	if ind<len(moves)and(val>=lvalue or order>40):moves[ind]=mv|val+512<<14|order<<24;ind+=1
	return ind
@micropython.native
def value(lpst,i,j,prom,p0,q,xor,eg,kp,ep,p):
	score=lpst[p][j^xor]-lpst[p][i^xor]
	if 8<=q<14:ind=j^63;q1=q&7;score+=lpst[q1][ind^xor^7]
	if abs(j-kp)<2:ind=j^63;score+=lpst[p][ind^xor^7]+14975
	if p0==_K and abs(i-j)==2:r_from=_A1 if j<i else _H1;p1=_R;score+=lpst[p1][i+j>>1^xor]-lpst[p1][r_from^xor]
	elif p0==_P:
		if j==ep:score+=lpst[p][j+_S^56^xor]
		elif _A8<=j<=_H8:prom=prom;score+=lpst[prom][j^xor]
	return score
@micropython.native
def king_ring(k,buff):
	r,f=k>>3,k&7;i=0
	for dr in b'\x00\x01\x02':
		rr=r+dr-1
		if 0<=rr<=7:
			base=rr<<3
			for df in b'\x00\x01\x02':
				ff=f+df-1
				if 0<=ff<=7:buff[i]=base+ff;i+=1
	return buff[:i]
@micropython.native
def rq_mobility(r_file,q_file,enemy_pawns,own_pawns,pf2,sop_r,sop_q,op_r,op_q,pc4=PC4):pf1=enemy_pawns&(255^own_pawns);a=r_file&pf1;b=r_file&pf2;c=q_file&pf1;d=q_file&pf2;return(pc4[a&15]+pc4[a>>4])*sop_r+(pc4[b&15]+pc4[b>>4])*op_r+(pc4[c&15]+pc4[c>>4])*sop_q+(pc4[d&15]+pc4[d>>4])*op_q
@micropython.native
def gen_moves(gm,ind,pos,lvalue,kll,hva,mhva,hmv,eg,op_mode,base_seed,dpth,lbuff=_buff):
	b,ksq,wcek,_,_,_=pos
	if op_mode:lpst=pst[0]
	else:lpst=pst[eg]
	l=ind;ep=wcek>>8&255;kp=wcek&255;cwq=wcek>>18&2;cke=wcek>>18&1;bk=ksq>>8;wk=ksq&255;xor=wcek>>20;empt=6|xor<<3;xor=xor*7;bkr,bkf,wkr,wkf=bk>>3,bk&7,wk>>3,wk&7;bk_ring=king_ring(bk,lbuff);wk_ring=king_ring(wk,lbuff);bpi=0;wp_files=[0]*8;bp_files=[0]*8;i=-1;bshp=[0,0];mob=[0,0];attc=[0,0];att=mob_ex[eg][_ATT];krc=mob_ex[eg][_KRC];mbt=mob_ex[eg][_MBT];sopn=mob_ex[eg][_SOPN];opn=mob_ex[eg][_OPN];mob_t=mob_ex[eg][0];RQ_files=[0,0,0,0];P_files=[0,0]
	for p in b:
		i+=1
		if p==empt:continue
		bbit=p&8;pp=p&7;p16=pp<<4;wb=1 if bbit else 0;fi=i&7;t=pp;ring=wk_ring if bbit else bk_ring
		if pp==_P:
			r=i>>3;P_files[wb]=P_files[wb]|1<<fi
			if bbit:dir=BPDIR;lbuff[bpi]=i;bpi+=1;bp_files[fi]=bp_files[fi]|1<<r
			else:
				phlx=0;ppawn=0
				if fi>0:
					if b[i-1]==_P:phlx+=1;mob[0]+=mob_t[_PHLX]-99
					if b[i+7]==_P:ppawn+=1
				if fi<7:
					if b[i+9]==_P and not ppawn:ppawn+=1
				if r<5:
					if bp_files[fi]==0:mxe=max(abs(r-1-bkr),abs(fi-bkf));mxo=max(abs(r-1-wkr),abs(fi-wkf));mob[0]+=mob_t[_CTPA]-99+(mob_t[_MXEPA]-99)*mxe*(5-r)+(mob_t[_MXOPA]-99)*mxo*(5-r)+(mob_t[_RRPA]-99)*(5-r)+(mob_t[_PHPA]-99)*phlx+(mob_t[_PPPA]-99)*ppawn
				dir=directions[pp];wp_files[fi]=wp_files[fi]|1<<(i>>3)
		else:
			dir=directions[pp]
			if pp==_B:
				if bshp[wb]==1:mob[wb]+=mob_t[_BSHP]-99
				bshp[wb]+=1
			elif pp==_R:RQ_files[wb]=RQ_files[wb]|1<<fi
			elif pp==_Q:RQ_files[wb+2]=RQ_files[wb+2]|1<<fi
		opf=0
		for dn in range(0,len(dir)-1,2):
			df=dir[dn]-2;d=dir[dn+1]-17;j=i;f=fi
			while True:
				j+=d;f+=df
				if f&~7|j&~63:
					if df==0:
						opf+=1
						if opf==2:
							if pp==_R:mob[wb]+=mob_t[_OPNR]-99
							elif pp==_Q:mob[wb]+=mob_t[_OPNQ]-99
					break
				r=j>>3
				if pp!=_P and pp!=_K:
					if j in ring:
						if j!=(wk if bbit else bk):mob[wb]+=att[pp-1]-99+krc[attc[wb]]-99;attc[wb]+=1 if attc[wb]<3 else 0
				q=b[j];qn=q^bbit
				if pp==_P and(d==_NO or d==-_NO):
					if q!=empt:mob[wb]+=mbt[96+qn]-99;break
				if qn<6:
					if df or pp!=_P:
						if df==0 and qn==_P and(pp==_R or pp==_Q):
							if pp==_R:mob[wb]+=mob_t[_SOPNR]-99
							else:mob[wb]+=mob_t[_SOPNQ]-99
						elif pp==_K and(wb==0 and(d>2 or r<6)or wb==1 and(d<-2 or r>1)):
							if qn==_P:mob[wb]+=mob_t[_PB]-99
							elif qn<5:mob[wb]+=mob_t[_OPB]-99
						else:
							if p==_P:wp_files[f]=wp_files[f]|1<<r
							elif p==_BP:bp_files[f]=bp_files[f]|1<<r
							mob[wb]+=mbt[p16+qn]-99
					break
				if p==_P:
					if d==_NO+_NO and(i<_A1+_NO or b[i+_NO]!=empt or q!=empt):break
					if df:
						wp_files[f]=wp_files[f]|1<<r
						if q==empt and j!=kp and j!=ep and j!=kp-1 and j!=kp+1:break
						if q!=empt:mob[0]+=mbt[p16+qn]-99
					if p==_P and _A8<=j<=_H8:
						for prom in range(1,5):v=value(lpst,i,j,prom,p,q,xor,eg,kp,ep,t);ind=ma(gm,ind,i<<8|j|prom-1<<6,v,lvalue,kll,hva,mhva,hmv,p,q,prom-1,empt)
						break
				elif p==_BP:
					if df:
						if q!=empt:mob[1]+=mbt[p16+qn]-99
						bp_files[f]=bp_files[f]|1<<r
					break
				else:mob[wb]+=mbt[p16+qn]-99
				if not bbit:v=value(lpst,i,j,0,p,q,xor,eg,kp,ep,t);ind=ma(gm,ind,i<<8|j,v,lvalue,kll,hva,mhva,hmv,p,q,4,empt)
				if qn^8<6 or pp==_P or pp==_K or pp==_N:break
				if bbit:continue
				if i==_A1 and cwq and j<63 and b[j+_E]==_K:it=j+_E;jt=j+_W;tt=_K;v=value(lpst,it,jt,0,_K,6,xor,eg,kp,ep,tt);ind=ma(gm,ind,it<<8|jt,v,lvalue,kll,hva,mhva,hmv,p,q,4,empt);break
				if i==_H1 and cke and j>0 and b[j+_W]==_K:it=j+_W;jt=j+_E;tt=_K;v=value(lpst,it,jt,0,_K,6,xor,eg,kp,ep,tt);ind=ma(gm,ind,it<<8|jt,v,lvalue,kll,hva,mhva,hmv,p,q,4,empt);break
	l=ind-l
	if l:
		moves=gm[ind-l:ind];moves.sort()
		if base_seed and not op_mode:
			l=len(moves)
			for k in range(1,min(randint(0,3)+1,l)):
				if moves[-k]>>14==moves[-k-1]>>14:moves[-k],moves[-k-1]=moves[-k-1],moves[-k]
		gm[ind-l:ind]=moves
	pf2=255^(P_files[1]|P_files[0])
	if RQ_files[0]or RQ_files[2]:mob[0]+=rq_mobility(RQ_files[0],RQ_files[2],P_files[1],P_files[0],pf2,sopn[0]-99,sopn[1]-99,opn[0]-99,opn[1]-99)
	if RQ_files[1]or RQ_files[3]:mob[1]+=rq_mobility(RQ_files[1],RQ_files[3],P_files[0],P_files[1],pf2,sopn[0]-99,sopn[1]-99,opn[0]-99,opn[1]-99)
	for i in lbuff[0:bpi]:
		r=i>>3;f=i&7;phlx=0;ppawn=0
		if f>0:
			if b[i-1]==_BP:phlx+=1;mob[1]+=mob_t[_PHLX]-99
			if b[i-9]==_BP and not ppawn:ppawn+=1
		if r>2:
			if f<7:
				if b[i-7]==_BP:ppawn+=1
			ahead=255^(1<<r)-1
			if wp_files[f]&ahead==0:mxe=max(abs(r+1-wkr),abs(f-wkf));mxo=max(abs(r+1-bkr),abs(f-bkf));mob[1]+=mob_t[_CTPA]-99+(mob_t[_MXEPA]-99)*mxe*(r-2)+(mob_t[_MXOPA]-99)*mxo*(r-2)+(mob_t[_RRPA]-99)*(r-2)+(mob_t[_PHPA]-99)*phlx+(mob_t[_PPPA]-99)*ppawn
	pos[4]=mob[0]-mob[1];return l