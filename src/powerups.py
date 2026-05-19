"""
Power-ups — Items récupérables droppés par les ennemis.
Torpedo (blanc cassé) : +1 torpille
Repair (jaune)        : +1 HP
Force (bleu)          : +jauge Force
Fake (violet Sith)    : piège — inflige des dégâts
"""

from panda3d.core import (
    Vec3, Vec4,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib, ColorBlendAttrib,
    TextNode, FontPool,
)
import random
import math


# ── Couleurs de base ──────────────────────────────────────────────────────────
COLOR_TORPEDO = Vec4(0.92, 0.92, 0.88, 1.0)
COLOR_REPAIR  = Vec4(0.95, 0.82, 0.12, 1.0)
COLOR_FORCE   = Vec4(0.25, 0.55, 1.00, 1.0)
COLOR_FAKE    = Vec4(0.70, 0.05, 0.85, 1.0)

# Lettre et couleur du label StarJedi par type
_LABELS = {
    "torpedo": ("T", Vec4(0.92, 0.92, 0.88, 1.0)),
    "repair":  ("H", Vec4(1.00, 0.90, 0.20, 1.0)),
    "force":   ("F", Vec4(0.40, 0.75, 1.00, 1.0)),
    "fake":    ("?", Vec4(1.00, 0.10, 0.15, 1.0)),
}
_BASE_COLORS = {
    "torpedo": COLOR_TORPEDO,
    "repair":  COLOR_REPAIR,
    "force":   COLOR_FORCE,
    "fake":    COLOR_FAKE,
}

# ── Probabilités — 25% chacun ─────────────────────────────────────────────────
DROP_CHANCE = 0.15
# r < 0.42 torpedo | r < 0.75 repair | r < 0.92 force | else fake (~8%)

COLLECT_RADIUS = 8.0
LIFETIME       = 12.0
NO_DROP_TIME   = 0

# ── Font StarJedi (lazy singleton) ───────────────────────────────────────────
_STAR_JEDI_FONT = None


def _get_font():
    global _STAR_JEDI_FONT
    if _STAR_JEDI_FONT is None:
        try:
            _STAR_JEDI_FONT = FontPool.loadFont("assets/fonts/StarJedi.ttf")
        except Exception:
            pass
    return _STAR_JEDI_FONT


# ── Helpers géométrie ─────────────────────────────────────────────────────────

def _make_disc(radius, color, alpha_center, segments=14):
    """Disque fan billboard pour les couches de flamme mystique."""
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("disc", fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")

    vw.addData3(0, 0, 0)
    cw.addData4(color.getX(), color.getY(), color.getZ(), alpha_center)
    for i in range(segments):
        a = 2 * math.pi * i / segments
        vw.addData3(math.cos(a) * radius, 0, math.sin(a) * radius)
        cw.addData4(color.getX(), color.getY(), color.getZ(), 0.0)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, 1 + i, 1 + (i + 1) % segments)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode("disc")
    gn.addGeom(geom)
    np = NodePath(gn)
    np.setBillboardPointEye()
    np.setLightOff()
    np.setDepthWrite(False)
    np.setBin("transparent", 10)
    np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd))
    return np


# ── Classe PowerUp ────────────────────────────────────────────────────────────

