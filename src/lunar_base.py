"""
LunarBase — Spaceport impérial procédural pour L2.
Bâtiments hauts + marquages au sol variés + collisions AABB.
"""

from panda3d.core import (
    Vec4,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomPoints, GeomNode,
    NodePath, TransparencyAttrib, ColorBlendAttrib, TextNode,
)
import random
import math
from src.settings import LUNAR, BUILDING_TYPES, LAYOUTS

GROUND_Z = -7.8   # niveau du sol lunaire (== LunarTerrain.GROUND_Z)

# Pool de marquages au sol — chaque groupe tire sans remise sur les 2 derniers
_MARK_STYLES = ['runway', 'platform', 'grid', 'compound',
                'taxiway', 'perimeter', 'scattered', 'crossfire']
_last_marks  = []   # suivi global des 2 derniers styles utilisés


# ─────────────────────────────────────────────────────────────
# GeomBatch — accumule boîtes + cylindres dans 1 seul GeomNode
# ─────────────────────────────────────────────────────────────

class _GeomBatch:
    """Accumule de la géométrie opaque et émet 1 seul NodePath.
    Chaque bâtiment utilise 1 instance → 1 draw call au lieu de 3-5."""

    def __init__(self):
        fmt       = GeomVertexFormat.getV3c4()
        self._vd  = GeomVertexData("batch", fmt, Geom.UHStatic)
        self._vw  = GeomVertexWriter(self._vd, "vertex")
        self._cw  = GeomVertexWriter(self._vd, "color")
        self._tri = GeomTriangles(Geom.UHStatic)
        self._vi  = 0

    def box(self, ox, oy, oz, hw, hd, hh, col_top, col_side, col_dark):
        """Boîte 5 faces (sans fond) centrée en (ox,oy,oz)."""
        def quad(pts, col):
            for p in pts:
                self._vw.addData3(ox+p[0], oy+p[1], oz+p[2])
                self._cw.addData4(col)
            b = self._vi
            self._tri.addVertices(b,b+1,b+2); self._tri.addVertices(b,b+2,b+3)
            self._vi += 4
        quad([(-hw,-hd,hh),(hw,-hd,hh),(hw,hd,hh),(-hw,hd,hh)],   col_top)
        quad([(-hw,hd,-hh),(hw,hd,-hh),(hw,hd,hh),(-hw,hd,hh)],   col_side)
        quad([(hw,-hd,-hh),(-hw,-hd,-hh),(-hw,-hd,hh),(hw,-hd,hh)], col_dark)
        quad([(hw,-hd,-hh),(hw,hd,-hh),(hw,hd,hh),(hw,-hd,hh)],   col_side)
        quad([(-hw,hd,-hh),(-hw,-hd,-hh),(-hw,-hd,hh),(-hw,hd,hh)], col_dark)

    def cylinder(self, ox, oy, oz, r, hh, col_side, col_top, sides=8):
        """Cylindre centré en (ox,oy,oz)."""
        base = self._vi
        self._vw.addData3(ox, oy, oz+hh); self._cw.addData4(col_top)
        for i in range(sides):
            a = 2*math.pi*i/sides
            self._vw.addData3(ox+math.cos(a)*r, oy+math.sin(a)*r, oz+hh)
            self._cw.addData4(col_side)
        for i in range(sides):
            a = 2*math.pi*i/sides
            self._vw.addData3(ox+math.cos(a)*r, oy+math.sin(a)*r, oz-hh)
            self._cw.addData4(col_side)
        for i in range(sides):
            self._tri.addVertices(base, base+1+i, base+1+(i+1)%sides)
        for i in range(sides):
            b0=base+1+sides+i; b1=base+1+sides+(i+1)%sides
            t0=base+1+i;       t1=base+1+(i+1)%sides
            self._tri.addVertices(b0,t0,b1); self._tri.addVertices(b1,t0,t1)
        self._vi += 1 + 2*sides

    def emit(self, name="body"):
        """Émet un NodePath avec 1 seul GeomNode — 1 draw call."""
        geom = Geom(self._vd); geom.addPrimitive(self._tri)
        gn   = GeomNode(name); gn.addGeom(geom)
        np   = NodePath(gn);   np.setLightOff()
        return np


# ─────────────────────────────────────────────────────────────
# Couleurs néon impériales
# ─────────────────────────────────────────────────────────────
_NEON_ORANGE = Vec4(0.95, 0.45, 0.05, 1.0)
_NEON_RED    = Vec4(0.95, 0.10, 0.08, 1.0)
_NEON_BLUE   = Vec4(0.25, 0.65, 1.00, 0.90)
_NEON_WHITE  = Vec4(0.85, 0.92, 1.00, 0.75)

# Codes d'identification impériaux
_CODES_TOWER  = [f"TW-{i:02d}"  for i in range(1, 30)]
_CODES_HANGAR = ([f"BAY {i}"    for i in range(1, 10)] +
                 [f"HGR-{i:02d}" for i in range(10, 20)])
_CODES_BUNKER = ([f"SEC-{i:02d}" for i in range(1, 20)] +
                 [f"POST {i}"   for i in range(1, 8)])


def _neon_attrib(np, thick, alpha, additive=False):
    """Applique épaisseur + transparence + blending additif optionnel."""
    np.setRenderModeThickness(thick)
    np.setLightOff()
    np.setDepthWrite(False)
    np.setDepthOffset(-1)
    np.setTransparency(TransparencyAttrib.MAlpha)
    if additive:
        np.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OIncomingAlpha,
            ColorBlendAttrib.OOne,
        ))


