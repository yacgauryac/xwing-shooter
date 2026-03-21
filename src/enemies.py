"""
Enemies — Bestiaire impérial, formations, et gestion des vagues.
Types : TIE Fighter (standard), TIE Interceptor (rapide), TIE Bomber (tank).
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath
)
import random
import math
import os


# ============================================================
# Tirs ennemis
# ============================================================

class EnemyBolt:
    """Un tir laser ennemi (vert)."""

    SPEED = 65.0
    DAMAGE = 2
    HIT_RADIUS = 1.8

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
        pos = self.node.getPos()
        if pos.getY() < -15 or abs(pos.getX()) > 20 or abs(pos.getZ()) > 15:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# Classe de base ennemi
# ============================================================

class BaseEnemy:
    """Classe de base pour tous les ennemis."""

    # Overrides dans les sous-classes
    SPEED_BASE = 15.0
    SPEED_CHARGE = 35.0      # Vitesse quand il fonce vers le joueur
    CHARGE_DISTANCE = 60.0   # Distance à laquelle il accélère
    HP = 2
    HIT_RADIUS = 1.8
    FIRE_RANGE = 80.0
    FIRE_COOLDOWN_MIN = 2.0
    FIRE_COOLDOWN_MAX = 5.0
    BOLTS_PER_SHOT = 2       # Nombre de tirs simultanés
    SCORE_VALUE = 100

    MODEL_PATH = None
    MODEL_SCALE = 0.5
    MODEL_H = 0               # Rotation horizontale du modèle
    TARGET_SIZE = 2.0
    COLOR_BOOST = Vec4(1.8, 1.8, 2.0, 1)

    # Cache de modèles par classe
    _model_cache = {}

    def __init__(self, parent_node, start_pos, game=None):
        self.alive = True
        self.hp = self.HP
        self.flash_timer = 0.0
        self.game = game
        self.score_value = self.SCORE_VALUE

        # Drift latéral
        self.drift_x = random.uniform(-3.0, 3.0)
        self.drift_z = random.uniform(-1.5, 1.5)
        self.drift_speed = random.uniform(0.5, 1.5)
        self.drift_time = random.uniform(0, math.pi * 2)

        # Tir
        self.fire_timer = random.uniform(1.0, 3.0)

        # Vitesse actuelle (accélère à l'approche)
        self.current_speed = self.SPEED_BASE

        self.node = self.load_model()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)

    def load_model(self):
        """Charge le modèle .glb/.gltf (caché) ou fallback procédural."""
        class_name = type(self).__name__

        if self.MODEL_PATH and os.path.exists(self.MODEL_PATH) and self.game:
            try:
                if class_name not in BaseEnemy._model_cache:
                    template = self.game.loader.loadModel(self.MODEL_PATH)
                    if template:
                        BaseEnemy._model_cache[class_name] = template
                        print(f"[{class_name}] Modèle 3D chargé: {self.MODEL_PATH}")

                        # Log les dimensions pour calibrer le scale
                        bounds = template.getTightBounds()
                        if bounds:
                            bmin, bmax = bounds
                            size = bmax - bmin
                            print(f"[{class_name}] Dimensions brutes: {size}")
                            max_dim = max(size.getX(), size.getY(), size.getZ())
                            # Calcule le scale pour que le modèle fasse TARGET_SIZE
                            if max_dim > 0:
                                auto_scale = self.TARGET_SIZE / max_dim
                                print(f"[{class_name}] Auto-scale: {auto_scale:.4f} (target {self.TARGET_SIZE})")
                                BaseEnemy._model_cache[class_name + "_scale"] = auto_scale

                if class_name in BaseEnemy._model_cache:
                    model = BaseEnemy._model_cache[class_name].copyTo(NodePath(f"{class_name}_inst"))

                    # Utilise l'auto-scale si disponible, sinon MODEL_SCALE
                    scale = BaseEnemy._model_cache.get(class_name + "_scale", self.MODEL_SCALE)
                    model.setScale(scale)
                    model.setH(self.MODEL_H)
                    model.setColorScale(self.COLOR_BOOST)
                    return model
            except Exception as e:
                print(f"[{class_name}] Erreur: {e}")

        return self.create_procedural()

    def create_procedural(self):
        """Fallback procédural — override dans les sous-classes."""
        return self._make_default_shape()

    def _make_box(self, sx, sy, sz, color):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),
            (-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz),
        ]
        for c in corners:
            vertex.addData3(*c)
            col.addData4(color)
        tris = GeomTriangles(Geom.UHStatic)
        for f in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),(2,6,7),(2,7,3),(0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
            tris.addVertices(*f)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("box")
        node.addGeom(geom)
        return NodePath(node)

    def _make_default_shape(self):
        root = NodePath("enemy_default")
        box = self._make_box(0.6, 0.6, 0.6, Vec4(0.4, 0.4, 0.45, 1))
        box.reparentTo(root)
        return root

    def update(self, dt, player_pos=None):
        if not self.alive:
            return None

        # Accélération à l'approche du joueur
        if player_pos:
            dist = (self.node.getPos() - player_pos).length()
            if dist < self.CHARGE_DISTANCE:
                # Plus on est proche, plus on accélère
                charge_factor = 1.0 - (dist / self.CHARGE_DISTANCE)
                self.current_speed = self.SPEED_BASE + (self.SPEED_CHARGE - self.SPEED_BASE) * charge_factor
            else:
                self.current_speed = self.SPEED_BASE

        self.node.setY(self.node.getY() - self.current_speed * dt)

        # Drift
        self.drift_time += self.drift_speed * dt
        self.node.setX(self.node.getX() + math.sin(self.drift_time) * self.drift_x * dt)
        self.node.setZ(self.node.getZ() + math.cos(self.drift_time * 0.7) * self.drift_z * dt)

        # Clamp dans la zone jouable
        x = self.node.getX()
        z = self.node.getZ()
        if x < -9:
            self.node.setX(-9)
        elif x > 9:
            self.node.setX(9)
        if z < -6:
            self.node.setZ(-6)
        elif z > 6:
            self.node.setZ(6)

        # Flash de dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.node.setColorScale(self.COLOR_BOOST)

        if self.node.getY() < -10:
            self.destroy()
            return None

        # Tir
        self.fire_timer -= dt
        if self.fire_timer <= 0 and player_pos is not None:
            return self._try_fire(player_pos)

        return None

    def _try_fire(self, player_pos):
        my_pos = self.node.getPos()
        dist = (my_pos - player_pos).length()
        if dist < self.FIRE_RANGE and my_pos.getY() > player_pos.getY():
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            direction = player_pos - my_pos
            direction.setX(direction.getX() + random.uniform(-1.2, 1.2))
            direction.setZ(direction.getZ() + random.uniform(-0.8, 0.8))
            direction.normalize()

            results = []
            offset = 0.4
            if self.BOLTS_PER_SHOT >= 2:
                pos_l = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() + offset)
                pos_r = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() - offset)
                results.append((pos_l, direction))
                results.append((pos_r, direction))
            else:
                results.append((Vec3(my_pos), direction))
            return results

        return None

    SPAWN_PROTECT_Y = 120.0  # Invincible tant qu'au-delà de cette distance

    def hit(self, damage=1):
        # Protection au spawn — pas touchable tant que trop loin
        if self.node.getY() > self.SPAWN_PROTECT_Y:
            return False

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


# ============================================================
# Types d'ennemis
# ============================================================

class TIEFighter(BaseEnemy):
    """TIE Fighter standard — équilibré."""
    SPEED_BASE = 18.0
    SPEED_CHARGE = 65.0       # Kamikaze !
    CHARGE_DISTANCE = 100.0   # Accélère de loin
    HP = 2
    HIT_RADIUS = 1.8
    FIRE_COOLDOWN_MIN = 1.2
    FIRE_COOLDOWN_MAX = 3.0
    BOLTS_PER_SHOT = 2
    SCORE_VALUE = 100

    MODEL_PATH = "assets/models/tie_fighter/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 2.0         # ~2 unités monde

    def create_procedural(self):
        root = NodePath("tie_fighter")
        cockpit = self._make_box(0.6, 0.6, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        cockpit.reparentTo(root)
        for y_sign in [-1, 1]:
            panel = self._make_box(0.06, 0.06, 1.6, Vec4(0.25, 0.25, 0.3, 1))
            panel.reparentTo(root)
            panel.setPos(0, 0.7 * y_sign, 0)
        root.setH(90)
        return root


class TIEInterceptor(BaseEnemy):
    """TIE Interceptor — rapide et agressif, tir fréquent."""
    SPEED_BASE = 25.0
    SPEED_CHARGE = 80.0       # Ultra rapide en charge
    CHARGE_DISTANCE = 110.0   # Fonce de très loin
    HP = 1
    HIT_RADIUS = 1.5
    FIRE_COOLDOWN_MIN = 0.6
    FIRE_COOLDOWN_MAX = 1.5
    BOLTS_PER_SHOT = 1
    SCORE_VALUE = 150

    MODEL_PATH = "assets/models/tie_interceptor/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 1.8         # Un peu plus petit que le TIE standard

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drift plus agressif
        self.drift_x = random.uniform(-5.0, 5.0)
        self.drift_z = random.uniform(-3.0, 3.0)
        self.drift_speed = random.uniform(1.5, 3.0)

    def create_procedural(self):
        """Interceptor procédural — ailes en pointe."""
        root = NodePath("tie_interceptor")
        cockpit = self._make_box(0.5, 0.5, 0.5, Vec4(0.35, 0.35, 0.4, 1))
        cockpit.reparentTo(root)
        # Ailes en pointe (triangulaires approximées)
        wing_color = Vec4(0.3, 0.3, 0.35, 1)
        for y_sign in [-1, 1]:
            wing = self._make_box(0.04, 0.04, 1.4, wing_color)
            wing.reparentTo(root)
            wing.setPos(0.2, 0.6 * y_sign, 0)
            wing.setP(15 * y_sign)

            wing2 = self._make_box(0.04, 0.04, 1.4, wing_color)
            wing2.reparentTo(root)
            wing2.setPos(-0.2, 0.6 * y_sign, 0)
            wing2.setP(-15 * y_sign)
        root.setH(90)
        return root


class TIEBomber(BaseEnemy):
    """TIE Bomber — lent, résistant, tire des salves lourdes."""
    SPEED_BASE = 10.0
    SPEED_CHARGE = 30.0       # Même le bomber accélère
    CHARGE_DISTANCE = 80.0
    HP = 5
    HIT_RADIUS = 2.2
    FIRE_COOLDOWN_MIN = 3.0
    FIRE_COOLDOWN_MAX = 6.0
    BOLTS_PER_SHOT = 2
    SCORE_VALUE = 250

    MODEL_PATH = "assets/models/tie_bomber/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 2.5         # Plus gros que les autres

    def create_procedural(self):
        """Bomber procédural — double cockpit."""
        root = NodePath("tie_bomber")
        # Double pod
        pod1 = self._make_box(0.6, 0.7, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        pod1.reparentTo(root)
        pod1.setPos(0, -0.3, 0)
        pod2 = self._make_box(0.6, 0.7, 0.6, Vec4(0.28, 0.28, 0.33, 1))
        pod2.reparentTo(root)
        pod2.setPos(0, 0.3, 0)
        # Panels
        for y_sign in [-1, 1]:
            panel = self._make_box(0.06, 0.08, 1.8, Vec4(0.25, 0.25, 0.3, 1))
            panel.reparentTo(root)
            panel.setPos(0, 0.8 * y_sign, 0)
        root.setH(90)
        return root


# ============================================================
# Formations
# ============================================================

class Formation:
    """Définit un pattern de spawn pour un groupe d'ennemis."""

    @staticmethod
    def v_formation(center_x, center_z, count, spacing=2.5):
        """Formation en V."""
        positions = []
        for i in range(count):
            side = 1 if i % 2 == 0 else -1
            row = (i + 1) // 2
            x = center_x + side * row * spacing
            # Clamp X pour rester dans les bounds
            x = max(-8, min(8, x))
            z = center_z + row * spacing * 0.3
            y_offset = row * 6
            positions.append((x, y_offset, z))
        return positions

    @staticmethod
    def line_formation(center_x, center_z, count, spacing=3.0):
        """Formation en ligne horizontale."""
        positions = []
        start_x = center_x - (count - 1) * spacing / 2
        for i in range(count):
            x = max(-8, min(8, start_x + i * spacing))
            positions.append((x, 0, center_z))
        return positions

    @staticmethod
    def pincer_formation(count):
        """Attaque en tenaille — ennemis arrivent des côtés."""
        positions = []
        per_side = count // 2
        for i in range(per_side):
            positions.append((-6 - i * 1, i * 10, random.uniform(-2, 2)))
        for i in range(count - per_side):
            positions.append((6 + i * 1, i * 10, random.uniform(-2, 2)))
        return positions

    @staticmethod
    def swarm_formation(center_x, center_z, count):
        """Essaim aléatoire concentré."""
        positions = []
        for _ in range(count):
            x = max(-8, min(8, center_x + random.uniform(-5, 5)))
            z = max(-5, min(5, center_z + random.uniform(-3, 3)))
            y_offset = random.uniform(0, 20)
            positions.append((x, y_offset, z))
        return positions


