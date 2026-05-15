"""
LunarBase — Spaceport impérial procédural pour L2.
Bâtiments hauts + marquages au sol variés + collisions AABB.
"""

from panda3d.core import (
    Vec4,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomPoints, GeomNode,
    NodePath, TransparencyAttrib,
)
import random
import math

GROUND_Z = -7.8   # niveau du sol lunaire (== LunarTerrain.GROUND_Z)

# Pool de marquages au sol — chaque groupe tire sans remise sur les 2 derniers
_MARK_STYLES = ['runway', 'platform', 'grid', 'compound',
                'taxiway', 'perimeter', 'scattered', 'crossfire']
_last_marks  = []   # suivi global des 2 derniers styles utilisés


# ─────────────────────────────────────────────────────────────
# Helpers géométriques bas-niveau
# ─────────────────────────────────────────────────────────────

def _box_geom(hw, hd, hh, col_top, col_side, col_dark):
    """Boîte 5 faces (sans fond) centrée à l'origine."""
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("box", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    tris = GeomTriangles(Geom.UHStatic)
    idx  = [0]

    def quad(pts, col):
        for p in pts:
            vw.addData3(*p); cw.addData4(col)
        b = idx[0]
        tris.addVertices(b, b+1, b+2); tris.addVertices(b, b+2, b+3)
        idx[0] += 4

    quad([(-hw,-hd, hh),( hw,-hd, hh),( hw, hd, hh),(-hw, hd, hh)], col_top)
    quad([(-hw, hd,-hh),( hw, hd,-hh),( hw, hd, hh),(-hw, hd, hh)], col_side)
    quad([( hw,-hd,-hh),(-hw,-hd,-hh),(-hw,-hd, hh),( hw,-hd, hh)], col_dark)
    quad([( hw,-hd,-hh),( hw, hd,-hh),( hw, hd, hh),( hw,-hd, hh)], col_side)
    quad([(-hw, hd,-hh),(-hw,-hd,-hh),(-hw,-hd, hh),(-hw, hd, hh)], col_dark)

    geom = Geom(vd); geom.addPrimitive(tris)
    gn   = GeomNode("box"); gn.addGeom(geom)
    return NodePath(gn)


def _cylinder_geom(r, hh, col_side, col_top, sides=8):
    """Cylindre centré en Z."""
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("cyl", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    tris = GeomTriangles(Geom.UHStatic)

    vw.addData3(0, 0, hh); cw.addData4(col_top)
    for i in range(sides):
        a = 2*math.pi * i / sides
        vw.addData3(math.cos(a)*r, math.sin(a)*r,  hh); cw.addData4(col_side)
    for i in range(sides):
        a = 2*math.pi * i / sides
        vw.addData3(math.cos(a)*r, math.sin(a)*r, -hh); cw.addData4(col_side)

    for i in range(sides):
        tris.addVertices(0, 1+i, 1+(i+1)%sides)
    for i in range(sides):
        b0 = 1+sides+i;  b1 = 1+sides+(i+1)%sides
        t0 = 1+i;        t1 = 1+(i+1)%sides
        tris.addVertices(b0, t0, b1); tris.addVertices(b1, t0, t1)

    geom = Geom(vd); geom.addPrimitive(tris)
    gn   = GeomNode("cyl"); gn.addGeom(geom)
    return NodePath(gn)


def _beacon(x, y, z, color, size=4.0):
    """Point lumineux (balise)."""
    fmt = GeomVertexFormat.getV3c4()
    vd  = GeomVertexData("dot", fmt, Geom.UHStatic)
    vw  = GeomVertexWriter(vd, "vertex")
    cw  = GeomVertexWriter(vd, "color")
    vw.addData3(x, y, z); cw.addData4(color)
    pts = GeomPoints(Geom.UHStatic); pts.addVertex(0)
    geom = Geom(vd); geom.addPrimitive(pts)
    gn   = GeomNode("bcn"); gn.addGeom(geom)
    np   = NodePath(gn)
    np.setRenderModeThickness(size)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


# ─────────────────────────────────────────────────────────────
# Fabricants de bâtiments
# ─────────────────────────────────────────────────────────────

def _make_tower(hw, hd, h, rng):
    """Tour de contrôle — fine, très haute, beacon rouge."""
    root = NodePath("tower")
    b  = 0.28 + rng.uniform(0, 0.08)
    np = _box_geom(hw, hd, h/2,
                   Vec4(b,       b*0.98, b*0.95, 1),
                   Vec4(b*0.75,  b*0.74, b*0.72, 1),
                   Vec4(b*0.45,  b*0.44, b*0.43, 1))
    np.reparentTo(root)
    # Étage intermédiaire
    if h > 8:
        mid_h = h * 0.35
        mid = _box_geom(hw*1.6, hd*1.6, mid_h/2,
                        Vec4(b*0.88, b*0.86, b*0.83, 1),
                        Vec4(b*0.68, b*0.67, b*0.65, 1),
                        Vec4(b*0.40, b*0.39, b*0.38, 1))
        mid.reparentTo(root); mid.setPos(0, 0, mid_h/2 - mid_h*0.6)
    ant_h = h * 0.55
    ant   = _cylinder_geom(0.06, ant_h/2, Vec4(0.18,0.18,0.17,1), Vec4(0.15,0.15,0.14,1), sides=4)
    ant.reparentTo(root); ant.setPos(0, 0, h/2 + ant_h/2)
    _beacon(0, 0, h/2 + ant_h + 0.15, Vec4(1.0, 0.1, 0.1, 1.0), 6).reparentTo(root)
    root.setLightOff()
    return root


def _make_hangar(hw, hd, h, rng):
    """Hangar — large, haut, toit en double pente."""
    root = NodePath("hangar")
    b  = 0.26 + rng.uniform(0, 0.06)
    np = _box_geom(hw, hd, h/2,
                   Vec4(b*1.05, b,       b*0.96, 1),
                   Vec4(b*0.80, b*0.78,  b*0.75, 1),
                   Vec4(b*0.48, b*0.47,  b*0.45, 1))
    np.reparentTo(root)
    ridge_h = h * 0.25
    rc = Vec4(b*0.60, b*0.58, b*0.56, 1)
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("ridge", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex"); cw = GeomVertexWriter(vd, "color")
    tris = GeomTriangles(Geom.UHStatic)
    for sx in [-1, 1]:
        vw.addData3(sx*hw, -hd, h/2); cw.addData4(rc)
        vw.addData3(sx*hw,  hd, h/2); cw.addData4(rc)
        vw.addData3(0,     -hd, h/2+ridge_h); cw.addData4(rc)
        vw.addData3(0,      hd, h/2+ridge_h); cw.addData4(rc)
    for base in [0, 4]:
        tris.addVertices(base, base+2, base+1); tris.addVertices(base+1, base+2, base+3)
    geom2 = Geom(vd); geom2.addPrimitive(tris)
    gn2   = GeomNode("ridge"); gn2.addGeom(geom2)
    NodePath(gn2).reparentTo(root)
    root.setLightOff()
    return root


def _make_silo(r, h, rng):
    """Réservoir cylindrique avec bande orange + beacon."""
    root = NodePath("silo")
    b    = 0.30 + rng.uniform(0, 0.06)
    body = _cylinder_geom(r, h/2,
                          Vec4(b*0.82, b*0.80, b*0.78, 1),
                          Vec4(b,      b*0.98, b*0.95, 1), sides=10)
    body.reparentTo(root)
    band = _cylinder_geom(r*1.02, h*0.06,
                          Vec4(0.55, 0.35, 0.12, 0.9),
                          Vec4(0.55, 0.35, 0.12, 0.9), sides=10)
    band.reparentTo(root); band.setPos(0, 0, -h*0.1)
    # Deuxième bande haute
    band2 = _cylinder_geom(r*1.01, h*0.04,
                           Vec4(0.45, 0.28, 0.10, 0.8),
                           Vec4(0.45, 0.28, 0.10, 0.8), sides=10)
    band2.reparentTo(root); band2.setPos(0, 0, h*0.25)
    _beacon(0, 0, h/2+0.15, Vec4(1.0, 0.65, 0.1, 1.0), 5).reparentTo(root)
    root.setLightOff()
    return root


def _make_bunker(hw, hd, h, rng):
    """Bunker massif, fente de tir + tourelle si très haut."""
    root = NodePath("bunker")
    b  = 0.22 + rng.uniform(0, 0.05)
    np = _box_geom(hw, hd, h/2,
                   Vec4(b,      b*0.99, b*0.95, 1),
                   Vec4(b*0.70, b*0.69, b*0.67, 1),
                   Vec4(b*0.42, b*0.41, b*0.40, 1))
    np.reparentTo(root)
    slot = _box_geom(hw*0.55, 0.06, h*0.12,
                     Vec4(0.04,0.04,0.04,1), Vec4(0.04,0.04,0.04,1), Vec4(0.04,0.04,0.04,1))
    slot.reparentTo(root); slot.setPos(0, hd+0.02, 0)
    # Tourelle au sommet si assez grand
    if h > 3.5:
        turret = _cylinder_geom(hw*0.35, h*0.12,
                                Vec4(b*0.55, b*0.54, b*0.52, 1),
                                Vec4(b*0.45, b*0.44, b*0.42, 1), sides=6)
        turret.reparentTo(root); turret.setPos(0, 0, h/2 + h*0.12)
    root.setLightOff()
    return root


def _make_antenna_mast(r, h, rng):
    """Mât d'antenne fin avec bras horizontaux multiples."""
    root = NodePath("antenna")
    mast = _cylinder_geom(r, h/2, Vec4(0.20,0.20,0.19,1), Vec4(0.18,0.18,0.17,1), sides=4)
    mast.reparentTo(root)
    arm_len = r * 18
    for frac, angle in [(0.55, 0), (0.70, 45), (0.82, -30), (0.92, 15)]:
        arm = _cylinder_geom(r*0.6, arm_len/2, Vec4(0.18,0.18,0.17,1), Vec4(0.16,0.16,0.15,1), sides=4)
        arm.reparentTo(root)
        arm.setHpr(angle, 90, 0)
        arm.setPos(0, 0, h/2 * frac)
    _beacon(0, 0, h/2+0.12, Vec4(1.0, 0.15, 0.15, 1.0), 4).reparentTo(root)
    root.setLightOff()
    return root


def _make_landing_pad(r, rng):
    """Plate-forme hexagonale surélevée avec balises."""
    root  = NodePath("pad")
    SIDES = 6
    h_plat = 0.30
    fmt   = GeomVertexFormat.getV3c4()
    vd    = GeomVertexData("pad", fmt, Geom.UHStatic)
    vw    = GeomVertexWriter(vd, "vertex"); cw = GeomVertexWriter(vd, "color")
    tris  = GeomTriangles(Geom.UHStatic)
    col_top  = Vec4(0.28, 0.28, 0.27, 1)
    col_side = Vec4(0.20, 0.20, 0.19, 1)

    vw.addData3(0, 0, h_plat); cw.addData4(col_top)
    for i in range(SIDES):
        a = 2*math.pi*i/SIDES + math.pi/6
        vw.addData3(math.cos(a)*r, math.sin(a)*r, h_plat); cw.addData4(col_top)
    for i in range(SIDES):
        a = 2*math.pi*i/SIDES + math.pi/6
        vw.addData3(math.cos(a)*r, math.sin(a)*r, 0); cw.addData4(col_side)

    for i in range(SIDES):
        tris.addVertices(0, 1+i, 1+(i+1)%SIDES)
    for i in range(SIDES):
        t0 = 1+i; t1 = 1+(i+1)%SIDES; b0 = 7+i; b1 = 7+(i+1)%SIDES
        tris.addVertices(t0, b0, t1); tris.addVertices(t1, b0, b1)

    geom = Geom(vd); geom.addPrimitive(tris)
    gn   = GeomNode("pad_mesh"); gn.addGeom(geom)
    NodePath(gn).reparentTo(root)

    for i in range(SIDES):
        a = 2*math.pi*i/SIDES + math.pi/6
        cx, cy = math.cos(a)*r, math.sin(a)*r
        col = Vec4(0.1, 0.4, 1.0, 0.95) if i%2==0 else Vec4(1.0, 0.88, 0.1, 0.9)
        _beacon(cx, cy, h_plat+0.15, col, 3).reparentTo(root)

    # Croix centrale
    fmt2  = GeomVertexFormat.getV3c4()
    vd2   = GeomVertexData("cross", fmt2, Geom.UHStatic)
    vw2   = GeomVertexWriter(vd2, "vertex"); cw2 = GeomVertexWriter(vd2, "color")
    lns   = GeomLines(Geom.UHStatic)
    corc  = Vec4(0.85, 0.5, 0.1, 0.85)
    S = r * 0.6
    for (x1,y1,x2,y2) in [(-S,0,S,0),(0,-S,0,S)]:
        vw2.addData3(x1,y1,h_plat+0.04); cw2.addData4(corc)
        vw2.addData3(x2,y2,h_plat+0.04); cw2.addData4(corc)
    lns.addVertices(0,1); lns.addVertices(2,3)
    geom2 = Geom(vd2); geom2.addPrimitive(lns)
    gn2   = GeomNode("cross"); gn2.addGeom(geom2)
    cross_np = NodePath(gn2)
    cross_np.reparentTo(root)
    cross_np.setRenderModeThickness(2.0)
    cross_np.setTransparency(TransparencyAttrib.MAlpha)
    cross_np.setDepthOffset(1)

    root.setLightOff()
    return root


def _make_relay_tower(r, h, rng):
    """Tour relais cylindrique haute avec disque parabolique au sommet."""
    root = NodePath("relay")
    b    = 0.25 + rng.uniform(0, 0.05)
    body = _cylinder_geom(r, h/2,
                          Vec4(b*0.80, b*0.79, b*0.77, 1),
                          Vec4(b,      b*0.99, b*0.97, 1), sides=6)
    body.reparentTo(root)
    # Disque = cylindre très plat
    dish = _cylinder_geom(r*3.5, h*0.04,
                          Vec4(0.30, 0.28, 0.25, 0.9),
                          Vec4(0.38, 0.36, 0.33, 0.9), sides=12)
    dish.reparentTo(root); dish.setPos(0, 0, h/2 + h*0.06)
    dish.setHpr(rng.uniform(0,360), 0, 0)
    _beacon(0, 0, h/2+h*0.14, Vec4(1.0, 0.85, 0.1, 1.0), 5).reparentTo(root)
    root.setLightOff()
    return root


# ─────────────────────────────────────────────────────────────
# Marquages au sol
# ─────────────────────────────────────────────────────────────

def _make_ground_markings(parent, rng, style):
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("marks", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    lns  = GeomLines(Geom.UHStatic)
    idx  = [0]
    MZ   = GROUND_Z + 0.06

    def line(x1, y1, x2, y2, col):
        vw.addData3(x1, y1, MZ); cw.addData4(col)
        vw.addData3(x2, y2, MZ); cw.addData4(col)
        lns.addVertices(idx[0], idx[0]+1); idx[0] += 2

    def arc_approx(cx, cy, r, a_start, a_end, n, col):
        for i in range(n):
            t0 = a_start + (a_end-a_start)*i/n
            t1 = a_start + (a_end-a_start)*(i+1)/n
            line(cx+math.cos(t0)*r, cy+math.sin(t0)*r,
                 cx+math.cos(t1)*r, cy+math.sin(t1)*r, col)

    white  = Vec4(0.68, 0.70, 0.65, 0.80)
    orange = Vec4(0.85, 0.50, 0.08, 0.75)
    yellow = Vec4(0.85, 0.78, 0.15, 0.65)
    dim    = Vec4(0.38, 0.38, 0.36, 0.40)
    red    = Vec4(0.80, 0.18, 0.10, 0.60)

    if style == 'runway':
        # Piste centrale avec tirets et bords
        for xr in [-4.0, 4.0]:
            line(xr, -11, xr, 11, white)
        for dy in range(-10, 11, 3):
            line(0, dy, 0, dy+1.8, orange)
        for xr in [-3.2,-1.8,-0.5, 0.5, 1.8, 3.2]:
            line(xr, -10.5, xr, -8.5, white)
            line(xr,  8.5,  xr,  10.5, white)
        for xr in [-7.0, 7.0]:
            for dy in range(-8, 9, 4):
                line(xr, dy, xr, dy+2.2, yellow)

    elif style == 'platform':
        # Cercles concentriques + axes
        cx, cy = rng.uniform(-2, 2), rng.uniform(-2, 2)
        for R, col in [(6.5, white),(3.5, dim),(1.5, orange)]:
            arc_approx(cx, cy, R, 0, 2*math.pi, 20, col)
        S = 4.5
        line(cx-S, cy, cx+S, cy, orange); line(cx, cy-S, cx, cy+S, orange)
        for ang in [0, 90, 180, 270]:
            a = math.radians(ang)
            line(cx+math.cos(a)*3.5, cy+math.sin(a)*3.5,
                 cx+math.cos(a)*6.5,  cy+math.sin(a)*6.5, orange)

    elif style == 'grid':
        for xi in range(-4, 5):
            line(xi*2.2, -11, xi*2.2, 11, dim)
        for yi in range(-5, 6):
            line(-9.5, yi*2.1, 9.5, yi*2.1, dim)
        line(-9.5, 0, 9.5, 0, orange); line(0, -11, 0, 11, orange)
        for gx, gy in [(-4.4,-4.2),(4.4,-4.2),(-4.4,4.2),(4.4,4.2)]:
            S = 1.5
            line(gx-S, gy-S, gx+S, gy+S, yellow)
            line(gx+S, gy-S, gx-S, gy+S, yellow)

    elif style == 'compound':
        # Périmètre rectangulaire + subdivisions
        for xr in [-9.5, 9.5]:
            line(xr, -11, xr, 11, white)
        line(-9.5,-11, 9.5,-11, white); line(-9.5,11, 9.5,11, white)
        for xr in [-4.5, 0, 4.5]:
            line(xr,-11, xr,11, dim)
        for yr in [-5.5, 0, 5.5]:
            line(-9.5,yr, 9.5,yr, dim)
        # Triangles de pointage
        for (fx, fy) in [(-6,-8),(0,-8),(6,-8),(-6,8),(0,8),(6,8)]:
            line(fx-1.0, fy-1.4, fx, fy+1.4, orange)
            line(fx+1.0, fy-1.4, fx, fy+1.4, orange)

    elif style == 'taxiway':
        # Voies de circulation en L et T
        for xr in [-6.0, 6.0]:
            line(xr, -11, xr, 11, white)
        line(-6.0, 0, 6.0, 0, white)
        # Tirets de guidage le long des voies
        for dy in range(-10, 11, 2):
            for xr in [-6.0, 6.0]:
                line(xr-0.5, dy, xr+0.5, dy, orange)
        for dx in range(-5, 6, 2):
            line(dx, -0.5, dx, 0.5, orange)
        # Croix d'interdiction aux intersections
        for (cx2, cy2) in [(-6.0, 0.0), (6.0, 0.0)]:
            S = 0.7
            line(cx2-S, cy2-S, cx2+S, cy2+S, red)
            line(cx2+S, cy2-S, cx2-S, cy2+S, red)

    elif style == 'perimeter':
        # Lignes de périmètre de sécurité + pointage cardinal
        R_out = 10.0; R_in = 7.0
        arc_approx(0, 0, R_out, 0, 2*math.pi, 32, white)
        arc_approx(0, 0, R_in,  0, 2*math.pi, 28, dim)
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            col = orange if ang % 90 == 0 else yellow
            line(math.cos(a)*R_in, math.sin(a)*R_in,
                 math.cos(a)*R_out, math.sin(a)*R_out, col)
        # Croix centrale
        for S in [2.5, 4.0]:
            line(-S, 0, S, 0, orange); line(0, -S, 0, S, orange)

    elif style == 'scattered':
        # Marques éparpillées — numéros de zone + pointages aléatoires
        positions = [(-7,-7),(-7,0),(-7,7),(0,-8),(0,8),(7,-7),(7,0),(7,7)]
        rng2 = rng  # utilise le même RNG du groupe
        for (px2, py2) in positions:
            px2 += rng2.uniform(-1.2, 1.2); py2 += rng2.uniform(-1.2, 1.2)
            S = rng2.uniform(1.0, 2.2)
            col = rng2.choice([white, orange, yellow, dim])
            # Carré
            line(px2-S, py2-S, px2+S, py2-S, col)
            line(px2+S, py2-S, px2+S, py2+S, col)
            line(px2+S, py2+S, px2-S, py2+S, col)
            line(px2-S, py2+S, px2-S, py2-S, col)
        # Diagonale centrale
        line(-9, -10, 9, 10, dim); line(9, -10, -9, 10, dim)

    elif style == 'crossfire':
        # Étoile de lignes en diagonales + cercle
        cx, cy = rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5)
        for ang in range(0, 180, 30):
            a = math.radians(ang)
            R = 10.0
            line(cx-math.cos(a)*R, cy-math.sin(a)*R,
                 cx+math.cos(a)*R, cy+math.sin(a)*R, dim)
        arc_approx(cx, cy, 5.0, 0, 2*math.pi, 24, orange)
        arc_approx(cx, cy, 2.5, 0, 2*math.pi, 16, yellow)

    geom = Geom(vd); geom.addPrimitive(lns)
    gn   = GeomNode("ground_marks"); gn.addGeom(geom)
    np   = NodePath(gn)
    np.reparentTo(parent)
    np.setRenderModeThickness(1.8)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setDepthOffset(1)
    np.setLightOff()


def _pick_mark_style(rng):
    """Choisit un style de marquage sans répéter les 2 derniers."""
    global _last_marks
    pool = [s for s in _MARK_STYLES if s not in _last_marks]
    if not pool:
        pool = _MARK_STYLES[:]
    choice = rng.choice(pool)
    _last_marks = (_last_marks + [choice])[-2:]
    return choice


# ─────────────────────────────────────────────────────────────
# Classe principale
# ─────────────────────────────────────────────────────────────

# Pool de layouts — 9 patterns distincts, jamais les 2 derniers en succession
_LAYOUT_POOL = ['runway','platform','compound','tower_row',
                'industrial','fortress','outpost','depot','mixed']
_last_layouts = []


class LunarBaseGroup:
    """Section de spaceport impérial — bâtiments + marquages + hitboxes."""

    def __init__(self, game, y_pos, seed):
        self.alive     = True
        self.game      = game
        self._hitboxes = []

        self.node = NodePath("lunar_base")
        self.node.reparentTo(game.render)
        self.node.setPos(0, y_pos, 0)
        self.node.setLightOff()

        rng    = random.Random(seed)
        layout = self._pick_layout(rng)
        mark   = _pick_mark_style(rng)
        _make_ground_markings(self.node, rng, mark)
        getattr(self, f'_layout_{layout}')(rng)

    # ── Sélection anti-répétition ─────────────────────────────

    def _pick_layout(self, rng):
        global _last_layouts
        pool = [p for p in _LAYOUT_POOL if p not in _last_layouts]
        if not pool:
            pool = _LAYOUT_POOL[:]
        choice = rng.choice(pool)
        _last_layouts = (_last_layouts + [choice])[-2:]
        return choice

    # ── Ajout de bâtiment ────────────────────────────────────

    def _add(self, rng, lx, ly, style, scale=1.0):
        """Crée un bâtiment, l'attache au groupe et enregistre sa hitbox."""
        PARAMS = {
            'tower':   (0.55*scale, 0.55*scale, rng.uniform(8.0, 15.0)*scale),
            'hangar':  (rng.uniform(2.5,4.5)*scale, rng.uniform(3.0,5.5)*scale, rng.uniform(4.5, 8.0)*scale),
            'silo':    (rng.uniform(0.7,1.2)*scale, rng.uniform(0.7,1.2)*scale, rng.uniform(6.0,12.0)*scale),
            'bunker':  (rng.uniform(1.8,3.0)*scale, rng.uniform(1.8,3.0)*scale, rng.uniform(3.0, 6.0)*scale),
            'antenna': (0.10*scale, 0.10*scale, rng.uniform(10.0,18.0)*scale),
            'pad':     (rng.uniform(2.5,4.5)*scale, rng.uniform(2.5,4.5)*scale, 0.30),
            'relay':   (rng.uniform(0.4,0.7)*scale, rng.uniform(0.4,0.7)*scale, rng.uniform(7.0,13.0)*scale),
        }
        if style not in PARAMS:
            return
        hw, hd, h = PARAMS[style]

        MAKERS = {
            'tower':   lambda: _make_tower(hw, hd, h, rng),
            'hangar':  lambda: _make_hangar(hw, hd, h, rng),
            'silo':    lambda: _make_silo(hw, h, rng),
            'bunker':  lambda: _make_bunker(hw, hd, h, rng),
            'antenna': lambda: _make_antenna_mast(hw, h, rng),
            'pad':     lambda: _make_landing_pad(hw, rng),
            'relay':   lambda: _make_relay_tower(hw, h, rng),
        }
        mesh = MAKERS[style]()
        mesh.reparentTo(self.node)
        mesh.setPos(lx, ly, GROUND_Z + h/2)

        margin = 0.5
        self._hitboxes.append({'lx': lx, 'ly': ly, 'hw': hw+margin, 'hd': hd+margin, 'height': h})

    # ── Layouts ───────────────────────────────────────────────

    def _layout_runway(self, rng):
        """Piste centrale flanquée de tours hautes et silos."""
        for side in [-1, 1]:
            self._add(rng, side*rng.uniform(8.0, 12.0), rng.uniform(-4, 4), 'tower', scale=rng.uniform(1.0, 1.4))
            for _ in range(rng.randint(1, 2)):
                self._add(rng, side*rng.uniform(6,11), rng.uniform(-8,8), 'hangar')
            for _ in range(rng.randint(3, 5)):
                self._add(rng, side*rng.uniform(8,13), rng.uniform(-9,9), 'silo')
        for _ in range(rng.randint(3, 6)):
            ax = rng.uniform(-13, 13)
            if abs(ax) > 5:
                self._add(rng, ax, rng.uniform(-10,10), 'antenna')

    def _layout_platform(self, rng):
        """Pad central entouré de bunkers et relais."""
        cx, cy = rng.uniform(-2,2), rng.uniform(-2,2)
        self._add(rng, cx, cy, 'pad', scale=1.3)
        self._add(rng, cx+rng.uniform(7,11), cy+rng.uniform(-3,3), 'tower', scale=1.4)
        self._add(rng, cx-rng.uniform(7,11), cy+rng.uniform(-3,3), 'relay', scale=1.2)
        for ang in [40, 130, 220, 310]:
            r2 = rng.uniform(7, 11)
            a  = math.radians(ang + rng.uniform(-20,20))
            self._add(rng, cx+math.cos(a)*r2, cy+math.sin(a)*r2, rng.choice(['bunker','silo','relay']))
        for _ in range(4):
            ax = rng.uniform(-12,12)
            if abs(ax) > 5:
                self._add(rng, ax, rng.uniform(-9,9), 'antenna')

    def _layout_compound(self, rng):
        """Grande base — 2 hangars massifs, silos multiples, tours aux coins."""
        for side in [-1,1]:
            self._add(rng, side*rng.uniform(8,12), rng.uniform(-5,5), 'hangar', scale=rng.uniform(1.1,1.4))
        for i in range(rng.randint(4,7)):
            sx = rng.choice([-1,1]) * rng.uniform(8,14)
            self._add(rng, sx, -9+i*3.5+rng.uniform(-0.5,0.5), 'silo')
        for _ in range(rng.randint(2,4)):
            self._add(rng, rng.choice([-1,1])*rng.uniform(5,11), rng.uniform(-9,9), 'bunker')
        for side in [-1,1]:
            for ty in [-8, 8]:
                self._add(rng, side*rng.uniform(9,13), ty, 'tower', scale=rng.uniform(1.0,1.3))
        for _ in range(rng.randint(3,5)):
            ax = rng.uniform(-13,13)
            if abs(ax) > 5:
                self._add(rng, ax, rng.uniform(-10,10), 'antenna')

    def _layout_tower_row(self, rng):
        """Rangées de tours imposantes des deux côtés."""
        for side in [-1,1]:
            n = rng.randint(5,7)
            for i in range(n):
                tx = side * rng.uniform(8,12)
                ty = -10 + i*(20.0/max(n-1,1)) + rng.uniform(-0.6,0.6)
                t  = rng.choice(['tower','tower','silo','relay'])
                sc = rng.uniform(1.0, 1.5)
                self._add(rng, tx, ty, t, scale=sc)
            self._add(rng, side*rng.uniform(9,13), rng.uniform(-6,6), 'hangar', scale=1.2)
        for _ in range(rng.randint(2,4)):
            ax = rng.uniform(-14,14)
            if abs(ax) > 6:
                self._add(rng, ax, rng.uniform(-9,9), 'antenna')

    def _layout_industrial(self, rng):
        """Zone industrielle dense — silos serrés, bunkers, relais."""
        # Cluster de silos côté gauche
        for i in range(rng.randint(4,6)):
            self._add(rng, -rng.uniform(7,14), -6+i*2.8+rng.uniform(-0.4,0.4), 'silo', scale=rng.uniform(1.0,1.5))
        # Rangée de bunkers au centre
        for i in range(rng.randint(3,5)):
            self._add(rng, rng.uniform(-3,3), -8+i*4.5+rng.uniform(-0.5,0.5), 'bunker', scale=rng.uniform(1.1,1.4))
        # Relais côté droit
        for _ in range(rng.randint(2,3)):
            self._add(rng, rng.uniform(7,13), rng.uniform(-9,9), 'relay', scale=rng.uniform(1.0,1.3))
        for _ in range(rng.randint(2,3)):
            self._add(rng, rng.uniform(-13,13), rng.uniform(-10,10), 'antenna')

    def _layout_fortress(self, rng):
        """Forteresse — 4 tours aux coins, hangars et bunkers intérieurs."""
        corners = [(-1,-1),(-1,1),(1,-1),(1,1)]
        for (sx, sy) in corners:
            tx = sx * rng.uniform(9,13)
            ty = sy * rng.uniform(7,11)
            self._add(rng, tx, ty, 'tower', scale=rng.uniform(1.3, 1.8))
        # Murs de bunkers entre les tours
        for i in range(rng.randint(3,5)):
            self._add(rng, rng.uniform(-8,8), -9+i*4.5, 'bunker', scale=rng.uniform(1.2,1.6))
        # Centre : pad + relais
        self._add(rng, rng.uniform(-2,2), rng.uniform(-2,2), 'pad', scale=1.1)
        self._add(rng, rng.uniform(3,6),  rng.uniform(-3,3), 'relay')
        for _ in range(rng.randint(2,4)):
            ax = rng.uniform(-14,14)
            if abs(ax) > 5:
                self._add(rng, ax, rng.uniform(-10,10), 'antenna')

    def _layout_outpost(self, rng):
        """Avant-poste léger — quelques structures isolées, beaucoup d'espace."""
        # 1 tour très haute au centre
        self._add(rng, rng.uniform(-3,3), rng.uniform(-3,3), 'tower', scale=1.8)
        # Quelques silos épars
        for _ in range(rng.randint(3,5)):
            angle = rng.uniform(0, 2*math.pi)
            r2    = rng.uniform(7, 14)
            self._add(rng, math.cos(angle)*r2, math.sin(angle)*r2,
                      rng.choice(['silo','relay','bunker']))
        for _ in range(rng.randint(4,6)):
            ax = rng.uniform(-14,14)
            if abs(ax) > 4:
                self._add(rng, ax, rng.uniform(-10,10), 'antenna', scale=rng.uniform(0.9,1.4))

    def _layout_depot(self, rng):
        """Dépôt logistique — rangées de hangars + silos alignés."""
        # Deux rangées de hangars parallèles
        for side in [-1,1]:
            for i in range(rng.randint(2,3)):
                hy = -6 + i*7.0 + rng.uniform(-0.5,0.5)
                self._add(rng, side*rng.uniform(6,10), hy, 'hangar', scale=rng.uniform(1.0,1.3))
        # Silos entre les rangées
        for i in range(rng.randint(4,6)):
            self._add(rng, rng.uniform(-4,4), -9+i*3.8+rng.uniform(-0.3,0.3), 'silo')
        # Relais au fond
        for side in [-1,1]:
            self._add(rng, side*rng.uniform(10,14), rng.uniform(-5,5), 'relay', scale=1.1)
        for _ in range(2):
            self._add(rng, rng.uniform(-14,14), rng.uniform(-10,10), 'antenna')

    def _layout_mixed(self, rng):
        """Mélange runway + pad + bunkers aléatoires."""
        self._layout_runway(rng)
        self._add(rng, rng.choice([-1,1])*rng.uniform(5,10), rng.uniform(-6,6), 'pad')
        for _ in range(2):
            self._add(rng, rng.choice([-1,1])*rng.uniform(6,11), rng.uniform(-8,8), 'bunker')
        self._add(rng, rng.uniform(-12,12), rng.uniform(-8,8), 'relay')

    # ── Collision ─────────────────────────────────────────────

    def check_collision(self, player_pos):
        if not self.alive or self.node.isEmpty():
            return 0, 0.0
        group_y = self.node.getY()
        for hb in self._hitboxes:
            world_y = group_y + hb['ly']
            world_x = hb['lx']
            bz_bot  = GROUND_Z - 0.5
            bz_top  = GROUND_Z + hb['height'] + 0.6
            dy = abs(player_pos.getY() - world_y)
            if dy > hb['hd'] + 1.5: continue
            dx = abs(player_pos.getX() - world_x)
            if dx > hb['hw']: continue
            if player_pos.getZ() > bz_top or player_pos.getZ() < bz_bot: continue
            sign_x = 1.0 if player_pos.getX() >= world_x else -1.0
            push_x = sign_x * (hb['hw'] - dx + 0.6)
            return 2, push_x
        return 0, 0.0

    # ── Update / Destroy ──────────────────────────────────────

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -60:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()