def _build_box_lines(hw, hd, hh, z_list, color, off):
    """Géométrie brute des 4 segments horizontaux autour d'une boîte."""
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("neon", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    lns  = GeomLines(Geom.UHStatic)
    vi   = [0]

    def seg(p0, p1):
        vw.addData3(*p0); cw.addData4(color)
        vw.addData3(*p1); cw.addData4(color)
        lns.addVertices(vi[0], vi[0] + 1); vi[0] += 2

    for z in z_list:
        seg((-hw, -hd - off, z), ( hw, -hd - off, z))
        seg(( hw,  hd + off, z), (-hw,  hd + off, z))
        seg(( hw + off, -hd, z), ( hw + off,  hd, z))
        seg((-hw - off,  hd, z), (-hw - off, -hd, z))

    geom = Geom(vd); geom.addPrimitive(lns)
    gn   = GeomNode("neon_lines"); gn.addGeom(geom)
    return NodePath(gn)


def _build_cyl_lines(r, z, color, off, sides):
    """Géométrie brute d'un anneau circulaire."""
    R    = r + off
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("neon_cyl", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    lns  = GeomLines(Geom.UHStatic)
    for i in range(sides):
        a0 = 2 * math.pi * i / sides
        a1 = 2 * math.pi * (i + 1) / sides
        vw.addData3(math.cos(a0) * R, math.sin(a0) * R, z); cw.addData4(color)
        vw.addData3(math.cos(a1) * R, math.sin(a1) * R, z); cw.addData4(color)
        lns.addVertices(i * 2, i * 2 + 1)
    geom = Geom(vd); geom.addPrimitive(lns)
    gn   = GeomNode("neon_cring"); gn.addGeom(geom)
    return NodePath(gn)


def _build_rect_lines(hw, hh, color, off):
    """Géométrie brute d'un cadre rectangulaire plan XZ."""
    fmt  = GeomVertexFormat.getV3c4()
    vd   = GeomVertexData("frame", fmt, Geom.UHStatic)
    vw   = GeomVertexWriter(vd, "vertex")
    cw   = GeomVertexWriter(vd, "color")
    lns  = GeomLines(Geom.UHStatic)
    corners = [
        (-hw - off, 0, -hh - off),
        ( hw + off, 0, -hh - off),
        ( hw + off, 0,  hh + off),
        (-hw - off, 0,  hh + off),
    ]
    for i in range(4):
        for p in (corners[i], corners[(i + 1) % 4]):
            vw.addData3(*p); cw.addData4(color)
        lns.addVertices(i * 2, i * 2 + 1)
    geom = Geom(vd); geom.addPrimitive(lns)
    gn   = GeomNode("neon_frame"); gn.addGeom(geom)
    return NodePath(gn)


def _c(color, alpha):
    """Couleur avec alpha modifié."""
    return Vec4(color.getX(), color.getY(), color.getZ(), alpha)


# ─────────────────────────────────────────────────────────────
# NeonLineBatch — accumule TOUS les neons d'un groupe en 2 NodePaths
# BeaconBatch   — accumule toutes les balises en 1 NodePath
# Résultat : ~60 draw calls transparents → 3 par groupe
# ─────────────────────────────────────────────────────────────

class _NeonLineBatch:
    """Accumule les lignes néon de tous les bâtiments d'un groupe.
    Émet core (fin, opaque) + glow (épais, additif) = 2 draw calls."""

    def __init__(self):
        fmt       = GeomVertexFormat.getV3c4()
        self._vc  = GeomVertexData("neon_core", fmt, Geom.UHStatic)
        self._wvc = GeomVertexWriter(self._vc, "vertex")
        self._cwc = GeomVertexWriter(self._vc, "color")
        self._lnc = GeomLines(Geom.UHStatic)
        self._ic  = 0
        self._vg  = GeomVertexData("neon_glow", fmt, Geom.UHStatic)
        self._wvg = GeomVertexWriter(self._vg, "vertex")
        self._cwg = GeomVertexWriter(self._vg, "color")
        self._lng = GeomLines(Geom.UHStatic)
        self._ig  = 0

    def _sc(self, p0, p1, col):
        self._wvc.addData3(*p0); self._cwc.addData4(col)
        self._wvc.addData3(*p1); self._cwc.addData4(col)
        self._lnc.addVertices(self._ic, self._ic + 1); self._ic += 2

    def _sg(self, p0, p1, col):
        self._wvg.addData3(*p0); self._cwg.addData4(col)
        self._wvg.addData3(*p1); self._cwg.addData4(col)
        self._lng.addVertices(self._ig, self._ig + 1); self._ig += 2

    def box_rings(self, ox, oy, oz, hw, hd, z_list, color):
        """Anneaux horizontaux — oz=centre bâtiment, z_list relatif à oz."""
        co = Vec4(color.getX(), color.getY(), color.getZ(), 1.00)
        cg = Vec4(color.getX(), color.getY(), color.getZ(), 0.22)
        for z in z_list:
            wz = oz + z
            self._sc((ox-hw,       oy-hd-0.025, wz), (ox+hw,       oy-hd-0.025, wz), co)
            self._sc((ox+hw,       oy+hd+0.025, wz), (ox-hw,       oy+hd+0.025, wz), co)
            self._sc((ox+hw+0.025, oy-hd,       wz), (ox+hw+0.025, oy+hd,       wz), co)
            self._sc((ox-hw-0.025, oy+hd,       wz), (ox-hw-0.025, oy-hd,       wz), co)
            self._sg((ox-hw,       oy-hd-0.07,  wz), (ox+hw,       oy-hd-0.07,  wz), cg)
            self._sg((ox+hw,       oy+hd+0.07,  wz), (ox-hw,       oy+hd+0.07,  wz), cg)
            self._sg((ox+hw+0.07,  oy-hd,       wz), (ox+hw+0.07,  oy+hd,       wz), cg)
            self._sg((ox-hw-0.07,  oy+hd,       wz), (ox-hw-0.07,  oy-hd,       wz), cg)

    def cyl_ring(self, ox, oy, oz, r, z_off, color, sides=12):
        """Anneau circulaire — z_off relatif à oz."""
        co = Vec4(color.getX(), color.getY(), color.getZ(), 1.00)
        cg = Vec4(color.getX(), color.getY(), color.getZ(), 0.22)
        wz = oz + z_off; rc = r + 0.030; rg = r + 0.085
        for i in range(sides):
            a0 = 2*math.pi*i/sides; a1 = 2*math.pi*(i+1)/sides
            self._sc((ox+math.cos(a0)*rc, oy+math.sin(a0)*rc, wz),
                     (ox+math.cos(a1)*rc, oy+math.sin(a1)*rc, wz), co)
            self._sg((ox+math.cos(a0)*rg, oy+math.sin(a0)*rg, wz),
                     (ox+math.cos(a1)*rg, oy+math.sin(a1)*rg, wz), cg)

    def rect_frame(self, ox, oy_face, oz, hw, hh, color):
        """Cadre XZ à oy_face — oz=centre Z du cadre."""
        co = Vec4(color.getX(), color.getY(), color.getZ(), 1.00)
        cg = Vec4(color.getX(), color.getY(), color.getZ(), 0.22)
        cc = [(ox-hw-0.025, oy_face, oz-hh-0.025), (ox+hw+0.025, oy_face, oz-hh-0.025),
              (ox+hw+0.025, oy_face, oz+hh+0.025), (ox-hw-0.025, oy_face, oz+hh+0.025)]
        gc = [(ox-hw-0.07,  oy_face, oz-hh-0.07),  (ox+hw+0.07,  oy_face, oz-hh-0.07),
              (ox+hw+0.07,  oy_face, oz+hh+0.07),  (ox-hw-0.07,  oy_face, oz+hh+0.07)]
        for i in range(4):
            self._sc(cc[i], cc[(i+1)%4], co)
            self._sg(gc[i], gc[(i+1)%4], cg)

    def emit(self, parent):
        """Émet core + glow dans parent — 2 draw calls transparents."""
        for vd, lns, cnt, name, thick, additive in [
            (self._vc, self._lnc, self._ic, "neon_core", 2.5, False),
            (self._vg, self._lng, self._ig, "neon_glow", 3.0, True),
        ]:
            if cnt == 0:
                continue
            geom = Geom(vd); geom.addPrimitive(lns)
            gn   = GeomNode(name); gn.addGeom(geom)
            np   = NodePath(gn)
            np.setRenderModeThickness(thick)
            np.setLightOff()
            np.setDepthWrite(False)
            np.setDepthOffset(-1)
            np.setTransparency(TransparencyAttrib.MAlpha)
            if additive:
                np.setAttrib(ColorBlendAttrib.make(
                    ColorBlendAttrib.MAdd,
                    ColorBlendAttrib.OIncomingAlpha,
                    ColorBlendAttrib.OOne,
                ))
            np.reparentTo(parent)


class _BeaconBatch:
    """Accumule les balises lumineuses d'un groupe — 1 draw call."""

    def __init__(self):
        fmt       = GeomVertexFormat.getV3c4()
        self._vd  = GeomVertexData("bcn_bat", fmt, Geom.UHStatic)
        self._vw  = GeomVertexWriter(self._vd, "vertex")
        self._cw  = GeomVertexWriter(self._vd, "color")
        self._pts = GeomPoints(Geom.UHStatic)
        self._vi  = 0

    def add(self, x, y, z, color):
        self._vw.addData3(x, y, z); self._cw.addData4(color)
        self._pts.addVertex(self._vi); self._vi += 1

    def emit(self, parent, size=5.0):
        if self._vi == 0:
            return
        geom = Geom(self._vd); geom.addPrimitive(self._pts)
        gn   = GeomNode("beacons"); gn.addGeom(geom)
        np   = NodePath(gn)
        np.setRenderModeThickness(size)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setLightOff()
        np.reparentTo(parent)


def _neon_box_rings(hw, hd, hh, z_list, color, thick=2.5):
    """Anneau néon avec 2 couches (core + glow). Bloom supprimé — perf."""
    root = NodePath("neon_box_grp")
    layers = [
        (0.025, thick,       1.00, False),
        (0.070, thick * 3.5, 0.22, True),
    ]
    for off, t, a, add in layers:
        np = _build_box_lines(hw, hd, hh, z_list, _c(color, a), off)
        _neon_attrib(np, t, a, add)
        np.reparentTo(root)
    return root


def _neon_cyl_ring(r, z, color, thick=2.5, sides=12):
    """Anneau cylindrique néon avec 2 couches (core + glow). Bloom supprimé — perf."""
    root = NodePath("neon_cyl_grp")
    layers = [
        (0.030, thick,       1.00, False),
        (0.085, thick * 3.5, 0.22, True),
    ]
    for off, t, a, add in layers:
        np = _build_cyl_lines(r, z, _c(color, a), off, sides)
        _neon_attrib(np, t, a, add)
        np.reparentTo(root)
    return root


def _neon_rect_frame(hw, hh, color, thick=2.5):
    """Cadre rectangulaire néon avec 2 couches (core + glow). Bloom supprimé — perf."""
    root = NodePath("neon_rect_grp")
    layers = [
        (0.025, thick,       1.00, False),
        (0.070, thick * 3.5, 0.22, True),
    ]
    for off, t, a, add in layers:
        np = _build_rect_lines(hw, hh, _c(color, a), off)
        _neon_attrib(np, t, a, add)
        np.reparentTo(root)
    return root


_STAR_JEDI_FONT = None

def _get_star_jedi_font():
    """Charge StarJedi.ttf une seule fois (lazy, évite les imports circulaires)."""
    global _STAR_JEDI_FONT
    if _STAR_JEDI_FONT is None:
        try:
            from panda3d.core import FontPool
            _STAR_JEDI_FONT = FontPool.loadFont("assets/fonts/StarJedi.ttf")
        except Exception:
            pass   # Fallback : police par défaut
    return _STAR_JEDI_FONT


def _imperial_label(text, size=0.28, color=(0.90, 0.55, 0.12, 0.90)):
    """Label texte style impérial — billboard face caméra, police Star Jedi."""
    tn = TextNode("imp_label")
    tn.setText(text)
    tn.setAlign(TextNode.ACenter)
    tn.setTextColor(*color)
    font = _get_star_jedi_font()
    if font:
        tn.setFont(font)
    np = NodePath(tn)
    np.setScale(size)
    np.setLightOff()
    np.setBillboardPointEye()
    return np


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

def _make_tower(hw, hd, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Tour de contrôle — 1 draw call opaque (batch corps+antenne)."""
    root = NodePath("tower")
    b    = 0.28 + rng.uniform(0, 0.08)
    bat  = _GeomBatch()
    bat.box(0, 0, 0, hw, hd, h/2,
            Vec4(b, b*0.98, b*0.95, 1),
            Vec4(b*0.75, b*0.74, b*0.72, 1),
            Vec4(b*0.45, b*0.44, b*0.43, 1))
    if h > 8:
        mid_h = h * 0.35
        bat.box(0, 0, mid_h/2 - mid_h*0.6, hw*1.6, hd*1.6, mid_h/2,
                Vec4(b*0.88, b*0.86, b*0.83, 1),
                Vec4(b*0.68, b*0.67, b*0.65, 1),
                Vec4(b*0.40, b*0.39, b*0.38, 1))
    ant_h = h * 0.55
    bat.cylinder(0, 0, h/2 + ant_h/2, 0.06, ant_h/2,
                 Vec4(0.18,0.18,0.17,1), Vec4(0.15,0.15,0.14,1), sides=4)
    bat.emit("tower_body").reparentTo(root)
    z_list = [-h/2 + h*0.28, -h/2 + h*0.52, -h/2 + h*0.78]
    if bb is not None:
        bb.add(ox, oy, oz + h/2 + ant_h + 0.15, Vec4(1.0, 0.1, 0.1, 1.0))
    else:
        _beacon(0, 0, h/2 + ant_h + 0.15, Vec4(1.0, 0.1, 0.1, 1.0), 6).reparentTo(root)
    if nc is not None:
        nc.box_rings(ox, oy, oz, hw, hd, z_list, _NEON_ORANGE)
    else:
        _neon_box_rings(hw, hd, h/2, z_list, _NEON_ORANGE).reparentTo(root)
    lbl = _imperial_label(rng.choice(_CODES_TOWER))
    lbl.reparentTo(root); lbl.setPos(0, -hd - 0.05, -h/2 + h * 0.12)
    root.setLightOff()
    return root


def _make_hangar(hw, hd, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Hangar — 1 draw call opaque (batch corps+faîtage)."""
    root    = NodePath("hangar")
    b       = 0.26 + rng.uniform(0, 0.06)
    ridge_h = h * 0.25
    rc      = Vec4(b*0.60, b*0.58, b*0.56, 1)
    bat     = _GeomBatch()
    bat.box(0, 0, 0, hw, hd, h/2,
            Vec4(b*1.05, b, b*0.96, 1),
            Vec4(b*0.80, b*0.78, b*0.75, 1),
            Vec4(b*0.48, b*0.47, b*0.45, 1))
    # Faîtage (ridge) ajouté manuellement au batch
    vw, cw, tri = bat._vw, bat._cw, bat._tri
    for sx in [-1, 1]:
        vw.addData3(sx*hw, -hd, h/2);       cw.addData4(rc)
        vw.addData3(sx*hw,  hd, h/2);       cw.addData4(rc)
        vw.addData3(0,     -hd, h/2+ridge_h); cw.addData4(rc)
        vw.addData3(0,      hd, h/2+ridge_h); cw.addData4(rc)
    for base in [bat._vi, bat._vi + 4]:
        tri.addVertices(base, base+2, base+1); tri.addVertices(base+1, base+2, base+3)
    bat._vi += 8
    bat.emit("hangar_body").reparentTo(root)
    if nc is not None:
        nc.box_rings(ox, oy, oz, hw, hd, [h/2 - 0.12],         _NEON_ORANGE)
        nc.box_rings(ox, oy, oz, hw, hd, [-h/2 + h*0.42],      _NEON_BLUE)
        nc.rect_frame(ox, oy - hd - 0.04, oz + (-h/2 + h*0.42), hw*0.75, h*0.42, _NEON_BLUE)
    else:
        _neon_box_rings(hw, hd, h/2, [h/2 - 0.12], _NEON_ORANGE, thick=3.0).reparentTo(root)
        _neon_box_rings(hw, hd, h/2, [-h/2 + h*0.42], _NEON_BLUE, thick=2.0).reparentTo(root)
        door_frame = _neon_rect_frame(hw * 0.75, h * 0.42, _NEON_BLUE, thick=2.5)
        door_frame.reparentTo(root); door_frame.setPos(0, -hd - 0.04, -h/2 + h * 0.42)
    lbl = _imperial_label(rng.choice(_CODES_HANGAR), size=0.38)
    lbl.reparentTo(root); lbl.setPos(0, -hd - 0.08, -h/2 + h * 0.72)
    root.setLightOff()
    return root


def _make_silo(r, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Réservoir cylindrique — 1 draw call opaque (batch corps+bandes)."""
    root = NodePath("silo")
    b    = 0.30 + rng.uniform(0, 0.06)
    bat  = _GeomBatch()
    bat.cylinder(0, 0, 0, r, h/2,
                 Vec4(b*0.82, b*0.80, b*0.78, 1),
                 Vec4(b, b*0.98, b*0.95, 1), sides=10)
    bat.cylinder(0, 0, -h*0.1, r*1.02, h*0.06,
                 Vec4(0.55, 0.35, 0.12, 0.9),
                 Vec4(0.55, 0.35, 0.12, 0.9), sides=10)
    bat.cylinder(0, 0, h*0.25, r*1.01, h*0.04,
                 Vec4(0.45, 0.28, 0.10, 0.8),
                 Vec4(0.45, 0.28, 0.10, 0.8), sides=10)
    bat.emit("silo_body").reparentTo(root)
    if bb is not None:
        bb.add(ox, oy, oz + h/2 + 0.15, Vec4(1.0, 0.65, 0.1, 1.0))
    else:
        _beacon(0, 0, h/2+0.15, Vec4(1.0, 0.65, 0.1, 1.0), 5).reparentTo(root)
    if nc is not None:
        nc.cyl_ring(ox, oy, oz, r * 1.02,  h/2 - 0.10, _NEON_ORANGE)
        nc.cyl_ring(ox, oy, oz, r * 1.02, -h * 0.08,   _NEON_RED)
    else:
        _neon_cyl_ring(r * 1.02, h/2 - 0.10, _NEON_ORANGE, thick=3.0).reparentTo(root)
        _neon_cyl_ring(r * 1.02, -h * 0.08,  _NEON_RED,    thick=2.0).reparentTo(root)
    root.setLightOff()
    return root


def _make_bunker(hw, hd, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Bunker massif — 1 draw call opaque (batch corps+fente+tourelle)."""
    root = NodePath("bunker")
    b    = 0.22 + rng.uniform(0, 0.05)
    bat  = _GeomBatch()
    bat.box(0, 0, 0, hw, hd, h/2,
            Vec4(b, b*0.99, b*0.95, 1),
            Vec4(b*0.70, b*0.69, b*0.67, 1),
            Vec4(b*0.42, b*0.41, b*0.40, 1))
    bat.box(0, hd+0.02, 0, hw*0.55, 0.06, h*0.12,
            Vec4(0.04,0.04,0.04,1), Vec4(0.04,0.04,0.04,1), Vec4(0.04,0.04,0.04,1))
    if h > 3.5:
        bat.cylinder(0, 0, h/2 + h*0.12, hw*0.35, h*0.12,
                     Vec4(b*0.55, b*0.54, b*0.52, 1),
                     Vec4(b*0.45, b*0.44, b*0.42, 1), sides=6)
    bat.emit("bunker_body").reparentTo(root)
    if nc is not None:
        # fente facade arrière (hd+0.08) ; cadre centré sur oz
        nc.rect_frame(ox, oy + hd + 0.08, oz, hw*0.55, h*0.12, _NEON_RED)
        nc.box_rings(ox, oy, oz, hw, hd, [h/2 - 0.08], _NEON_ORANGE)
    else:
        slit_frame = _neon_rect_frame(hw * 0.55, h * 0.12, _NEON_RED, thick=2.5)
        slit_frame.reparentTo(root); slit_frame.setPos(0, hd + 0.08, 0)
        _neon_box_rings(hw, hd, h/2, [h/2 - 0.08], _NEON_ORANGE, thick=2.5).reparentTo(root)
    lbl = _imperial_label(rng.choice(_CODES_BUNKER))
    lbl.reparentTo(root); lbl.setPos(0, -hd - 0.05, -h/2 + h * 0.65)
    root.setLightOff()
    return root


def _make_antenna_mast(r, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Mât d'antenne — mât en batch, bras gardés en NodePaths (rotation HPR)."""
    root    = NodePath("antenna")
    bat     = _GeomBatch()
    bat.cylinder(0, 0, 0, r, h/2, Vec4(0.20,0.20,0.19,1), Vec4(0.18,0.18,0.17,1), sides=4)
    bat.emit("antenna_mast").reparentTo(root)
    arm_len = r * 18
    for frac, angle in [(0.55, 0), (0.70, 45), (0.82, -30), (0.92, 15)]:
        # Bras avec rotation — NodePath séparé (pas de rotation dans _GeomBatch)
        fmt = GeomVertexFormat.getV3c4()
        vd  = GeomVertexData("arm", fmt, Geom.UHStatic)
        vw  = GeomVertexWriter(vd, "vertex"); cw = GeomVertexWriter(vd, "color")
        tri = GeomTriangles(Geom.UHStatic)
        ar  = r * 0.6; ahl = arm_len / 2; sides = 4
        cs  = Vec4(0.18,0.18,0.17,1); ct = Vec4(0.16,0.16,0.15,1)
        vw.addData3(0, 0, ahl); cw.addData4(ct)
        for i in range(sides):
            a = 2*math.pi*i/sides
            vw.addData3(math.cos(a)*ar, math.sin(a)*ar, ahl); cw.addData4(cs)
        for i in range(sides):
            a = 2*math.pi*i/sides
            vw.addData3(math.cos(a)*ar, math.sin(a)*ar, -ahl); cw.addData4(cs)
        for i in range(sides):
            tri.addVertices(0, 1+i, 1+(i+1)%sides)
        for i in range(sides):
            b0=1+sides+i; b1=1+sides+(i+1)%sides; t0=1+i; t1=1+(i+1)%sides
            tri.addVertices(b0,t0,b1); tri.addVertices(b1,t0,t1)
        geom = Geom(vd); geom.addPrimitive(tri)
        gn   = GeomNode("arm"); gn.addGeom(geom)
        arm_np = NodePath(gn)
        arm_np.reparentTo(root); arm_np.setHpr(angle, 90, 0)
        arm_np.setPos(0, 0, h/2 * frac); arm_np.setLightOff()
    if bb is not None:
        bb.add(ox, oy, oz + h/2 + 0.12, Vec4(1.0, 0.15, 0.15, 1.0))
    else:
        _beacon(0, 0, h/2+0.12, Vec4(1.0, 0.15, 0.15, 1.0), 4).reparentTo(root)
    root.setLightOff()
    return root


def _make_landing_pad(r, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
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
        if bb is not None:
            bb.add(ox + cx, oy + cy, oz + h_plat + 0.15, col)
        else:
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


def _make_relay_tower(r, h, rng, nc=None, bb=None, ox=0.0, oy=0.0, oz=0.0):
    """Tour relais — 1 draw call opaque (corps+disque, rotation disque ignorée)."""
    root = NodePath("relay")
    b    = 0.25 + rng.uniform(0, 0.05)
    bat  = _GeomBatch()
    bat.cylinder(0, 0, 0, r, h/2,
                 Vec4(b*0.80, b*0.79, b*0.77, 1),
                 Vec4(b, b*0.99, b*0.97, 1), sides=6)
    bat.cylinder(0, 0, h/2 + h*0.06, r*3.5, h*0.04,
                 Vec4(0.30, 0.28, 0.25, 0.9),
                 Vec4(0.38, 0.36, 0.33, 0.9), sides=12)
    bat.emit("relay_body").reparentTo(root)
    if bb is not None:
        bb.add(ox, oy, oz + h/2 + h*0.14, Vec4(1.0, 0.85, 0.1, 1.0))
    else:
        _beacon(0, 0, h/2+h*0.14, Vec4(1.0, 0.85, 0.1, 1.0), 5).reparentTo(root)
    if nc is not None:
        nc.cyl_ring(ox, oy, oz, r*3.5,  h/2 + h*0.07, _NEON_ORANGE, sides=14)
        nc.cyl_ring(ox, oy, oz, r,      -h * 0.12,     _NEON_WHITE,  sides=8)
    else:
        _neon_cyl_ring(r*3.5, h/2 + h*0.07, _NEON_ORANGE, thick=2.5, sides=14).reparentTo(root)
        _neon_cyl_ring(r,    -h * 0.12,      _NEON_WHITE,  thick=2.0, sides=8).reparentTo(root)
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
        # PAS de setTransparency sur le root — ça classerait TOUT le sous-arbre
        # dans le bucket transparent (tri par distance chaque frame = énorme coût).
        # Chaque enfant qui en a besoin (neons, balises, marquages) le déclare lui-même.
        self.node.setLightOff()

        rng    = random.Random(seed)
        layout = self._pick_layout(rng, LUNAR.get("enabled_layouts"))
        mark   = _pick_mark_style(rng)

        # Batches créés AVANT layout — les bâtiments y accumulent neons + balises
        # Résultat : ~60 draw calls transparents → 3 (core + glow + beacons)
        self._neon_bat   = _NeonLineBatch()
        self._beacon_bat = _BeaconBatch()

        _make_ground_markings(self.node, rng, mark)
        getattr(self, f'_layout_{layout}')(rng)

        # Émet les batches dans le groupe
        self._neon_bat.emit(self.node)
        self._beacon_bat.emit(self.node)

    # ── Sélection anti-répétition ─────────────────────────────

    def _pick_layout(self, rng, enabled=None):
        global _last_layouts
        base_pool = _LAYOUT_POOL if not enabled else [p for p in _LAYOUT_POOL if p in enabled]
        if not base_pool:
            base_pool = _LAYOUT_POOL[:]
        pool = [p for p in base_pool if p not in _last_layouts]
        if not pool:
            pool = base_pool[:]
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
        bz = GROUND_Z + h / 2
        nc = self._neon_bat; bb = self._beacon_bat

        MAKERS = {
            'tower':   lambda: _make_tower(hw, hd, h, rng, nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'hangar':  lambda: _make_hangar(hw, hd, h, rng, nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'silo':    lambda: _make_silo(hw, h, rng,        nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'bunker':  lambda: _make_bunker(hw, hd, h, rng,  nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'antenna': lambda: _make_antenna_mast(hw, h, rng, nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'pad':     lambda: _make_landing_pad(hw, rng,     nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            'relay':   lambda: _make_relay_tower(hw, h, rng,  nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
        }
        mesh = MAKERS[style]()
        mesh.reparentTo(self.node)
        mesh.setPos(lx, ly, bz)

        self._hitboxes.append({'lx': lx, 'ly': ly, 'hw': hw, 'hd': hd, 'height': h})

        # Hitbox supplémentaire pour le toit en pente des hangars
        if style == 'hangar':
            ridge_h = h * 0.25
            self._hitboxes.append({
                'lx': lx, 'ly': ly,
                'hw': hw * 0.55,
                'hd': hd,
                'height': h + ridge_h,
                '_is_ridge': True,
                '_ridge_bot': h,
                '_debug_hidden': True,   # pas de wireframe debug (géom triangulaire)
            })

    # ── Placement générique depuis LAYOUTS / BUILDING_TYPES ──

    def _layout_from_json(self, rng, layout_name):
        """Lit le layout depuis settings.LAYOUTS et place les bâtiments."""
        rules = LAYOUTS.get(layout_name, [])
        for rule in rules:
            btype    = rule["type"]
            btdef    = BUILDING_TYPES.get(btype, {})
            if not btdef:
                continue

            x_range  = rule.get("x", [-12.0, 12.0])
            y_range  = rule.get("y", [-10.0, 10.0])
            sc_range = rule.get("scale", [1.0, 1.0])
            prob     = rule.get("prob", 1.0)
            sides    = rule.get("sides", False)
            min_ax   = rule.get("min_abs_x", 0.0)

            raw_count = rule.get("count", 1)
            if isinstance(raw_count, list):
                count = rng.randint(raw_count[0], raw_count[1])
            else:
                count = int(raw_count)

            side_list = [-1, 1] if sides else [0]

            for side in side_list:
                for _ in range(count):
                    if rng.random() > prob:
                        continue
                    scale = rng.uniform(sc_range[0], sc_range[1])
                    if sides:
                        lx = side * rng.uniform(x_range[0], x_range[1])
                    else:
                        lx = rng.uniform(x_range[0], x_range[1])
                        if min_ax > 0 and abs(lx) < min_ax:
                            lx = min_ax * (1.0 if lx >= 0 else -1.0)
                    ly = rng.uniform(y_range[0], y_range[1])
                    self._add_from_type(rng, lx, ly, btype, scale)

    def _add_from_type(self, rng, lx, ly, type_name, scale=1.0):
        """Crée un bâtiment depuis BUILDING_TYPES[type_name]."""
        btdef = BUILDING_TYPES.get(type_name)
        if not btdef:
            return

        hw = rng.uniform(*btdef["hw"]) * scale
        hd = rng.uniform(*btdef["hd"]) * scale
        h  = rng.uniform(*btdef["h"])  * scale
        hb = btdef.get("hb_scale", 1.0)
        bz = GROUND_Z + h / 2
        nc = self._neon_bat; bb = self._beacon_bat

        mesh_name = btdef["mesh"]
        MAKERS = {
            "tower":   lambda: _make_tower(hw, hd, h, rng,  nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "hangar":  lambda: _make_hangar(hw, hd, h, rng, nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "silo":    lambda: _make_silo(hw, h, rng,        nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "bunker":  lambda: _make_bunker(hw, hd, h, rng,  nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "antenna": lambda: _make_antenna_mast(hw, h, rng, nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "pad":     lambda: _make_landing_pad(hw, rng,     nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
            "relay":   lambda: _make_relay_tower(hw, h, rng,  nc=nc, bb=bb, ox=lx, oy=ly, oz=bz),
        }
        maker = MAKERS.get(mesh_name)
        if not maker:
            return

        mesh = maker()
        mesh.reparentTo(self.node)
        mesh.setPos(lx, ly, bz)

        # Hitbox corps (hb_scale réduit les cylindres)
        self._hitboxes.append({
            "lx": lx, "ly": ly,
            "hw": hw * hb, "hd": hd * hb,
            "height": h,
        })

        # Ridge pour les hangars
        if mesh_name == "hangar":
            ridge_h = h * 0.25
            self._hitboxes.append({
                "lx": lx, "ly": ly,
                "hw": hw * 0.55,
                "hd": hd,
                "height": h + ridge_h,
                "_is_ridge": True,
                "_ridge_bot": h,
                "_debug_hidden": True,
            })

    # ── Layouts ───────────────────────────────────────────────

    def _layout_runway(self, rng):
        """Piste centrale flanquée de tours et silos."""
        self._layout_from_json(rng, "runway")

    def _layout_platform(self, rng):
        """Pad central entouré de bunkers et relais."""
        self._layout_from_json(rng, "platform")

    def _layout_compound(self, rng):
        """Grande base — 2 hangars massifs, silos multiples, tours aux coins."""
        self._layout_from_json(rng, "compound")

    def _layout_tower_row(self, rng):
        """Rangées de tours imposantes des deux côtés."""
        self._layout_from_json(rng, "tower_row")

    def _layout_industrial(self, rng):
        """Zone industrielle dense — silos serrés, bunkers, relais."""
        self._layout_from_json(rng, "industrial")

    def _layout_fortress(self, rng):
        """Forteresse — 4 tours aux coins, hangars et bunkers intérieurs."""
        self._layout_from_json(rng, "fortress")

    def _layout_outpost(self, rng):
        """Avant-poste léger — quelques structures isolées, beaucoup d'espace."""
        self._layout_from_json(rng, "outpost")

    def _layout_depot(self, rng):
        """Dépôt logistique — rangées de hangars + silos alignés."""
        self._layout_from_json(rng, "depot")

    def _layout_mixed(self, rng):
        """Mélange de bâtiments variés."""
        self._layout_from_json(rng, "mixed")

    # ── Hitboxes (debug) ─────────────────────────────────────

    def get_hitboxes(self):
        """Retourne les AABB des bâtiments en coordonnées monde.

        Chaque entrée : (cx, cy, cz, hw, hd, hh) où
          cx/cy/cz  — centre monde du bâtiment
          hw/hd     — demi-largeurs X et Y (avec marge de collision)
          hh        — demi-hauteur (height/2)
        """
        if not self.alive or self.node.isEmpty():
            return []
        group_y = self.node.getY()
        result = []
        for hb in self._hitboxes:
            if hb.get('_debug_hidden'):
                continue   # hitboxes internes (ridge) — collision active, pas de wireframe
            if hb.get('_is_ridge'):
                ridge_bot = hb['_ridge_bot']
                ridge_top = hb['height']
                half_h = (ridge_top - ridge_bot) / 2
                cz = GROUND_Z + ridge_bot + half_h
            else:
                h  = hb['height']
                cz = GROUND_Z + h / 2
                half_h = h / 2
            cx = hb['lx']
            cy = group_y + hb['ly']
            result.append((cx, cy, cz, hb['hw'], hb['hd'], half_h))
        return result

    # ── Collision ellipsoïde (joueur) vs AABB (bâtiment) ────────
    #
    # Algorithme : point le plus proche de la AABB du bâtiment par
    # rapport au centre du vaisseau, puis test ellipsoïde :
    #   (dx/rx)² + (dy/ry)² + (dz/rz)² ≤ 1
    #
    # L'ellipsoïde couvre naturellement les ailes (rx large) sans
    # les coins carrés d'une AABB.
    _E_RX = 1.10   # demi-axe X — bout d'aile à bout d'aile
    _E_RY = 0.15   # demi-axe Y — quasi-ignoré (on s'en fout du nez)
    _E_RZ = 0.40   # demi-axe Z — hauteur

    def check_collision(self, player_pos):
        if not self.alive or self.node.isEmpty():
            return 0, (0.0, 0.0)
        group_y = self.node.getY()
        px = player_pos.getX()
        py = player_pos.getY()
        pz = player_pos.getZ()

        for hb in self._hitboxes:
            bx  = hb['lx']
            by  = group_y + hb['ly']
            bhw = hb['hw']
            bhd = hb['hd']

            if hb.get('_is_ridge'):
                ridge_bot = hb['_ridge_bot']
                ridge_top = hb['height']
                bcz = GROUND_Z + ridge_bot + (ridge_top - ridge_bot) / 2
                bhh = (ridge_top - ridge_bot) / 2
            else:
                bhh = hb['height'] / 2
                bcz = GROUND_Z + bhh

            # Rejet rapide AABB élargie (évite le sqrt pour les cas lointains)
            if abs(px - bx) > self._E_RX + bhw: continue
            if abs(py - by) > self._E_RY + bhd: continue
            if abs(pz - bcz) > self._E_RZ + bhh: continue

            # Point le plus proche de la AABB du bâtiment depuis le centre vaisseau
            cx = max(bx - bhw, min(px, bx + bhw))
            cy = max(by - bhd, min(py, by + bhd))
            cz = max(bcz - bhh, min(pz, bcz + bhh))

            # Test ellipsoïde : (dx/rx)² + (dy/ry)² + (dz/rz)² ≤ 1
            dx = (cx - px) / self._E_RX
            dy = (cy - py) / self._E_RY
            dz = (cz - pz) / self._E_RZ
            if dx*dx + dy*dy + dz*dz > 1.0:
                continue

            # Axe de pénétration minimale → push sur l'axe le moins pénétré
            ox = (self._E_RX + bhw) - abs(px - bx)
            oz = (self._E_RZ + bhh) - abs(pz - bcz)

            if oz < ox:
                # Collision par dessus/dessous → push vertical
                sign_z = 1.0 if pz >= bcz else -1.0
                return 2, (0.0, sign_z * oz)
            else:
                # Collision latérale → push horizontal
                sign_x = 1.0 if px >= bx else -1.0
                return 2, (sign_x * ox, 0.0)

        return 0, (0.0, 0.0)

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


# ─────────────────────────────────────────────────────────────
# Montagnes de bord — pyramides rocheuses sur les flancs X
# ─────────────────────────────────────────────────────────────

class LunarBorderMountain:
    """Bande de montagnes procédurales sur les bords gauche/droit du niveau L2.

    Chaque montagne = pyramide triangulaire (4 faces), couleur roc lunaire,
    hauteur aléatoire 2.0–6.0 units, espacées de 8–15 units en Y.
    Spawn en band de X ≈ ±18 à ±22.
    """

    _ROC_COLORS = [
        (0.45, 0.42, 0.38),
        (0.40, 0.38, 0.34),
        (0.50, 0.47, 0.43),
        (0.42, 0.40, 0.36),
    ]

    def __init__(self, parent, y_start, y_end, seed):
        self.alive = True
        self.node  = NodePath("border_mountains")
        self.node.reparentTo(parent)
        self.node.setLightOff()

        rng = random.Random(seed)
        self._build(rng, y_start, y_end)

    def _build(self, rng, y_start, y_end):
        """Batch manuel : toutes les pyramides dans 1 seul GeomNode → 2 draw calls."""
        fmt  = GeomVertexFormat.getV3c4()
        vd   = GeomVertexData("mtns_batch", fmt, Geom.UHStatic)
        vw   = GeomVertexWriter(vd, "vertex")
        cw   = GeomVertexWriter(vd, "color")
        tris = GeomTriangles(Geom.UHStatic)
        vi   = [0]   # indice de vertex courant

        def add_pyramid(cx, cy, h, base, col):
            r = base / 2.0
            bz = GROUND_Z
            tz = GROUND_Z + h
            verts = [
                (cx - r, cy - r, bz),
                (cx + r, cy - r, bz),
                (cx + r, cy + r, bz),
                (cx - r, cy + r, bz),
                (cx,     cy,     tz),
            ]
            faces = [(0,1,4), (1,2,4), (2,3,4), (3,0,4)]
            c = Vec4(*col, 1.0)
            c_dark = Vec4(col[0]*0.65, col[1]*0.63, col[2]*0.60, 1.0)
            for i, (a, b, c_idx) in enumerate(faces):
                shade = c if i in (0, 1) else c_dark
                for idx in (a, b, c_idx):
                    vw.addData3(*verts[idx]); cw.addData4(shade)
                base_i = vi[0]
                tris.addVertices(base_i, base_i + 1, base_i + 2)
                vi[0] += 3

        y = y_start
        while y < y_end:
            for side in (-1, 1):
                cx  = side * rng.uniform(18.0, 22.0)
                h   = rng.uniform(2.0, 6.0)
                base = rng.uniform(3.0, 7.0)
                col = rng.choice(self._ROC_COLORS)
                add_pyramid(cx, y, h, base, col)
            y += rng.uniform(LUNAR["mountain_spacing_min"], LUNAR["mountain_spacing_max"])

        geom = Geom(vd); geom.addPrimitive(tris)
        gn   = GeomNode("mtns_batch"); gn.addGeom(geom)
        NodePath(gn).reparentTo(self.node)

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        # Détruire quand toute la géométrie (qui s'étend jusqu'à ~SPAWN_DEPTH+80)
        # est passée derrière le joueur. -250 laisse la dernière pyramide (~230u)
        # sortir complètement avant de nettoyer.
        if self.node.getY() < -250:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ─────────────────────────────────────────────────────────────
# Routes lunaires — bandes perpendiculaires à la direction de vol
# ─────────────────────────────────────────────────────────────

class LunarRoad:
    """2–3 routes horizontales (quads plats) perpendiculaires à l'axe Y.

    Chaque route = quad légèrement au-dessus du sol + pointillés sur la ligne
    médiane. Couleur plus claire que le sol lunaire.
    """

    ROAD_COLOR    = (0.55, 0.52, 0.48)
    DASH_COLOR    = (0.80, 0.78, 0.70)
    ROAD_WIDTH    = 0.8   # demi-largeur totale = ±0.4
    ROAD_HALF_X   = 14.0  # s'étend de -14 à +14 en X
    Z_OFFSET      = 0.05  # légèrement au-dessus de GROUND_Z

    def __init__(self, parent, y_positions):
        """y_positions : liste de Y absolus (coordonnées monde) pour les routes."""
        self.alive = True
        self.node  = NodePath("lunar_roads")
        self.node.reparentTo(parent)
        self.node.setLightOff()
        self.node.setDepthOffset(1)

        for y in y_positions:
            self._make_road(y)

    def _make_road(self, y):
        z     = GROUND_Z + self.Z_OFFSET
        hw    = self.ROAD_HALF_X
        hd    = self.ROAD_WIDTH / 2.0   # = 0.4
        rc    = Vec4(*self.ROAD_COLOR, 1.0)
        dc    = Vec4(*self.DASH_COLOR, 0.9)

        # ── Quad principal ──
        fmt  = GeomVertexFormat.getV3c4()
        vd   = GeomVertexData("road", fmt, Geom.UHStatic)
        vw   = GeomVertexWriter(vd, "vertex")
        cw   = GeomVertexWriter(vd, "color")
        tris = GeomTriangles(Geom.UHStatic)

        verts = [
            (-hw, y - hd, z),
            ( hw, y - hd, z),
            ( hw, y + hd, z),
            (-hw, y + hd, z),
        ]
        for v in verts:
            vw.addData3(*v); cw.addData4(rc)
        tris.addVertices(0, 1, 2); tris.addVertices(0, 2, 3)

        geom = Geom(vd); geom.addPrimitive(tris)
        gn   = GeomNode("road_quad"); gn.addGeom(geom)
        np_q = NodePath(gn)
        np_q.reparentTo(self.node)
        np_q.setTransparency(TransparencyAttrib.MAlpha)

        # ── Pointillés sur la médiane ──
        fmt2  = GeomVertexFormat.getV3c4()
        vd2   = GeomVertexData("dashes", fmt2, Geom.UHStatic)
        vw2   = GeomVertexWriter(vd2, "vertex")
        cw2   = GeomVertexWriter(vd2, "color")
        lns   = GeomLines(Geom.UHStatic)
        dz    = z + 0.02
        DASH  = 1.2   # longueur d'un tiret
        GAP   = 0.8   # espace entre tirets
        step  = DASH + GAP
        x     = -hw
        vi    = 0
        while x < hw:
            x1 = x
            x2 = min(x + DASH, hw)
            vw2.addData3(x1, y, dz); cw2.addData4(dc)
            vw2.addData3(x2, y, dz); cw2.addData4(dc)
            lns.addVertices(vi, vi + 1)
            vi += 2
            x  += step

        geom2 = Geom(vd2); geom2.addPrimitive(lns)
        gn2   = GeomNode("road_dashes"); gn2.addGeom(geom2)
        np_d  = NodePath(gn2)
        np_d.reparentTo(self.node)
        np_d.setRenderModeThickness(1.8)
        np_d.setTransparency(TransparencyAttrib.MAlpha)
        np_d.setDepthOffset(2)

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -80:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()
