import re, os, glob
from reportlab.pdfgen import canvas
from reportlab.lib.colors import CMYKColor
CMYK = {'#17241D':(60,30,55,80), '#F1EEE6':(0,1,5,5), '#D9A84E':(0,23,64,15), '#B8862E':(0,27,75,28),
        '#111111':(0,0,0,100), '#FFFFFF':(0,0,0,0)}
def mul(m, n):  # 2x3 affine (a,b,c,d,e,f)
    a,b,c,d,e,f = m; A,B,C,D,E,F = n
    return (a*A+c*B, b*A+d*B, a*C+c*D, b*C+d*D, a*E+c*F+e, b*E+d*F+f)
def parse_tf(s):
    m = (1,0,0,1,0,0)
    for op, args in re.findall(r'(translate|scale)\(([^)]*)\)', s or ''):
        v = [float(x) for x in re.split(r'[ ,]+', args.strip())]
        n = (1,0,0,1,v[0],v[1] if len(v)>1 else 0) if op=='translate' else (v[0],0,0,v[1] if len(v)>1 else v[0],0,0)
        m = mul(m, n)
    return m
def items(svg):
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    out = []; stack = [(1,0,0,1,0,0)]
    for tag in re.findall(r'<(/?g[^>]*|rect[^>]*|path[^>]*)>', svg):
        if tag.startswith('/g'): stack.pop(); continue
        if tag.startswith('g'): stack.append(mul(stack[-1], parse_tf(re.search(r'transform="([^"]*)"', tag).group(1)))); continue
        fill = re.search(r'fill="([^"]+)"', tag).group(1)
        tf = mul(stack[-1], parse_tf((re.search(r'transform="([^"]*)"', tag) or [None, ''])[1] if 'transform' in tag else ''))
        if tag.startswith('rect'):
            w = float(re.search(r'width="([^"]+)"', tag).group(1)); h = float(re.search(r'height="([^"]+)"', tag).group(1))
            d = f'M0 0 L{w} 0 L{w} {h} L0 {h}Z'
        else: d = re.search(r' d="([^"]+)"', tag).group(1)
        out.append((d, fill, tf, 'evenodd' in tag))
    return vb, out
def segs(d):
    t = re.findall(r'[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?', d); i = 0; x = y = 0; sx = sy = 0; res = []; last = None
    isnum = lambda k: k < len(t) and t[k] not in 'MLHVCQZ'
    while i < len(t):
        if t[i] in 'MLHVCQZ': c = t[i]; i += 1
        else: c = 'L' if last == 'M' else last   # implicit repeat of previous command
        last = c
        if c == 'M': x, y = float(t[i]), float(t[i+1]); i += 2; sx, sy = x, y; res.append(('M', x, y))
        elif c == 'L': x, y = float(t[i]), float(t[i+1]); i += 2; res.append(('L', x, y))
        elif c == 'H': x = float(t[i]); i += 1; res.append(('L', x, y))
        elif c == 'V': y = float(t[i]); i += 1; res.append(('L', x, y))
        elif c == 'C': a = [float(v) for v in t[i:i+6]]; i += 6; res.append(('C', *a)); x, y = a[4], a[5]
        elif c == 'Q':
            qx, qy, ex, ey = [float(v) for v in t[i:i+4]]; i += 4
            res.append(('C', x+2/3*(qx-x), y+2/3*(qy-y), ex+2/3*(qx-ex), ey+2/3*(qy-ey), ex, ey)); x, y = ex, ey
        elif c == 'Z': res.append(('Z',)); x, y = sx, sy; last = None
    return res
def build(path_svg, scale_pt=4.0):
    svg = open(path_svg).read(); vb, its = items(svg)
    W, H = vb[2]*scale_pt, vb[3]*scale_pt
    def P(m, x, y):  # svg user -> page pts (y up)
        X = m[0]*x + m[2]*y + m[4]; Y = m[1]*x + m[3]*y + m[5]
        return (X - vb[0])*scale_pt, H - (Y - vb[1])*scale_pt
    return W, H, [( [ (s[0],)+tuple(v for k in range(1, len(s), 2) for v in P(tf, s[k], s[k+1])) for s in segs(d) ], fill, eo) for d, fill, tf, eo in its]
def write_pdf(src, dst):
    W, H, shapes = build(src); c = canvas.Canvas(dst, pagesize=(W, H)); c.setTitle('Braveholt logo')
    for sg, fill, eo in shapes:
        cm = CMYK[fill]; c.setFillColor(CMYKColor(*[v/100 for v in cm])); p = c.beginPath()
        for s in sg:
            if s[0]=='M': p.moveTo(s[1], s[2])
            elif s[0]=='L': p.lineTo(s[1], s[2])
            elif s[0]=='C': p.curveTo(*s[1:])
            else: p.close()
        c.drawPath(p, fill=1, stroke=0, fillMode=0 if eo else 1)  # 0 even-odd, 1 nonzero
    c.showPage(); c.save()
def write_eps(src, dst):
    W, H, shapes = build(src)
    L = ['%!PS-Adobe-3.0 EPSF-3.0', f'%%BoundingBox: 0 0 {int(W+0.999)} {int(H+0.999)}', f'%%HiResBoundingBox: 0 0 {W:.3f} {H:.3f}',
         '%%Title: Braveholt logo', '%%Creator: Braveholt brand files', '%%EndComments', 'gsave']
    for sg, fill, eo in shapes:
        cm = CMYK[fill]; L.append(' '.join(f'{v/100:.3f}' for v in cm) + ' setcmykcolor newpath')
        for s in sg:
            if s[0]=='M': L.append(f'{s[1]:.3f} {s[2]:.3f} moveto')
            elif s[0]=='L': L.append(f'{s[1]:.3f} {s[2]:.3f} lineto')
            elif s[0]=='C': L.append(' '.join(f'{v:.3f}' for v in s[1:]) + ' curveto')
            else: L.append('closepath')
        L.append('eofill' if eo else 'fill')
    L += ['grestore', 'showpage', '%%EOF']; open(dst, 'w').write('\n'.join(L) + '\n')
os.makedirs('out/pdf', exist_ok=True); os.makedirs('out/eps', exist_ok=True)
for f in sorted(glob.glob('out/svg/*.svg')):
    n = os.path.basename(f)[:-4]; write_pdf(f, f'out/pdf/{n}.pdf'); write_eps(f, f'out/eps/{n}.eps')
print('done')
