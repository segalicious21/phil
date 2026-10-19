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
forest_small = unary_union(parse(G['small_L']) + parse(G['small_R']) + parse(G['small_fill']) + parse(G['trunks']))
MARK_SMALL = geom_d(forest_small.difference(B).simplify(0.01))  # 16-24 px: step-free trees so the B stays clear
GROUND = G['ground']; CX = (11.5 + 51.2) / 2  # foliage center

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
def svg_mark(fill, acc, pad=2.5):
    vb = f'{11.5-pad} {3.5-pad} {39.7+2*pad} {56.1+2*pad}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="Braveholt">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/></svg>\n')
def svg_lockup(fill, acc, wfill, kind):
    # Mark: foliage x 11.5..51.2, top 3.5, ground (trunk base) y 56, brass line 56.8..58.8.
    if kind == 'horizontal':
        cap = 56 - 37; s = cap/capH; gap = 12  # cap top = the tier line both trees share and the B waist (y37)           # gap = 1/4 of mark height (clear-space unit)
        wx = 51.2 + gap; wy = 56                        # wordmark stands on the same ground as the trees and the B
        W = wx + WM_W*s + 2.5; vb = f'9 1 {W-9:.3f} 61.1'
        wm = f'<path fill="{wfill}" transform="translate({wx:.3f} {wy:.3f}) scale({s:.6f})" d="{WM_D}"/>'
    else:  # stacked: everything centred on the foliage centre
        cap = 11; s = cap/capH; ww = WM_W*s
        wx = CX - ww/2; wy = 59.6 + 9.5 + cap
        x0 = min(9, wx-2.5); W = max(53.7, wx+ww+2.5) - x0
        vb = f'{x0:.3f} 1 {W:.3f} {wy+3.5-1:.3f}'
        wm = f'<path fill="{wfill}" transform="translate({wx:.3f} {wy:.3f}) scale({s:.6f})" d="{WM_D}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="Braveholt">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/>{wm}</svg>\n')
def svg_icon(bg='#17241D', fill='#F1EEE6', acc='#D9A84E', radius=0):
    # square app icon: mark box (11.5..51.2 x 3.5..58.8) centred, 74% of the square
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="{radius}" fill="{bg}"/>'
            f'<g transform="translate(32 32) scale(0.86) translate({-CX} -31.55)"><path fill="{fill}" fill-rule="evenodd" d="{MARK}"/><path fill="{acc}" d="{GROUND}"/></g></svg>\n')
import os
os.makedirs('out/svg', exist_ok=True)
files = {}
for name, (f, a, w) in COLORS.items():
    files[f'braveholt-mark-{name}.svg'] = svg_mark(f, a)
    files[f'braveholt-logo-horizontal-{name}.svg'] = svg_lockup(f, a, w, 'horizontal')
    files[f'braveholt-logo-stacked-{name}.svg'] = svg_lockup(f, a, w, 'stacked')
files['braveholt-app-icon.svg'] = svg_icon()
for name, (f, a, w) in COLORS.items():
    files[f'braveholt-mark-small-{name}.svg'] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="9 1 44.2 61.6" role="img" aria-label="Braveholt">'
        f'<path fill="{f}" fill-rule="evenodd" d="{MARK_SMALL}"/><path fill="{a}" d="{G['ground_small']}"/></svg>\n')
def svg_icon_small(bg='#17241D', fill='#F1EEE6', acc='#D9A84E'):
    # 16-48 px: larger mark and a 3.5-unit brass line so it stays visible at 16 px
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" fill="{bg}"/>'
            f'<g transform="translate(32 32) scale(0.98) translate({-CX} -32.3)"><path fill="{fill}" fill-rule="evenodd" d="{MARK_SMALL}"/><path fill="{acc}" d="{G['ground_small']}"/></g></svg>\n')
files['braveholt-app-icon-small.svg'] = svg_icon_small()
for n, s in files.items(): open('out/svg/' + n, 'w').write(s)
print(len(files), 'svgs')
