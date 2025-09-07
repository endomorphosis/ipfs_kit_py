from pathlib import Path

def scan(file, start, end):
    lines = Path(file).read_text(encoding='utf-8', errors='ignore').splitlines()
    code = '\n'.join(lines[start-1:end])
    i=0; n=len(code)
    mode='code'; esc=False
    tpl_expr_stack=[]
    line=start; col=0
    def adv(ch):
        nonlocal line,col
        if ch=='\n': line+=1; col=0
        else: col+=1
    while i<n:
        ch=code[i]; nxt= code[i+1] if i+1<n else ''
        if ch=='\n': adv('\n'); i+=1; continue
        if mode=='code':
            if ch=='"': mode='dbl'; adv(ch); i+=1; continue
            if ch=="'": mode='sgl'; adv(ch); i+=1; continue
            if ch=='`': mode='tpl'; adv(ch); i+=1; continue
            if ch=='/' and nxt=='/':
                # skip line comment
                while i<n and code[i]!='\n': i+=1
                continue
            if ch=='/' and nxt=='*':
                i+=2; adv('/'); adv('*')
                while i<n-1 and not (code[i]=='*' and code[i+1]=='/'):
                    adv(code[i]); i+=1
                if i<n-1:
                    i+=2; adv('*'); adv('/')
                continue
            adv(ch); i+=1; continue
        elif mode in ('dbl','sgl'):
            adv(ch)
            if esc:
                esc=False
            elif ch=='\\':
                esc=True
            elif (mode=='dbl' and ch=='"') or (mode=='sgl' and ch=="'"):
                mode='code'
            i+=1; continue
        elif mode=='tpl':
            # within template literal; track ${...}
            if esc:
                esc=False; adv(ch); i+=1; continue
            if ch=='\\':
                esc=True; adv(ch); i+=1; continue
            if ch=='`':
                if tpl_expr_stack:
                    return {'error':'EOF in ${...} before closing template backtick', 'line': line, 'col': col}
                mode='code'; adv(ch); i+=1; continue
            if ch=='$' and nxt=='{':
                tpl_expr_stack.append((line,col))
                adv(ch); i+=1; adv('{'); i+=1; continue
            if ch=='}' and tpl_expr_stack:
                tpl_expr_stack.pop(); adv(ch); i+=1; continue
            # normal char
            adv(ch); i+=1; continue
    if mode=='tpl':
        return {'error':'Unterminated template literal', 'line': line, 'col': col}
    if tpl_expr_stack:
        l,c=tpl_expr_stack[-1]
        return {'error':'Unclosed ${ expression', 'line': l, 'col': c}
    return {'ok': True}

if __name__=='__main__':
    import sys, json
    file = sys.argv[1]; start=int(sys.argv[2]); end=int(sys.argv[3])
    print(json.dumps(scan(file,start,end)))
