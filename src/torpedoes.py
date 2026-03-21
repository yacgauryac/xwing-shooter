"""
Torpilles à tête chercheuse — Proton Torpedoes.
Lock-on sur l'ennemi le plus proche du réticule, tir au clic droit.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomPoints, GeomNode,
    NodePath, TransparencyAttrib
)
import random
import math


# Paramètres
TORPEDO_SPEED_MIN = 40.0
TORPEDO_SPEED_MAX = 120.0
TORPEDO_ACCEL = 80.0       # Accélération par seconde
TORPEDO_TURN_RATE = 3.0    # Vitesse de virage (lerp vers cible)
TORPEDO_MAX_DIST = 200.0
TORPEDO_SPLASH_RADIUS = 15.0
TORPEDO_SPLASH_DAMAGE = 10  # Tue tout dans le rayon
TORPEDO_COOLDOWN = 1.0
LOCK_RANGE = 120.0         # Distance max de lock
LOCK_CONE = 8.0            # Rayon autour du réticule pour le lock


class ProtonTorpedo:
    """Un projectile à tête chercheuse."""

    def __init__(self, game, position, direction, target=None):
        self.game = game
        self.alive = True
        self.target = target
        self.speed = TORPEDO_SPEED_MIN
        self.direction = Vec3(direction)
        self.direction.normalize()
        self.distance_traveled = 0.0
        self.age = 0.0

        # Modèle procédural (cylindre + cône, bleu/blanc)
        self.node = self._make_torpedo()
        self.node.reparentTo(game.render)
        self.node.setPos(position)
        self.node.setLightOff()

        # Traînée
        self.trail_particles = []

    def _make_torpedo(self):
        """Crée le modèle de torpille — forme allongée luminescente."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("torp", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        white = Vec4(0.9, 0.95, 1.0, 1.0)
        blue = Vec4(0.4, 0.6, 1.0, 1.0)
        blue_dim = Vec4(0.3, 0.4, 0.9, 0.9)

        segs = 8
        length = 1.2
        radius = 0.15

        # Pointe avant (blanc)
        v.addData3(0, length * 0.5, 0)
        c.addData4(white)

        # Anneau avant
        for i in range(segs):
            a = i / segs * math.pi * 2
            v.addData3(math.cos(a) * radius, length * 0.2, math.sin(a) * radius)
            c.addData4(blue)

        # Anneau arrière
        for i in range(segs):
            a = i / segs * math.pi * 2
            v.addData3(math.cos(a) * radius, -length * 0.5, math.sin(a) * radius)
            c.addData4(blue_dim)

        # Pointe arrière (moteur)
        v.addData3(0, -length * 0.5, 0)
        c.addData4(Vec4(0.5, 0.7, 1.0, 1.0))

        tris = GeomTriangles(Geom.UHStatic)
        # Cône avant
        for i in range(segs):
            tris.addVertices(0, 1 + i, 1 + (i + 1) % segs)
        # Corps (anneau avant → arrière)
        for i in range(segs):
            a1 = 1 + i
            a2 = 1 + (i + 1) % segs
            b1 = 1 + segs + i
            b2 = 1 + segs + (i + 1) % segs
            tris.addVertices(a1, b1, b2)
            tris.addVertices(a1, b2, a2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("torpedo")
        node.addGeom(geom)
        np = NodePath(node)
        np.setColorScale(3.0, 3.0, 4.0, 1.0)  # Très lumineux
        return np

    def update(self, dt):
        if not self.alive:
            return

        self.age += dt

        # Accélère
        self.speed = min(TORPEDO_SPEED_MAX, self.speed + TORPEDO_ACCEL * dt)

        # Homing vers la cible
        if self.target and hasattr(self.target, 'alive') and self.target.alive:
            target_pos = self.target.get_pos()
            if target_pos:
                to_target = target_pos - self.node.getPos()
                to_target.normalize()
                # Lerp la direction vers la cible
                lerp = min(1.0, TORPEDO_TURN_RATE * dt)
                self.direction = self.direction * (1 - lerp) + to_target * lerp
                self.direction.normalize()

        # Avance
        movement = self.direction * self.speed * dt
        self.node.setPos(self.node.getPos() + movement)
        self.distance_traveled += movement.length()

        # Oriente le modèle dans la direction de vol
        self.node.lookAt(self.node.getPos() + self.direction)

        # Grosse traînée bleu-blanc
        self._spawn_trail()
        if self.speed > 60:
            self._spawn_trail()  # Double traînée à haute vitesse

        # Update traînée
        for p in self.trail_particles:
            p["life"] -= dt
            if p["life"] <= 0:
                p["node"].removeNode()
                p["alive"] = False
            else:
                alpha = p["life"] / p["max_life"]
                p["node"].setColorScale(1.5, 1.5, 2.5, alpha * 0.9)
                p["node"].setScale(0.06 * alpha + 0.02)
                p["node"].setRenderModeThickness(8.0 * alpha + 2.0)
        self.trail_particles = [p for p in self.trail_particles if p.get("alive", True)]

        # Auto-destruction
        if self.distance_traveled > TORPEDO_MAX_DIST:
            self.destroy()

    def _spawn_trail(self):
        """Spawne une particule de traînée grosse et lumineuse."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("tp", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")
        v.addData3(0, 0, 0)
        c.addData4(Vec4(0.7, 0.85, 1.0, 0.9))
        pts = GeomPoints(Geom.UHStatic)
        pts.addVertex(0)
        geom = Geom(vdata)
        geom.addPrimitive(pts)
        node = GeomNode("trail")
        node.addGeom(geom)
        np = NodePath(node)
        np.reparentTo(self.game.render)
        pos = self.node.getPos()
        np.setPos(pos.getX() + random.uniform(-0.1, 0.1),
                  pos.getY() + random.uniform(-0.1, 0.1),
                  pos.getZ() + random.uniform(-0.1, 0.1))
        np.setLightOff()
        np.setRenderModeThickness(8.0)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setColorScale(2.0, 2.0, 3.0, 0.9)

        life = random.uniform(0.3, 0.6)
        self.trail_particles.append({
            "node": np, "life": life, "max_life": life, "alive": True,
        })

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None

    def destroy(self):
        self.alive = False
        for p in self.trail_particles:
            if p.get("alive"):
                p["node"].removeNode()
        self.trail_particles = []
        if not self.node.isEmpty():
            self.node.removeNode()


class LockIndicator:
    """Losange orange qui pulse autour de l'ennemi locké."""

    def __init__(self, game):
        self.game = game
        self.node = self._make_diamond()
        self.node.reparentTo(game.render)
        self.node.hide()
        self.node.setLightOff()
        self.node.setTransparency(TransparencyAttrib.MAlpha)
        self.node.setBin("fixed", 45)
        self.node.setDepthWrite(False)
        self.node.setDepthTest(False)
        self.timer = 0.0

    def _make_diamond(self):
        """Losange/bracket autour de la cible."""
        from panda3d.core import GeomLines
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("lock", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        s = 1.2
        col = Vec4(1.0, 0.6, 0.1, 0.9)

        # 4 coins du losange (brackets)
        # Top
        v.addData3(-s*0.3, 0, s); c.addData4(col)
        v.addData3(0, 0, s*1.2); c.addData4(col)
        v.addData3(s*0.3, 0, s); c.addData4(col)
        # Right
        v.addData3(s, 0, s*0.3); c.addData4(col)
        v.addData3(s*1.2, 0, 0); c.addData4(col)
        v.addData3(s, 0, -s*0.3); c.addData4(col)
        # Bottom
        v.addData3(s*0.3, 0, -s); c.addData4(col)
        v.addData3(0, 0, -s*1.2); c.addData4(col)
        v.addData3(-s*0.3, 0, -s); c.addData4(col)
        # Left
        v.addData3(-s, 0, -s*0.3); c.addData4(col)
        v.addData3(-s*1.2, 0, 0); c.addData4(col)
        v.addData3(-s, 0, s*0.3); c.addData4(col)

        lines = GeomLines(Geom.UHStatic)
        for i in range(4):
            base = i * 3
            lines.addVertices(base, base + 1)
            lines.addVertices(base + 1, base + 2)

        geom = Geom(vdata)
        geom.addPrimitive(lines)
        node = GeomNode("lock_indicator")
        node.addGeom(geom)
        np = NodePath(node)
        np.setRenderModeThickness(2.0)
        return np

    def update(self, dt, target_pos):
        self.timer += dt
        if target_pos:
            self.node.show()
            self.node.setPos(target_pos)
            self.node.lookAt(self.game.camera)
            # Pulse
            pulse = 0.9 + 0.2 * math.sin(self.timer * 8.0)
            self.node.setScale(pulse)
            self.node.setColorScale(1, 1, 1, 0.7 + 0.3 * math.sin(self.timer * 6.0))
        else:
            self.node.hide()

    def destroy(self):
        if not self.node.isEmpty():
            self.node.removeNode()


class TorpedoSystem:
    """Gère le stock de torpilles, le lock-on et les torpilles en vol."""

    def __init__(self, game):
        self.game = game
        self.stock = 3
        self.max_stock = 9
        self.torpedoes = []
        self.cooldown = 0.0
        self.locked_target = None
        self.lock_indicator = LockIndicator(game)

    def update_lock(self, crosshair_x, crosshair_z, enemies):
        """Cherche l'ennemi le plus proche du réticule."""
        best = None
        best_dist = LOCK_CONE

        # Position 3D approximative du réticule
        reticle_pos = Point3(crosshair_x, 20 + 60, crosshair_z)

        for enemy in enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None:
                continue
            # Distance au réticule (XZ seulement)
            dx = epos.getX() - crosshair_x
            dz = epos.getZ() - crosshair_z
            dist_xz = (dx*dx + dz*dz) ** 0.5

            # Distance Y (doit être devant le joueur)
            if epos.getY() < 20:
                continue
            dist_y = epos.getY() - 20
            if dist_y > LOCK_RANGE:
                continue

            if dist_xz < best_dist:
                best_dist = dist_xz
                best = enemy

        self.locked_target = best

    def fire(self, player_pos):
        """Tire une torpille si possible."""
        if self.stock <= 0:
            return False
        if self.cooldown > 0:
            return False
        if self.locked_target is None:
            return False

        self.stock -= 1
        self.cooldown = TORPEDO_COOLDOWN

        direction = Vec3(0, 1, 0)
        target_pos = self.locked_target.get_pos()
        if target_pos:
            direction = target_pos - player_pos
            direction.normalize()

        # 2 torpilles côte à côte (comme dans les films)
        offset = 0.8
        for side in [-1, 1]:
            pos = Vec3(player_pos.getX() + side * offset,
                       player_pos.getY(),
                       player_pos.getZ())
            torpedo = ProtonTorpedo(
                self.game, pos, direction,
                target=self.locked_target
            )
            self.torpedoes.append(torpedo)
        return True

    def update(self, dt, crosshair_x, crosshair_z, enemies, locking=False):
        """Update lock-on + torpilles en vol."""
        if self.cooldown > 0:
            self.cooldown -= dt

        # Lock-on seulement si clic droit enfoncé
        if locking and self.stock > 0:
            self.update_lock(crosshair_x, crosshair_z, enemies)
        else:
            if not locking:
                self.locked_target = None

        # Lock indicator
        lock_pos = None
        if self.locked_target and self.locked_target.alive:
            lock_pos = self.locked_target.get_pos()
        self.lock_indicator.update(dt, lock_pos)

        # Update torpilles
        for torp in self.torpedoes:
            torp.update(dt)
        self.torpedoes = [t for t in self.torpedoes if t.alive]

    def check_impacts(self, enemies, explosion_manager, score_tracker):
        """Vérifie les impacts de torpilles. Retourne le score gagné."""
        total_score = 0

        for torp in self.torpedoes:
            if not torp.alive:
                continue
            torp_pos = torp.get_pos()
            if torp_pos is None:
                continue

            # Check impact direct sur la cible ou tout ennemi proche
            hit = False
            for enemy in enemies:
                if not enemy.alive:
                    continue
                epos = enemy.get_pos()
                if epos is None:
                    continue
                dist = (torp_pos - epos).length()
                if dist < 3.5:  # Impact direct
                    hit = True
                    break

            if hit:
                # Splash damage !
                impact_pos = torp_pos
                torp.destroy()

                # Grosse explosion x3
                explosion_manager.spawn(impact_pos, score=0)
                for _ in range(2):
                    offset = Vec3(random.uniform(-2, 2),
                                  random.uniform(-2, 2),
                                  random.uniform(-1, 1))
                    explosion_manager.spawn(impact_pos + offset, score=0)

                # Dégâts splash sur tous les ennemis dans le rayon
                for enemy in enemies:
                    if not enemy.alive:
                        continue
                    epos = enemy.get_pos()
                    if epos is None:
                        continue
                    dist = (impact_pos - epos).length()
                    if dist < TORPEDO_SPLASH_RADIUS:
                        destroyed = enemy.hit(TORPEDO_SPLASH_DAMAGE)
                        if destroyed:
                            total_score += enemy.SCORE_VALUE
                            score_tracker["last_kill_pos"] = Vec3(epos)
                            explosion_manager.spawn(epos, score=enemy.SCORE_VALUE)

        return total_score

    def add_stock(self, amount):
        self.stock = min(self.max_stock, self.stock + amount)

    def reset(self):
        for t in self.torpedoes:
            t.destroy()
        self.torpedoes = []
        self.stock = 3
        self.cooldown = 0.0
        self.locked_target = None
        self.lock_indicator.destroy()
        self.lock_indicator = LockIndicator(self.game)
