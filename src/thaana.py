"""Original Thaana letter skeletons for Rasmee Thaana.

Every letter is constructed from pen strokes (tools/stroke.py) drawn along
hand-authored skeleton paths. Sizes, positions and advance widths are matched
to the reference metrics (spec/metrics.json). Selected edges (CUT below: noonu's lip slot and scoop,
laamu's branch, right recess and diagonal edges, chaviyani's diagonal and tip, the outer heels of
eybeyfili/obofili/oaboafili, and the Arabic question mark's hook inner edge and tail)
and the Allah ligature outline are fitted to measured sections of Faruma, with the authorisation of
the President's Office (Faruma's owner); no Faruma outline points are copied.
Coordinates: font units, UPM 2048, y up, baseline 0.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from stroke import stroke, dot, NIB

# Entry terminal: Faruma-style letters start with a heavier, slightly drooped pen entry.
ENTRY = [(0, 1.12), (0.08, 1.0), (1, 1.0)]
EXIT_TAPER = [(0, 1.0), (0.85, 1.0), (1, 0.9)]
BOTH = [(0, 1.12), (0.08, 1.0), (0.9, 1.0), (1, 0.92)]
# Flat oblique entry facet (the reference's short nib edge at the low-left pen entry)
FACET = (105, 70)
# Pen-pause knob: second strokes start with a teardrop blob (characteristic of the reference style)
KNOB = [(0, 1.32), (0.07, 1.12), (0.16, 1.0), (1, 1.0)]

G = {}

def glyph(name):
    def deco(fn):
        G[name] = fn
        return fn
    return deco

# ---------------------------------------------------------------- base letters
@glyph('uni0780')  # HAA
def haa():
    return [stroke('M 120 200 C 205 196 285 228 385 285 C 565 390 785 520 962 622', profile=BOTH, facet0=FACET)]

@glyph('uni0781')  # SHAVIYANI
def shaviyani():
    return [stroke('M 82 165 C 190 168 300 225 410 305 C 480 357 545 415 610 475', profile=ENTRY, facet0=FACET),
            stroke('M 640 555 C 680 510 740 500 800 502 C 910 503 990 505 1045 528 C 1090 548 1118 572 1135 600', profile=KNOB)]

@glyph('uni0782')  # NOONU — soft two-hump crown (smooth spline skeleton)
def noonu():
    return [stroke('M -20 172 C 95 175 220 250 360 345 C 470 420 560 490 640 545', profile=ENTRY, facet0=FACET),
            stroke(_cr([(711, 640), (923, 622), (1040, 712), (1028, 630), (1070, 566), (1239, 551), (1403, 684)], 0.85), profile=KNOB)]

@glyph('uni0783')  # RAA
def raa():
    return [stroke('M -40 95 C 70 92 170 135 300 210 C 560 360 850 540 1090 690', profile=BOTH, facet0=FACET),
            stroke('M 520 560 C 640 522 770 482 880 458 C 920 450 950 444 975 440', profile=[(0, 1.32), (0.07, 1.12), (0.16, 1.0), (0.65, 1.0), (1, 0.72)])]

def _sp(path, cx, cy, k):
    """Scale a skeleton path about (cx, cy) by k (used to tune counter sizes)."""
    import re
    toks = re.findall(r'[MCQL]|-?\d+(?:\.\d+)?', path); out = []; xy = 0
    for t in toks:
        if t in 'MCQL': out.append(t); xy = 0; continue
        v = float(t); c = cx if xy % 2 == 0 else cy; out.append('%.1f' % (c + (v - c) * k)); xy += 1
    return ' '.join(out)

def _cr(pts, t=0.5):
    """Smooth Catmull-Rom skeleton through key points -> cubic path string."""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = 'M %.1f %.1f' % pts[0]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) * t / 3, p1[1] + (p2[1] - p0[1]) * t / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * t / 3, p2[1] - (p3[1] - p1[1]) * t / 3)
        out += ' C %.1f %.1f %.1f %.1f %.1f %.1f' % (c1 + c2 + p2)
    return out

def _oval(cx, cy, a, b, tilt, start=0):
    import math
    t = math.radians(tilt); pts = []
    for k in range(start, start + 361, 15):
        u = math.radians(k); x, y = a * math.cos(u), b * math.sin(u)
        pts.append((cx + x * math.cos(t) - y * math.sin(t), cy + x * math.sin(t) + y * math.cos(t)))
    return 'M %.1f %.1f ' % pts[0] + ' '.join('L %.1f %.1f' % p for p in pts[1:])

@glyph('uni0784')  # BAA — two linked ovals with open counters
def baa():
    # eyes drawn as rings around the target apertures (rising tapered ovals)
    return [stroke(_oval(418, 480, 192, 112, 22, 0), w=178, h=130),
            stroke(_oval(763, 516, 224, 102, 22, 180), w=178, h=130)]
@glyph('uni0785')  # LHAVIYANI
def lhaviyani():
    return [stroke('M 100 85 C 200 88 300 130 420 200 C 620 320 820 440 985 545', profile=BOTH, facet0=FACET),
            stroke('M 690 400 C 600 450 560 520 600 580 C 640 640 700 680 740 740')]

@glyph('uni0786')  # KAAFU
def kaafu():
    return [stroke('M 380 690 C 400 560 335 385 258 262', profile=[(0, 1.1), (0.15, 1.0), (0.85, 1.0), (1, 0.9)]),
            stroke('M 250 250 C 420 320 700 470 985 640', profile=EXIT_TAPER)]

@glyph('uni0787')  # ALIFU
def alifu():
    return [stroke(_cr([(97, 308), (357, 332), (863, 602), (976, 535), (870, 253)], 0.9), profile=[(0, 1.12), (0.06, 1.0), (0.68, 1.0), (1, 0.76)], facet0=FACET)]

VAAVU_K = 0.96

@glyph('uni0788')  # VAAVU
def vaavu():
    return [stroke('M 40 75 C 130 100 215 105 325 165 C 490 255 700 380 868 500', profile=ENTRY, facet0=FACET),
            stroke(_sp('M 868 500 C 965 575 925 690 765 692 C 610 694 480 615 460 520 C 450 440 525 385 630 350', 760, 520, VAAVU_K))]

@glyph('uni0789')  # MEEMU
def meemu():
    return [stroke('M 165 110 C 255 140 335 150 445 200 C 640 295 800 400 895 510 C 965 610 900 680 765 686 C 665 690 600 672 562 640', profile=ENTRY, facet0=FACET)]

@glyph('uni078A')  # FAAFU
def faafu():
    return [stroke('M -215 -190 C -120 -168 -40 -166 60 -120 C 260 -10 440 110 600 205', profile=[(0, 0.88), (0.15, 0.95), (0.3, 1.0), (1, 1.0)], facet0=FACET),
            stroke('M 600 205 C 540 250 460 290 410 325 C 520 355 620 380 690 415 C 610 470 520 540 480 600 C 590 630 680 650 765 700')]

@glyph('uni078B')  # DHAALU
def dhaalu():
    return [stroke('M -250 -200 C -150 -182 -60 -170 50 -108 C 250 20 400 150 520 270', profile=[(0, 0.95), (0.15, 0.95), (0.25, 1.0), (1, 1.0)], facet0=FACET),
            stroke(_cr([(507, 228), (945, 286), (931, 498), (774, 510), (1025, 559)], 0.9), profile=[(0, 1.4), (0.06, 1.15), (0.14, 1.0), (1, 1.0)])]

@glyph('uni078C')  # THAA
def thaa():
    return [stroke('M -25 20 C 90 30 230 40 350 120 C 420 190 310 250 270 320 C 440 440 640 560 830 660 C 960 712 1035 615 990 495 C 945 385 820 345 705 355 C 620 365 550 390 505 420', profile=ENTRY, facet0=FACET)]

@glyph('uni078D')  # LAAMU
def laamu():
    return [stroke('M -170 -172 C -80 -138 10 -118 110 -68 C 410 110 750 310 1040 500', profile=[(0, 1.0), (1, 1.0)], facet0=FACET),
            stroke(_cr([(480, 442), (560, 456), (788, 491), (724, 556), (802, 591), (813, 645)], 0.85), profile=KNOB)]

@glyph('uni078E')  # GAAFU
def gaafu():
    return [stroke('M 165 210 C 290 185 470 190 575 245 C 672 315 640 400 545 450 C 470 488 475 555 570 598 C 680 640 780 675 860 705', profile=ENTRY, facet0=FACET)]

@glyph('uni078F')  # GNAVIYANI
def gnaviyani():
    return [stroke('M 880 40 C 700 10 480 -10 330 20 C 180 50 140 180 240 300 C 320 390 400 440 480 480', profile=[(0, 1.0), (1, 1.0)]),
            stroke(_cr([(432, 639), (502, 545), (623, 568), (782, 655), (733, 560), (915, 484), (1069, 595), (1090, 643)], 0.9), profile=KNOB)]

@glyph('uni0790')  # SEENU
def seenu():
    return [stroke('M 1880 715 C 1800 560 1700 478 1540 476 L 470 476'),
            stroke('M 490 476 C 478 585 400 625 315 615 C 235 605 210 545 250 500 C 280 468 320 455 340 440 C 265 370 190 305 125 250', profile=[(0, 1.0), (0.35, 1.12), (0.6, 1.0), (1, 1.0)])]

@glyph('uni0791')  # DAVIYANI
def daviyani():
    return [stroke(_cr([(584, 720), (371, 595), (758, 452), (359, 258), (585, 173), (1055, 140)], 0.9), w=148, h=108, profile=[(0, 1.0), (0.8, 1.0), (1, 0.78)])]

@glyph('uni0792')  # ZAVIYANI
def zaviyani():
    return [stroke('M 905 -15 C 700 -42 480 -60 340 -25 C 180 20 160 180 300 300 C 420 400 620 520 760 590 C 860 640 950 680 1050 705'),
            stroke('M 460 520 C 580 474 740 420 880 352', profile=[(0, 1.32), (0.1, 1.12), (0.2, 1.0), (0.65, 1.0), (1, 0.8)])]

@glyph('uni0793')  # TAVIYANI — bowl under the BAA double-oval (counters tuned to the reference)
def taviyani():
    # bowl + two rising eyes drawn as rings around the target apertures
    return [stroke('M 870 50 C 700 -35 470 -62 330 -20 C 170 30 170 200 300 300', profile=[(0, 0.8), (0.12, 1.0), (1, 1.0)], w=180, h=132),
            stroke(_oval(492, 510, 178, 108, 30, 0), w=166, h=121),
            stroke(_oval(814, 512, 208, 98, 26, 180), w=166, h=121)]
@glyph('uni0794')  # YAA
def yaa():
    return [stroke('M 0 60 C 110 90 260 190 420 320 C 500 390 550 450 590 520', profile=ENTRY, facet0=FACET),
            stroke('M 560 590 C 640 650 780 620 920 670 C 990 620 920 420 820 245', profile=[(0, 1.32), (0.07, 1.12), (0.16, 1.0), (0.75, 1.0), (1, 0.84)])]

@glyph('uni0796')  # JAVIYANI
def javiyani():
    return [stroke('M 815 0 C 670 -70 440 -150 300 -112 C 160 -60 150 80 260 190 C 330 260 400 300 450 330', profile=[(0, 0.78), (0.12, 1.0), (1, 1.0)], w=182, h=132),
            stroke(_cr([(350, 377), (772, 346), (803, 638), (547, 604), (923, 680)], 0.9), w=182, h=132, profile=[(0, 1.32), (0.07, 1.12), (0.16, 1.0), (1, 1.0)])]

@glyph('uni0797')  # CHAVIYANI
def chaviyani():
    return [stroke('M -10 140 C 90 150 200 180 260 230 C 290 300 200 340 180 400 C 520 600 1000 870 1420 1080', profile=[(0, 1.12), (0.08, 1.0), (0.6, 1.08), (0.86, 1.15), (1, 0.96)], facet0=FACET),
            stroke('M 940 818 C 1005 750 1018 605 928 515 C 848 440 722 446 660 515 C 628 553 613 590 615 627')]

@glyph('uni07B1')  # NAA (Addu) — closed upper eye on a sloping spine into an open lower bowl.
# The reference font leaves this blank; drawn to its 903 advance and kept inside it.
def naa():
    return [stroke('M 360 330 C 375 540 530 668 670 628 C 790 595 790 430 665 385 C 570 352 455 350 360 330 '
                   'C 260 300 160 225 150 120 C 140 0 250 -80 400 -88 C 462 -91 508 -82 545 -58',
                   profile=[(0, 1.0), (0.88, 1.0), (1, 0.74)])]

# ---------------------------------------------------------------- fili (vowel & sukun marks)
FW = dict(w=186, h=136, profile=[(0, 0.86), (0.12, 1.0), (0.88, 1.0), (1, 0.86)])  # fili: tapered pen entries/exits

@glyph('uni07A6')  # ABAFILI
def abafili():
    return [stroke('M 425 1090 C 600 1190 780 1300 940 1400', **FW, facet0=(110, 40))]

@glyph('uni07A7')  # AABAAFILI
def aabaafili():
    return [stroke('M 500 1310 L 1080 1620', w=186, h=136, profile=[(0, 0.86), (0.12, 1.0), (0.8, 1.0), (1, 0.78)]),
            stroke('M 590 1060 L 1170 1370', **FW)]

@glyph('uni07A8')  # IBIFILI
def ibifili():
    return [stroke('M 95 -705 C 270 -610 450 -500 610 -405', **FW, facet0=(110, 40))]

@glyph('uni07A9')  # EEBEEFILI
def eebeefili():
    return [stroke('M 70 -595 L 600 -338', w=200, h=146, profile=[(0, 0.86), (0.12, 1.0), (0.78, 1.0), (1, 0.7)]),
            stroke('M 150 -860 L 710 -585', **FW)]

def _ubu(dx):
    return stroke(f'M {650+dx} 1480 C {760+dx} 1510 {960+dx} 1500 {990+dx} 1400 C {1012+dx} 1300 {870+dx} 1185 {650+dx} 1110', **FW)

@glyph('uni07AA')  # UBUFILI
def ubufili():
    return [_ubu(0)]

@glyph('uni07AB')  # OOBOOFILI
def ooboofili():
    return [stroke(_cr([(362, 1482), (512, 1496), (612, 1401), (496, 1180), (310, 1112)], 0.9), w=196, h=144, profile=FW['profile']),
            stroke(_cr([(921, 1524), (1165, 1452), (1183, 1395), (1125, 1215), (886, 1081)], 0.9), w=206, h=150, profile=FW['profile'])]

def _ebe(dx):
    return stroke(f'M {940+dx} 1480 C {820+dx} 1410 {700+dx} 1330 {660+dx} 1230 C {645+dx} 1160 {720+dx} 1114 {820+dx} 1114 C {870+dx} 1114 {910+dx} 1115 {945+dx} 1117', **FW)

@glyph('uni07AC')  # EBEFILI
def ebefili():
    return [_ebe(0)]

@glyph('uni07AD')  # EYBEYFILI
def eybeyfili():
    tip = dict(w=198, h=146, profile=[(0, 0.76), (0.15, 1.0), (0.85, 1.0), (1, 0.76)])
    return [stroke(f'M 540 1480 C 420 1410 300 1330 260 1230 C 245 1160 320 1114 420 1114 C 470 1114 510 1115 545 1117', **tip),
            stroke(f'M 1090 1480 C 970 1410 850 1330 810 1230 C 795 1160 870 1114 970 1114 C 1020 1114 1060 1115 1095 1117', **tip)]

@glyph('uni07AE')  # OBOFILI
def obofili():
    return [stroke(_cr([(490, 1490), (662, 1403), (653, 1290), (585, 1152), (398, 1133)], 0.9), w=186, h=136, profile=[(0, 0.7), (0.15, 1.0), (0.85, 1.0), (1, 0.7)]),
            stroke('M 1120 1470 C 960 1430 800 1380 700 1300 C 800 1190 960 1110 1110 1100', w=186, h=136, profile=[(0, 0.7), (0.15, 1.0), (0.85, 1.0), (1, 0.7)])]

@glyph('uni07AF')  # OABOAFILI — tilted loop; right flank kept high to clear neighbouring fili,
# lower hook kept short/high to clear built-in dots and carets (fitted to a raised-floor box)
def oaboafili():
    return [stroke(_cr([(880, 1335), (1389, 1637), (1246, 1969), (575, 1615), (432, 1268), (668, 1180)], 0.9),
                   w=186, h=136, profile=[(0, 0.86), (0.1, 1.0), (0.9, 1.0), (1, 0.82)])]

@glyph('uni07B0')  # SUKUN — tilted oval ring
def sukun():
    import math
    cx, cy, a, b, t = 859, 1278, 237, 158, math.radians(24.5)
    pts = []
    for k in range(0, 361, 15):
        u = math.radians(k); x, y = a * math.cos(u), b * math.sin(u)
        pts.append((cx + x * math.cos(t) - y * math.sin(t), cy + x * math.sin(t) + y * math.cos(t)))
    path = 'M %.1f %.1f ' % pts[0] + ' '.join('L %.1f %.1f' % p for p in pts[1:])
    return [stroke(path, w=165, h=150, angle=24)]

# ---------------------------------------------------------------- Arabic question mark (reversed ?)
@glyph('afii57407')
def arabic_question():
    return [stroke(_cr([(760, 1403), (752, 1690), (420, 1772), (180, 1600), (165, 1320), (262, 1120), (428, 870), (490, 622)], 0.85), w=124, h=92, angle=30,
                   profile=[(0, 1.55), (0.06, 1.0), (0.13, 0.6), (0.25, 0.6), (0.33, 1.1), (0.41, 1.75), (0.56, 1.3), (0.82, 0.8), (1, 0.55)]),
            dot(480, 410, 224, 226, 30)]

def _turned_comma(dx=0, dy=0, k=1.0):
    return stroke(f'M {360+dx} {420+dy} C {330+dx} {500+dy} {345+dx} {600+dy} {430+dx} {690+dy} C {470+dx} {730+dy} {520+dx} {760+dy} {570+dx} {780+dy}',
                  w=150 * k, h=112 * k, angle=30, profile=[(0, 1.95), (0.12, 1.45), (0.35, 1.0), (1, 0.42)])

@glyph('afii57388')  # ARABIC COMMA (turned comma)
def arabic_comma():
    return [_turned_comma(0, 0, 0.96)]

@glyph('afii57403')  # ARABIC SEMICOLON: slender turned comma over a dot
def arabic_semicolon():
    return [_turned_comma(-20, 215, 0.84), dot(362, 116, 252, 246, 30)]

# ---------------------------------------------------------------- nuqta components
@glyph('DotAbove')
def dot_above():
    return [dot(340, 602, 205, 200, 30)]

@glyph('DotBelow')
def dot_below():
    return [dot(340, 602, 205, 200, 30)]

@glyph('TwoDots')
def two_dots():
    return [dot(176, 594, 205, 190, 30), dot(504, 594, 205, 190, 30)]

@glyph('ThreeDots')  # the reference draws the three-dot sign as a caret
def three_dots():
    # wide chevron with thin tapered legs and an open underside notch (reference proportion);
    # right leg kept short and apex low so it clears the bowl and SUKUN on ޘ ޝ
    left = stroke('M 118 615 C 185 690 250 752 312 790', w=164, h=114, angle=30, profile=[(0, 0.45), (0.4, 1.0), (1, 1.08)])
    right = stroke('M 312 790 C 372 756 425 712 470 662', w=164, h=114, angle=30, profile=[(0, 1.08), (0.6, 1.0), (1, 0.45)])
    return [_notch(left.union(right))]


def _outline(runs, t=0.5):
    """Closed outline from runs of points; each run is a smooth Catmull-Rom edge (2 points = straight),
    consecutive runs meet at sharp corners (flat calligraphic cuts)."""
    from shapely.geometry import Polygon as _P
    import numpy as _np
    pts = []
    for r in runs:
        seg = _np.linspace(r[0], r[1], 30) if len(r) == 2 else _stroke.sample(_cr(r, t), 4.0)
        seg = [tuple(p) for p in seg]
        pts.extend(seg if not pts else seg[1:])
    return _P(pts).buffer(0)


@glyph('uniFDF2')  # ARABIC LIGATURE ALLAH: flat-cut calligraphic silhouette on the reference's geometry
def allah():
    body = _outline([
        # ha: upper edge from the descending tip over the hump into the valley and up the first lam
        [(-133, 150), (-109, 200), (-84, 250), (-58, 300), (-31, 350), (-3, 400), (27, 450), (58, 500), (93, 550),
         (134, 600), (162, 625), (195, 634), (226, 618), (250, 588), (275, 549), (313, 500), (351, 470), (389, 450),
         (430, 433), (468, 427), (501, 445), (526, 470), (545, 495), (560, 520), (572, 545), (581, 570), (589, 595),
         (595, 620), (605, 670), (611, 720), (614, 770), (616, 815), (617, 832)],
        [(617, 832), (806, 1012)],   # first lam: flat oblique cut
        [(806, 1012), (803, 995), (797, 970), (791, 945), (786, 920), (782, 895), (779, 870), (776, 845), (773, 820),
         (771, 770), (770, 745), (771, 695), (772, 670), (775, 645), (778, 620), (783, 595), (791, 570), (801, 545),
         (819, 520), (850, 500), (868, 493), (884, 500), (924, 520), (943, 545), (957, 570), (969, 595), (978, 620),
         (986, 645), (994, 670), (1000, 695), (1005, 720), (1010, 745), (1015, 770), (1019, 795), (1022, 820),
         (1026, 845), (1029, 870), (1031, 895), (1034, 920), (1036, 945), (1038, 970), (1040, 995), (1041, 1020),
         (1043, 1045), (1044, 1070), (1045, 1095), (1047, 1122)],
        [(1047, 1122), (1225, 1252)],   # second lam: flat oblique cut
        [(1225, 1252), (1224, 1220), (1223, 1170), (1221, 1120), (1219, 1070), (1215, 1020), (1211, 970), (1205, 920),
         (1198, 870), (1189, 820), (1178, 770), (1164, 720), (1148, 670), (1128, 620), (1102, 570), (1070, 520),
         (1040, 470), (1006, 420), (968, 370), (952, 350), (904, 300), (839, 250), (775, 220), (725, 212), (675, 232),
         (654, 250), (627, 300), (617, 350), (615, 420), (615, 470), (614, 503)],
        # connector underside back down to the hump's foot and the pointed exit
        [(614, 503), (595, 470), (580, 445), (564, 420), (547, 395), (529, 370), (514, 350), (471, 300), (417, 250),
         (337, 200), (275, 182), (225, 179), (175, 199), (125, 242), (75, 297), (48, 314), (25, 320), (-10, 300),
         (-25, 288), (-60, 250), (-75, 231), (-97, 200), (-133, 150)],
    ])
    alif = _outline([
        [(1354, 378), (1536, 632)],
        [(1536, 632), (1590, 1015), (1643, 1400)],
        [(1643, 1400), (1453, 1162)],
        [(1453, 1162), (1447, 1120), (1420, 945), (1395, 795), (1372, 595), (1356, 470), (1354, 378)],
    ])
    shadda = _outline([
        [(481, 1330), (495, 1348), (520, 1333), (540, 1321), (560, 1320), (580, 1323), (600, 1329), (620, 1341),
         (640, 1376), (660, 1385), (680, 1382), (700, 1348), (720, 1332), (740, 1327), (760, 1330), (780, 1338),
         (800, 1351), (820, 1362), (840, 1370), (862, 1378)],
        [(862, 1378), (840, 1309), (820, 1283), (800, 1265), (780, 1253), (760, 1243), (740, 1236), (720, 1235),
         (700, 1236), (680, 1240), (660, 1247), (640, 1258), (620, 1258), (600, 1242), (580, 1233), (560, 1230),
         (540, 1233), (520, 1244), (500, 1266), (481, 1330)],
    ])
    dagger = _outline([
        [(697, 1535), (763, 1625)],
        [(763, 1625), (763, 1860)],
        [(763, 1860), (742, 1877), (718, 1885), (702, 1879), (690, 1862)],
        [(690, 1862), (692, 1700), (695, 1600), (697, 1535)],
    ])
    return [body, alif, shadda, dagger]


def _notch(g):
    from shapely.geometry import Polygon as _P
    return g.difference(_P([(228, 600), (312, 748), (398, 600)])).buffer(-8).buffer(8)

@glyph('uni25CC')  # DOTTED CIRCLE (mark carrier)
def dotted_circle():
    import math
    cx, cy, r = 612, 613, 463
    return [dot(cx + r * math.cos(2 * math.pi * k / 14), cy + r * math.sin(2 * math.pi * k / 14), 66, 64, 30) for k in range(14)]


# ---------------------------------------------------------------- metric alignment
# Each drawn letter is translated so that its bounding-box centre sits exactly on the
# reference bounding-box centre (keeps the reference's placement & sidebearings).
import json as _json
from shapely import affinity as _aff
from shapely.ops import unary_union as _uu
_M = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spec', 'metrics.json'), encoding='utf-8'))
NO_ALIGN = {'uni25CC', 'ThreeDots', 'uniFDF2'}
BBOX_OVERRIDE = {'uni07AF': [348, 1062, 1407, 1895], 'uni07AB': [310, 1027, 1292, 1578]}

import stroke as _stroke
NO_FIT = set()  # glyphs whose drawn size is intentional (not fitted)
_AREA = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spec', 'ref_area.json'), encoding='utf-8'))
COLOUR_LIMIT = 0.10  # max per-glyph pen scaling for colour matching

def _fit_bbox(fn, tb, k):
    """Find skeleton scale (sx, sy) about the skeleton centre so the stroked bbox equals tb."""
    _stroke.PEN_K = k
    sx = sy = 1.0; cx = cy = None
    for _ in range(6):
        _stroke.SKEL_T = None if cx is None else (sx, sy, cx, cy)
        x0, y0, x1, y1 = _uu(fn()).bounds
        if cx is None:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        pw, ph = 150 * k, 140 * k
        sx *= max(0.8, min(1.25, ((tb[2] - tb[0]) - pw) / max(1, (x1 - x0) - pw)))
        sy *= max(0.8, min(1.25, ((tb[3] - tb[1]) - ph) / max(1, (y1 - y0) - ph)))
    return (sx, sy, cx, cy)


def _aligned(name, fn):
    def run():
        _stroke.CURRENT = name   # lets optional stroke styling (stroke.ENTRY_ROUND) know the glyph
        tb =BBOX_OVERRIDE.get(name) or _M['glyphs'].get(name, {}).get('ink_bbox') or _M['glyphs'].get(name, {}).get('bbox')
        if not tb or name in NO_ALIGN:
            return fn()
        try:
            k = 1.0; T = None
            if name in NO_FIT:
                geoms = fn()
            else:
                ra = _AREA.get(name)
                for it in range(3):
                    T = _fit_bbox(fn, tb, k)
                    _stroke.SKEL_T = T; _stroke.PEN_K = k
                    geoms = fn()
                    if not ra or it == 2:
                        break
                    gg = geoms
                    if name in PARE or name in CARVE or name in ROUND_COUNTER or name in CUT:  # measure colour after relief/carving
                        ux0, uy0, ux1, uy1 = _uu(geoms).bounds
                        tdx = (tb[0] + tb[2]) / 2 - (ux0 + ux1) / 2; tdy = (tb[1] + tb[3]) / 2 - (uy0 + uy1) / 2
                        gg = _pare(name, [_aff.translate(g, tdx, tdy) for g in geoms])
                    k *= (ra / _uu(gg).area) ** 0.9
                    k = max(1 - COLOUR_LIMIT, min(1 + COLOUR_LIMIT, k))
        finally:
            _stroke.SKEL_T = None; _stroke.PEN_K = 1.0
        u = _uu(geoms); x0, y0, x1, y1 = u.bounds
        dx = round((tb[0] + tb[2]) / 2 - (x0 + x1) / 2); dy = round((tb[1] + tb[3]) / 2 - (y0 + y1) / 2)
        out = [_aff.translate(g, dx, dy) for g in geoms]
        return _pare(name, out)
    return run


# Local relief ("paring"): erode the outline by d units only inside a box, in final glyph
# coordinates (used for reviewer-specified clearance fixes after fitting & colour matching).
PARE = {
    'uni07AD': [((200, 1040, 292, 1155), 18), ((225, 1245, 475, 1505), 18)],
    'uni07AE': [((240, 1055, 300, 1150), 34)],
    'uni07AF': [((348, 1235, 405, 1360), 34)],
    'uni0797': [((1080, 950, 1220, 1050), 26), ((1160, 990, 1210, 1050), 12)],
    'uni07A9': [((620, -330, 712, -262), 22)],
    'uni078A': [((440, -25, 575, 65), 20)],
    'uni078B': [((680, 630, 920, 710), 12)],
    'uni0793': [((560, 430, 660, 560), 6)],
}


# Aperture carving: subtract the target counter oval (cx, cy, a, b, tilt_deg) from the ink so each
# counter is at least that smooth rounded shape; guarded so it can never break a stroke.
CARVE = {
    'uni078C': [(767, 487, 96, 56, 15)],
    'uni0788': [(707, 509, 106, 66, 25)],
    'uni0784': [(418, 480, 100, 50, 34), (763, 516, 127, 40, 28)],
    'uni0793': [(492, 510, 99, 51, 36), (814, 512, 120, 42, 29)],
    'uni0797': [(794, 553, 92, 44, 13)],
}


def _carve(name, g):
    if name not in CARVE:
        return g
    from shapely.geometry import Point as _Pt
    from shapely import affinity as _af
    from shapely.geometry import Polygon as _P
    t0 = _topo(g)
    for (cx, cy, a, b, t) in CARVE[name]:
        e = _af.rotate(_af.scale(_Pt(cx, cy).buffer(1.0, quad_segs=32), a, b), t, origin=(cx, cy))
        polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
        holes = [_P(h) for p in polys for h in p.interiors]
        if not holes:
            continue
        h = min(holes, key=lambda q: q.distance(_Pt(cx, cy)) if not q.contains(_Pt(cx, cy)) else -1)
        g2 = g.union(h.buffer(0.5)).difference(e).buffer(0)   # counter becomes exactly the target oval
        if _topo(g2) == t0:
            g = g2
    return g


# Counter-corner rounding: morphological closing (radius r) confined to a window around the
# named extreme of the glyph's counter, so an acute counter nose becomes a round turn.
ROUND_COUNTER = {'uni078C': ('left', 24), 'uni0788': ('lowerleft', 40)}


def _round_counter(name, g):
    if name not in ROUND_COUNTER:
        return g
    from shapely.geometry import Polygon as _P, Point as _Pt
    where, r = ROUND_COUNTER[name]
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    holes = [_P(h) for p in polys for h in p.interiors]
    if not holes:
        return g
    h = max(holes, key=lambda q: q.area)
    pts = list(h.exterior.coords)
    if where == 'left':
        px, py = min(pts, key=lambda q: q[0])
    else:  # lower-left
        px, py = min(pts, key=lambda q: q[0] + q[1])
    W = _Pt(px, py).buffer(3 * r)
    closed = g.buffer(r, join_style=1, quad_segs=16).buffer(-r, join_style=1, quad_segs=16)
    return g.union(closed.intersection(W)).buffer(0)


# stronger rolling-ball smoothing (opening r, closing r) inside relief zones of the fili heels
SMOOTH_R = {'uni07AD': (40, 26), 'uni07AE': (20, 24), 'uni07AF': (40, 26)}


# Exact inner-edge cuts: (cx, cy, rx, ry, clip box) ellipse removed from the final outline, then
# a rolling-ball smoothing confined to the cut's neighbourhood so the new edge joins tangentially.
CUT = {
  'uni0782': [dict(fill=30, close=3, pts=[  # noonu: slot under the lip and the scoop floor near (1060, 556)
    (1072, 668), (1069, 655), (1065, 640), (1062, 630), (1057, 620), (1052, 610), (1046, 600), (1041, 590), (1036, 580),
    (1034, 570), (1037, 562), (1045, 557), (1055, 556), (1065, 557), (1075, 560), (1090, 566), (1100, 571), (1115, 580),
    (1130, 590), (1144, 600), (1156, 610), (1168, 620), (1179, 630), (1190, 640),
    (1240, 700), (1120, 735), (1085, 700)])],
  'uni078D': [dict(fill=30, close=5, smooth=(12, 3), pts=[  # laamu: branch rising into the upright, right recess, flat upper stroke
    (375, 495), (400, 510), (425, 519), (450, 526), (475, 532), (500, 538), (525, 545), (550, 556), (575, 568),
    (600, 581), (625, 595), (650, 611), (675, 628), (700, 648), (725, 673), (750, 705), (775, 721), (800, 726),
    (820, 725), (840, 716), (860, 702), (880, 682), (889, 665), (893, 650), (894, 635), (889, 620), (878, 605),
    (865, 590), (846, 575), (826, 560), (810, 546), (818, 541), (831, 545), (880, 550), (940, 557), (1000, 564),
    (1050, 569), (1073, 560), (1082, 550), (1088, 535), (1090, 515), (1088, 495), (1083, 472), (1070, 456),
    (1044, 440), (1000, 412), (950, 381),
    (900, 300), (1250, 350), (1200, 750), (600, 830), (330, 570)]),
    dict(fill=30, close=2, smooth=(12, 3), pts=[  # laamu: branch head and underside into the lower recess near (713, 398)
    (352, 462), (349, 445), (350, 425), (355, 402), (364, 386), (384, 371), (400, 366), (440, 366), (480, 368), (520, 371),
    (560, 377), (600, 382), (640, 387), (680, 392), (700, 395), (712, 398), (716, 400), (690, 385), (680, 379),
    (650, 360), (600, 327), (550, 296), (500, 264), (450, 234), (420, 215), (400, 203), (380, 191), (360, 179),
    (340, 168), (320, 156), (300, 144), (280, 132), (260, 120),
    (200, 220), (318, 440)])],
  'uni07AD': [dict(fill=30, close=3, pts=[  # eybeyfili: convex outside heel (reference arc, 12 units in)
    (332, 1030), (320, 1036), (302, 1050), (287, 1065), (273, 1080), (261, 1095), (251, 1110), (243, 1125), (236, 1140),
    (231, 1155), (227, 1170), (224, 1185), (224, 1200), (227, 1215), (232, 1230), (243, 1255), (257, 1285), (276, 1315),
    (287, 1330),
    (230, 1390), (150, 1200), (260, 985)])],
  'uni07AE': [dict(fill=30, close=3, pts=[  # obofili: rounded lower-left cap through the current x minimum
    (371, 1029), (351, 1032), (331, 1038), (324, 1040), (301, 1052), (287, 1064), (279, 1076), (274, 1088), (273, 1100),
    (273, 1112), (275, 1124), (278, 1136), (283, 1148), (290, 1160), (301, 1172), (320, 1184), (350, 1192), (401, 1196),
    (471, 1208),
    (430, 1238), (200, 1150), (290, 1000)])],
  'uni07AF': [dict(fill=30, close=4, pts=[  # oaboafili: one convex outside sweep of the lower-left loop
    (480, 1066), (460, 1073), (440, 1084), (420, 1102), (405, 1122), (394, 1142), (386, 1162), (381, 1182), (379, 1200),
    (378, 1220), (378.5, 1240), (380, 1260), (381.5, 1280), (383, 1300), (385, 1320), (387.5, 1340), (390.5, 1360),
    (394, 1380), (398.5, 1400), (404, 1420), (412, 1440), (427, 1460), (447, 1480), (469, 1500),
    (420, 1580), (300, 1300), (380, 1040), (520, 1040)])],
  'uni0797': [  # chaviyani: diagonal as one continuous taper (underside, tip, then upper edge blending into the pared zone)
    dict(fill=25, close=5, straight_close=True, pts=[
        (1100, 806), (1130, 822), (1160, 840), (1190, 857), (1220, 874), (1250, 890), (1280, 905), (1310, 920),
        (1340, 935), (1355, 942), (1370, 950), (1400, 965), (1430, 980), (1460, 995), (1478, 1006), (1490, 1018),
        (1497, 1040), (1498, 1060), (1495, 1080), (1487, 1100), (1473, 1120), (1460, 1131), (1445, 1136),
        (1430, 1137), (1415, 1134), (1400, 1130), (1370, 1117), (1340, 1102),
        (1360, 1260), (1650, 1150), (1650, 850), (1250, 730), (1110, 770)]),
    dict(fill=25, close=2, straight_close=True, pts=[
        (1415, 1134), (1400, 1130), (1370, 1117), (1340, 1102), (1310, 1086), (1280, 1071), (1250, 1055), (1240, 1047),
        (1225, 1037), (1210, 1025), (1195, 1012), (1180, 1000), (1165, 990), (1150, 984), (1135, 979), (1120, 975),
        (1105, 971), (1090, 967), (1075, 963), (1060, 959), (1045, 955), (1030, 951), (1015, 946), (1000, 938), (985, 930),
        (970, 922), (955, 913), (940, 905), (925, 897),
        (880, 1150), (1420, 1260)])],
  'afii57407': [dict(fill=40, close=3, trim_ends=False, pts=[
    (521, 600), (520, 680), (516, 700), (510, 740), (503, 780), (494, 820), (481, 860), (466, 900), (449, 940), (430, 980), (410, 1020),
    (390, 1060), (369, 1100), (349, 1140), (331, 1180), (316, 1220), (304, 1260), (298, 1290), (294, 1330), (293, 1370), (296, 1410), (304, 1450), (317, 1490), (339, 1530), (372, 1570),
    (420, 1607), (460, 1624), (540, 1634), (620, 1618), (660, 1595), (686, 1570), (705, 1540), (713, 1510), (710, 1480),
    (701, 1450), (687, 1420), (671, 1390), (658, 1360), (653, 1330), (658, 1300),
    (580, 1190), (600, 900), (620, 590)])]}


def _cut(name, g):
    """Set a counter edge exactly to a smooth closed spline: trim ink inside it, and (fill) close
    gaps up to `fill` units between the ink and the spline, then a confined rolling-ball pass."""
    if name not in CUT:
        return g
    from shapely.geometry import Polygon as _P
    t0 = _topo(g)
    for c in CUT[name]:
        pts = c['pts']
        if c.get('straight_close'):   # spline along the edge only; closing points joined by straight lines
            ne_ = len(pts) - c['close']
            e = _P([tuple(v) for v in _stroke.sample(_cr(pts[:ne_], 0.85), 3.0)] + list(pts[ne_:])).buffer(0)
        else:
            e = _P(_stroke.sample(_cr(pts + [pts[0]], 0.85), 3.0)).buffer(0)
        g2 = g
        if c.get('fill'):
            f = c['fill']
            band = e.buffer(f).difference(e).intersection(g.buffer(f))
            ne = len(pts) - c['close'] if 'close' in c else c.get('edge')
            if ne:
                from shapely.geometry import LineString as _L
                band = band.intersection(_L(_stroke.sample(_cr(pts[:ne], 0.85), 3.0)).buffer(f, cap_style=2))
                from shapely.geometry import Point as _Pt
                if c.get('trim_ends', True):   # stop the fill short of the edge ends (no closing-side blobs)
                    band = band.difference(_Pt(pts[0]).buffer(1.5 * f)).difference(_Pt(pts[ne - 1]).buffer(1.5 * f))
            g2 = g2.union(band)
        g2 = g2.difference(e)
        W = e.buffer(45)
        ro, rc = c.get('smooth', (18, 14))
        sm = g2.buffer(-ro, join_style=1, quad_segs=16).buffer(ro, join_style=1, quad_segs=16)
        sm = sm.buffer(rc, join_style=1, quad_segs=16).buffer(-rc, join_style=1, quad_segs=16)
        g2 = g2.difference(W).union(sm.intersection(W)).buffer(0)
        _ps = [g2] if g2.geom_type == 'Polygon' else list(g2.geoms)
        for _p in _ps:
            for _h in _p.interiors:
                if _P(_h).area < 2000 and _P(_h).intersects(W):
                    print('CUT pinhole', name, round(_P(_h).area), [round(v) for v in _P(_h).bounds])
                    g2 = g2.union(_P(_h).buffer(0.5))
        g2 = g2.buffer(0)
        if _topo(g2) == t0:
            g = g2
        else:
            print('CUT skipped (topology)', name, _topo(g2), t0)
    return g


def _pare(name, geoms):
    """Smooth local relief: erosion depth follows a smoothstep from 0 at an expanded margin to d at
    the window core, realised as 20 nested windows (steps < 1.5u) and a final rolling-ball smoothing,
    so the relieved edge is tangent-continuous with the untouched contour."""
    if name not in PARE:
        if name in ROUND_COUNTER or name in CARVE or name in CUT:
            return [_cut(name, _carve(name, _round_counter(name, _uu(geoms))))]
        return geoms
    from shapely.geometry import box as _box
    g = _uu(geoms)
    topo0 = _topo(g)
    for (bx0, by0, bx1, by1), d in PARE[name]:
        m = max(40, 0.45 * max(bx1 - bx0, by1 - by0))
        steps = 32
        g0 = g  # every step erodes the ORIGINAL outline (depths must not accumulate)
        for k in range(1, steps + 1):
            f = k / steps
            e = m * (1 - f)
            b = _box(bx0 - e, by0 - e, bx1 + e, by1 + e)
            dk = d * (f * f * (3 - 2 * f))   # smoothstep
            g = g.difference(b.difference(g0.buffer(-dk, join_style=1, quad_segs=16)))
        # rolling-ball smoothing confined to the relief zone (tips elsewhere untouched)
        W = _box(bx0 - m, by0 - m, bx1 + m, by1 + m)
        ro, rc = SMOOTH_R.get(name, (24, 14))
        sm = g.buffer(-ro, join_style=1, quad_segs=16).buffer(ro, join_style=1, quad_segs=16)
        sm = sm.buffer(rc, join_style=1, quad_segs=16).buffer(-rc, join_style=1, quad_segs=16)
        g = g.difference(W).union(sm.intersection(W)).buffer(0)
    if _topo(g) != topo0:
        raise ValueError(f'{name}: local relief changed outline topology {topo0} -> {_topo(g)}')
    g = _cut(name, _carve(name, _round_counter(name, g)))
    return [g]


def _topo(g):
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    polys = [p for p in polys if p.area > 50]
    return (len(polys), sum(len(p.interiors) for p in polys))


def _unused():
    def run():
        return None
    return run

GLYPHS = {n: _aligned(n, f) for n, f in G.items()}
