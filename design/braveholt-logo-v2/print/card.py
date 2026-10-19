import json, re, sys
from reportlab.pdfgen import canvas
from reportlab.lib.colors import CMYKColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
G = json.load(open('../sent/b2.json'))
pdfmetrics.registerFont(TTFont('SpectralSC', 'fonts/SpectralSC-SemiBold.ttf'))
pdfmetrics.registerFont(TTFont('Spectral', 'fonts/Spectral-SemiBold.ttf'))
pdfmetrics.registerFont(TTFont('PlexMono', 'fonts/IBMPlexMono-Regular.ttf'))
C = lambda c,m,y,k: CMYKColor(c/100, m/100, y/100, k/100)
INK   = C(60, 30, 55, 80)   # deep pine green
BONE  = C(0, 1, 5, 5)
PAPER = C(0, 1, 3, 3)
BRASS_DARK = C(0, 23, 64, 15)  # on dark ground
BRASS = C(0, 27, 75, 28)       # on light ground
GREY  = C(13, 0, 8, 65)
TRIM_W, TRIM_H, BLEED = 252, 144, 9   # 3.5 x 2 in, 0.125 in bleed
PW, PH = TRIM_W + 2*BLEED, TRIM_H + 2*BLEED
proof = len(sys.argv) > 1 and sys.argv[1] == 'proof'

def tokens(d): return re.findall(r'[MLHVCZ]|-?\d*\.?\d+', d)
def draw_path(c, d, ox, oy, s, xf=None):
    p = c.beginPath(); t = tokens(d); i = 0; x = y = 0
    def P(px, py):
        if xf: px, py = xf(px, py)
        return ox + px*s, oy - py*s
    while i < len(t):
        cmd = t[i]; i += 1
        if cmd == 'M': x, y = float(t[i]), float(t[i+1]); i += 2; p.moveTo(*P(x, y))
        elif cmd == 'L': x, y = float(t[i]), float(t[i+1]); i += 2; p.lineTo(*P(x, y))
        elif cmd == 'H': x = float(t[i]); i += 1; p.lineTo(*P(x, y))
        elif cmd == 'V': y = float(t[i]); i += 1; p.lineTo(*P(x, y))
        elif cmd == 'C':
            a = [float(v) for v in t[i:i+6]]; i += 6
            p.curveTo(*P(a[0], a[1]), *P(a[2], a[3]), *P(a[4], a[5])); x, y = a[4], a[5]
        elif cmd == 'Z': p.close()
    c.drawPath(p, fill=1, stroke=0)
def mark(c, cx, top, size, fg, ground, hole):
    s = size/64; ox = cx - 32*s; oy = top
    c.setFillColor(fg)
    for k in ('L', 'R'): draw_path(c, G[k], ox, oy, s)
    for part in G['fill'].split(' M'): draw_path(c, part if part.startswith('M') else 'M'+part, ox, oy, s)
    for part in G['trunks'].split(' M'): draw_path(c, part if part.startswith('M') else 'M'+part, ox, oy, s)
    c.setFillColor(hole)  # the B is the ground showing through
    sc = lambda px, py: (32.6 + (px-32.6)*0.85, 56 + (py-56)*0.85)
    draw_path(c, G['B'], ox, oy, s, sc)
    c.setFillColor(ground); c.rect(ox + 11.5*s, oy - 59.6*s, 39.7*s, 2*s, fill=1, stroke=0)  # ground line = foliage width, 1.6 below the trunks
def spaced(c, x, y, text, font, size, tracking, align='left'):
    w = sum(pdfmetrics.stringWidth(ch, font, size) for ch in text) + tracking*size*(len(text)-1)
    if align == 'center': x -= w/2
    if align == 'right': x -= w
    c.setFont(font, size)
    for ch in text:
        c.drawString(x, y, ch); x += pdfmetrics.stringWidth(ch, font, size) + tracking*size
def guides(c):
    if not proof: return
    c.setLineWidth(0.4); c.setDash(2, 2)
    c.setStrokeColor(CMYKColor(0, 1, 0, 0)); c.rect(BLEED, BLEED, TRIM_W, TRIM_H, fill=0)          # trim
    c.setStrokeColor(CMYKColor(1, 0, 0, 0)); c.rect(2*BLEED, 2*BLEED, TRIM_W-2*BLEED, TRIM_H-2*BLEED, fill=0)  # safe
    c.setDash()
fn = 'braveholt-card-proof.pdf' if proof else 'braveholt-card-print.pdf'
c = canvas.Canvas(fn, pagesize=(PW, PH), initialFontName='SpectralSC', initialFontSize=8)
c.setTitle('Braveholt business card' + (' (proof)' if proof else ''))
# ---- front ----
c.setFillColor(INK); c.rect(0, 0, PW, PH, fill=1, stroke=0)
cx = PW/2; size = 62; block = size + 6 + 10.5
top = PH - (PH - block)/2
mark(c, cx, top, size, BONE, BRASS_DARK, INK)
c.setFillColor(BONE); spaced(c, cx, top - size - 6 - 9.5, 'BRAVEHOLT', 'SpectralSC', 12.5, 0.1, 'center')
guides(c); c.showPage()
# ---- back ----
c.setFillColor(PAPER); c.rect(0, 0, PW, PH, fill=1, stroke=0)
L = BLEED + 22; R = PW - BLEED - 22; T = PH - BLEED - 22; B = BLEED + 20
c.setFillColor(INK); c.setFont('Spectral', 12); c.drawString(L, T - 11, '[Name]')
c.setFillColor(GREY); spaced(c, L, T - 24, '[TITLE]', 'SpectralSC', 7.5, 0.12)
mark(c, R - 15, T + 2, 32, INK, BRASS, PAPER)
c.setFillColor(C(10, 0, 8, 72)); c.setFont('PlexMono', 7)
for i, line in enumerate(['braveholt.com', '[Phone]', '[email]@braveholt.com']): c.drawString(L, B + i*10, line)
c.setFillColor(INK); spaced(c, R, B, 'BRAVEHOLT', 'SpectralSC', 7.5, 0.1, 'right')
guides(c); c.showPage(); c.save(); print('wrote', fn)
