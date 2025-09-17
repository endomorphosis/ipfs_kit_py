from pathlib import Path

def scan_js_segment(file, start, end):
    lines = Path(file).read_text(encoding='utf-8', errors='ignore').splitlines()
    code = '\n'.join(lines[start-1:end])
    mode = 'code'  # code, sgl, dbl, tpl, lineC, blockC
    stack = []
    line = start
    col = 0
    i = 0
    n = len(code)
    def pos():
        return line, col
    while i < n:
        ch = code[i]
        if ch == '\n':
            line += 1
            col = 0
            i += 1
            continue
        col += 1
        nxt = code[i+1] if i+1 < n else ''
        if mode == 'code':
            if ch == "'": mode = 'sgl'; i += 1; continue
            if ch == '"': mode = 'dbl'; i += 1; continue
            if ch == '`': mode = 'tpl'; i += 1; continue
            if ch == '/' and nxt == '/': mode = 'lineC'; i += 2; col += 1; continue
            if ch == '/' and nxt == '*': mode = 'blockC'; i += 2; col += 1; continue
            if ch in '([{': stack.append((ch, line, col)); i += 1; continue
            if ch in ')]}':
                if not stack:
                    return {'error': f'unmatched closer {ch}', 'line': line, 'col': col, 'context': lines[line-1]}
                top, l, c = stack[-1][0], stack[-1][1], stack[-1][2]
                pair = {')':'(',']':'[','}':'{'}
                if pair[ch] != top:
                    return {'error': f'mismatch {top} vs {ch}', 'line': line, 'col': col, 'context': lines[line-1]}
                stack.pop()
                i += 1; continue
            i += 1; continue
        elif mode == 'sgl':
            if ch == '\\': i += 2; col += 1; continue
            if ch == "'": mode = 'code'; i += 1; continue
            i += 1; continue
        elif mode == 'dbl':
            if ch == '\\': i += 2; col += 1; continue
            if ch == '"': mode = 'code'; i += 1; continue
            i += 1; continue
        elif mode == 'tpl':
            if ch == '\\': i += 2; col += 1; continue
            if ch == '`': mode = 'code'; i += 1; continue
            i += 1; continue
        elif mode == 'lineC':
            if ch == '\n': mode = 'code'
            i += 1; continue
        elif mode == 'blockC':
            if ch == '*' and nxt == '/': mode = 'code'; i += 2; col += 1; continue
            i += 1; continue
    return {'ok': True, 'remaining_opens': [(ch,l,c) for ch,l,c in stack], 'mode': mode}

if __name__ == '__main__':
    import sys, json
    file = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    res = scan_js_segment(file, start, end)
    print(json.dumps(res, ensure_ascii=False))