class PowerUp:
    """Item récupérable avec effet flamme mystique + label StarJedi."""

    def __init__(self, parent, position, pu_type):
        self.type  = pu_type
        self.alive = True
        self.age   = 0.0

        color           = _BASE_COLORS[pu_type]
        self._base_color = color
        self.bob_phase  = random.uniform(0, math.pi * 2)

        # Nœud racine
        self.node = NodePath(f"powerup_{pu_type}")
        self.node.reparentTo(parent)
        self.node.setPos(position)
        self.node.setLightOff()

        # Gemme octaédrique
        self._gem = self._make_octahedron(color)
        self._gem.reparentTo(self.node)
        self._gem.setTransparency(TransparencyAttrib.MAlpha)

        # Flamme mystique — 3 disques additifs
        # (radius, alpha_center, speed, scale_anim, phase)
        layer_cfg = [
            (0.25, 0.45, 3.0, 0.04, 0.00),
            (0.50, 0.18, 2.3, 0.04, 1.10),
            (0.75, 0.07, 1.6, 0.04, 2.35),
        ]
        self._layers = []
        for r, ac, spd, sanim, phi in layer_cfg:
            disc = _make_disc(r, color, ac)
            disc.reparentTo(self.node)
            self._layers.append((disc, spd, sanim, phi))

        # Label StarJedi billboard
        self._label = self._make_label(pu_type)
        self._label.reparentTo(self.node)
        self._label.setPos(0, 0, 1.25)

    # ── Construction ─────────────────────────────────────────────────────────

    def _make_octahedron(self, color):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("pu", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        s = 0.5
        verts = [
            Vec3(0,       0,       s * 1.4),
            Vec3(0,       0,      -s * 1.4),
            Vec3(0,       s * 0.8, 0),
            Vec3(0,      -s * 0.8, 0),
            Vec3(-s * 0.8, 0,      0),
            Vec3( s * 0.8, 0,      0),
        ]
        top = Vec4(min(1, color.getX() * 1.7), min(1, color.getY() * 1.7),
                   min(1, color.getZ() * 1.7), 0.95)
        bot = Vec4(color.getX() * 0.35, color.getY() * 0.35,
                   color.getZ() * 0.35, 0.75)
        mid = Vec4(color.getX(), color.getY(), color.getZ(), 0.90)

        for vert in verts:
            v.addData3(vert)
        for col in (top, bot, mid, mid, mid, mid):
            c.addData4(col)

        tris = GeomTriangles(Geom.UHStatic)
        for face in [(0,2,5),(0,5,3),(0,3,4),(0,4,2),
                     (1,5,2),(1,3,5),(1,4,3),(1,2,4)]:
            tris.addVertices(*face)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("gem")
        gn.addGeom(geom)
        return NodePath(gn)

    def _make_label(self, pu_type):
        letter, col = _LABELS[pu_type]
        tn = TextNode("pu_label")
        tn.setText(letter)
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(col)
        font = _get_font()
        if font:
            tn.setFont(font)
        np = NodePath(tn)
        np.setScale(0.40)
        np.setLightOff()
        np.setBillboardPointEye()
        return np

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.age += dt

        if self.age > LIFETIME:
            self.destroy()
            return

        # Scroll + bob
        pos = self.node.getPos()
        pos.setY(pos.getY() - scroll_speed * dt * 0.5)
        bob = math.sin(self.age * 3.0 + self.bob_phase) * 0.3 * dt
        self.node.setPos(pos.getX(), pos.getY(), pos.getZ() + bob)

        # Rotation gemme
        h, p, r = self._gem.getHpr()
        self._gem.setHpr(h + 60 * dt, p + 30 * dt, r)

        # ── Clignotement subtil — légère respiration, pas de phare ──────────
        blink = 0.85 + 0.10 * math.sin(self.age * 2.1) + 0.05 * math.sin(self.age * 5.3)
        blink = max(0.75, min(1.05, blink))
        c = self._base_color

        if self.age > LIFETIME - 2.0:
            fade  = (LIFETIME - self.age) / 2.0
            flash = 0.9 if int(self.age * 7) % 2 == 0 else 0.1
            self._gem.setColorScale(flash, flash, flash, fade * flash)
            self._label.setColorScale(1, 1, 1, fade)
        else:
            self._gem.setColorScale(
                c.getX() * blink, c.getY() * blink, c.getZ() * blink, 0.88,
            )

        # ── Flamme mystique — douce, stable ──────────────────────────────
        breathe = 1.0 + 0.05 * math.sin(self.age * 1.8)
        for disc, spd, sanim, phi in self._layers:
            t     = self.age * spd + phi
            pulse = 0.55 + 0.45 * abs(math.sin(t))   # jamais à 0 — plancher 0.55
            sc    = breathe * (1.0 + sanim * 0.4 * math.sin(t * 0.7))
            disc.setScale(sc)
            disc.setColorScale(
                c.getX() * pulse,
                c.getY() * pulse,
                c.getZ() * pulse,
                pulse * 0.7,
            )

        if self.node.getPos().getY() < -10:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ── Manager ───────────────────────────────────────────────────────────────────

class PowerUpManager:
    def __init__(self, game):
        self.game      = game
        self.powerups  = []
        self.game_time = 0.0

    def try_spawn(self, position):
        if self.game_time < NO_DROP_TIME:
            return
        if random.random() > DROP_CHANCE:
            return
        r = random.random()
        if r < 0.42:
            pu_type = "torpedo"
        elif r < 0.75:
            pu_type = "repair"
        elif r < 0.92:
            pu_type = "force"
        else:
            pu_type = "fake"
        self.powerups.append(PowerUp(self.game.render, position, pu_type))

    def update(self, dt, player_pos, scroll_speed):
        self.game_time += dt
        collected = []
        for pu in self.powerups:
            if not pu.alive:
                continue
            pu.update(dt, scroll_speed)
            if not pu.alive:
                continue
            pu_pos = pu.node.getPos()
            dx = pu_pos.getX() - player_pos.getX()
            dz = pu_pos.getZ() - player_pos.getZ()
            dy = pu_pos.getY() - player_pos.getY()
            dist = (dx*dx + dz*dz + dy*dy*0.05) ** 0.5
            if dist < COLLECT_RADIUS:
                collected.append(pu.type)
                pu.destroy()
        self.powerups = [p for p in self.powerups if p.alive]
        return collected

    def reset(self):
        for pu in self.powerups:
            pu.destroy()
        self.powerups  = []
        self.game_time = 0.0
