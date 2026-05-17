"""
Power-ups — Items récupérables droppés par les ennemis.
Torpedo (blanc cassé) : +3 torpilles | Repair (jaune) : +2 HP | Force (bleu) : +jauge Force
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib
)
import random
import math


COLOR_TORPEDO = Vec4(0.92, 0.92, 0.88, 1.0)  # Blanc cassé
COLOR_REPAIR  = Vec4(0.95, 0.82, 0.12, 1.0)  # Jaune interface
COLOR_FORCE   = Vec4(0.25, 0.55, 1.00, 1.0)  # Bleu force

DROP_CHANCE    = 0.22
WEIGHT_TORPEDO = 0.45   # 45% → torpilles
WEIGHT_REPAIR  = 0.30   # 30% → hull
# reste 25% → force
COLLECT_RADIUS = 5.0
LIFETIME       = 12.0
NO_DROP_TIME   = 15.0


class PowerUp:
    """Item récupérable dans l'espace."""

    def __init__(self, parent, position, pu_type):
        self.type = pu_type
        self.alive = True
        self.age = 0.0

        if pu_type == "torpedo":
            color = COLOR_TORPEDO
        elif pu_type == "force":
            color = COLOR_FORCE
        else:
            color = COLOR_REPAIR

        self.node = self._make_octahedron(color)
        self.node.reparentTo(parent)
        self.node.setPos(position)
        self.node.setLightOff()
        self.node.setTransparency(TransparencyAttrib.MAlpha)

        self.bob_phase = random.uniform(0, math.pi * 2)

    def _make_octahedron(self, color):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("pu", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        s = 0.5
        verts = [
            Vec3(0, 0, s * 1.4),    # 0 top (allongé, style diamant)
            Vec3(0, 0, -s * 1.4),   # 1 bottom
            Vec3(0, s * 0.8, 0),     # 2 front
            Vec3(0, -s * 0.8, 0),    # 3 back
            Vec3(-s * 0.8, 0, 0),    # 4 left
            Vec3(s * 0.8, 0, 0),     # 5 right
        ]

        # Dégradé subtil : clair en haut, sombre en bas
        top = Vec4(min(1, color.getX() * 1.4), min(1, color.getY() * 1.4),
                   min(1, color.getZ() * 1.4), 0.9)
        bot = Vec4(color.getX() * 0.5, color.getY() * 0.5,
                   color.getZ() * 0.5, 0.7)
        mid = Vec4(color.getX() * 0.9, color.getY() * 0.9,
                   color.getZ() * 0.9, 0.85)

        for vert in verts:
            v.addData3(vert)
        c.addData4(top)   # top
        c.addData4(bot)   # bottom
        c.addData4(mid)   # front
        c.addData4(mid)   # back
        c.addData4(mid)   # left
        c.addData4(mid)   # right

        faces = [
            (0, 2, 5), (0, 5, 3), (0, 3, 4), (0, 4, 2),
            (1, 5, 2), (1, 3, 5), (1, 4, 3), (1, 2, 4),
        ]
        tris = GeomTriangles(Geom.UHStatic)
        for f in faces:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("powerup")
        node.addGeom(geom)
        np = NodePath(node)
        return np

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.age += dt

        if self.age > LIFETIME:
            self.destroy()
            return

        pos = self.node.getPos()
        pos.setY(pos.getY() - scroll_speed * dt * 0.5)
        self.node.setPos(pos)

        bob = math.sin(self.age * 3.0 + self.bob_phase) * 0.3
        self.node.setZ(pos.getZ() + bob * dt)

        # Rotation lente et élégante
        h, p, r = self.node.getHpr()
        self.node.setHpr(h + 60 * dt, p + 30 * dt, r)

        # Blink visible — strobe à ~4 Hz
        blink = 0.42 + 0.58 * abs(math.sin(self.age * 4.2))
        if self.age > LIFETIME - 2.0:
            # Clignotement rapide en fin de vie + fondu
            alpha = (LIFETIME - self.age) / 2.0
            fast  = 0.9 if int(self.age * 7) % 2 == 0 else 0.1
            self.node.setColorScale(fast, fast, fast, alpha * fast)
        else:
            self.node.setColorScale(blink, blink, blink, 0.75 + 0.25 * blink)

        if pos.getY() < -10:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class PowerUpManager:
    def __init__(self, game):
        self.game = game
        self.powerups = []
        self.game_time = 0.0

    def try_spawn(self, position):
        if self.game_time < NO_DROP_TIME:
            return
        if random.random() > DROP_CHANCE:
            return
        r = random.random()
        if r < WEIGHT_TORPEDO:
            pu_type = "torpedo"
        elif r < WEIGHT_TORPEDO + WEIGHT_REPAIR:
            pu_type = "repair"
        else:
            pu_type = "force"
        pu = PowerUp(self.game.render, position, pu_type)
        self.powerups.append(pu)

    def update(self, dt, player_pos, scroll_speed):
        self.game_time += dt
        collected = []
        for pu in self.powerups:
            if not pu.alive:
                continue
            pu.update(dt, scroll_speed)
            if pu.alive:
                pu_pos = pu.node.getPos()
                dx = pu_pos.getX() - player_pos.getX()
                dz = pu_pos.getZ() - player_pos.getZ()
                dy = pu_pos.getY() - player_pos.getY()
                dist = (dx*dx + dz*dz + dy*dy*0.05) ** 0.5  # Y compte moins
                if dist < COLLECT_RADIUS:
                    collected.append(pu.type)
                    pu.destroy()
        self.powerups = [p for p in self.powerups if p.alive]
        return collected

    def reset(self):
        for pu in self.powerups:
            pu.destroy()
        self.powerups = []
        self.game_time = 0.0
