import json, re
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
G = json.load(open('../sent/b2.json'))

def parse(d, n=24):
    """absolute M/L/H/V/C/Z path -> list of polygons (bezier sampled)"""
    t = re.findall(r'[MLHVCZ]|-?\d*\.?\d+', d); i = 0; polys = []; cur = []; x = y = 0
    while i < len(t):
        c = t[i]; i += 1
        if c == 'M':
            if cur: polys.append(cur)
            x, y = float(t[i]), float(t[i+1]); i += 2; cur = [(x, y)]
        elif c == 'L': x, y = float(t[i]), float(t[i+1]); i += 2; cur.append((x, y))
        elif c == 'H': x = float(t[i]); i += 1; cur.append((x, y))
        elif c == 'V': y = float(t[i]); i += 1; cur.append((x, y))
        elif c == 'C':
            a = [float(v) for v in t[i:i+6]]; i += 6; x0, y0 = x, y
            for k in range(1, n+1):
                s = k/n; u = 1-s
                cur.append((u**3*x0 + 3*u*u*s*a[0] + 3*u*s*s*a[2] + s**3*a[4],
                            u**3*y0 + 3*u*u*s*a[1] + 3*u*s*s*a[3] + s**3*a[5]))
            x, y = a[4], a[5]
        elif c == 'Z':
            if cur: polys.append(cur); cur = []
    if cur: polys.append(cur)
    return [Polygon(p).buffer(0) for p in polys if len(p) > 2]

forest = unary_union(parse(G['L']) + parse(G['R']) + parse(G['fill']) + parse(G['trunks']))
B = unary_union(parse(G['B'], 48))
B = affinity.scale(B, 0.85, 0.85, origin=(32.6, 56))
mark_geom = forest.difference(B)
def geom_d(g):
    out = []
    geoms = getattr(g, 'geoms', [g])
    for p in geoms:
        for ring in [p.exterior] + list(p.interiors):
            c = list(ring.coords)[:-1]
            out.append('M' + ' L'.join(f'{x:.3f} {y:.3f}' for x, y in c) + 'Z')
    return ' '.join(out)
MARK = geom_d(mark_geom.simplify(0.01))
GROUND = 'M8 56 H56 V58 H8Z'

# wordmark: Spectral SC SemiBold outlines, tracking .1em
font = TTFont('../print/fonts/SpectralSC-SemiBold.ttf'); gs = font.getGlyphSet(); cmap = font.getBestCmap()
upm = font['head'].unitsPerEm; capH = font['OS/2'].sCapHeight
def wordmark(text='BRAVEHOLT', tracking=0.1):
    pen = SVGPathPen(gs); x = 0
    for i, ch in enumerate(text):
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (1, 0, 0, -1, x, 0)); gs[g].draw(tp)
        x += gs[g].width + (tracking*upm if i < len(text)-1 else 0)
    return pen.getCommands(), x  # in font units, baseline at y=0, cap top at -capH
WM_D, WM_W = wordmark()

COLORS = {
  'color-on-light': ('#17241D', '#B8862E', '#17241D'),
  'color-on-dark':  ('#F1EEE6', '#D9A84E', '#F1EEE6'),
  'black':          ('#111111', '#111111', '#111111'),
  'white':          ('#FFFFFF', '#FFFFFF', '#FFFFFF'),
}
def svg_mark(fill, acc, pad=2):
    vb = f'{8-pad} {3.5-pad} {48+2*pad} {54.5+2*pad}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="Braveholt">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/></svg>\n')
def svg_lockup(fill, acc, wfill, kind):
    # mark box: x 8..56, y 3.5..58 (h 54.5). wordmark cap height relative to mark height
    if kind == 'horizontal':
        cap = 54.5*0.34; s = cap/capH; gap = 10
        wx = 56 + gap; wy = 58 - (54.5 - cap)/2   # vertically centered-ish on mark (baseline)
        wy = 3.5 + 54.5/2 + cap/2
        W = wx + WM_W*s; vb = f'4 0 {W-4+4} 62'
        wm = f'<path fill="{wfill}" transform="translate({wx:.3f} {wy:.3f}) scale({s:.6f})" d="{WM_D}"/>'
    else:  # stacked
        cap = 54.5*0.2; s = cap/capH; ww = WM_W*s
        wx = 32 - ww/2; wy = 58 + 10 + cap
        x0 = min(4, wx-4); W = max(60, wx+ww+4) - x0
        vb = f'{x0:.3f} 0 {W:.3f} {wy+5:.3f}'
        wm = f'<path fill="{wfill}" transform="translate({wx:.3f} {wy:.3f}) scale({s:.6f})" d="{WM_D}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="Braveholt">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/>{wm}</svg>\n')
def svg_icon(bg='#17241D', fill='#F1EEE6', acc='#D9A84E', radius=0):
    # square app icon / favicon source: mark centered with padding
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="{radius}" fill="{bg}"/>'
            f'<g transform="translate(32 33) scale(0.78) translate(-32 -30.75)"><path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/></g></svg>\n')
import os
os.makedirs('out/svg', exist_ok=True)
files = {}
for name, (f, a, w) in COLORS.items():
    files[f'braveholt-mark-{name}.svg'] = svg_mark(f, a)
    files[f'braveholt-logo-horizontal-{name}.svg'] = svg_lockup(f, a, w, 'horizontal')
    files[f'braveholt-logo-stacked-{name}.svg'] = svg_lockup(f, a, w, 'stacked')
files['braveholt-app-icon.svg'] = svg_icon()
for n, s in files.items(): open('out/svg/' + n, 'w').write(s)
print(len(files), 'svgs')
