"""
HUD v4 — Overlay PNG + barres en bas + score en haut.
Barres sous les lignes de l'interface, style futuriste gras.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    TextNode, Vec4, TransparencyAttrib,
    ColorBlendAttrib,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, Point2, Point3
)
import math
import os


C_ORANGE = Vec4(0.9, 0.55, 0.15, 1.0)
C_BRIGHT = Vec4(1.0, 0.7, 0.2, 1.0)
C_DANGER = Vec4(1.0, 0.2, 0.05, 1.0)
C_WARN = Vec4(1.0, 0.5, 0.1, 1.0)
C_BAR_BG = Vec4(0.1, 0.06, 0.02, 0.4)

OVERLAY_PATH = "assets/hud_overlay.png"


def _make_rect(parent, x, z, w, h, color):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("r", fmt, Geom.UHStatic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    v.addData3(x, 0, z); c.addData4(color)
    v.addData3(x+w, 0, z); c.addData4(color)
    v.addData3(x+w, 0, z+h); c.addData4(color)
    v.addData3(x, 0, z+h); c.addData4(color)
    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)
    g = Geom(vd)
    g.addPrimitive(tris)
    n = GeomNode("rect")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_rounded_rect(parent, x, z, w, h, color, segs=6):
    """Rectangle à coins arrondis — triangle fan depuis le centre."""
    r = min(h / 2.0, w / 4.0)
    cx, cz = x + w / 2.0, z + h / 2.0
    fmt = GeomVertexFormat.getV3c4()
    vd  = GeomVertexData("rr", fmt, Geom.UHStatic)
    vw  = GeomVertexWriter(vd, "vertex")
    cw  = GeomVertexWriter(vd, "color")
    tris = GeomTriangles(Geom.UHStatic)
    vw.addData3(cx, 0, cz); cw.addData4(color)
    corners = [
        (x + r,     z + r,     180, 270),
        (x + w - r, z + r,     270, 360),
        (x + w - r, z + h - r, 0,   90),
        (x + r,     z + h - r, 90,  180),
    ]
    rim = []
    for ox, oz, a0, a1 in corners:
        for i in range(segs + 1):
            a = math.radians(a0 + (a1 - a0) * i / segs)
            rim.append((ox + math.cos(a) * r, oz + math.sin(a) * r))
    for vx, vz in rim:
        vw.addData3(vx, 0, vz); cw.addData4(color)
    n = len(rim)
    for i in range(n):
        tris.addVertices(0, 1 + i, 1 + (i + 1) % n)
    geom = Geom(vd); geom.addPrimitive(tris)
    gn = GeomNode("rrect"); gn.addGeom(geom)
    np = NodePath(gn)
    np.reparentTo(parent)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_rect_outline(parent, x, z, w, h, color):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("o", fmt, Geom.UHStatic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    for px, pz in [(x,z),(x+w,z),(x+w,z+h),(x,z+h),(x,z)]:
        v.addData3(px, 0, pz); c.addData4(color)
    lines = GeomLines(Geom.UHStatic)
    for i in range(4):
        lines.addVertices(i, i+1)
    g = Geom(vd)
    g.addPrimitive(lines)
    n = GeomNode("outline")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setRenderModeThickness(1.0)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_bar(parent, x, z, width, height, segments=12):
    bar = {"segments": segments, "seg_nodes": []}
    gap = 0.003
    seg_w = (width - (segments + 1) * gap) / segments

    # Fond sombre arrondi (un seul rect)
    _make_rect(parent, x - 0.006, z - 0.004, width + 0.012, height + 0.008,
               Vec4(0.08, 0.05, 0.02, 0.4))
    # Contour fin
    _make_rect_outline(parent, x - 0.006, z - 0.004, width + 0.012, height + 0.008,
                       Vec4(1, 0.55, 0.1, 0.2))

    for i in range(segments):
        sx = x + gap + i * (seg_w + gap)
        seg = _make_rect(parent, sx, z, seg_w, height, C_ORANGE)
        bar["seg_nodes"].append(seg)
    return bar


def _update_bar(bar, pct, color=C_ORANGE):
    filled = int(pct * bar["segments"])
    for i, seg in enumerate(bar["seg_nodes"]):
        if i < filled:
            seg.show()
            seg.setColorScale(color)
        else:
            seg.hide()


# ---------------------------------------------------------------------------
# Panneau radio boss — géométrie procédurale (rectangle + 2 demi-cercles)
# ---------------------------------------------------------------------------

def _make_panel_bg(parent, cx, cz, hw, hh, color, segs=14):
    """Fond rempli : rectangle central + 2 demi-cercles aux extrémités."""
    fmt = GeomVertexFormat.getV3c4()
    vd  = GeomVertexData("pbg", fmt, Geom.UHStatic)
    vtx = GeomVertexWriter(vd, "vertex")
    col = GeomVertexWriter(vd, "color")
    tri = GeomTriangles(Geom.UHStatic)
    idx = [0]

    def av(x, z):
        vtx.addData3(x, 0, z); col.addData4(color); idx[0] += 1

    # Rectangle central
    av(cx - hw, cz - hh)  # 0
    av(cx + hw, cz - hh)  # 1
    av(cx + hw, cz + hh)  # 2
    av(cx - hw, cz + hh)  # 3
    tri.addVertices(0, 1, 2); tri.addVertices(0, 2, 3)

    # Demi-cercle gauche (90° → 270°)
    lc = idx[0]; av(cx - hw, cz)
    ls = idx[0]
    for i in range(segs + 1):
        a = math.pi/2 + math.pi * i / segs
        av(cx - hw + math.cos(a) * hh, cz + math.sin(a) * hh)
    for i in range(segs):
        tri.addVertices(lc, ls + i, ls + i + 1)

    # Demi-cercle droit (-90° → 90°)
    rc = idx[0]; av(cx + hw, cz)
    rs = idx[0]
    for i in range(segs + 1):
        a = -math.pi/2 + math.pi * i / segs
        av(cx + hw + math.cos(a) * hh, cz + math.sin(a) * hh)
    for i in range(segs):
        tri.addVertices(rc, rs + i, rs + i + 1)

    geom = Geom(vd); geom.addPrimitive(tri)
    gn = GeomNode("panel_bg"); gn.addGeom(geom)
    np = NodePath(gn)
    np.reparentTo(parent)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setBin("fixed", 43)
    np.setDepthTest(False); np.setDepthWrite(False)
    return np


def _make_panel_border(parent, cx, cz, hw, hh, color, segs=16, thickness=1.5):
    """Contour lumineux : 2 lignes droites + 2 arcs demi-cercles."""
    from panda3d.core import GeomLines
    fmt = GeomVertexFormat.getV3c4()
    vd  = GeomVertexData("pb", fmt, Geom.UHStatic)
    vtx = GeomVertexWriter(vd, "vertex")
    col = GeomVertexWriter(vd, "color")
    lines = GeomLines(Geom.UHStatic)
    idx = [0]

    def av(x, z):
        vtx.addData3(x, 0, z); col.addData4(color); idx[0] += 1

    # Ligne haute
    av(cx - hw, cz + hh); av(cx + hw, cz + hh); lines.addVertices(0, 1)
    # Ligne basse
    av(cx - hw, cz - hh); av(cx + hw, cz - hh); lines.addVertices(2, 3)

    # Arc gauche
    ls = idx[0]
    for i in range(segs + 1):
        a = math.pi/2 + math.pi * i / segs
        av(cx - hw + math.cos(a) * hh, cz + math.sin(a) * hh)
    for i in range(segs):
        lines.addVertices(ls + i, ls + i + 1)

    # Arc droit
    rs = idx[0]
    for i in range(segs + 1):
        a = -math.pi/2 + math.pi * i / segs
        av(cx + hw + math.cos(a) * hh, cz + math.sin(a) * hh)
    for i in range(segs):
        lines.addVertices(rs + i, rs + i + 1)

    geom = Geom(vd); geom.addPrimitive(lines)
    gn = GeomNode("panel_border"); gn.addGeom(geom)
    np = NodePath(gn)
    np.reparentTo(parent)
    np.setRenderModeThickness(thickness)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setBin("fixed", 44)
    np.setDepthTest(False); np.setDepthWrite(False)
    return np




class HUD:
    def __init__(self, game):
        self.game = game
        self.blink_timer = 0.0

        # ===== OVERLAY =====
        if os.path.exists(OVERLAY_PATH):
            self.overlay = OnscreenImage(
                image=OVERLAY_PATH, pos=(0, 0, 0),
                scale=(1.78, 1, 1.0),
            )
            self.overlay.setTransparency(TransparencyAttrib.MAlpha)
            self.overlay.setAttrib(ColorBlendAttrib.make(
                ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne,
            ))
            self.overlay.setBin("fixed", 40)
            self.overlay.setDepthTest(False)
            self.overlay.setDepthWrite(False)
            # Transparence sur l'overlay
            self.overlay.setColorScale(0.65, 0.65, 0.65, 0.65)
        else:
            self.overlay = None

        # ===== SCORE (haut centre, gros) =====
        self.score_text = OnscreenText(
            text="0", pos=(0, 0.78), scale=0.07,
            fg=C_BRIGHT, align=TextNode.ACenter,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),  # Faux gras via shadow
        )

        # ===== WAVE (haut gauche) — texte unifié, aligne avec l'annonce =====
        self.wave_text = OnscreenText(
            text="WAVE 1", pos=(-1.20, 0.90), scale=0.040,
            fg=C_BRIGHT, align=TextNode.ALeft,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== BARRES EN BAS — uniquement Force =====
        self.bar_root = game.aspect2d.attachNewNode("bars")
        self.bar_root.setTransparency(TransparencyAttrib.MAlpha)
        self.bar_root.setBin("fixed", 45)

        # Losange bas-centre (indicateur torpille)
        self._torp_diamond_root = game.aspect2d.attachNewNode("torp_diamond")
        self._torp_diamond_root.setBin("fixed", 50)
        self._torp_diamond_root.setDepthTest(False)
        self._torp_diamond_root.setDepthWrite(False)
        self._torp_diamond_root.setTransparency(TransparencyAttrib.MAlpha)
        self._build_single_diamond(self._torp_diamond_root, 0, -0.93, 0.056)
        self._torp_diamonds = []
        self._torp_count_text = OnscreenText(
            text="6", pos=(0, -0.944), scale=0.032,
            fg=Vec4(0.9, 0.6, 0.1, 0.88), align=TextNode.ACenter,
            mayChange=True, sort=51,
        )

        # ===== WARNINGS near-ship (overheat + torp low) =====
        # Texte WARN clignotant near-ship — pré-alloué, repositionné chaque frame
        self._warn_overheat = OnscreenText(
            text="", pos=(0, 0), scale=0.022,
            fg=Vec4(1.0, 0.35, 0.0, 1.0), align=TextNode.ACenter,
            mayChange=True, sort=56, shadow=(0,0,0,0.7),
        )
        # Warn near-ship (fuselage) — nœud persistant mis à jour chaque frame
        self._ship_warn_text = OnscreenText(
            text="", pos=(0, 0), scale=0.022,
            fg=Vec4(1.0, 0.35, 0.0, 0.0), align=TextNode.ACenter,
            mayChange=True, sort=56, shadow=(0,0,0,0.6),
        )
        self._warn_torp_shown = False

        # ===== MINI HUD near-ship — barres persistantes (repositionnées chaque frame) =====
        _W, _H, _GAP = 0.132, 0.0072, 0.0090
        self._sbar_W   = _W
        self._sbar_H   = _H
        self._sbar_GAP = _GAP

        sbar = game.aspect2d.attachNewNode("ship_bars")
        sbar.setBin("fixed", 47)
        sbar.setDepthTest(False)
        sbar.setDepthWrite(False)
        sbar.setTransparency(TransparencyAttrib.MAlpha)
        self._sbar_root = sbar

        # Laser bar (z = 0 dans l'espace local de sbar)
        _make_rounded_rect(sbar, 0, 0, _W, _H, Vec4(0.12, 0.05, 0.02, 0.38))
        self._sbar_laser_fill = _make_rect(sbar, 0, 0, _W, _H, C_ORANGE)

        # Barre HP — 6 segments arrondis (z = -(H+GAP) dans l'espace local de sbar)
        _z2    = -(_H + _GAP)
        _SGAP  = 0.0025
        _sw    = (_W - 7 * _SGAP) / 6
        _make_rounded_rect(sbar, -_SGAP, _z2 - 0.001, _W + 2 * _SGAP, _H + 0.002,
                           Vec4(0.0, 0.0, 0.0, 0.55))
        self._seg_nodes = []
        for i in range(6):
            sx = _SGAP + i * (_sw + _SGAP)
            seg = _make_rounded_rect(sbar, sx, _z2, _sw, _H, Vec4(1.0, 1.0, 1.0, 1.0))
            self._seg_nodes.append(seg)
        self._seg_z2   = _z2
        self._seg_sw   = _sw
        self._seg_sgap = _SGAP

        # Flash hit segments
        self._seg_flash_timer = 0.0

        # Étincelles d'impact
        self._sparks = []
        self._spark_cooldown = 0.0

        # ===== ANNONCE WAVE — dezoom vers le label permanent =====
        self.wave_announce = OnscreenText(
            text="", pos=(-1.20, 0.90), scale=0.065,
            fg=C_BRIGHT, align=TextNode.ALeft, mayChange=True, sort=51,
            shadow=(0, 0, 0, 0.7),
        )
        self.announce_timer    = 0.0
        self._announce_total   = 2.0   # durée totale de l'animation

        # ── Trapèzes dégâts style HL2 — géométrie custom avec dégradé ──
        self._dmg_left_np  = self._make_damage_trapeze(game, side='left')
        self._dmg_right_np = self._make_damage_trapeze(game, side='right')
        self._dmg_timer    = 0.0    # durée restante
        self._dmg_max      = 2.4    # durée totale fade
        self._dmg_peak     = 0.0    # intensité au déclenchement (0..1)
        self._dmg_intensity = 0.0   # intensité courante appliquée aux vertices

        self.game_over_text = OnscreenText(
            text="", pos=(0, 0.08), scale=0.1,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )
        self.game_over_sub = OnscreenText(
            text="", pos=(0, -0.05), scale=0.035,
            fg=C_ORANGE, align=TextNode.ACenter, mayChange=True, sort=50,
        )

        # Attitude — désactivé
        self.attitude_root = game.aspect2d.attachNewNode("attitude")
        self.attitude_root.hide()
        self.attitude_lines = None

        # Pickup feedback
        self.pickup_text = OnscreenText(
            text="", pos=(0, -0.15), scale=0.04,
            fg=Vec4(1, 1, 1, 1), align=TextNode.ACenter,
            mayChange=True, sort=50, shadow=(0, 0, 0, 0.6),
        )
        self.pickup_timer = 0.0

        # Force gauge — bas centre, sous les torpilles
        self.force_label = OnscreenText(
            text="FORCE", pos=(0, -0.72), scale=0.02,
            fg=Vec4(0.4, 0.5, 0.9, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=50,
        )
        self.force_bar = _make_bar(self.bar_root, -0.15, -0.77, 0.3, 0.02, segments=10)
        self.force_ready_text = OnscreenText(
            text="", pos=(0, -0.68), scale=0.025,
            fg=Vec4(0.5, 0.6, 1.0, 1.0), align=TextNode.ACenter,
            mayChange=True, sort=50,
        )

        # Force overlay (bleu semi-transparent)
        self.force_overlay = DirectFrame(
            frameColor=Vec4(0.1, 0.15, 0.4, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=98,
        )

        # ===== SCREEN FLASH (blanc, grosses explosions / mort boss) =====
        self.screen_flash = DirectFrame(
            frameColor=Vec4(1, 1, 1, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=102,
        )
        self.screen_flash_timer     = 0.0
        self.screen_flash_duration  = 0.15
        self.screen_flash_intensity = 0.35

        # ===== COMBO TEXT (côté droit, hors regard central) =====
        self.combo_text = OnscreenText(
            text="", pos=(1.15, 0.40), scale=0.07,
            fg=Vec4(1.0, 0.55, 0.1, 0.0),
            align=TextNode.ARight, mayChange=True, sort=65,
            shadow=(0, 0, 0, 0.6),
        )
        self.combo_timer = 0.0

        # (pips 3D torpilles supprimés — remplacés par losange aspect2d near-ship)
        # (barre chaleur 3D supprimée — remplacée par warning near-ship)

        # ===== PYRAMIDE ALTITUDE =====
        self.altitude_root = game.aspect2d.attachNewNode("altitude_pyramid")
        self.altitude_root.setTransparency(TransparencyAttrib.MAlpha)
        self.altitude_root.setBin("fixed", 48)
        self.altitude_root.setDepthTest(False)
        self.altitude_root.setDepthWrite(False)
        self.altitude_lines = None

        # ===== PANNEAU RADIO BOSS (bas d'écran, style HUD militaire) =====
        # Géométrie : rectangle + 2 demi-cercles — affiché uniquement pendant le boss
        _P_CZ = -0.810    # Centre Z du panneau
        _P_HW = 0.55      # Demi-largeur rectangle
        _P_HH = 0.060     # Demi-hauteur = rayon demi-cercles
        # Panneau spans Z : -0.870 à -0.750

        self._boss_bar_visible = False
        self._boss_panel_root  = game.aspect2d.attachNewNode("boss_radio")
        self._boss_panel_root.setTransparency(TransparencyAttrib.MAlpha)
        self._boss_panel_root.hide()

        # Fond sombre semi-transparent
        _make_panel_bg(
            self._boss_panel_root, 0, _P_CZ, _P_HW, _P_HH,
            Vec4(0.02, 0.0, 0.0, 0.82),
        )
        # Bordure orange-rouge lumineuse
        _make_panel_border(
            self._boss_panel_root, 0, _P_CZ, _P_HW, _P_HH,
            Vec4(1.0, 0.25, 0.04, 0.95), thickness=1.5,
        )
        # Ligne décorative intérieure (séparateur entre nom et barre)
        _make_panel_border(
            self._boss_panel_root, 0, _P_CZ, _P_HW * 0.88, _P_HH * 0.30,
            Vec4(0.8, 0.2, 0.03, 0.30), thickness=1.0,
        )

        # Barre HP à l'intérieur
        self.boss_bar_root = self._boss_panel_root   # alias pour compatibilité
        self.boss_bar = _make_bar(
            self._boss_panel_root, -0.42, _P_CZ - 0.013, 0.84, 0.017, segments=20
        )

        # Textes (hors hiérarchie NodePath → gérés manuellement)
        self.boss_name_text = OnscreenText(
            text="", pos=(0, _P_CZ + 0.036), scale=0.025,
            fg=Vec4(1.0, 0.25, 0.05, 0.95),
            align=TextNode.ACenter, mayChange=True, sort=55,
            shadow=(0, 0, 0, 0.9),
        )
        self.boss_phase_text = OnscreenText(
            text="", pos=(0, _P_CZ - 0.033), scale=0.018,
            fg=Vec4(1.0, 0.50, 0.10, 0.80),
            align=TextNode.ACenter, mayChange=True, sort=55,
        )

        # ===== VISEUR CENTRE =====
        self.crosshair = self._make_crosshair(game)

        # ===== WARNING ASTÉROÏDES =====
        self._ast_warn_l = OnscreenText(
            text="", pos=(-1.30, 0.0), scale=0.055,
            fg=Vec4(1.0, 0.15, 0.05, 0.0), align=TextNode.ACenter,
            mayChange=True, sort=80, shadow=(0,0,0,0.6),
        )
        self._ast_warn_r = OnscreenText(
            text="", pos=( 1.30, 0.0), scale=0.055,
            fg=Vec4(1.0, 0.15, 0.05, 0.0), align=TextNode.ACenter,
            mayChange=True, sort=80, shadow=(0,0,0,0.6),
        )
        self._ast_warn_timer = 0.0

    def _make_crosshair(self, game):
        """Viseur fixe : croix simple 4 branches avec gap central, jaune."""
        c = Vec4(0.95, 0.82, 0.18, 0.80)

        # Nœud racine positionné chaque frame par _update_crosshair_static()
        root = game.aspect2d.attachNewNode("crosshair_static")
        root.setBin("fixed", 60)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.setTransparency(TransparencyAttrib.MAlpha)

        # Géométrie à échelle 1.0 — scale mis à jour dans update()
        # 4 petits traits (ticks) aux positions cardinales, qui croisent le cercle
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("xhair_s", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        # Chaque tick va de r_in à r_out en traversant le bord du cercle (r=1.0)
        r_in  = 0.65   # début côté centre
        r_out = 1.25   # fin côté extérieur
        segs = [
            (0,  r_in,  0,  r_out),   # haut
            (0, -r_in,  0, -r_out),   # bas
            ( r_in, 0,  r_out, 0),    # droite
            (-r_in, 0, -r_out, 0),    # gauche
        ]
        for x0, z0, x1, z1 in segs:
            vw.addData3(x0, 0, z0);  cw.addData4(c)
            vw.addData3(x1, 0, z1);  cw.addData4(c)

        lines = GeomLines(Geom.UHStatic)
        for i in range(0, 8, 2):
            lines.addVertices(i, i + 1)

        geom = Geom(vdata)
        geom.addPrimitive(lines)
        gn = GeomNode("xhair_s_mesh")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.reparentTo(root)
        np.setRenderModeThickness(1.5)
        np.setScale(0.022)   # recalculé dans _update_crosshair_static()
        self._crosshair_geom = np

        return root

    def update(self, dt, score, wave, enemy_count, health, max_health,
               heat_pct=0.0, overheated=False, cooldown_pct=0.0,
               roll=0.0, pitch=0.0, torpedo_count=0, player_node=None,
               force_pct=0.0, force_active=False, player_z=0.0):
        self.blink_timer += dt

        # Score
        self.score_text.setText(f"{score:,}".replace(",", " "))

        # Warnings near-ship (chaleur)
        self._update_heat_warnings(player_node, heat_pct, overheated, self.blink_timer)
        self._update_ship_hud(player_node, heat_pct, overheated, torpedo_count,
                              force_pct, force_active, health, max_health)
        self._update_torp_display(torpedo_count, 20, self.blink_timer)

        # Force gauge — drain continu en usage, recharge aux kills
        if force_active:
            # En cours d'utilisation : bleu vif pulsant, drain visible
            pulse = 0.85 + 0.15 * abs(math.sin(self.blink_timer * 9))
            force_color = Vec4(0.3 * pulse, 0.5 * pulse, 1.0 * pulse, 1.0)
            self.force_ready_text.setText("FORCE ACTIVE")
            self.force_ready_text.setFg(Vec4(0.4, 0.6, 1.0, pulse))
        elif force_pct >= 1.0:
            # Jauge pleine — pulse pour signaler
            pulse = 0.7 + 0.3 * abs(math.sin(self.blink_timer * 4))
            force_color = Vec4(0.5 * pulse, 0.6 * pulse, 1.0 * pulse, 1.0)
            self.force_ready_text.setText("USE THE FORCE")
            self.force_ready_text.setFg(Vec4(0.5, 0.6, 1.0, pulse))
        elif force_pct > 0.05:
            # Jauge disponible (pas pleine) — bleu atténué, pas de texte
            force_color = Vec4(0.3, 0.4, 0.85, 0.7)
            self.force_ready_text.setText("")
        else:
            # Vide
            force_color = Vec4(0.15, 0.2, 0.5, 0.4)
            self.force_ready_text.setText("")
        _update_bar(self.force_bar, force_pct, force_color)

        # Force overlay bleu
        if force_active:
            self.force_overlay["frameColor"] = Vec4(0.08, 0.1, 0.3, 0.15)
        else:
            self.force_overlay["frameColor"] = Vec4(0.1, 0.15, 0.4, 0)

        # Wave — texte unifié "WAVE X"
        self.wave_text.setText(f"WAVE {wave}")

        # Attitude — désactivé
        # self._update_attitude(roll, pitch)

        # Annonce wave — dezoom + fade
        if self.announce_timer > 0:
            self.announce_timer -= dt
            progress = max(0.0, self.announce_timer / self._announce_total)  # 1 → 0
            # dezoom : 0.065 → 0.040 (taille du label permanent)
            scale = 0.040 + 0.025 * progress
            self.wave_announce.setScale(scale)
            # fade : visible la première moitié, disparaît en seconde moitié
            alpha = min(1.0, progress * 2.0)
            self.wave_announce.setFg(Vec4(C_BRIGHT.getX(), C_BRIGHT.getY(), C_BRIGHT.getZ(), alpha))
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # ── Trapèzes dégâts style HL2 ──
        if self._dmg_timer > 0:
            self._dmg_timer -= dt
            t = max(0.0, self._dmg_timer / self._dmg_max)
            a = self._dmg_peak * (t ** 0.55)
            self._dmg_intensity = a
            self._set_trapeze_alpha(self._dmg_left_np,  a, 'left')
            self._set_trapeze_alpha(self._dmg_right_np, a, 'right')
        elif self._dmg_intensity > 0.0:
            self._dmg_intensity = 0.0
            self._set_trapeze_alpha(self._dmg_left_np,  0.0, 'left')
            self._set_trapeze_alpha(self._dmg_right_np, 0.0, 'right')

        # ── Warning astéroïdes ──
        if self._ast_warn_timer > 0:
            self._ast_warn_timer -= dt
            a = min(1.0, self._ast_warn_timer / 0.25) * 0.95
            blink = 0.6 + 0.4 * abs(math.sin(self.blink_timer * 14))
            self._ast_warn_l.setFg(Vec4(1.0, 0.15, 0.05, a * blink))
            self._ast_warn_r.setFg(Vec4(1.0, 0.15, 0.05, a * blink))
        else:
            self._ast_warn_l.setFg(Vec4(1.0, 0.15, 0.05, 0.0))
            self._ast_warn_r.setFg(Vec4(1.0, 0.15, 0.05, 0.0))

        # Pickup text fade
        if self.pickup_timer > 0:
            self.pickup_timer -= dt
            progress = self.pickup_timer / 1.5
            self.pickup_text.setFg(Vec4(1, 1, 1, progress))
            self.pickup_text.setScale(0.04 + (1.0 - progress) * 0.005)
            if self.pickup_timer <= 0:
                self.pickup_text.setText("")

        # Screen flash blanc
        if self.screen_flash_timer > 0:
            self.screen_flash_timer -= dt
            a = max(0.0, (self.screen_flash_timer / self.screen_flash_duration)
                    * self.screen_flash_intensity)
            self.screen_flash["frameColor"] = Vec4(1, 1, 1, a)
            if self.screen_flash_timer <= 0:
                self.screen_flash["frameColor"] = Vec4(1, 1, 1, 0)

        # Combo text
        if self.combo_timer > 0:
            self.combo_timer -= dt
            progress = self.combo_timer / 1.5
            pulse = 0.85 + 0.15 * abs(math.sin(self.blink_timer * 8))
            self.combo_text.setFg(Vec4(1.0 * pulse, 0.55 * pulse, 0.1, progress))
            self.combo_text.setScale(0.09 + (1.0 - progress) * 0.02)
            if self.combo_timer <= 0:
                self.combo_text.setText("")

        # Flash hit segments
        if self._seg_flash_timer > 0:
            self._seg_flash_timer = max(0.0, self._seg_flash_timer - dt)

        # Étincelles d'impact
        if self._spark_cooldown > 0:
            self._spark_cooldown = max(0.0, self._spark_cooldown - dt)
        dead = []
        for sp in self._sparks:
            sp["life"] -= dt
            if sp["life"] <= 0:
                sp["np"].removeNode()
                dead.append(sp)
            else:
                sp["np"].setX(sp["np"].getX() + sp["vx"] * dt)
                sp["np"].setZ(sp["np"].getZ() + sp["vz"] * dt)
                a = max(0.0, sp["life"] / sp["max_life"]) * 0.90
                sp["np"].setColorScale(Vec4(1.0, sp["og"], 0.0, a))
        for sp in dead:
            self._sparks.remove(sp)

        # Pyramide altitude — désactivée, remplacée par paliers ennemis
        # self._update_altitude_pyramid(player_z)

        # Viseur statique — projection du point de repos du réticule 3D
        self._update_crosshair_static()

    def _update_crosshair_static(self):
        """Met à jour position + taille du viseur fixe en projetant le point de repos
        du réticule 3D (position joueur + CH_DISTANCE=60 devant) via camLens."""
        if not hasattr(self, 'crosshair') or not hasattr(self, '_crosshair_geom'):
            return
        game = self.game
        if not hasattr(game, 'player') or game.player is None:
            return

        sp   = game.player.node.getPos()
        ch_y = sp.getY() + 60.0   # CH_DISTANCE

        # Transforme deux points monde → espace caméra
        p_ctr_cam = game.camera.getRelativePoint(
            game.render, Point3(sp.getX(), ch_y, sp.getZ()))
        p_rim_cam = game.camera.getRelativePoint(
            game.render, Point3(sp.getX(), ch_y, sp.getZ() + 0.6))  # +radius

        p2d_c = Point2()
        p2d_r = Point2()
        ok_c = game.camLens.project(p_ctr_cam, p2d_c)
        ok_r = game.camLens.project(p_rim_cam, p2d_r)

        if not (ok_c and ok_r):
            return

        ar = game.getAspectRatio()
        # NDC [-1,1] → aspect2d : X *= aspect_ratio, Z = NDC_y
        self.crosshair.setPos(p2d_c.getX() * ar, 0, p2d_c.getY())

        radius = abs(p2d_r.getY() - p2d_c.getY())
        if radius > 1e-4:
            self._crosshair_geom.setScale(radius)

    def _build_single_diamond(self, parent, cx, cz, s):
        """Dessine un contour de losange dans parent (aspect2d)."""
        from panda3d.core import GeomLines
        fmt = GeomVertexFormat.getV3c4()
        vd  = GeomVertexData("dout", fmt, Geom.UHStatic)
        v   = GeomVertexWriter(vd, "vertex")
        c   = GeomVertexWriter(vd, "color")
        col = Vec4(0.9, 0.6, 0.1, 0.7)
        v.addData3(cx,   0, cz+s); c.addData4(col)   # top
        v.addData3(cx+s, 0, cz);   c.addData4(col)   # right
        v.addData3(cx,   0, cz-s); c.addData4(col)   # bottom
        v.addData3(cx-s, 0, cz);   c.addData4(col)   # left
        lines = GeomLines(Geom.UHStatic)
        lines.addVertices(0,1); lines.addVertices(1,2)
        lines.addVertices(2,3); lines.addVertices(3,0)
        g  = Geom(vd); g.addPrimitive(lines)
        gn = GeomNode("dout"); gn.addGeom(g)
        np = NodePath(gn)
        np.reparentTo(parent)
        np.setRenderModeThickness(1.8)
        np.setTransparency(TransparencyAttrib.MAlpha)

    def _update_torp_display(self, torpedo_count, max_torp=20, blink_timer=0.0, player_node=None):
        """Compteur torpilles dans le losange bas-centre."""
        if torpedo_count <= 2:
            col = Vec4(1.0, 0.25, 0.0, 0.90)
            if torpedo_count == 0:
                pulse = 0.55 + 0.45 * abs(math.sin(blink_timer * 7))
                col = Vec4(1.0, 0.12, 0.0, pulse)
        else:
            col = Vec4(0.9, 0.6, 0.1, 0.88)
        self._torp_count_text.setText(str(torpedo_count))
        self._torp_count_text.setFg(col)


    def _make_damage_trapeze(self, game, side):
        """Trapèze dégâts — géométrie vertex colors, gradient outer→inner.
        Outer alpha=1 baked, inner alpha=0. Visibilité via setAlphaScale."""
        AR        =  1.78
        EDGE_GAP  =  0.25   # écart bord écran
        OUTER_TOP =  0.68
        OUTER_BOT = -0.68
        INNER_TOP =  0.40
        INNER_BOT = -0.40
        WIDTH     =  0.30

        if side == 'left':
            ox = -(AR - EDGE_GAP)
            ix = -(AR - EDGE_GAP) + WIDTH
        else:
            ox =  (AR - EDGE_GAP)
            ix =  (AR - EDGE_GAP) - WIDTH

        C_OUTER = (0.70, 0.0, 0.0, 1.0)
        C_INNER = (0.40, 0.0, 0.0, 0.0)

        fmt = GeomVertexFormat.getV3c4()
        vd  = GeomVertexData("dmg_trap", fmt, Geom.UHStatic)
        vw  = GeomVertexWriter(vd, "vertex")
        cw  = GeomVertexWriter(vd, "color")

        vw.addData3(ox, 0, OUTER_BOT); cw.addData4(*C_OUTER)
        vw.addData3(ox, 0, OUTER_TOP); cw.addData4(*C_OUTER)
        vw.addData3(ix, 0, INNER_TOP); cw.addData4(*C_INNER)
        vw.addData3(ix, 0, INNER_BOT); cw.addData4(*C_INNER)

        tris = GeomTriangles(Geom.UHStatic)
        tris.addVertices(0, 1, 2)
        tris.addVertices(0, 2, 3)

        geom = Geom(vd); geom.addPrimitive(tris)
        gn   = GeomNode(f"dmg_{side}"); gn.addGeom(geom)

        np = game.aspect2d.attachNewNode(gn)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthTest(False)
        np.setDepthWrite(False)
        # PAS de setBin — c'est ce qui cassait setAlphaScale
        np.setAlphaScale(0.0)   # invisible au départ
        return np

    def _set_trapeze_alpha(self, np, alpha, side=None):
        np.setAlphaScale(max(0.0, min(1.0, alpha)))

    def _update_heat_warnings(self, player_node, heat_pct, overheated, blink_timer):
        """Texte WARN clignotant near-ship — en dessous du vaisseau, centré."""
        warn_x, warn_z = 0.0, -0.15
        if player_node and not player_node.isEmpty():
            game = self.game
            sp = player_node.getPos()
            p_cam = game.camera.getRelativePoint(game.render, sp)
            p2d = Point2()
            if game.camLens.project(p_cam, p2d):
                ar = game.getAspectRatio()
                warn_x = p2d.getX() * ar
                warn_z = p2d.getY() - 0.10

        # WARN near-ship géré par le mini HUD — ce label bas est désactivé
        self._warn_overheat.setText("")

    def _update_ship_hud(self, player_node, heat_pct, overheated,
                         torpedo_count, force_pct, force_active,
                         health=16, max_health=16):
        """Mini HUD — barres persistantes repositionnées chaque frame."""
        if player_node is None or player_node.isEmpty():
            self._sbar_root.hide()
            self._ship_warn_text.setText("")
            return

        game  = self.game
        sp    = player_node.getPos()
        p_cam = game.camera.getRelativePoint(game.render, sp)
        p2d   = Point2()
        if not game.camLens.project(p_cam, p2d):
            self._sbar_root.hide()
            return

        ar = game.getAspectRatio()
        sx = p2d.getX() * ar
        sz = p2d.getY()

        W   = self._sbar_W
        H   = self._sbar_H

        # Ancrage Y — moteurs bas
        eng_world = game.render.getRelativePoint(player_node, Point3(0, -1.20, -0.17))
        eng_cam   = game.camera.getRelativePoint(game.render, eng_world)
        p2d_eng   = Point2()
        if game.camLens.project(eng_cam, p2d_eng):
            lz = p2d_eng.getY() - 0.008
        else:
            lz = sz - 0.055

        # Déplace le root persistant — toute la géométrie suit
        self._sbar_root.setPos(sx - W / 2.0, 0, lz)
        self._sbar_root.show()

        bt = self.blink_timer

        # ── Barre Laser ──────────────────────────────────────────────────────
        if heat_pct > 0.002:
            if overheated:
                pulse = 0.65 + 0.35 * abs(math.sin(bt * 8))
                hc = Vec4(1.0, 0.12 * pulse, 0.0, pulse)
            elif heat_pct > 0.72:
                hc = Vec4(1.0, 0.38, 0.05, 0.90)
            else:
                t  = heat_pct
                hc = Vec4(0.85 + 0.15 * t, 0.65 - 0.45 * t, 0.10, 0.80)
            self._sbar_laser_fill.setScale(min(heat_pct, 1.0), 1.0, 1.0)
            self._sbar_laser_fill.setColorScale(hc)
            self._sbar_laser_fill.show()
        else:
            self._sbar_laser_fill.hide()

        # WARN / OVERHEAT (nœud persistant, repositionné)
        if overheated:
            pulse_w = 0.55 + 0.45 * abs(math.sin(bt * 6))
            self._ship_warn_text.setText("OVERHEAT")
            self._ship_warn_text.setPos(sx, sz + 0.018)
            self._ship_warn_text.setFg(Vec4(1.0, 0.12, 0.0, pulse_w))
        elif heat_pct > 0.65:
            self._ship_warn_text.setText("WARN")
            self._ship_warn_text.setPos(sx, sz + 0.018)
            self._ship_warn_text.setFg(Vec4(1.0, 0.60, 0.10, 0.90))
        else:
            self._ship_warn_text.setText("")
            self._ship_warn_text.setFg(Vec4(1.0, 0.35, 0.0, 0.0))

        # ── Segments vie ────────────────────────────────────────────────────
        n_lit = (max(1, round(health / max(max_health, 1) * 6)) if health > 0 else 0)
        flash_active = self._seg_flash_timer > 0
        for i, seg in enumerate(self._seg_nodes):
            if i >= n_lit:
                seg.hide()
                continue
            seg.show()
            if flash_active:
                seg.setColorScale(Vec4(1.0, 1.0, 1.0, 1.0))
            elif n_lit == 1:
                pulse = 0.55 + 0.45 * abs(math.sin(bt * 5))
                seg.setColorScale(Vec4(1.0, 0.12, 0.04, pulse))
            else:
                seg.setColorScale(C_BRIGHT)

    def _build_torp_pips(self, max_count):
        """Obsolète."""
        pass

    def _update_torp_pips(self, *args, **kwargs):
        """Obsolète."""
        pass

    def _update_altitude_pyramid(self, player_z, bounds_z=8.0):
        """3 barres horizontales en pyramide indiquant l'altitude.
        Pointe vers le haut si Z>0, vers le bas si Z<0.
        Couleur : vert → orange → rouge selon distance au 0.
        Suit la position écran du vaisseau.
        """
        if self.altitude_lines:
            self.altitude_lines.removeNode()
            self.altitude_lines = None

        # Pas d'affichage si proche du 0
        threshold = 0.4
        if abs(player_z) < threshold:
            return

        norm = min(1.0, abs(player_z) / bounds_z)  # 0→1

        # Couleur : vert (0) → orange (0.5) → rouge (1)
        if norm < 0.5:
            t = norm * 2.0
            r, g = t * 0.9, 0.6 - t * 0.2
        else:
            t = (norm - 0.5) * 2.0
            r, g = 0.9 + t * 0.1, 0.4 - t * 0.35
        alpha = 0.35 + norm * 0.45  # plus opaque qu'avant

        # Position écran du vaisseau (même logique que le crosshair)
        base_x, base_z = 0.0, -0.12  # fallback
        game = self.game
        if hasattr(game, 'player') and game.player is not None:
            sp = game.player.node.getPos()
            p_cam = game.camera.getRelativePoint(game.render, sp)
            p2d = Point2()
            if game.camLens.project(p_cam, p2d):
                ar = game.getAspectRatio()
                base_x = p2d.getX() * ar
                base_z = p2d.getY() - 0.08  # légèrement sous le vaisseau

        # Longueurs des 3 barres : grande / moyenne / petite
        lengths = [0.10, 0.065, 0.032]
        spacing = 0.022  # serré

        # Z>0 → pointe vers le haut (petite barre en haut)
        # Z<0 → pointe vers le bas (petite barre en bas)
        pointing_up = player_z > 0

        fmt = GeomVertexFormat.getV3c4()
        vd = GeomVertexData("alt", fmt, Geom.UHDynamic)
        vw = GeomVertexWriter(vd, "vertex")
        cw = GeomVertexWriter(vd, "color")
        lines = GeomLines(Geom.UHDynamic)

        for i, half_len in enumerate([l / 2.0 for l in lengths]):
            if pointing_up:
                bz = base_z + i * spacing       # grande en bas, petite en haut
            else:
                bz = base_z + (2 - i) * spacing  # grande en haut, petite en bas

            fade = 1.0 - i * 0.15
            bar_col = Vec4(r, g, 0.05, alpha * fade)

            idx_base = i * 2
            vw.addData3(base_x - half_len, 0, bz); cw.addData4(bar_col)
            vw.addData3(base_x + half_len, 0, bz); cw.addData4(bar_col)
            lines.addVertices(idx_base, idx_base + 1)

        geom = Geom(vd)
        geom.addPrimitive(lines)
        gn = GeomNode("alt_pyramid")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.reparentTo(self.altitude_root)
        np.setRenderModeThickness(2.5)
        self.altitude_lines = np

    def _update_attitude(self, roll, pitch):
        if self.attitude_lines:
            self.attitude_lines.removeNode()

        fmt = GeomVertexFormat.getV3c4()
        vd = GeomVertexData("att", fmt, Geom.UHDynamic)
        v = GeomVertexWriter(vd, "vertex")
        c = GeomVertexWriter(vd, "color")

        roll_rad = math.radians(roll * 0.015)
        p_off = pitch * 0.003
        col = Vec4(1, 0.55, 0.1, 0.12)
        col_c = Vec4(1, 0.55, 0.1, 0.2)
        cos_r, sin_r = math.cos(roll_rad), math.sin(roll_rad)

        h = 0.08
        v.addData3(-h*cos_r, 0, -h*sin_r+p_off); c.addData4(col_c)
        v.addData3(h*cos_r, 0, h*sin_r+p_off); c.addData4(col_c)

        for off in [0.18, 0.3]:
            for side in [-1, 1]:
                x1, x2 = side*off, side*(off+0.05)
                z1 = x1*sin_r/cos_r+p_off if cos_r != 0 else p_off
                z2 = x2*sin_r/cos_r+p_off if cos_r != 0 else p_off
                v.addData3(x1, 0, z1); c.addData4(col)
                v.addData3(x2, 0, z2); c.addData4(col)

        lines = GeomLines(Geom.UHDynamic)
        for i in range(5):
            lines.addVertices(i*2, i*2+1)
        g = Geom(vd)
        g.addPrimitive(lines)
        n = GeomNode("att")
        n.addGeom(g)
        self.attitude_lines = NodePath(n)
        self.attitude_lines.reparentTo(self.attitude_root)
        self.attitude_lines.setRenderModeThickness(1.0)

    # ------------------------------------------------------------------
    # Nouveaux effets V2
    # ------------------------------------------------------------------

    def on_hit(self):
        """Flash blanc segments + étincelles — appelé depuis game.py au hit joueur."""
        self._seg_flash_timer = 0.10
        if self._spark_cooldown <= 0:
            self._spawn_sparks()
            self._spark_cooldown = 0.35

    def _spawn_sparks(self):
        """6 à 8 particules orange/blanc depuis la position écran du vaisseau."""
        import random
        game = self.game
        if not hasattr(game, 'player') or game.player is None:
            return
        sp = game.player.node.getPos()
        p_cam = game.camera.getRelativePoint(game.render, sp)
        p2d = Point2()
        if not game.camLens.project(p_cam, p2d):
            return
        ar = game.getAspectRatio()
        sx = p2d.getX() * ar
        sz = p2d.getY()

        count = random.randint(12, 18)
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.15, 0.45)
            vx = math.cos(angle) * speed
            vz = math.sin(angle) * speed
            life = random.uniform(0.20, 0.32)
            og = random.uniform(0.45, 0.85)

            hw = random.uniform(0.002, 0.006)
            hh = hw * random.uniform(0.5, 0.9)
            np = _make_rect(game.aspect2d,
                            sx - hw / 2, sz - hh / 2, hw, hh,
                            Vec4(1.0, og, 0.0, 0.50))
            np.setBin("fixed", 60)
            np.setDepthTest(False)
            np.setDepthWrite(False)
            np.setAttrib(ColorBlendAttrib.make(
                ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
            self._sparks.append({"np": np, "vx": vx, "vz": vz,
                                  "life": life, "max_life": life, "og": og})

    def trigger_screen_flash(self, intensity=0.35, duration=0.15):
        """Flash blanc plein écran — grosses explosions ou mort boss."""
        self.screen_flash_timer     = duration
        self.screen_flash_duration  = duration
        self.screen_flash_intensity = intensity

    def show_combo(self, count):
        """Affiche 'xN COMBO !' en orange pulsant en haut de l'écran."""
        self.combo_text.setText(f"x{count} COMBO!")
        boost = min(0.15, (count - 3) * 0.02)
        self.combo_text.setScale(0.09 + boost)
        self.combo_text.setFg(Vec4(1.0, 0.55, 0.1, 1.0))
        self.combo_timer = 1.5

    def show_boss_bar(self, name="DARTH VADER — TIE ADVANCED"):
        """Affiche le panneau radio boss."""
        self.boss_name_text.setText(f"◈  {name}")
        self._boss_panel_root.show()
        self._boss_bar_visible = True

    def hide_boss_bar(self):
        self._boss_panel_root.hide()
        self._boss_bar_visible = False
        self.boss_name_text.setText("")
        self.boss_phase_text.setText("")

    def update_boss_bar(self, hp_pct, phase_label=""):
        if not self._boss_bar_visible:
            return
        bar_c = C_DANGER if hp_pct < 0.35 else (C_WARN if hp_pct < 0.65 else C_ORANGE)
        _update_bar(self.boss_bar, max(0.0, hp_pct), bar_c)
        self.boss_phase_text.setText(phase_label)

    # ------------------------------------------------------------------

    def announce_wave(self, wave_num):
        self.wave_announce.setText(f"WAVE {wave_num}")
        self.wave_announce.setScale(0.065)
        self.wave_announce.setFg(Vec4(C_BRIGHT.getX(), C_BRIGHT.getY(), C_BRIGHT.getZ(), 1.0))
        self.announce_timer = self._announce_total

    def show_damage_flash(self, hp_pct=0.5):
        """Trapèzes rouges latéraux style HL2 — intensité fixe."""
        self._dmg_peak  = 0.88
        self._dmg_timer = self._dmg_max

    def show_shield_flash(self):
        """Conservé pour compatibilité — ne fait plus rien de visible."""
        pass

    def show_asteroid_warning(self, side='both'):
        """Déclenche le warning astéroïde — ◄ à gauche et/ou ► à droite."""
        self._ast_warn_timer = 0.55
        txt = "◄ ! ►" if side == 'both' else ("◄ !" if side == 'left' else "! ►")
        self._ast_warn_l.setText("◄ !")
        self._ast_warn_r.setText("! ►")

    def hide_all(self):
        """Cache immédiatement TOUT le HUD — appelé au début du fondu game over."""
        self._seg_flash_timer = 0.0
        for sp in self._sparks:
            sp["np"].removeNode()
        self._sparks.clear()

        # Trapèzes
        self._dmg_timer     = 0.0
        self._dmg_peak      = 0.0
        self._dmg_intensity = 0.0
        self._set_trapeze_alpha(self._dmg_left_np,  0.0)
        self._set_trapeze_alpha(self._dmg_right_np, 0.0)

        # Flash blanc
        self.screen_flash_timer = 0.0
        self.screen_flash["frameColor"] = Vec4(1, 1, 1, 0)

        # Force overlay
        self.force_overlay["frameColor"] = Vec4(0, 0, 0, 0)

        # Boss bar + textes boss
        self.hide_boss_bar()

        # Tous les textes HUD
        self.game_over_text.setText("")
        self.game_over_sub.setText("")
        self.wave_announce.setText("")
        self.pickup_text.setText("")
        self._warn_overheat.setText("")
        self._ship_warn_text.setText("")
        self._ship_warn_text.setFg(Vec4(1.0, 0.35, 0.0, 0.0))
        self.combo_text.setText("")
        self.force_ready_text.setText("")

        # Warnings astéroïdes
        self._ast_warn_timer = 0.0
        self._ast_warn_l.setFg(Vec4(1, 0, 0, 0))
        self._ast_warn_r.setFg(Vec4(1, 0, 0, 0))

        # Mini HUD near-ship — barres persistantes
        self._sbar_root.hide()

        # Cache les barres + overlay complet
        self.bar_root.hide()
        if self.overlay:
            self.overlay.hide()

    def reset(self):
        """Remet tous les états transitoires à zéro — appelé au restart."""
        self._seg_flash_timer = 0.0
        self._spark_cooldown  = 0.0
        for sp in self._sparks:
            sp["np"].removeNode()
        self._sparks.clear()

        self._dmg_timer     = 0.0
        self._dmg_peak      = 0.0
        self._dmg_intensity = 0.0
        self._set_trapeze_alpha(self._dmg_left_np,  0.0)
        self._set_trapeze_alpha(self._dmg_right_np, 0.0)

        self.screen_flash_timer = 0.0
        self.screen_flash["frameColor"] = Vec4(1, 1, 1, 0)
        self.force_overlay["frameColor"] = Vec4(0, 0, 0, 0)

        self.blink_timer    = 0.0
        self.announce_timer = 0.0
        self.pickup_timer   = 0.0

        self.wave_announce.setText("")
        self.pickup_text.setText("")
        self.game_over_text.setText("")
        self.game_over_sub.setText("")
        self._warn_overheat.setText("")
        self._ship_warn_text.setText("")
        self._ship_warn_text.setFg(Vec4(1.0, 0.35, 0.0, 0.0))
        self.combo_text.setText("")

        self.hide_boss_bar()

        self._ast_warn_timer = 0.0
        self._ast_warn_l.setFg(Vec4(1, 0, 0, 0))
        self._ast_warn_r.setFg(Vec4(1, 0, 0, 0))

        # Mini HUD near-ship — barres persistantes
        self._sbar_root.hide()

        # Réaffiche les barres et overlay si cachés
        self.bar_root.show()
        if self.overlay:
            self.overlay.show()

    def show_pickup(self, text, color=None):
        """Affiche un texte de pickup qui fade. color = Vec4 optionnel."""
        self.pickup_text.setText(text)
        self.pickup_text.setFg(color if color is not None else Vec4(1, 1, 1, 1))
        self.pickup_text.setScale(0.05)
        self.pickup_timer = 1.5

    def show_game_over(self, score):
        self.game_over_text.setText("DESTROYED")
        self.game_over_sub.setText(f"Final score: {score:,}".replace(",", " "))

    # =========================================
    # LEADERBOARD SCREENS
    # =========================================

    def show_name_entry(self):
        """Affiche l'écran de saisie du nom (frappe clavier)."""
        self._clear_leaderboard()
        self.name_entry_active = True
        self.typed_name = ""

        # Fond sombre
        self.lb_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.7),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=55,
        )

        self.lb_title = OnscreenText(
            text="NEW HIGH SCORE!", pos=(0, 0.55), scale=0.07,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=False, sort=60,
            shadow=(0, 0, 0, 0.8),
        )
        self.lb_subtitle = OnscreenText(
            text="ENTER YOUR NAME", pos=(0, 0.45), scale=0.035,
            fg=C_ORANGE, align=TextNode.ACenter, mayChange=False, sort=60,
        )

        self.name_display = OnscreenText(
            text="___", pos=(0, 0.30), scale=0.09,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True, sort=60,
            shadow=(0, 0, 0, 0.8),
        )

        self.lb_controls = OnscreenText(
            text="TYPE 3 LETTERS  |  BACKSPACE TO DELETE  |  ENTER TO VALIDATE",
            pos=(0, 0.18), scale=0.022,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )

    def update_name_entry(self, key):
        """Gère la frappe clavier pour le nom."""
        if not hasattr(self, 'name_entry_active') or not self.name_entry_active:
            return False

        if key == "backspace":
            self.typed_name = self.typed_name[:-1]
        elif key == "enter":
            if len(self.typed_name) > 0:
                self.name_entry_active = False
                return self.typed_name[:3].upper()
        elif len(key) == 1 and key.isalpha() and len(self.typed_name) < 3:
            self.typed_name += key.upper()

        # Affiche avec des underscores pour les places vides
        display = self.typed_name + "_" * (3 - len(self.typed_name))
        if hasattr(self, 'name_display'):
            self.name_display.setText(display)

        return False

    def _update_name_display(self):
        pass  # Plus utilisé avec la frappe clavier

    def show_leaderboard(self, entries, highlight_rank=None):
        """Affiche le tableau des scores."""
        self._clear_leaderboard()
        self.leaderboard_active = True

        # Fond sombre
        self.lb_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.7),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=55,
        )

        self.lb_elements = []

        title = OnscreenText(
            text="TOP PILOTS", pos=(0, 0.65), scale=0.06,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=False, sort=60,
            shadow=(0, 0, 0, 0.8),
        )
        self.lb_elements.append(title)

        # En-tête
        header = OnscreenText(
            text="  #   NAME   SCORE    WAVE  KILLS   DATE",
            pos=(0, 0.55), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )
        self.lb_elements.append(header)

        # Lignes
        for i, entry in enumerate(entries[:10]):
            rank = i + 1
            name = entry.get("name", "???")
            score = entry.get("score", 0)
            wave = entry.get("wave", 0)
            kills = entry.get("kills", 0)
            date = entry.get("date", "")

            line = f" {rank:>2}.   {name}   {score:>6}     {wave:>2}     {kills:>3}   {date}"

            is_highlight = (highlight_rank is not None and rank == highlight_rank)
            fg = C_BRIGHT if is_highlight else C_ORANGE

            t = OnscreenText(
                text=line, pos=(0, 0.48 - i * 0.07), scale=0.028,
                fg=fg, align=TextNode.ACenter, mayChange=False, sort=60,
            )
            self.lb_elements.append(t)

        restart = OnscreenText(
            text="PRESS R TO PLAY AGAIN", pos=(0, -0.35), scale=0.03,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )
        self.lb_elements.append(restart)

    def _clear_leaderboard(self):
        """Nettoie les éléments du leaderboard."""
        if hasattr(self, 'lb_bg') and self.lb_bg:
            self.lb_bg.destroy()
            self.lb_bg = None
        for attr in ['lb_title', 'lb_subtitle', 'lb_controls']:
            if hasattr(self, attr):
                getattr(self, attr).destroy()
                delattr(self, attr)
        if hasattr(self, 'name_texts'):
            for t in self.name_texts:
                t.destroy()
            del self.name_texts
        if hasattr(self, 'name_display'):
            self.name_display.destroy()
            del self.name_display
        if hasattr(self, 'lb_elements'):
            for e in self.lb_elements:
                e.destroy()
            del self.lb_elements
        self.name_entry_active = False
        self.leaderboard_active = False
