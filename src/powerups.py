"""
Power-ups — Items récupérables droppés par les ennemis.
Torpedo (bleu) : +3 torpilles | Repair (vert) : +2 HP
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib
)
import random
import math


COLOR_TORPEDO = Vec4(1.0, 0.85, 0.2, 1.0)   # Jaune doré
COLOR_REPAIR = Vec4(1.0, 0.5, 0.15, 1.0)    # Orange chaud

DROP_CHANCE = 0.20
WEIGHT_TORPEDO = 0.6
COLLECT_RADIUS = 2.8
LIFETIME = 12.0
NO_DROP_TIME = 15.0


class PowerUp:
    """Item récupérable dans l'espace."""

    def __init__(self, parent, position, pu_type):
        self.type = pu_type
        self.alive = True
        self.age = 0.0

        color = COLOR_TORPEDO if pu_type == "torpedo" else COLOR_REPAIR

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

        s = 0.25
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

        # Pulse doux
        pulse = 0.9 + 0.2 * math.sin(self.age * 3.0)
        if self.age > LIFETIME - 2.0:
            alpha = (LIFETIME - self.age) / 2.0
            blink = 0.8 if int(self.age * 4) % 2 == 0 else 0.3
            self.node.setColorScale(pulse * blink, pulse * blink, pulse * blink, alpha)
        else:
            self.node.setColorScale(pulse, pulse, pulse, 0.9)

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
        pu_type = "torpedo" if random.random() < WEIGHT_TORPEDO else "repair"
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
                dist = (dx*dx + dz*dz + dy*dy*0.3) ** 0.5  # Y compte moins
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
