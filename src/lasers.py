"""
Lasers — Système de tir laser du X-Wing.
Les bolts partent des 4 canons en alternance avec léger auto-aim.
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

    SPEED = 90.0          # Vitesse du bolt
    MAX_DISTANCE = 200.0  # Distance max avant suppression
    DAMAGE = 1

    def __init__(self, parent_node, start_pos, direction):
        self.alive = True
        self.distance_traveled = 0.0
        self.direction = direction  # Vec3 normalisé

        # Crée le modèle du bolt
        self.node = self.make_bolt()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)

        # Oriente le bolt dans la direction de tir
        self.node.lookAt(start_pos + direction)

        # Pas d'éclairage (le laser brille tout seul)
        self.node.setLightOff()

    def make_bolt(self):
        """Crée un bolt laser bien visible."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("bolt", fmt, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Bolt plus gros et plus long pour être visible
        hx, hy, hz = 0.06, 0.8, 0.06

        colors_back = Vec4(1.0, 0.2, 0.0, 1)   # arrière : rouge vif
        colors_front = Vec4(1.0, 0.7, 0.4, 1)   # avant : orange clair

        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
            (-hx,  hy, -hz), (hx,  hy, -hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        colors = [colors_back]*4 + [colors_front]*4

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
        """Avance le bolt dans sa direction."""
        if not self.alive:
            return

        move = self.SPEED * dt
        offset = self.direction * move
        self.node.setPos(self.node.getPos() + offset)
        self.distance_traveled += move

        if self.distance_traveled > self.MAX_DISTANCE:
            self.destroy()

    def destroy(self):
        """Supprime le bolt."""
        self.alive = False
        self.node.removeNode()


class LaserSystem:
    """Gère tous les tirs laser du joueur."""

    FIRE_RATE = 0.10  # Tir un peu plus rapide

    # Positions des 4 canons relatif au vaisseau
    # Le vaisseau est tourné de -90 sur H :
    #   X vaisseau -> -Y monde
    #   Y vaisseau -> X monde
    # Canons sont aux bouts des ailes
    CANNON_OFFSETS = [
        Point3( 0.25, 0.0,  0.8),   # haut-droit
        Point3(-0.25, 0.0,  0.8),   # haut-gauche
        Point3( 0.25, 0.0, -0.8),   # bas-droit
        Point3(-0.25, 0.0, -0.8),   # bas-gauche
    ]

    # Distance max pour l'auto-aim (au-delà, tir droit)
    AUTO_AIM_RANGE = 120.0
    # Force de l'auto-aim (0 = aucun, 1 = 100% vers l'ennemi)
    AUTO_AIM_STRENGTH = 0.15

    def __init__(self, game):
        self.game = game
        self.bolts = []
        self.fire_timer = 0.0
        self.cannon_index = 0
        self.firing = False
        self.enemies_ref = None  # Référence au spawner, set par game.py

        # Contrôles de tir
        game.accept("mouse1", self.start_fire)
        game.accept("mouse1-up", self.stop_fire)
        game.accept("space", self.start_fire)
        game.accept("space-up", self.stop_fire)

    def set_enemies(self, spawner):
        """Connecte le système de tir au spawner pour l'auto-aim."""
        self.enemies_ref = spawner

    def start_fire(self):
        self.firing = True

    def stop_fire(self):
        self.firing = False

    def update(self, dt, player_node):
        """Met à jour les tirs et crée de nouveaux bolts."""
        self.fire_timer -= dt

        if self.firing and self.fire_timer <= 0:
            self.fire(player_node)
            self.fire_timer = self.FIRE_RATE

        for bolt in self.bolts:
            bolt.update(dt)

        self.bolts = [b for b in self.bolts if b.alive]

    def find_nearest_enemy(self, from_pos):
        """Trouve l'ennemi vivant le plus proche devant le joueur."""
        if not self.enemies_ref:
            return None

        nearest = None
        nearest_dist = self.AUTO_AIM_RANGE

        for enemy in self.enemies_ref.enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None:
                continue
            # Seulement les ennemis devant le joueur
            if epos.getY() <= from_pos.getY():
                continue
            dist = (epos - from_pos).length()
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = enemy

        return nearest

    def fire(self, player_node):
        """Tire un bolt depuis le canon suivant avec auto-aim."""
        offset = self.CANNON_OFFSETS[self.cannon_index]
        world_pos = self.game.render.getRelativePoint(player_node, offset)

        # Direction de base : droit devant (+Y)
        base_dir = Vec3(0, 1, 0)

        # Auto-aim : dévie légèrement vers l'ennemi le plus proche
        nearest = self.find_nearest_enemy(world_pos)
        if nearest:
            epos = nearest.get_pos()
            if epos:
                to_enemy = epos - world_pos
                to_enemy.normalize()
                # Mélange direction de base + direction vers l'ennemi
                aim_dir = base_dir * (1 - self.AUTO_AIM_STRENGTH) + to_enemy * self.AUTO_AIM_STRENGTH
                aim_dir.normalize()
                base_dir = aim_dir

        bolt = LaserBolt(self.game.render, world_pos, base_dir)
        self.bolts.append(bolt)

        # Alterne le canon
        self.cannon_index = (self.cannon_index + 1) % len(self.CANNON_OFFSETS)

    def get_bolts(self):
        """Retourne les bolts actifs."""
        return [b for b in self.bolts if b.alive]
