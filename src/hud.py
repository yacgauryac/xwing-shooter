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

        # ===== WAVE (haut gauche) =====
        self.wave_label = OnscreenText(
            text="WAVE", pos=(-1.2, 0.90), scale=0.028,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ALeft,
            mayChange=False, sort=50,
        )
        self.wave_text = OnscreenText(
            text="1", pos=(-1.05, 0.90), scale=0.04,
            fg=C_BRIGHT, align=TextNode.ALeft,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== HOSTILES (haut droit) =====
        self.hostiles_label = OnscreenText(
            text="HOSTILES", pos=(1.2, 0.90), scale=0.028,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ARight,
            mayChange=False, sort=50,
        )
        self.hostiles_text = OnscreenText(
            text="0", pos=(1.05, 0.90), scale=0.04,
            fg=C_DANGER, align=TextNode.ARight,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== BARRES EN BAS (sous la ligne inférieure de l'overlay) =====
        self.bar_root = game.aspect2d.attachNewNode("bars")
        self.bar_root.setTransparency(TransparencyAttrib.MAlpha)
        self.bar_root.setBin("fixed", 45)

        # Shield — bas gauche, ENTRE les lignes du cadre
        self.shield_label = OnscreenText(
            text="SHIELD", pos=(-0.75, -0.90), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ALeft,
            mayChange=False, sort=50,
        )
        self.shield_bar = _make_bar(self.bar_root, -0.75, -0.95, 0.5, 0.025, segments=12)

        # Laser Energy — bas droit, label en haut à droite de la barre
        self.laser_label = OnscreenText(
            text="LASER", pos=(0.76, -0.90), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ARight,
            mayChange=False, sort=50,
        )
        self.heat_bar = _make_bar(self.bar_root, 0.25, -0.95, 0.5, 0.025, segments=12)
        self.overheat_text = OnscreenText(
            text="", pos=(0.50, -0.90), scale=0.022,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True, sort=50,
        )

        # Torpedo counter — losange + chiffre en bas
        self.torpedo_label = OnscreenText(
            text="TORP", pos=(0, -0.83), scale=0.020,
            fg=Vec4(0.9, 0.55, 0.15, 0.5), align=TextNode.ACenter,
            mayChange=False, sort=50,
        )
        self.torpedo_count_text = OnscreenText(
            text="20", pos=(0, -0.935), scale=0.038,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True, sort=52,
            shadow=(0, 0, 0, 0.9),
        )
        # Losange bas-centre (20% plus petit : 0.07 → 0.056)
        self._torp_diamond_root = game.aspect2d.attachNewNode("torp_diamond")
        self._torp_diamond_root.setBin("fixed", 50)
        self._torp_diamond_root.setDepthTest(False)
        self._torp_diamond_root.setDepthWrite(False)
        self._torp_diamond_root.setTransparency(TransparencyAttrib.MAlpha)
        self._build_single_diamond(self._torp_diamond_root, 0, -0.93, 0.056)
        self._torp_diamonds = []

        # ===== WARNINGS near-ship (overheat + torp low) =====
        self._warn_overheat = OnscreenText(
            text="", pos=(0, 0.12), scale=0.032,
            fg=Vec4(1.0, 0.15, 0.0, 1.0), align=TextNode.ACenter,
            mayChange=True, sort=55, shadow=(0,0,0,0.8),
        )
        self._warn_torp = OnscreenText(
            text="", pos=(0, 0.07), scale=0.028,
            fg=Vec4(1.0, 0.65, 0.1, 1.0), align=TextNode.ACenter,
            mayChange=True, sort=55, shadow=(0,0,0,0.8),
        )
        self._warn_torp_shown = False

        # ===== ANNONCE / FLASH / GAME OVER =====
        self.wave_announce = OnscreenText(
            text="", pos=(-1.15, 0.35), scale=0.05,
            fg=C_BRIGHT, align=TextNode.ALeft, mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.5),
        )
        self.announce_timer = 0.0

        self.damage_flash = DirectFrame(
            frameColor=Vec4(1, 0.3, 0, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=100,
        )
        self.flash_timer = 0.0

        # Shield flash bleu (bords d'écran)
        self.shield_flash = DirectFrame(
            frameColor=Vec4(0.8, 0.1, 0.0, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=99,
        )
        self.shield_flash_timer = 0.0

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

        # ===== BARRE CHALEUR LASER (suit le vaisseau) =====
        self.heat_bar_root = game.render.attachNewNode("heat_bar_3d")
        self.heat_bar_root.setLightOff()
        self.heat_bar_root.setBin("fixed", 46)
        self.heat_bar_root.setDepthWrite(False)
        self.heat_bar_root.setDepthTest(False)
        self.heat_bar_root.setTransparency(TransparencyAttrib.MAlpha)
        self._heat_bar_fill = None
        self._heat_bar_bg   = None
        self._build_heat_bar_3d()

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

    def _make_crosshair(self, game):
        """Viseur fixe : croix simple 4 branches avec gap central, vert."""
        c = Vec4(0.2, 1.0, 0.3, 0.75)

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

        # Torpilles + warnings
        self._update_torp_display(torpedo_count, 20, self.blink_timer)
        if player_node:
            self._update_heat_bar_3d(player_node, heat_pct, overheated, self.blink_timer)

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

        # Wave + hostiles
        self.wave_text.setText(f"{wave}")
        self.hostiles_text.setText(f"{enemy_count}")

        # Shield
        hp = max(0, health / max_health)
        if hp > 0.5:
            bar_c = C_ORANGE
        elif hp > 0.25:
            bar_c = C_WARN
        else:
            bar_c = C_DANGER
        _update_bar(self.shield_bar, hp, bar_c)

        # Laser energy
        disp = cooldown_pct if overheated else heat_pct
        energy = 1.0 - disp
        if overheated:
            blink = abs(math.sin(self.blink_timer * 6))
            self.overheat_text.setText("OVERHEAT")
            self.overheat_text.setFg(Vec4(1, 0.15, 0.05, 0.5 + 0.5 * blink))
            _update_bar(self.heat_bar, energy, C_DANGER)
        else:
            self.overheat_text.setText("")
            _update_bar(self.heat_bar, energy, C_ORANGE)

        # Attitude — désactivé
        # self._update_attitude(roll, pitch)

        # Annonce
        if self.announce_timer > 0:
            self.announce_timer -= dt
            a = min(1.0, self.announce_timer / 0.5)
            self.wave_announce.setFg(Vec4(C_BRIGHT.getX(), C_BRIGHT.getY(), C_BRIGHT.getZ(), a))
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # Flash dégâts orange
        if self.flash_timer > 0:
            self.flash_timer -= dt
            a = max(0, self.flash_timer / 0.3) * 0.2
            self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, a)
            if self.flash_timer <= 0:
                self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, 0)

        # Flash bouclier bleu
        if self.shield_flash_timer > 0:
            self.shield_flash_timer -= dt
            progress = self.shield_flash_timer / 0.3
            a = progress * 0.35
            self.shield_flash["frameColor"] = Vec4(0.9, 0.15, 0.0, a)
            if self.shield_flash_timer <= 0:
                self.shield_flash["frameColor"] = Vec4(0.8, 0.1, 0.0, 0)

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

    def _update_torp_display(self, torpedo_count, max_torp, blink_timer):
        """Met à jour le chiffre torpilles bas + warnings near-ship."""
        if torpedo_count <= 3:
            pulse = abs(math.sin(blink_timer * 8))
            fg = Vec4(1.0, 0.1 + 0.1*pulse, 0.0, 1.0)
        elif torpedo_count <= max_torp // 3:
            fg = Vec4(1.0, 0.65, 0.1, 1.0)
        else:
            fg = Vec4(0.85, 0.95, 1.0, 1.0)
        self.torpedo_count_text.setText(str(torpedo_count))
        self.torpedo_count_text['fg'] = fg

        # Warning torpilles basses (≤ 1/3 du max)
        if torpedo_count <= max_torp // 3 and torpedo_count > 0:
            if torpedo_count <= 3:
                pulse = abs(math.sin(blink_timer * 7))
                self._warn_torp['fg'] = Vec4(1.0, 0.1+0.1*pulse, 0.0, 1.0)
                self._warn_torp.setText("◆ TORP CRITIQUE ◆")
            else:
                self._warn_torp['fg'] = Vec4(1.0, 0.65, 0.1, 0.9)
                self._warn_torp.setText("◆ TORP FAIBLES")
        else:
            self._warn_torp.setText("")

    def _build_heat_bar_3d(self):
        """Barre chaleur 3D — géométrie de 0 à BAR_W dans plan XZ.
        Root positionné au bord gauche → setScale(pct) = remplissage gauche→droite."""
        BAR_W = 1.6
        BAR_H = 0.10
        fmt = GeomVertexFormat.getV3c4()

        # Fond sombre (0 → BAR_W)
        vd = GeomVertexData("hbg", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vd, "vertex"); c = GeomVertexWriter(vd, "color")
        col_bg = Vec4(0.08, 0.04, 0.01, 0.65)
        v.addData3(0,     0,      0); c.addData4(col_bg)
        v.addData3(BAR_W, 0,      0); c.addData4(col_bg)
        v.addData3(BAR_W, 0, BAR_H); c.addData4(col_bg)
        v.addData3(0,     0, BAR_H); c.addData4(col_bg)
        tris = GeomTriangles(Geom.UHStatic)
        tris.addVertices(0,1,2); tris.addVertices(0,2,3)
        g = Geom(vd); g.addPrimitive(tris)
        gn = GeomNode("hbg"); gn.addGeom(g)
        bg2 = NodePath(gn); bg2.reparentTo(self.heat_bar_root); bg2.setTransparency(TransparencyAttrib.MAlpha)

        # Fill (0 → BAR_W) — setScale(pct,1,1) depuis l'origine = gauche→droite ✓
        vd2 = GeomVertexData("hbf", fmt, Geom.UHStatic)
        v2 = GeomVertexWriter(vd2, "vertex"); c2 = GeomVertexWriter(vd2, "color")
        col_f = Vec4(0.4, 0.9, 0.2, 0.95)
        v2.addData3(0,     0,      0); c2.addData4(col_f)
        v2.addData3(BAR_W, 0,      0); c2.addData4(col_f)
        v2.addData3(BAR_W, 0, BAR_H); c2.addData4(col_f)
        v2.addData3(0,     0, BAR_H); c2.addData4(col_f)
        tris2 = GeomTriangles(Geom.UHStatic)
        tris2.addVertices(0,1,2); tris2.addVertices(0,2,3)
        g2 = Geom(vd2); g2.addPrimitive(tris2)
        gn2 = GeomNode("hbf"); gn2.addGeom(g2)
        fill = NodePath(gn2)
        fill.reparentTo(self.heat_bar_root)
        fill.setTransparency(TransparencyAttrib.MAlpha)
        self._heat_bar_fill = fill
        self._heat_bar_w    = BAR_W

    def _update_heat_bar_3d(self, player_node, heat_pct, overheated, blink_timer):
        """Barre chaleur + warning overheat near-ship."""
        if not player_node or player_node.isEmpty():
            return
        pos = player_node.getPos()
        # Root au bord GAUCHE de la barre, centré sur le vaisseau
        self.heat_bar_root.setPos(
            pos.getX() - self._heat_bar_w / 2,
            pos.getY(),
            pos.getZ() + 0.85
        )
        # setScale sur le fill depuis son origine (0) → gauche→droite comme la barre du bas
        pct = 1.0 if overheated else max(0.0, heat_pct)
        self._heat_bar_fill.setScale(pct, 1, 1)

        if overheated:
            pulse = abs(math.sin(blink_timer * 10))
            self._heat_bar_fill.setColorScale(1.0, 0.05 + 0.1*pulse, 0.0, 1.0)
            self._warn_overheat['fg'] = Vec4(1.0, 0.1 + 0.15*pulse, 0.0, 1.0)
            self._warn_overheat.setText("◆ LASER OVERHEAT ◆")
        else:
            self._warn_overheat.setText("")
            if heat_pct > 0.75:
                self._heat_bar_fill.setColorScale(1.0, 0.25, 0.0, 1.0)
            elif heat_pct > 0.45:
                self._heat_bar_fill.setColorScale(1.0, 0.6, 0.05, 1.0)
            else:
                self._heat_bar_fill.setColorScale(0.4, 1.0, 0.2, 1.0)

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
        self.wave_announce.setText(f"WAVE {wave_num} INCOMING")
        self.announce_timer = 2.5

    def show_damage_flash(self):
        self.flash_timer = 0.3

    def show_shield_flash(self):
        """Flash bleu-blanc sur les bords de l'écran."""
        self.shield_flash_timer = 0.3

    def show_pickup(self, text):
        """Affiche un texte de pickup qui fade."""
        self.pickup_text.setText(text)
        self.pickup_text.setFg(Vec4(1, 1, 1, 1))
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
