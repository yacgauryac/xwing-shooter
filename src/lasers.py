"""
Lasers — Système de tir avec surchauffe/cooldown.
Tir en paires alternées, surchauffe après trop de tirs, cooldown avec timer rotatif.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, ColorBlendAttrib, TransparencyAttrib
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
        """Bolt laser : noyau blanc + halo coloré en blending additif (pas d'enveloppe visible)."""
        root = NodePath("bolt_root")
        fmt = GeomVertexFormat.getV3c4()

        def make_box(hx, hy, hz, col_back, col_front):
            vd = GeomVertexData("b", fmt, Geom.UHStatic)
            v  = GeomVertexWriter(vd, "vertex")
            c  = GeomVertexWriter(vd, "color")
            corners = [
                (-hx,-hy,-hz),(hx,-hy,-hz),(hx,-hy,hz),(-hx,-hy,hz),
                (-hx, hy,-hz),(hx, hy,-hz),(hx, hy,hz),(-hx, hy,hz),
            ]
            for i, corner in enumerate(corners):
                v.addData3(*corner)
                c.addData4(col_back if i < 4 else col_front)
            tris = GeomTriangles(Geom.UHStatic)
            for f in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),
                      (0,4,5),(0,5,1),(2,6,7),(2,7,3),
                      (0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
                tris.addVertices(*f)
            geom = Geom(vd); geom.addPrimitive(tris)
            gn = GeomNode("box"); gn.addGeom(geom)
            return NodePath(gn)

        def additive(np):
            """Blending additif : pixels noirs = invisibles, pas d'enveloppe."""
            np.setAttrib(ColorBlendAttrib.make(
                ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
            np.setDepthWrite(False)
            np.setTransparency(TransparencyAttrib.MNone)

        # ── Noyau blanc brillant ─────────────────────────────────────────
        core = make_box(0.05, 1.8, 0.05,
                        Vec4(0.85, 0.85, 0.85, 1),   # arrière : blanc chaud
                        Vec4(1.0,  1.0,  1.0,  1))   # avant   : blanc pur
        core.reparentTo(root)
        additive(core)

        # ── Halo intermédiaire : dégradé blanc → couleur ────────────────
        mid = make_box(0.10, 2.0, 0.10,
                       Vec4(color_back.getX() * 0.6 + 0.4,   # mélange blanc + couleur
                            color_back.getY() * 0.6 + 0.4,
                            color_back.getZ() * 0.6 + 0.4, 1),
                       Vec4(color_front.getX(), color_front.getY(), color_front.getZ(), 1))
        mid.reparentTo(root)
        additive(mid)

        # ── Halo extérieur : pleine couleur, large ───────────────────────
        glow = make_box(0.20, 2.4, 0.20,
                        Vec4(color_back.getX()  * 0.7,
                             color_back.getY()  * 0.7,
                             color_back.getZ()  * 0.7, 1),
                        Vec4(color_front.getX() * 0.5,
                             color_front.getY() * 0.5,
                             color_front.getZ() * 0.5, 1))
        glow.reparentTo(root)
        additive(glow)

        return root

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
    """Tir par paires alternées avec système de surchauffe."""

    FIRE_RATE = 0.12          # Temps entre chaque paire (original)

    # Surchauffe
    MAX_HEAT = 100.0
    HEAT_PER_SHOT = 8.0       # Moins de chaleur = ~2 salves de plus avant overheat
    HEAT_DECAY = 25.0         # Refroidissement par seconde (quand on tire pas)
    OVERHEAT_THRESHOLD = 100.0  # Seuil de surchauffe
    COOLDOWN_TIME = 2.5       # Durée du cooldown forcé (secondes)

    # Canons
    CANNON_PAIRS = [
        [Point3( 1.0, 1.5,  0.03), Point3(-1.0, 1.5,  0.03)],
        [Point3( 1.0, 1.5, -0.03), Point3(-1.0, 1.5, -0.03)],
    ]

    AUTO_AIM_RANGE = 120.0
    AUTO_AIM_STRENGTH = 0.15

    def __init__(self, game):
        self.game = game
        self.bolts = []
        self.fire_timer = 0.0
        self.pair_index = 0
        self.firing = False
        self.enemies_ref = None

        # Surchauffe
        self.heat = 0.0
        self.overheated = False
        self.cooldown_timer = 0.0
        self.cooldown_total = self.COOLDOWN_TIME

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

    def update(self, dt, player_node, force_active=False):
        self.fire_timer -= dt

        # Force active → pas de surchauffe
        if force_active:
            self.heat = max(0, self.heat - self.HEAT_DECAY * 3 * dt)
            self.overheated = False
            self.cooldown_timer = 0

            if self.firing and self.fire_timer <= 0:
                self.fire_pair(player_node, force_active=True)
                self.fire_timer = self.FIRE_RATE * 0.7  # Tir plus rapide
        else:
            # Gestion surchauffe normale
            if self.overheated:
                self.cooldown_timer -= dt
                if self.cooldown_timer <= 0:
                    self.overheated = False
                    self.heat = 0.0
                    self.cooldown_timer = 0.0
            else:
                if not self.firing:
                    self.heat = max(0, self.heat - self.HEAT_DECAY * dt)
                else:
                    self.heat = max(0, self.heat - self.HEAT_DECAY * 0.3 * dt)

                if self.firing and self.fire_timer <= 0 and not self.overheated:
                    self.fire_pair(player_node)
                    self.fire_timer = self.FIRE_RATE
                    self.heat += self.HEAT_PER_SHOT

                    if self.heat >= self.OVERHEAT_THRESHOLD:
                        self.overheated = True
                        self.cooldown_timer = self.COOLDOWN_TIME
                        self.cooldown_total = self.COOLDOWN_TIME

        # Update bolts
        for bolt in self.bolts:
            bolt.update(dt)
        self.bolts = [b for b in self.bolts if b.alive]

    def find_nearest_enemy(self, from_pos, max_range=None):
        if not self.enemies_ref:
            return None
        nearest = None
        nearest_dist = max_range if max_range else self.AUTO_AIM_RANGE
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

    def fire_pair(self, player_node, force_active=False):
        """Tire 2 bolts simultanés depuis la paire de canons active."""
        pair = self.CANNON_PAIRS[self.pair_index]

        # Couleurs alternées
        if self.pair_index == 0:
            c_back = Vec4(1.0, 0.15, 0.0, 1)
            c_front = Vec4(1.0, 0.6, 0.35, 1)
        else:
            c_back = Vec4(1.0, 0.25, 0.0, 1)
            c_front = Vec4(1.0, 0.7, 0.4, 1)

        # Force → pas d'auto-aim (tir manuel pur)
        aim_strength = 0.0 if force_active else self.AUTO_AIM_STRENGTH
        aim_range = 0.0 if force_active else self.AUTO_AIM_RANGE

        for offset in pair:
            world_pos = self.game.render.getRelativePoint(player_node, offset)

            base_dir = Vec3(0, 1, 0)
            nearest = self.find_nearest_enemy(world_pos, max_range=aim_range)
            if nearest:
                epos = nearest.get_pos()
                if epos:
                    to_enemy = epos - world_pos
                    to_enemy.normalize()
                    aim_dir = base_dir * (1 - aim_strength) + to_enemy * aim_strength
                    aim_dir.normalize()
                    base_dir = aim_dir

            bolt = LaserBolt(self.game.render, world_pos, base_dir,
                            color_back=c_back, color_front=c_front)
            # Force → bolts plus gros et lumineux
            if force_active:
                bolt.node.setScale(1.5)
                bolt.node.setColorScale(1.5, 1.5, 1.5, 1)
            self.bolts.append(bolt)

        self.pair_index = (self.pair_index + 1) % len(self.CANNON_PAIRS)

    def get_bolts(self):
        return [b for b in self.bolts if b.alive]

    def get_heat_pct(self):
        """Retourne le % de chaleur (0.0 à 1.0)."""
        return self.heat / self.MAX_HEAT

    def is_overheated(self):
        return self.overheated

    def get_cooldown_pct(self):
        """Retourne le % de cooldown restant (1.0 = début, 0.0 = fini)."""
        if not self.overheated or self.cooldown_total <= 0:
            return 0.0
        return self.cooldown_timer / self.cooldown_total
