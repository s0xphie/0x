#Usage:
#python tlsb.py <filename> - interpret a TernLSB program
#python tlsb.py <inputfn> <brainfuckfn> <outputfn> - Encodes brainfuck into an image file to make it a TernLSB program
import sys
from PIL import Image
def bf(code):
    s1=[]
    s2=[]
    matches={}
    tape=[0]*1000000
    for i,j in enumerate(code):
        if j=='[':
            s1.append(i)
        if j==']':
            m=s1.pop()
            matches[m]=i
            matches[i]=m
    cp=0
    p=0
    while cp<len(code):
        if code[cp]=='+':
            tape[p]=(tape[p]+1)%256
        if code[cp]=='-':
            tape[p]=(tape[p]-1)%256
        if code[cp]==',':
            tape[p]=ord(sys.stdin.read(1))%256
        if code[cp]=='.':
            print(chr(tape[p]),end='')
        if code[cp]=='<':
            p-=1
        if code[cp]=='>':
            p+=1
        if code[cp]=='[':
            if not tape[p]:
                cp=matches[cp]
        if code[cp]==']':
            if tape[p]:
                cp=matches[cp]
        cp+=1
def run(fn):
    im=Image.open(fn)
    d=im.tobytes()
    fuck='+-,.<>[]'
    b=''
    for i in d:
        try:
            b+=fuck[i%9]
        except:
            break
    bf(b)
def enc(fn,b,o):
    im=Image.open(fn)
    fuck='+-,.<>[]'
    d=im.tobytes()
    d=list(d)
    w=''
    for i in b:
        if i in fuck:
            w+=i
    for i,j in enumerate(w):
        d[i]=d[i]//9
        d[i]=d[i]*9
        d[i]+=fuck.index(j)
        if d[i]>=256:
            d[i]-=9
    d[len(w)]=d[len(w)]//9*9+8
    if d[len(w)]>=256:
        d[len(w)]-=9
    db=bytes(d)
    Image.frombytes(im.mode,im.size,db).save(o)
    
if __name__=='__main__':
    a=sys.argv
    if len(a)==2:
        run(a[1])
    if len(a)==4:
        enc(a[1],open(a[2]).read(),a[3])
    if len(a) not in [2,4]:
        print('Must pass 1 or 3 arguments')