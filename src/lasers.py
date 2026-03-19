"""
Lasers — Système de tir laser du X-Wing.
Tir en paires alternées (haut puis bas) comme dans les films.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath
)
import math


class LaserBolt:
    """Un seul tir laser."""

    SPEED = 90.0
    MAX_DISTANCE = 200.0
    DAMAGE = 1

    def __init__(self, parent_node, start_pos, direction, color_back=None, color_front=None):
        self.alive = True
        self.distance_traveled = 0.0
        self.direction = direction

        # Couleurs par défaut : rouge/orange (joueur)
        if color_back is None:
            color_back = Vec4(1.0, 0.2, 0.0, 1)
        if color_front is None:
            color_front = Vec4(1.0, 0.7, 0.4, 1)

        self.node = self.make_bolt(color_back, color_front)
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)
        self.node.lookAt(start_pos + direction)
        self.node.setLightOff()

    def make_bolt(self, color_back, color_front):
        """Crée un bolt laser bien visible."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("bolt", fmt, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        hx, hy, hz = 0.06, 0.8, 0.06

        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
            (-hx,  hy, -hz), (hx,  hy, -hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        colors = [color_back]*4 + [color_front]*4

        for i, c in enumerate(corners):
            vertex.addData3(*c)
            col.addData4(colors[i])

        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0,1,2),(0,2,3),(4,6,5),(4,7,6),
            (0,4,5),(0,5,1),(2,6,7),(2,7,3),
            (0,3,7),(0,7,4),(1,5,6),(1,6,2),
        ]:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("bolt")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        if not self.alive:
            return

        move = self.SPEED * dt
        self.node.setPos(self.node.getPos() + self.direction * move)
        self.distance_traveled += move

        if self.distance_traveled > self.MAX_DISTANCE:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class LaserSystem:
    """Gère les tirs laser du joueur — 4 canons, tir par paires alternées."""

    FIRE_RATE = 0.15  # Temps entre chaque paire

    # Paires de canons en coordonnées LOCALES du modèle
    # Le modèle a: X = ailes (±1.0), Y = nez (1.4), Z = haut/bas (±0.3)
    # getRelativePoint convertit automatiquement en world space
    CANNON_PAIRS = [
        [Point3( 1.0, 1.3,  0.15), Point3(-1.0, 1.3,  0.15)],   # ailes haut
        [Point3( 1.0, 1.3, -0.15), Point3(-1.0, 1.3, -0.15)],   # ailes bas
    ]

    AUTO_AIM_RANGE = 120.0
    AUTO_AIM_STRENGTH = 0.15

    def __init__(self, game):
        self.game = game
        self.bolts = []
        self.fire_timer = 0.0
        self.pair_index = 0  # Alterne entre paire haute et basse
        self.firing = False
        self.enemies_ref = None

        game.accept("mouse1", self.start_fire)
        game.accept("mouse1-up", self.stop_fire)
        game.accept("space", self.start_fire)
        game.accept("space-up", self.stop_fire)

    def set_enemies(self, spawner):
        self.enemies_ref = spawner

    def start_fire(self):
        self.firing = True

    def stop_fire(self):
        self.firing = False

    def update(self, dt, player_node):
        self.fire_timer -= dt

        if self.firing and self.fire_timer <= 0:
            self.fire_pair(player_node)
            self.fire_timer = self.FIRE_RATE

        for bolt in self.bolts:
            bolt.update(dt)

        self.bolts = [b for b in self.bolts if b.alive]

    def find_nearest_enemy(self, from_pos):
        if not self.enemies_ref:
            return None

        nearest = None
        nearest_dist = self.AUTO_AIM_RANGE

        for enemy in self.enemies_ref.enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None or epos.getY() <= from_pos.getY():
                continue
            dist = (epos - from_pos).length()
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = enemy

        return nearest

    def fire_pair(self, player_node):
        """Tire 2 bolts simultanés depuis la paire de canons active."""
        pair = self.CANNON_PAIRS[self.pair_index]

        for offset in pair:
            world_pos = self.game.render.getRelativePoint(player_node, offset)

            # Direction de base
            base_dir = Vec3(0, 1, 0)

            # Auto-aim
            nearest = self.find_nearest_enemy(world_pos)
            if nearest:
                epos = nearest.get_pos()
                if epos:
                    to_enemy = epos - world_pos
                    to_enemy.normalize()
                    aim_dir = base_dir * (1 - self.AUTO_AIM_STRENGTH) + to_enemy * self.AUTO_AIM_STRENGTH
                    aim_dir.normalize()
                    base_dir = aim_dir

            bolt = LaserBolt(self.game.render, world_pos, base_dir)
            self.bolts.append(bolt)

        # Alterne la paire
        self.pair_index = (self.pair_index + 1) % len(self.CANNON_PAIRS)

    def get_bolts(self):
        return [b for b in self.bolts if b.alive]