# ============================================================
# Spawner
# ============================================================

class EnemySpawner:
    """Gère le spawn, les tirs ennemis, et les vagues."""

    SPAWN_DEPTH = 150.0
    MAX_ENEMIES = 15

    # Définition des vagues
    WAVE_DEFS = [
        # Vague 1 : TIE simples, ligne
        {"enemies": [TIEFighter] * 5, "formation": "line"},
        # Vague 2 : TIE en V
        {"enemies": [TIEFighter] * 7, "formation": "v"},
        # Vague 3 : Mix TIE + Interceptor
        {"enemies": [TIEFighter] * 4 + [TIEInterceptor] * 2, "formation": "swarm"},
        # Vague 4 : Interceptors rapides, pincer
        {"enemies": [TIEInterceptor] * 6, "formation": "pincer"},
        # Vague 5 : Premier Bomber + escorte
        {"enemies": [TIEBomber] * 1 + [TIEFighter] * 4, "formation": "v"},
        # Vague 6 : Gros mix
        {"enemies": [TIEFighter] * 4 + [TIEInterceptor] * 3 + [TIEBomber] * 1, "formation": "swarm"},
        # Vague 7+ : Escalade
        {"enemies": [TIEInterceptor] * 4 + [TIEBomber] * 2 + [TIEFighter] * 4, "formation": "pincer"},
    ]

    def __init__(self, game):
        self.game = game
        self.enemies = []
        self.enemy_bolts = []
        self.spawn_timer = 2.0
        self.score = 0
        self.wave = 1
        self.wave_enemies_to_spawn = []
        self.spawn_index = 0
        self.wave_started = False
        self.last_kill_pos = None

        self._prepare_wave()

    def _prepare_wave(self):
        """Prépare la vague courante."""
        wave_idx = min(self.wave - 1, len(self.WAVE_DEFS) - 1)
        wave_def = self.WAVE_DEFS[wave_idx]

        enemy_classes = wave_def["enemies"]
        formation_type = wave_def["formation"]

        # Pour les vagues au-delà des définitions, on scale
        if self.wave > len(self.WAVE_DEFS):
            extra = self.wave - len(self.WAVE_DEFS)
            # Ajoute des ennemis supplémentaires
            for _ in range(extra * 2):
                enemy_classes.append(random.choice([TIEFighter, TIEInterceptor, TIEBomber]))

        count = len(enemy_classes)
        center_x = random.uniform(-4, 4)
        center_z = random.uniform(-2, 2)

        if formation_type == "v":
            offsets = Formation.v_formation(center_x, center_z, count)
        elif formation_type == "line":
            offsets = Formation.line_formation(center_x, center_z, count)
        elif formation_type == "pincer":
            offsets = Formation.pincer_formation(count)
        else:  # swarm
            offsets = Formation.swarm_formation(center_x, center_z, count)

        self.wave_enemies_to_spawn = list(zip(enemy_classes, offsets))
        self.spawn_index = 0
        self.spawn_timer = 1.5  # Pause avant la vague
        self.wave_started = True

    def update(self, dt, laser_system, player_pos):
        # Spawn progressif de la vague
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and self.spawn_index < len(self.wave_enemies_to_spawn):
            if len(self.enemies) < self.MAX_ENEMIES:
                self._spawn_next()
                self.spawn_timer = 0.5  # Délai entre chaque spawn dans la formation

        # Update ennemis
        for enemy in self.enemies:
            fire_result = enemy.update(dt, player_pos)
            if fire_result is not None:
                for pos, direction in fire_result:
                    bolt = EnemyBolt(self.game.render, pos, direction)
                    self.enemy_bolts.append(bolt)

        # Update tirs ennemis
        for bolt in self.enemy_bolts:
            bolt.update(dt)

        # Collisions
        self.check_collisions(laser_system)

        # Nettoie
        self.enemies = [e for e in self.enemies if e.alive]
        self.enemy_bolts = [b for b in self.enemy_bolts if b.alive]

        # Vague terminée ?
        if (self.spawn_index >= len(self.wave_enemies_to_spawn)
                and len(self.enemies) == 0):
            self.next_wave()

    def _spawn_next(self):
        """Spawn le prochain ennemi de la vague."""
        if self.spawn_index >= len(self.wave_enemies_to_spawn):
            return

        enemy_class, (off_x, off_y, off_z) = self.wave_enemies_to_spawn[self.spawn_index]
        pos = Point3(off_x, self.SPAWN_DEPTH + off_y, off_z)

        enemy = enemy_class(self.game.render, pos, game=self.game)
        self.enemies.append(enemy)
        self.spawn_index += 1

    def check_player_hit(self, player_pos):
        damage = 0
        # Tirs ennemis → joueur
        for bolt in self.enemy_bolts:
            if not bolt.alive:
                continue
            dist = (bolt.node.getPos() - player_pos).length()
            if dist < bolt.HIT_RADIUS:
                damage += bolt.DAMAGE
                bolt.destroy()

        # Collision corps-à-corps TIE → joueur
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None:
                continue
            dist = (epos - player_pos).length()
            if dist < enemy.HIT_RADIUS + 1.0:  # Hitbox combinée
                damage += 3  # Gros dégâts collision
                enemy.hp = 0
                enemy.destroy()
                self.last_kill_pos = Vec3(epos)

        return damage

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
                if dist < enemy.HIT_RADIUS + 0.5:  # Plus généreux
                    destroyed = enemy.hit(bolt.DAMAGE)
                    bolt.destroy()
                    if destroyed:
                        self.score += enemy.score_value
                        self.last_kill_pos = Vec3(enemy_pos)
                    break

    def next_wave(self):
        self.wave += 1
        self._prepare_wave()

    def get_enemy_count(self):
        remaining = len(self.wave_enemies_to_spawn) - self.spawn_index
        return len(self.enemies) + remaining
