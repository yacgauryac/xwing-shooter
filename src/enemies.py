"""
Enemies — TIE Fighters, tirs ennemis, et gestion des vagues.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath
)
import random
import math


class EnemyBolt:
    """Un tir laser ennemi (vert)."""

    SPEED = 45.0
    DAMAGE = 1
    HIT_RADIUS = 1.5  # Rayon de collision avec le joueur

    def __init__(self, parent_node, start_pos, direction):
        self.alive = True
        self.direction = Vec3(direction)
        self.direction.normalize()

        self.node = self.make_bolt()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)
        self.node.lookAt(start_pos + self.direction)
        self.node.setLightOff()

    def make_bolt(self):
        """Crée un bolt laser vert."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("enemy_bolt", fmt, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        hx, hy, hz = 0.05, 0.6, 0.05

        color_back = Vec4(0.1, 0.8, 0.1, 1)
        color_front = Vec4(0.4, 1.0, 0.4, 1)

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
        node = GeomNode("enemy_bolt")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        if not self.alive:
            return
        self.node.setPos(self.node.getPos() + self.direction * self.SPEED * dt)

        # Hors champ → détruit
        pos = self.node.getPos()
        if pos.getY() < -15 or abs(pos.getX()) > 20 or abs(pos.getZ()) > 15:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TIEFighter:
    """Un TIE Fighter ennemi qui tire."""

    SPEED = 15.0
    HP = 2
    HIT_RADIUS = 1.8

    # Tir ennemi
    FIRE_RANGE = 80.0        # Distance max pour tirer
    FIRE_COOLDOWN_MIN = 2.0  # Cooldown minimum entre tirs
    FIRE_COOLDOWN_MAX = 5.0  # Cooldown maximum

    # Modèle 3D
    MODEL_PATH = "assets/models/tie.glb"
    MODEL_SCALE = 0.5   # Ajuster selon le modèle
    _model_template = None  # Cache du modèle (chargé une seule fois)

    def __init__(self, parent_node, start_pos, game=None):
        self.alive = True
        self.hp = self.HP
        self.flash_timer = 0.0
        self.game = game

        # Drift
        self.drift_x = random.uniform(-3.0, 3.0)
        self.drift_z = random.uniform(-1.5, 1.5)
        self.drift_speed = random.uniform(0.5, 1.5)
        self.drift_time = random.uniform(0, math.pi * 2)

        # Tir
        self.fire_timer = random.uniform(1.0, 3.0)

        self.node = self.load_model()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)

    def load_model(self):
        """Charge le modèle .glb ou fallback procédural."""
        import os
        if os.path.exists(self.MODEL_PATH) and self.game:
            try:
                # Charge le template une seule fois, puis copie
                if TIEFighter._model_template is None:
                    TIEFighter._model_template = self.game.loader.loadModel(self.MODEL_PATH)
                    if TIEFighter._model_template:
                        print(f"[TIE] Modèle 3D chargé: {self.MODEL_PATH}")

                if TIEFighter._model_template:
                    model = TIEFighter._model_template.copyTo(NodePath("tie_instance"))
                    model.setScale(self.MODEL_SCALE)
                    model.setH(90)  # Face au joueur
                    # Éclaircir le TIE pour qu'il soit visible sur fond noir
                    model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
                    # Debug
                    if not hasattr(TIEFighter, '_size_logged'):
                        bounds = model.getTightBounds()
                        if bounds:
                            bmin, bmax = bounds
                            print(f"[TIE] Dimensions: {bmax - bmin}")
                        TIEFighter._size_logged = True
                    return model
            except Exception as e:
                print(f"[TIE] Erreur chargement modèle: {e}")

        return self.create_tie()

    def create_tie(self):
        """Crée un TIE Fighter procédural."""
        root = NodePath("tie_fighter")

        cockpit = self.make_box(0.6, 0.6, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        cockpit.reparentTo(root)

        window = self.make_box(0.02, 0.4, 0.4, Vec4(0.1, 0.1, 0.4, 1))
        window.reparentTo(root)
        window.setPos(0.31, 0, 0)

        pylon_color = Vec4(0.4, 0.4, 0.45, 1)
        for y_sign in [-1, 1]:
            pylon = self.make_box(0.15, 0.08, 0.08, pylon_color)
            pylon.reparentTo(root)
            pylon.setPos(0, 0.45 * y_sign, 0)

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

        root.setH(90)
        return root

    def make_box(self, sx, sy, sz, color):
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

    def update(self, dt, player_pos=None):
        """Déplace le TIE et gère son tir."""
        if not self.alive:
            return None

        self.node.setY(self.node.getY() - self.SPEED * dt)

        self.drift_time += self.drift_speed * dt
        self.node.setX(self.node.getX() + math.sin(self.drift_time) * self.drift_x * dt)
        self.node.setZ(self.node.getZ() + math.cos(self.drift_time * 0.7) * self.drift_z * dt)

        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                # Restaure le boost de luminosité normal
                self.node.setColorScale(Vec4(1.8, 1.8, 2.0, 1))

        if self.node.getY() < -10:
            self.destroy()
            return None

        # Tir ennemi
        self.fire_timer -= dt
        if self.fire_timer <= 0 and player_pos is not None:
            my_pos = self.node.getPos()
            dist = (my_pos - player_pos).length()
            if dist < self.FIRE_RANGE and my_pos.getY() > player_pos.getY():
                self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
                # Direction vers le joueur avec imprécision
                direction = player_pos - my_pos
                direction.setX(direction.getX() + random.uniform(-2.0, 2.0))
                direction.setZ(direction.getZ() + random.uniform(-1.5, 1.5))
                direction.normalize()
                # Retourne 2 positions (gauche et droite du cockpit)
                offset = 0.4
                pos_left = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() + offset)
                pos_right = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() - offset)
                return [(pos_left, direction), (pos_right, direction)]

        return None

    def hit(self, damage=1):
        self.hp -= damage
        if self.hp <= 0:
            self.destroy()
            return True
        else:
            self.node.setColorScale(Vec4(3, 3, 3, 1))
            self.flash_timer = 0.1
            return False

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None


