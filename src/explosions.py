"""
Explosions — Effets visuels quand un TIE est détruit.
Particules procédurales (pas besoin de fichier externe).
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomPoints, GeomNode,
    NodePath
)
import random
import math


class Particle:
    """Une seule particule d'explosion."""

    def __init__(self, pos, velocity, color, lifetime):
        self.pos = Vec3(pos)
        self.velocity = Vec3(velocity)
        self.color = Vec4(color)
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.alive = True


class Explosion:
    """Une explosion composée de plusieurs particules."""

    NUM_PARTICLES = 20
    BASE_SPEED = 8.0
    LIFETIME = 0.8

    def __init__(self, game, position):
        self.game = game
        self.alive = True
        self.particles = []
        self.timer = 0.0

        # Crée les particules
        for _ in range(self.NUM_PARTICLES):
            # Direction aléatoire (sphère)
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0, math.pi)
            speed = random.uniform(self.BASE_SPEED * 0.3, self.BASE_SPEED)

            vel = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )

            # Couleur : mix orange/jaune/rouge
            r = random.uniform(0.8, 1.0)
            g = random.uniform(0.2, 0.7)
            b = random.uniform(0.0, 0.15)
            color = Vec4(r, g, b, 1.0)

            lifetime = random.uniform(self.LIFETIME * 0.5, self.LIFETIME)

            self.particles.append(Particle(position, vel, color, lifetime))

        # Node pour le rendu
        self.node = NodePath("explosion")
        self.node.reparentTo(game.render)
        self.node.setLightOff()

        # Crée la géométrie initiale
        self._build_geom()

    def _build_geom(self):
        """Construit la géométrie des particules."""
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
        np.setRenderModeThickness(4)

    def update(self, dt):
        """Met à jour les particules."""
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

            # Déplace la particule
            p.pos += p.velocity * dt

            # Ralentit (friction)
            p.velocity *= (1.0 - 2.0 * dt)

            # Fade out
            alpha = p.lifetime / p.max_lifetime
            faded = Vec4(p.color.getX(), p.color.getY(), p.color.getZ(), alpha)

            vertex.addData3(p.pos)
            color.addData4(faded)

        if not any_alive:
            self.destroy()

    def destroy(self):
        """Supprime l'explosion."""
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class ExplosionManager:
    """Gère toutes les explosions actives."""

    def __init__(self, game):
        self.game = game
        self.explosions = []

    def spawn(self, position):
        """Crée une explosion à la position donnée."""
        exp = Explosion(self.game, position)
        self.explosions.append(exp)

    def update(self, dt):
        """Met à jour toutes les explosions."""
        for exp in self.explosions:
            exp.update(dt)

        self.explosions = [e for e in self.explosions if e.alive]
