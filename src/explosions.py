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


class ScorePopup:
    """Points qui s'affichent et montent en fadant."""

    def __init__(self, game, position, score):
        self.alive = True
        self.timer = 0.0
        self.duration = 1.0
        self.game = game

        pos2d = self._world_to_screen(position)
        from direct.gui.OnscreenText import OnscreenText
        from panda3d.core import TextNode
        self.text = OnscreenText(
            text=f"+{score}",
            pos=pos2d,
            scale=0.05,
            fg=Vec4(1.0, 0.7, 0.2, 1.0),
            align=TextNode.ACenter,
            mayChange=True,
            sort=60,
        )
        self.start_y = pos2d[1]

    def _world_to_screen(self, world_pos):
        p3 = self.game.cam.getRelativePoint(self.game.render, world_pos)
        if p3.getY() <= 0:
            return (0, 0)
        lens = self.game.camLens
        from panda3d.core import Point3 as P3
        p2d = P3()
        if lens.project(p3, p2d):
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
        y_offset = progress * 0.15
        alpha = 1.0 - progress
        self.text.setPos(self.text.getPos()[0], self.start_y + y_offset)
        self.text.setFg(Vec4(1.0, 0.7, 0.2, alpha))
        self.text.setScale(0.05 + progress * 0.01)

    def destroy(self):
        self.alive = False
        self.text.destroy()


class ExplosionManager:
    """Gère explosions + score popups."""

    def __init__(self, game):
        self.game = game
        self.explosions = []
        self.popups = []

    def spawn(self, position, score=0):
        """Crée une explosion + popup de score."""
        exp = Explosion(self.game, position)
        self.explosions.append(exp)
        if score > 0:
            popup = ScorePopup(self.game, position, score)
            self.popups.append(popup)

    def update(self, dt):
        for exp in self.explosions:
            exp.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]
        for popup in self.popups:
            popup.update(dt)
        self.popups = [p for p in self.popups if p.alive]
