"""
Explosions — Boule de feu + débris solides + score popup.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomPoints, GeomTriangles, GeomNode,
    NodePath, TextNode
)
from direct.gui.OnscreenText import OnscreenText
import random
import math


class Particle:
    def __init__(self, pos, velocity, color, lifetime):
        self.pos = Vec3(pos)
        self.velocity = Vec3(velocity)
        self.color = Vec4(color)
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.alive = True


class DebrisChunk:
    """Morceau de TIE solide qui vole."""

    def __init__(self, game, position):
        self.alive = True
        self.lifetime = random.uniform(0.8, 1.5)
        self.max_lifetime = self.lifetime

        speed = random.uniform(8, 20)
        theta = random.uniform(0, math.pi * 2)
        phi = random.uniform(0, math.pi)
        self.velocity = Vec3(
            math.sin(phi) * math.cos(theta) * speed,
            math.sin(phi) * math.sin(theta) * speed,
            math.cos(phi) * speed,
        )
        self.rot_speed = Vec3(
            random.uniform(-200, 200),
            random.uniform(-200, 200),
            random.uniform(-200, 200),
        )

        self.node = self._make_chunk()
        self.node.reparentTo(game.render)
        self.node.setPos(position)
        self.node.setLightOff()

    def _make_chunk(self):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("chunk", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        s = random.uniform(0.1, 0.3)
        gray = random.uniform(0.3, 0.6)
        col = Vec4(gray, gray, gray * 0.9, 1)

        v.addData3(-s, 0, -s * 0.5); c.addData4(col)
        v.addData3(s, 0, -s * 0.3); c.addData4(col)
        v.addData3(0, 0, s * 0.6); c.addData4(col)

        tris = GeomTriangles(Geom.UHStatic)
        tris.addVertices(0, 1, 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("chunk")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        if not self.alive:
            return
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.destroy()
            return

        self.node.setPos(self.node.getPos() + self.velocity * dt)
        self.velocity *= (1.0 - 1.5 * dt)

        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )
        alpha = self.lifetime / self.max_lifetime
        self.node.setColorScale(1, 1, 1, alpha)

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class Explosion:
    """Boule de feu + fumée + débris solides."""

    def __init__(self, game, position):
        self.game = game
        self.alive = True
        self.particles = []
        self.debris = []
        self.timer = 0.0

        # Couche interne (blanc/jaune, flash rapide)
        for _ in range(15):
            speed = random.uniform(3, 8)
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0, math.pi)
            vel = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )
            color = Vec4(1.0, random.uniform(0.7, 1.0), random.uniform(0.3, 0.6), 1.0)
            self.particles.append(Particle(position, vel, color, random.uniform(0.2, 0.4)))

        # Couche externe (orange/rouge)
        for _ in range(20):
            speed = random.uniform(5, 12)
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0, math.pi)
            vel = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )
            color = Vec4(random.uniform(0.9, 1.0), random.uniform(0.2, 0.5), 0.0, 1.0)
            self.particles.append(Particle(position, vel, color, random.uniform(0.3, 0.7)))

        # Fumée grise
        for _ in range(10):
            speed = random.uniform(2, 5)
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0, math.pi)
            vel = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )
            gray = random.uniform(0.15, 0.3)
            self.particles.append(Particle(position, vel, Vec4(gray, gray, gray, 0.6),
                                          random.uniform(0.5, 1.0)))

        # Débris solides
        for _ in range(6):
            self.debris.append(DebrisChunk(game, position))

        self.node = NodePath("explosion")
        self.node.reparentTo(game.render)
        self.node.setLightOff()
        self._build_geom()

    def _build_geom(self):
        fmt = GeomVertexFormat.getV3c4()
        self.vdata = GeomVertexData("explosion", fmt, Geom.UHDynamic)
        self.vdata.setNumRows(len(self.particles))
        vertex = GeomVertexWriter(self.vdata, "vertex")
        color = GeomVertexWriter(self.vdata, "color")
        for p in self.particles:
            vertex.addData3(p.pos)
            color.addData4(p.color)
        points = GeomPoints(Geom.UHDynamic)
        points.addConsecutiveVertices(0, len(self.particles))
        geom = Geom(self.vdata)
        geom.addPrimitive(points)
        geom_node = GeomNode("explosion_geom")
        geom_node.addGeom(geom)
        np = NodePath(geom_node)
        np.reparentTo(self.node)
        np.setRenderModeThickness(5)

    def update(self, dt):
        if not self.alive:
            return
        self.timer += dt
        any_alive = False

        vertex = GeomVertexWriter(self.vdata, "vertex")
        color = GeomVertexWriter(self.vdata, "color")

        for p in self.particles:
            if not p.alive:
                vertex.addData3(0, 0, 0)
                color.addData4(0, 0, 0, 0)
                continue
            p.lifetime -= dt
            if p.lifetime <= 0:
                p.alive = False
                vertex.addData3(0, 0, 0)
                color.addData4(0, 0, 0, 0)
                continue
            any_alive = True
            p.pos += p.velocity * dt
            p.velocity *= (1.0 - 3.0 * dt)

            # Jaune → orange → rouge → noir
            progress = 1.0 - (p.lifetime / p.max_lifetime)
            alpha = (1.0 - progress) ** 0.5
            r = p.color.getX()
            g = p.color.getY() * (1.0 - progress * 0.7)
            b = p.color.getZ() * (1.0 - progress)
            vertex.addData3(p.pos)
            color.addData4(Vec4(r, g, b, alpha))

        for chunk in self.debris:
            chunk.update(dt)
        self.debris = [d for d in self.debris if d.alive]

        if not any_alive and len(self.debris) == 0:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class ScorePopup:
    """Points +100 qui montent et fade."""

    def __init__(self, game, position, score):
        self.alive = True
        self.timer = 0.0
        self.duration = 1.0
        self.game = game

        pos2d = self._world_to_screen(position)
        self.text = OnscreenText(
            text=f"+{score}", pos=pos2d, scale=0.05,
            fg=Vec4(1.0, 0.7, 0.2, 1.0),
            align=TextNode.ACenter, mayChange=True, sort=60,
        )
        self.start_y = pos2d[1]

    def _world_to_screen(self, world_pos):
        p3 = self.game.cam.getRelativePoint(self.game.render, world_pos)
        if p3.getY() <= 0:
            return (0, 0)
        p2d = Point3()
        if self.game.camLens.project(p3, p2d):
            return (p2d.getX(), p2d.getY())
        return (0, 0)

    def update(self, dt):
        if not self.alive:
            return
        self.timer += dt
        progress = self.timer / self.duration
        if progress >= 1.0:
            self.destroy()
            return
        self.text.setPos(self.text.getPos()[0], self.start_y + progress * 0.15)
        self.text.setFg(Vec4(1.0, 0.7, 0.2, 1.0 - progress))
        self.text.setScale(0.05 + progress * 0.01)

    def destroy(self):
        self.alive = False
        self.text.destroy()


class ExplosionManager:
    def __init__(self, game):
        self.game = game
        self.explosions = []
        self.popups = []

    def spawn(self, position, score=0):
        self.explosions.append(Explosion(self.game, position))
        if score > 0:
            self.popups.append(ScorePopup(self.game, position, score))

    def update(self, dt):
        for exp in self.explosions:
            exp.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]
        for p in self.popups:
            p.update(dt)
        self.popups = [p for p in self.popups if p.alive]
