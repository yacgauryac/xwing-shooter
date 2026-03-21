"""
HUD v2 — Elite Dangerous holographique.
Arcs gros, fonds semi-transparents, cadres, poussé vers les bords.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    TextNode, Vec4,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, TransparencyAttrib
)
import math


# Palette holographique orange/ambre
C_MAIN = Vec4(1.0, 0.65, 0.15, 0.85)
C_DIM = Vec4(1.0, 0.65, 0.15, 0.25)
C_BRIGHT = Vec4(1.0, 0.8, 0.3, 1.0)
C_DANGER = Vec4(1.0, 0.15, 0.05, 0.9)
C_WARN = Vec4(1.0, 0.5, 0.1, 0.9)
C_SAFE = Vec4(0.3, 0.7, 0.4, 0.8)
C_BG = Vec4(0.05, 0.03, 0.0, 0.35)       # Fond sombre semi-transparent
C_BG_DARK = Vec4(0.03, 0.02, 0.0, 0.5)


def _make_arc(parent, cx, cz, radius, a0, a1, segs=32, color=C_MAIN, thick=1.5):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("a", fmt, Geom.UHDynamic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    for i in range(segs + 1):
        t = i / segs
        a = a0 + t * (a1 - a0)
        v.addData3(cx + math.cos(a) * radius, 0, cz + math.sin(a) * radius)
        c.addData4(color)
    lines = GeomLines(Geom.UHDynamic)
    for i in range(segs):
        lines.addVertices(i, i + 1)
    g = Geom(vd)
    g.addPrimitive(lines)
    n = GeomNode("arc")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setRenderModeThickness(thick)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_filled_arc(parent, cx, cz, r_in, r_out, a0, a1, segs=32, color=C_MAIN):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("fa", fmt, Geom.UHDynamic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    c_in = Vec4(color.getX(), color.getY(), color.getZ(), color.getW() * 0.2)
    for i in range(segs + 1):
        t = i / segs
        a = a0 + t * (a1 - a0)
        cos_a, sin_a = math.cos(a), math.sin(a)
        v.addData3(cx + cos_a * r_in, 0, cz + sin_a * r_in)
        c.addData4(c_in)
        v.addData3(cx + cos_a * r_out, 0, cz + sin_a * r_out)
        c.addData4(color)
    tris = GeomTriangles(Geom.UHDynamic)
    for i in range(segs):
        b = i * 2
        tris.addVertices(b, b+1, b+2)
        tris.addVertices(b+1, b+3, b+2)
    g = Geom(vd)
    g.addPrimitive(tris)
    n = GeomNode("fa")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


class HUD:
    """HUD holographique v2 — Elite Dangerous style."""

    def __init__(self, game):
        self.game = game
        self.blink_timer = 0.0

        # =============================================
        # BANDEAU HAUT — fond semi-transparent + infos
        # =============================================
        self.top_bar = DirectFrame(
            frameColor=C_BG,
            frameSize=(-1.4, 1.4, -0.04, 0.04),
            pos=(0, 0, 0.92),
            sortOrder=0,
        )

        # Ligne lumineuse en bas du bandeau
        self.top_line = DirectFrame(
            frameColor=Vec4(1, 0.65, 0.15, 0.4),
            frameSize=(-1.4, 1.4, -0.001, 0.001),
            pos=(0, 0, 0.88),
            sortOrder=1,
        )

        # Score
        self.score_label = OnscreenText(
            text="SCORE", pos=(-1.3, 0.93), scale=0.025,
            fg=C_DIM, align=TextNode.ALeft, mayChange=False,
        )
        self.score_text = OnscreenText(
            text="0", pos=(-1.3, 0.895), scale=0.04,
            fg=C_BRIGHT, align=TextNode.ALeft, mayChange=True,
        )

        # Vague (centre)
        self.wave_text = OnscreenText(
            text="WAVE 1", pos=(0, 0.905), scale=0.035,
            fg=C_MAIN, align=TextNode.ACenter, mayChange=True,
        )

        # Hostiles
        self.enemy_label = OnscreenText(
            text="HOSTILES", pos=(1.3, 0.93), scale=0.025,
            fg=C_DIM, align=TextNode.ARight, mayChange=False,
        )
        self.enemy_text = OnscreenText(
            text="0", pos=(1.3, 0.895), scale=0.04,
            fg=C_DANGER, align=TextNode.ARight, mayChange=True,
        )

        # =============================================
        # SHIELD (bas gauche) — gros arc
        # =============================================
        self.shield_root = game.aspect2d.attachNewNode("shield_gauge")
        self.shield_root.setPos(-1.15, 0, -0.72)
        self.shield_root.setTransparency(TransparencyAttrib.MAlpha)

        # Fond sombre circulaire
        _make_filled_arc(self.shield_root, 0, 0, 0, 0.17,
                        0, math.pi * 2, 32, C_BG_DARK)

        # Arc de fond (contour complet)
        _make_arc(self.shield_root, 0, 0, 0.17,
                 math.pi * 0.65, math.pi * 2.35, 40, C_DIM, 1.5)

        self.shield_arc_np = None

        self.shield_text = OnscreenText(
            text="100", pos=(-1.15, -0.73), scale=0.04,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True,
        )
        self.shield_pct = OnscreenText(
            text="%", pos=(-1.09, -0.73), scale=0.025,
            fg=C_DIM, align=TextNode.ALeft, mayChange=False,
        )
        self.shield_label = OnscreenText(
            text="SHIELD", pos=(-1.15, -0.79), scale=0.022,
            fg=C_DIM, align=TextNode.ACenter, mayChange=False,
        )

        # =============================================
        # HEAT (bas droit) — gros arc
        # =============================================
        self.heat_root = game.aspect2d.attachNewNode("heat_gauge")
        self.heat_root.setPos(1.15, 0, -0.72)
        self.heat_root.setTransparency(TransparencyAttrib.MAlpha)

        # Fond sombre
        _make_filled_arc(self.heat_root, 0, 0, 0, 0.17,
                        0, math.pi * 2, 32, C_BG_DARK)

        # Arc de fond
        _make_arc(self.heat_root, 0, 0, 0.17,
                 -math.pi * 0.35, math.pi * 1.35, 40, C_DIM, 1.5)

        self.heat_arc_np = None

        self.heat_text = OnscreenText(
            text="", pos=(1.15, -0.73), scale=0.035,
            fg=C_MAIN, align=TextNode.ACenter, mayChange=True,
        )
        self.heat_label = OnscreenText(
            text="HEAT", pos=(1.15, -0.79), scale=0.022,
            fg=C_DIM, align=TextNode.ACenter, mayChange=False,
        )
        self.overheat_text = OnscreenText(
            text="", pos=(1.15, -0.64), scale=0.028,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True,
        )

        # =============================================
        # LIGNES DECO (coins + bords)
        # =============================================
        deco = game.aspect2d.attachNewNode("deco")
        deco.setTransparency(TransparencyAttrib.MAlpha)

        # Coins — petits angles
        for sx, sz in [(-1, 1), (1, 1), (-1, -1), (1, -1)]:
            cx, cz = sx * 1.35, sz * 0.88
            length = 0.08
            col = Vec4(1, 0.65, 0.15, 0.2)

            # Horizontal
            fmt = GeomVertexFormat.getV3c4()
            vd = GeomVertexData("d", fmt, Geom.UHStatic)
            v = GeomVertexWriter(vd, "vertex")
            c = GeomVertexWriter(vd, "color")
            v.addData3(cx, 0, cz); c.addData4(col)
            v.addData3(cx - sx * length, 0, cz); c.addData4(col)
            v.addData3(cx, 0, cz); c.addData4(col)
            v.addData3(cx, 0, cz - sz * length); c.addData4(col)
            lines = GeomLines(Geom.UHStatic)
            lines.addVertices(0, 1)
            lines.addVertices(2, 3)
            g = Geom(vd)
            g.addPrimitive(lines)
            n = GeomNode("corner")
            n.addGeom(g)
            np = NodePath(n)
            np.reparentTo(deco)
            np.setRenderModeThickness(1.0)

        # Lignes horizontales subtiles milieu bas
        for x1, x2 in [(-0.8, -0.3), (0.3, 0.8)]:
            fmt = GeomVertexFormat.getV3c4()
            vd = GeomVertexData("hl", fmt, Geom.UHStatic)
            v = GeomVertexWriter(vd, "vertex")
            c = GeomVertexWriter(vd, "color")
            v.addData3(x1, 0, -0.88); c.addData4(Vec4(1, 0.65, 0.15, 0.12))
            v.addData3(x2, 0, -0.88); c.addData4(Vec4(1, 0.65, 0.15, 0.12))
            lines = GeomLines(Geom.UHStatic)
            lines.addVertices(0, 1)
            g = Geom(vd)
            g.addPrimitive(lines)
            n = GeomNode("hline")
            n.addGeom(g)
            np = NodePath(n)
            np.reparentTo(deco)
            np.setRenderModeThickness(1.0)

        # =============================================
        # ANNONCE / FLASH / GAME OVER
        # =============================================
        self.wave_announce = OnscreenText(
            text="", pos=(0, 0.55), scale=0.06,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True,
        )
        self.announce_timer = 0.0

        self.damage_flash = DirectFrame(
            frameColor=Vec4(1, 0.3, 0, 0), frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=100,
        )
        self.flash_timer = 0.0

        self.game_over_text = OnscreenText(
            text="", pos=(0, 0.08), scale=0.1,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True,
        )
        self.game_over_sub = OnscreenText(
            text="", pos=(0, -0.05), scale=0.035,
            fg=C_MAIN, align=TextNode.ACenter, mayChange=True,
        )

        # Contrôles micro
        OnscreenText(
            text="ZQSD:MOVE  SPACE:FIRE  DBTAP:ROLL  M:SND  F11:FS  ESC:QUIT",
            pos=(0, -0.95), scale=0.02,
            fg=Vec4(1, 0.65, 0.15, 0.15), align=TextNode.ACenter,
        )

        # Attitude indicator (assiette)
        self.attitude_root = game.aspect2d.attachNewNode("attitude")
        self.attitude_root.setTransparency(TransparencyAttrib.MAlpha)
        self.attitude_lines = None

    def _update_attitude(self, roll, pitch):
        """Met à jour l'indicateur d'assiette (lignes d'horizon)."""
        if self.attitude_lines:
            self.attitude_lines.removeNode()

        fmt = GeomVertexFormat.getV3c4()
        vd = GeomVertexData("att", fmt, Geom.UHDynamic)
        v = GeomVertexWriter(vd, "vertex")
        c = GeomVertexWriter(vd, "color")

        # Convertit roll/pitch en radians
        roll_rad = math.radians(roll * 0.015)  # Subtil
        pitch_offset = pitch * 0.003

        col_main = Vec4(1, 0.65, 0.15, 0.2)
        col_center = Vec4(1, 0.65, 0.15, 0.35)

        # Ligne centrale (plus visible)
        half = 0.12
        cos_r, sin_r = math.cos(roll_rad), math.sin(roll_rad)

        v.addData3(-half * cos_r, 0, -half * sin_r + pitch_offset)
        c.addData4(col_center)
        v.addData3(half * cos_r, 0, half * sin_r + pitch_offset)
        c.addData4(col_center)

        # Lignes latérales (plus longues, plus dim)
        for offset in [0.25, 0.4]:
            for side in [-1, 1]:
                x1 = side * offset
                x2 = side * (offset + 0.08)
                z1 = x1 * sin_r / cos_r + pitch_offset if cos_r != 0 else pitch_offset
                z2 = x2 * sin_r / cos_r + pitch_offset if cos_r != 0 else pitch_offset
                v.addData3(x1, 0, z1)
                c.addData4(col_main)
                v.addData3(x2, 0, z2)
                c.addData4(col_main)

        lines = GeomLines(Geom.UHDynamic)
        num_lines = 1 + 4  # center + 4 lateral
        for i in range(num_lines):
            lines.addVertices(i * 2, i * 2 + 1)

        g = Geom(vd)
        g.addPrimitive(lines)
        n = GeomNode("attitude_lines")
        n.addGeom(g)
        self.attitude_lines = NodePath(n)
        self.attitude_lines.reparentTo(self.attitude_root)
        self.attitude_lines.setRenderModeThickness(1.0)

    # =========================================
    # UPDATE
    # =========================================

    def _rebuild_shield(self, pct):
        if self.shield_arc_np:
            self.shield_arc_np.removeNode()
            self.shield_arc_np = None
        if pct <= 0:
            return

        if pct > 0.5:
            color = C_SAFE
        elif pct > 0.25:
            color = C_WARN
        else:
            color = C_DANGER

        span = math.pi * 1.7
        end = math.pi * 0.65 + span * pct
        self.shield_arc_np = _make_filled_arc(
            self.shield_root, 0, 0, 0.12, 0.17,
            math.pi * 0.65, end, max(3, int(40 * pct)), color
        )

    def _rebuild_heat(self, pct, overheated=False):
        if self.heat_arc_np:
            self.heat_arc_np.removeNode()
            self.heat_arc_np = None
        if pct <= 0.01:
            return

        if overheated:
            blink = abs(math.sin(self.blink_timer * 6))
            color = Vec4(1, 0.1, 0.05, 0.4 + 0.5 * blink)
        elif pct > 0.75:
            color = C_DANGER
        elif pct > 0.5:
            color = C_WARN
        else:
            color = C_MAIN

        span = math.pi * 1.7
        end = -math.pi * 0.35 + span * pct
        self.heat_arc_np = _make_filled_arc(
            self.heat_root, 0, 0, 0.12, 0.17,
            -math.pi * 0.35, end, max(3, int(40 * pct)), color
        )

    def update(self, dt, score, wave, enemy_count, health, max_health,
               heat_pct=0.0, overheated=False, cooldown_pct=0.0,
               roll=0.0, pitch=0.0):
        self.blink_timer += dt

        # Textes
        self.score_text.setText(f"{score}")
        self.wave_text.setText(f"WAVE {wave}")
        self.enemy_text.setText(f"{enemy_count}")

        # Shield
        hp = max(0, health / max_health)
        self.shield_text.setText(f"{int(hp * 100)}")
        self._rebuild_shield(hp)

        # Heat
        disp = cooldown_pct if overheated else heat_pct
        self._rebuild_heat(disp, overheated)

        if overheated:
            self.overheat_text.setText("OVERHEAT")
            self.heat_text.setText("")
        else:
            self.overheat_text.setText("")
            self.heat_text.setText(f"{int(heat_pct * 100)}" if heat_pct > 0.01 else "")

        # Attitude indicator (assiette)
        self._update_attitude(roll, pitch)

        # Vague
        if self.announce_timer > 0:
            self.announce_timer -= dt
            alpha = min(1.0, self.announce_timer / 0.5)
            self.wave_announce.setFg(Vec4(C_BRIGHT.getX(), C_BRIGHT.getY(),
                                         C_BRIGHT.getZ(), alpha))
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # Flash
        if self.flash_timer > 0:
            self.flash_timer -= dt
            a = max(0, self.flash_timer / 0.3) * 0.2
            self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, a)
            if self.flash_timer <= 0:
                self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, 0)

    def announce_wave(self, wave_num):
        self.wave_announce.setText(f"WAVE {wave_num} INCOMING")
        self.announce_timer = 2.5

    def show_damage_flash(self):
        self.flash_timer = 0.3

    def show_game_over(self, score):
        self.game_over_text.setText("DESTROYED")
        self.game_over_sub.setText(f"Final score: {score}  |  Press R to restart")