class EnemySpawner:
    """Gère le spawn, les tirs ennemis, et les vagues."""

    SPAWN_INTERVAL = 1.8
    SPAWN_DEPTH = 150.0
    MAX_ENEMIES = 12

    def __init__(self, game):
        self.game = game
        self.enemies = []
        self.enemy_bolts = []
        self.spawn_timer = 1.0
        self.score = 0
        self.wave = 1
        self.enemies_spawned = 0
        self.enemies_per_wave = 5

    def update(self, dt, laser_system, player_pos):
        """Spawn, update, tirs ennemis, collisions."""
        # Spawn
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len(self.enemies) < self.MAX_ENEMIES:
            if self.enemies_spawned < self.enemies_per_wave:
                self.spawn_enemy()
                self.spawn_timer = max(0.4, self.SPAWN_INTERVAL - self.wave * 0.1)
                self.enemies_spawned += 1

        # Update ennemis + récupère les tirs
        for enemy in self.enemies:
            fire_result = enemy.update(dt, player_pos)
            if fire_result is not None:
                # fire_result est une liste de (pos, direction)
                for pos, direction in fire_result:
                    bolt = EnemyBolt(self.game.render, pos, direction)
                    self.enemy_bolts.append(bolt)

        # Update tirs ennemis
        for bolt in self.enemy_bolts:
            bolt.update(dt)

        # Collisions laser joueur -> ennemi
        self.check_collisions(laser_system)

        # Nettoie
        self.enemies = [e for e in self.enemies if e.alive]
        self.enemy_bolts = [b for b in self.enemy_bolts if b.alive]

        # Vague suivante
        if self.enemies_spawned >= self.enemies_per_wave and len(self.enemies) == 0:
            self.next_wave()

    def check_player_hit(self, player_pos):
        """Vérifie si un tir ennemi touche le joueur. Retourne les dégâts."""
        damage = 0
        for bolt in self.enemy_bolts:
            if not bolt.alive:
                continue
            dist = (bolt.node.getPos() - player_pos).length()
            if dist < bolt.HIT_RADIUS:
                damage += bolt.DAMAGE
                bolt.destroy()
        return damage

    def spawn_enemy(self):
        x = random.uniform(-6.0, 6.0)
        z = random.uniform(-3.5, 3.5)
        pos = Point3(x, self.SPAWN_DEPTH, z)
        tie = TIEFighter(self.game.render, pos, game=self.game)
        self.enemies.append(tie)

    def check_collisions(self, laser_system):
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
                        # Retourne la position pour l'explosion (via game.py)
                        self.last_kill_pos = Vec3(enemy_pos)
                    break

    def next_wave(self):
        self.wave += 1
        self.enemies_spawned = 0
        self.enemies_per_wave = 5 + self.wave * 2
        self.spawn_timer = 2.0

    def get_enemy_count(self):
        return len(self.enemies)
