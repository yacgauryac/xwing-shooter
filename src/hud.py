"""
HUD — Score, vague, vie, cercle de chaleur unifié, game over.
Le cercle de chaleur se remplit progressivement et change de couleur.
En surchauffe il clignote et le cooldown le vide.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    TextNode, Vec4,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib
)
import math


class HUD:
    """Affiche les infos de jeu à l'écran."""

    def __init__(self, game):
        self.game = game

        # Score
        self.score_text = OnscreenText(
            text="Score: 0", pos=(-1.3, 0.9), scale=0.06,
            fg=Vec4(0.2, 1.0, 0.2, 1), align=TextNode.ALeft, mayChange=True,
        )

        # Vague
        self.wave_text = OnscreenText(
            text="Vague 1", pos=(0, 0.9), scale=0.06,
            fg=Vec4(1.0, 1.0, 0.2, 1), align=TextNode.ACenter, mayChange=True,
        )

        # Ennemis
        self.enemy_text = OnscreenText(
            text="Ennemis: 0", pos=(1.3, 0.9), scale=0.06,
            fg=Vec4(1.0, 0.4, 0.4, 1), align=TextNode.ARight, mayChange=True,
        )

        # Vie
        self.health_text = OnscreenText(
            text="Blindage: 100%", pos=(-1.3, -0.85), scale=0.05,
            fg=Vec4(0.3, 0.8, 1.0, 1), align=TextNode.ALeft, mayChange=True,
        )
        self.health_bar_bg = DirectFrame(
            frameColor=Vec4(0.2, 0.2, 0.2, 0.8),
            frameSize=(-0.3, 0.3, -0.012, 0.012), pos=(-1.0, 0, -0.88),
        )
        self.health_bar = DirectFrame(
            frameColor=Vec4(0.2, 0.8, 1.0, 0.9),
            frameSize=(-0.3, 0.3, -0.01, 0.01), pos=(-1.0, 0, -0.88),
        )

        # --- Cercle de chaleur unifié ---
        self.heat_node = game.aspect2d.attachNewNode("heat_circle")
        self.heat_node.setPos(0, 0, -0.5)
        self.heat_node.setTransparency(TransparencyAttrib.MAlpha)
        self.last_heat_pct = -1  # Force le premier rendu
        self.blink_timer = 0.0

        # Texte surchauffe (au centre du cercle)
        self.overheat_text = OnscreenText(
            text="", pos=(0, -0.53), scale=0.035,
            fg=Vec4(1.0, 0.3, 0.1, 0.9), align=TextNode.ACenter, mayChange=True,
        )

        # Contrôles
        OnscreenText(
            text="ZQSD: bouger | Espace/Clic: tirer | M: son | Echap: quitter",
            pos=(0, -0.95), scale=0.035,
            fg=Vec4(0.5, 0.5, 0.5, 0.6), align=TextNode.ACenter, mayChange=False,
        )

        # Annonce de vague
        self.wave_announce = OnscreenText(
            text="", pos=(0, 0.3), scale=0.12,
            fg=Vec4(1.0, 0.8, 0.0, 1), align=TextNode.ACenter, mayChange=True,
        )
        self.announce_timer = 0.0

        # Flash de dégât
        self.damage_flash = DirectFrame(
            frameColor=Vec4(1, 0, 0, 0), frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=100,
        )
        self.flash_timer = 0.0

        # Game Over
        self.game_over_text = OnscreenText(
            text="", pos=(0, 0.1), scale=0.15,
            fg=Vec4(1.0, 0.2, 0.2, 1), align=TextNode.ACenter, mayChange=True,
        )
        self.game_over_sub = OnscreenText(
            text="", pos=(0, -0.1), scale=0.06,
            fg=Vec4(0.8, 0.8, 0.8, 1), align=TextNode.ACenter, mayChange=True,
        )

    def _get_heat_color(self, pct):
        """Couleur du cercle selon la chaleur : vert → jaune → orange → rouge."""
        if pct < 0.4:
            # Vert → jaune
            t = pct / 0.4
            return Vec4(t, 0.8, 0.2 * (1 - t), 0.4 + 0.2 * t)
        elif pct < 0.75:
            # Jaune → orange
            t = (pct - 0.4) / 0.35
            return Vec4(1.0, 0.8 - 0.4 * t, 0.1, 0.5 + 0.2 * t)
        else:
            # Orange → rouge
            t = (pct - 0.75) / 0.25
            return Vec4(1.0, 0.4 * (1 - t), 0.05, 0.7 + 0.2 * t)

    def _build_heat_circle(self, fill_pct, overheated=False):
        """Construit le cercle de chaleur. fill_pct = 0.0 à 1.0."""
        self.heat_node.getChildren().detach()

        radius = 0.055
        ring_width = 0.004
        segments = 32

        # --- Contour du cercle complet (toujours visible, discret) ---
        ring_color = Vec4(0.4, 0.4, 0.4, 0.2)
        self._draw_ring(radius, ring_width, segments, ring_color)

        if fill_pct <= 0.01:
            return

        # --- Arc rempli (chaleur) ---
        fill_color = self._get_heat_color(fill_pct)

        if overheated:
            # Clignotement en surchauffe
            blink = abs(math.sin(self.blink_timer * 6.0))
            fill_color = Vec4(1.0, 0.15, 0.05, 0.5 + 0.4 * blink)

        self._draw_arc(fill_pct, radius, segments, fill_color)

        # --- Petit point au sommet du remplissage (indicateur) ---
        if not overheated and fill_pct > 0.05:
            angle = -math.pi / 2 + fill_pct * 2.0 * math.pi
            dot_x = math.cos(angle) * radius
            dot_z = math.sin(angle) * radius
            self._draw_dot(dot_x, dot_z, 0.006, Vec4(1, 1, 1, 0.8))

    def _draw_arc(self, pct, radius, segments, color):
        """Dessine un arc rempli (camembert)."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("arc", fmt, Geom.UHDynamic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Centre (plus sombre)
        vertex.addData3(0, 0, 0)
        center_color = Vec4(color.getX() * 0.3, color.getY() * 0.3, color.getZ() * 0.3, color.getW() * 0.5)
        col.addData4(center_color)

        num_segs = max(3, int(segments * pct))
        angle_span = pct * 2.0 * math.pi

        for i in range(num_segs + 1):
            angle = -math.pi / 2 + (i / num_segs) * angle_span
            vertex.addData3(math.cos(angle) * radius, 0, math.sin(angle) * radius)
            col.addData4(color)

        tris = GeomTriangles(Geom.UHDynamic)
        for i in range(num_segs):
            tris.addVertices(0, i + 1, i + 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("arc")
        node.addGeom(geom)
        NodePath(node).reparentTo(self.heat_node)

    def _draw_ring(self, radius, width, segments, color):
        """Dessine un anneau fin."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("ring", fmt, Geom.UHDynamic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        r_in = radius - width
        r_out = radius + width

        for i in range(segments + 1):
            angle = (i / segments) * 2.0 * math.pi
            vertex.addData3(math.cos(angle) * r_in, 0, math.sin(angle) * r_in)
            col.addData4(color)
            vertex.addData3(math.cos(angle) * r_out, 0, math.sin(angle) * r_out)
            col.addData4(color)

        tris = GeomTriangles(Geom.UHDynamic)
        for i in range(segments):
            base = i * 2
            tris.addVertices(base, base + 1, base + 2)
            tris.addVertices(base + 1, base + 3, base + 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("ring")
        node.addGeom(geom)
        NodePath(node).reparentTo(self.heat_node)

    def _draw_dot(self, x, z, radius, color):
        """Dessine un petit point (indicateur)."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("dot", fmt, Geom.UHDynamic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        vertex.addData3(x, 0, z)
        col.addData4(color)

        segs = 8
        for i in range(segs + 1):
            angle = (i / segs) * 2.0 * math.pi
            vertex.addData3(x + math.cos(angle) * radius, 0, z + math.sin(angle) * radius)
            col.addData4(color)

        tris = GeomTriangles(Geom.UHDynamic)
        for i in range(segs):
            tris.addVertices(0, i + 1, i + 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("dot")
        node.addGeom(geom)
        NodePath(node).reparentTo(self.heat_node)

    def update(self, dt, score, wave, enemy_count, health, max_health,
               heat_pct=0.0, overheated=False, cooldown_pct=0.0):
        """Met à jour l'affichage."""
        self.score_text.setText(f"Score: {score}")
        self.wave_text.setText(f"Vague {wave}")
        self.enemy_text.setText(f"Ennemis: {enemy_count}")

        # Vie
        health_pct_val = max(0, health / max_health)
        self.health_text.setText(f"Blindage: {int(health_pct_val * 100)}%")

        if health_pct_val > 0.5:
            bar_color = Vec4(0.2, 0.8, 1.0, 0.9)
        elif health_pct_val > 0.25:
            bar_color = Vec4(1.0, 0.8, 0.0, 0.9)
        else:
            bar_color = Vec4(1.0, 0.2, 0.2, 0.9)
        self.health_bar["frameColor"] = bar_color
        self.health_bar["frameSize"] = (-0.3, -0.3 + 0.6 * health_pct_val, -0.01, 0.01)

        # --- Cercle de chaleur ---
        self.blink_timer += dt

        # En surchauffe : le cercle montre le cooldown (se vide)
        if overheated:
            self._build_heat_circle(cooldown_pct, overheated=True)
            self.overheat_text.setText("SURCHAUFFE")
        else:
            # Normal : le cercle montre la chaleur (se remplit)
            # Optimisation : ne redessine que si le % a changé significativement
            rounded = round(heat_pct, 2)
            if rounded != self.last_heat_pct:
                self._build_heat_circle(heat_pct, overheated=False)
                self.last_heat_pct = rounded
            self.overheat_text.setText("")

        # Annonce de vague
        if self.announce_timer > 0:
            self.announce_timer -= dt
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # Flash de dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            alpha = max(0, self.flash_timer / 0.3) * 0.3
            self.damage_flash["frameColor"] = Vec4(1, 0, 0, alpha)
            if self.flash_timer <= 0:
                self.damage_flash["frameColor"] = Vec4(1, 0, 0, 0)

    def announce_wave(self, wave_num):
        self.wave_announce.setText(f"--- VAGUE {wave_num} ---")
        self.announce_timer = 2.5

    def show_damage_flash(self):
        self.flash_timer = 0.3

    def show_game_over(self, score):
        self.game_over_text.setText("GAME OVER")
        self.game_over_sub.setText(f"Score final: {score}\n\nAppuie sur R pour recommencer")
