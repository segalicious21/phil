# Braveholt logo exploration v2 (DRAFT)

Four new concepts replacing logo K ("hidden-forest B"). All DRAFT until the
name checks (SCC, SAM.gov, listener test, trademark) pass.

| File | Concept | Idea |
|---|---|---|
| 01-chevron-pine.svg | Chevron Pine (recommended) | Three rank chevrons stack into a pine; the top chevron in brass |
| 02-growth-ring.svg | Growth Ring | Off-center tree rings double as a radar scope with a sweep and a contact |
| 03-hold-the-line.svg | Hold the Line | Solid pine above a brass ground line, roots below |
| 04-pine-a.svg | Pine A wordmark | The A in BRAVEHOLT drawn as a three-tier pine |

Palette: Holt Green #1F3A2E, Brass Deep #8A6A24 (light bg) / Brass #D2AE63 (dark bg), Bone #F5F2EA.
Wordmark type in the canvas: Archivo 700, width 125, tracking 0.12em.

## Final (founder confirmed 2026-10-13): Sentinel B

Two pines; the person standing between them is drawn as the letter B, cut out as negative space, on a brass ground line.

- Files: `final-sentinel-b-light-bg.svg`, `final-sentinel-b-dark-bg.svg`.
- The full package is in `logo-files/` (see its README.txt).
- Wordmark: Spectral SC 600, tracking 0.1em.

**Refined 2026-10-19** (founder: "바로 a로 바꿔줘"):
- The B's head-to-body ratio changed from 1 : 2.8 to 1 : 1.8.
- The trunk block is now symmetric around the B.
- A new `app-icon-small` (16–48 px, with a thicker brass line) is used for favicon.ico.
- The minimum mark size is 24 px / 8 mm.

**Second pass, same day** (founder: "B의 가독성, 골드 밑선의 정밀함, 전체 비율과 간격"):
- The B's waist is deeper and its top bowl is narrower.
- The brass line spans exactly the foliage (11.5–51.2) and sits 0.8 units below the trunks.
- In the horizontal lockup, the wordmark stands on the trunk baseline with cap height = hidden B height.

**Third pass, v4 structure, same day** (founder: "나무와 B의 결합 · 좌우 균형과 하단 골드 선 · 작은 크기에서의 가독성"):
- The B's top and waist sit on the trees' tier lines.
- Both trees share their lower tier line.
- The trunk stubs are equal.
- The ground line has a 1.6 gap.
- A new step-free `mark-small` covers 16–24 px.
- The horizontal wordmark's cap top sits on the shared tier line.

Geometry source: `print/mark.json`.

Earlier explorations are kept for the record and are not in use:
- the four concepts above
- Shadow: `final-shadow-*.svg`

## Intro animation

`intro/braveholt-intro.mp4` and `.gif`, 8 seconds:
1. The two trees slide in.
2. The B appears.
3. The brass line draws.
4. The wordmark and tagline follow.

## Business card (print)

`print/braveholt-card-print.pdf`: 2 pages (front, back), US 3.5 x 2 in trim plus 0.125 in bleed
(3.75 x 2.25 in page), CMYK vector, fonts embedded. `print/braveholt-card-proof.pdf` adds trim
(dashed grey) and safe-area (dashed cyan) guides; do not send the proof to the printer.
Regenerate with `python3 card.py` (needs reportlab and the Spectral SC / Spectral / IBM Plex Mono TTFs in `fonts/`).
Placeholders [Name], [Title], [email], [Phone] must be filled before printing.
CMYK: pine green 60/30/55/80, bone 0/1/5/5, paper 0/1/3/3, brass on dark 0/23/64/15, brass on light 0/27/75/28.
