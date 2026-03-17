"""
Enemies — TIE Fighters et gestion des vagues.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath
)
import random
import math


class TIEFighter:
    """Un TIE Fighter ennemi."""

    SPEED = 15.0
    HP = 2
    HIT_RADIUS = 1.8  # Hitbox plus généreuse

    def __init__(self, parent_node, start_pos):
        self.alive = True
        self.hp = self.HP
        self.flash_timer = 0.0

        # Drift latéral
        self.drift_x = random.uniform(-3.0, 3.0)
        self.drift_z = random.uniform(-1.5, 1.5)
        self.drift_speed = random.uniform(0.5, 1.5)
        self.drift_time = random.uniform(0, math.pi * 2)

        self.node = self.create_tie()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)

    def create_tie(self):
        """Crée un TIE Fighter procédural."""
        root = NodePath("tie_fighter")

        # Cockpit (gris foncé)
        cockpit = self.make_box(0.6, 0.6, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        cockpit.reparentTo(root)

        # Fenêtre cockpit (bleu foncé)
        window = self.make_box(0.02, 0.4, 0.4, Vec4(0.1, 0.1, 0.4, 1))
        window.reparentTo(root)
        window.setPos(0.31, 0, 0)

        # Pylônes
        pylon_color = Vec4(0.4, 0.4, 0.45, 1)
        for y_sign in [-1, 1]:
            pylon = self.make_box(0.15, 0.08, 0.08, pylon_color)
            pylon.reparentTo(root)
            pylon.setPos(0, 0.45 * y_sign, 0)

        # Panneaux solaires
        panel_color = Vec4(0.25, 0.25, 0.3, 1)
        panel_edge = Vec4(0.5, 0.5, 0.55, 1)
        for y_sign in [-1, 1]:
            panel = self.make_box(0.06, 0.06, 1.6, panel_color)
            panel.reparentTo(root)
            panel.setPos(0, 0.7 * y_sign, 0)

            for z_off in [-0.7, -0.35, 0, 0.35, 0.7]:
                bar = self.make_box(0.07, 0.04, 0.1, panel_edge)
                bar.reparentTo(root)
                bar.setPos(0, 0.7 * y_sign, z_off)

        # Face au joueur
        root.setH(90)
        return root

    def make_box(self, sx, sy, sz, color):
        """Crée un pavé coloré."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
            (-hx, -hy,  hz), (hx, -hy,  hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        for c in corners:
            vertex.addData3(*c)
            col.addData4(color)

        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0,1,2),(0,2,3),(4,6,5),(4,7,6),
            (0,4,5),(0,5,1),(2,6,7),(2,7,3),
            (0,3,7),(0,7,4),(1,5,6),(1,6,2),
        ]:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("box")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        """Déplace le TIE vers le joueur avec drift."""
        if not self.alive:
            return

        # Avance vers le joueur
        self.node.setY(self.node.getY() - self.SPEED * dt)

        # Drift sinusoïdal
        self.drift_time += self.drift_speed * dt
        drift_offset_x = math.sin(self.drift_time) * self.drift_x * dt
        drift_offset_z = math.cos(self.drift_time * 0.7) * self.drift_z * dt
        self.node.setX(self.node.getX() + drift_offset_x)
        self.node.setZ(self.node.getZ() + drift_offset_z)

        # Flash de dégât : revient à la normale
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.node.clearColorScale()

        # Passé derrière la caméra → détruit
        if self.node.getY() < -10:
            self.destroy()

    def hit(self, damage=1):
        """Touché par un laser."""
        self.hp -= damage
        if self.hp <= 0:
            self.destroy()
            return True
        else:
            # Flash blanc
            self.node.setColorScale(Vec4(3, 3, 3, 1))
            self.flash_timer = 0.1
            return False

    def destroy(self):
        """Supprime le TIE."""
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()

    def get_pos(self):
        """Position actuelle."""
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None


class EnemySpawner:
    """Gère le spawn des vagues d'ennemis."""

    SPAWN_INTERVAL = 1.8
    SPAWN_DEPTH = 150.0
    MAX_ENEMIES = 12

    def __init__(self, game):
        self.game = game
        self.enemies = []
        self.spawn_timer = 1.0
        self.score = 0
        self.wave = 1
        self.enemies_spawned = 0
        self.enemies_per_wave = 5

    def update(self, dt, laser_system):
        """Spawn des ennemis et vérifie les collisions."""
        self.spawn_timer -= dt

        if self.spawn_timer <= 0 and len(self.enemies) < self.MAX_ENEMIES:
            if self.enemies_spawned < self.enemies_per_wave:
                self.spawn_enemy()
                self.spawn_timer = max(0.4, self.SPAWN_INTERVAL - self.wave * 0.1)
                self.enemies_spawned += 1

        for enemy in self.enemies:
            enemy.update(dt)

        self.check_collisions(laser_system)
        self.enemies = [e for e in self.enemies if e.alive]

        # Vague suivante
        if self.enemies_spawned >= self.enemies_per_wave and len(self.enemies) == 0:
            self.next_wave()

    def spawn_enemy(self):
        """Fait apparaître un TIE Fighter."""
        x = random.uniform(-6.0, 6.0)
        z = random.uniform(-3.5, 3.5)
        pos = Point3(x, self.SPAWN_DEPTH, z)

        tie = TIEFighter(self.game.render, pos)
        self.enemies.append(tie)

    def check_collisions(self, laser_system):
        """Vérifie les collisions laser <-> ennemi."""
        for bolt in laser_system.get_bolts():
            if not bolt.alive:
                continue

            bolt_pos = bolt.node.getPos()

            for enemy in self.enemies:
                if not enemy.alive:
                    continue

                enemy_pos = enemy.get_pos()
                if enemy_pos is None:
                    continue

                dist = (bolt_pos - enemy_pos).length()

                if dist < enemy.HIT_RADIUS:
                    destroyed = enemy.hit(bolt.DAMAGE)
                    bolt.destroy()
                    if destroyed:
                        self.score += 100
                    break

    def next_wave(self):
        """Passe à la vague suivante."""
        self.wave += 1
        self.enemies_spawned = 0
        self.enemies_per_wave = 5 + self.wave * 2
        self.spawn_timer = 2.0

    def get_enemy_count(self):
        return len(self.enemies)
