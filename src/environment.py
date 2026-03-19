"""
Environment — Décor spatial : astéroïdes (sphères déformées), nébuleuses, planètes, débris.
Tout défile vers le joueur pour l'effet de vitesse.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib
)
import random
import math


class Asteroid:
    """Un astéroïde procédural — sphère déformée aléatoirement."""

    # Palettes de couleurs pour les astéroïdes
    COLOR_PALETTES = [
        # Gris foncé
        {"base": (0.28, 0.27, 0.26), "var": 0.05},
        # Gris moyen
        {"base": (0.35, 0.34, 0.33), "var": 0.06},
        # Gris clair
        {"base": (0.42, 0.41, 0.39), "var": 0.05},
        # Gris bleuté
        {"base": (0.30, 0.31, 0.35), "var": 0.05},
        # Gris chaud
        {"base": (0.36, 0.34, 0.32), "var": 0.06},
    ]

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.size = size
        self.hit_radius = size * 0.5  # Hitbox pour collisions
        self.rot_speed = Vec3(
            random.uniform(-40, 40),
            random.uniform(-40, 40),
            random.uniform(-40, 40),
        )

        self.node = self._make_deformed_sphere(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)

    def _make_deformed_sphere(self, size):
        """Crée une sphère UV déformée aléatoirement — chaque astéroïde est unique."""
        root = NodePath("asteroid")

        # Choisit une palette de couleurs
        palette = random.choice(self.COLOR_PALETTES)
        base_r, base_g, base_b = palette["base"]
        color_var = palette["var"]

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("asteroid", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Résolution de la sphère (plus c'est haut, plus c'est lisse)
        rings = 8
        sectors = 10
        radius = size / 2

        # Pré-génère les déformations (noise) pour la cohérence
        # On utilise un bruit par vertex pour déformer le rayon
        deform_strength = random.uniform(0.3, 0.55)  # 30-55% — certains très cabossés
        noise_freq = random.uniform(2.0, 3.5)  # Fréquence variable

        vertices_data = []

        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors

                # Position de base sur la sphère
                nx = math.sin(phi) * math.cos(theta)
                ny = math.sin(phi) * math.sin(theta)
                nz = math.cos(phi)

                # Déformation : bruit pseudo-aléatoire basé sur la position
                # Utilise sin/cos combinés pour un bruit cohérent (pas juste du random)
                noise = (
                    math.sin(nx * noise_freq + 1.3) * 0.4 +
                    math.sin(ny * noise_freq + 2.7) * 0.3 +
                    math.cos(nz * noise_freq + 0.5) * 0.3 +
                    random.uniform(-0.15, 0.15)  # Un peu de random pur pour la rugosité
                )
                deformed_r = radius * (1.0 + noise * deform_strength)

                x = nx * deformed_r
                y = ny * deformed_r
                z = nz * deformed_r

                vertex.addData3(x, y, z)

                # Couleur avec variation par vertex
                cr = base_r + random.uniform(-color_var, color_var)
                cg = base_g + random.uniform(-color_var, color_var)
                cb = base_b + random.uniform(-color_var, color_var)

                # Les cratères (creux) sont plus sombres
                if noise < -0.1:
                    cr *= 0.7
                    cg *= 0.7
                    cb *= 0.7

                col.addData4(
                    max(0.1, min(1, cr)),
                    max(0.1, min(1, cg)),
                    max(0.1, min(1, cb)),
                    1
                )

        # Triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1

                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)

        node = GeomNode("asteroid_mesh")
        node.addGeom(geom)

        np = NodePath(node)
        np.reparentTo(root)

        return root

    def update(self, dt):
        if not self.alive:
            return

        self.node.setY(self.node.getY() - self.speed * dt)

        # Rotation lente
        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )

        if self.node.getY() < -20:
            self.destroy()

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class DistantPlanet:
    """Une planète lointaine en arrière-plan (très lente)."""

    def __init__(self, parent, pos, size, color):
        self.alive = True
        self.speed = 0.5

        self.node = self._make_sphere(size, color)
        self.node.reparentTo(parent)
        self.node.setPos(pos)
        self.node.setLightOff()

    def _make_sphere(self, radius, color):
        """Crée une vraie sphère procédurale (UV sphere)."""
        root = NodePath("planet")

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("sphere", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        rings = 12
        sectors = 16

        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors

                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)

                vertex.addData3(x, y, z)

                band = math.sin(phi * 3) * 0.1
                c = Vec4(
                    max(0, min(1, color.getX() + band)),
                    max(0, min(1, color.getY() + band * 0.5)),
                    max(0, min(1, color.getZ() - band * 0.3)),
                    1,
                )
                col.addData4(c)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("sphere")
        node.addGeom(geom)

        np = NodePath(node)
        np.reparentTo(root)
        return root

    def update(self, dt):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - self.speed * dt)
        if self.node.getY() < -50:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class Nebula:
    """Nappe de couleur en fond (points colorés semi-transparents)."""

    def __init__(self, parent, center_pos, color, size=30.0):
        self.alive = True
        self.speed = 1.0

        self.node = NodePath("nebula")
        self.node.reparentTo(parent)
        self.node.setPos(center_pos)
        self.node.setLightOff()

        self._make_cloud(size, color)

    def _make_cloud(self, size, color):
        num_points = 80

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("nebula", fmt, Geom.UHStatic)
        vdata.setNumRows(num_points)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        for _ in range(num_points):
            x = random.gauss(0, size * 0.4)
            y = random.gauss(0, size * 0.3)
            z = random.gauss(0, size * 0.4)

            vertex.addData3(x, y, z)

            r = color.getX() + random.uniform(-0.1, 0.1)
            g = color.getY() + random.uniform(-0.1, 0.1)
            b = color.getZ() + random.uniform(-0.1, 0.1)
            a = random.uniform(0.03, 0.08)
            col.addData4(max(0, r), max(0, g), max(0, b), a)

        from panda3d.core import GeomPoints
        points = GeomPoints(Geom.UHStatic)
        points.addConsecutiveVertices(0, num_points)

        geom = Geom(vdata)
        geom.addPrimitive(points)

        geom_node = GeomNode("nebula_cloud")
        geom_node.addGeom(geom)

        np = NodePath(geom_node)
        np.reparentTo(self.node)
        np.setRenderModeThickness(2)
        np.setTransparency(TransparencyAttrib.MAlpha)

    def update(self, dt):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - self.speed * dt)
        if self.node.getY() < -80:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class Environment:
    """Gère tout le décor spatial."""

    ASTEROID_INTERVAL = 0.8
    PLANET_INTERVAL = 30.0
    NEBULA_INTERVAL = 35.0
    DEBRIS_INTERVAL = 3.0

    SPAWN_DEPTH = 200.0
    FIELD_WIDTH = 25.0
    FIELD_HEIGHT = 15.0

    def __init__(self, game):
        self.game = game

        self.asteroids = []
        self.planets = []
        self.nebulae = []
        self.debris = []

        self.asteroid_timer = 2.0
        self.planet_timer = 5.0
        self.nebula_timer = 15.0
        self.debris_timer = 4.0

        self.planet_colors = [
            Vec4(0.6, 0.3, 0.2, 1),
            Vec4(0.2, 0.4, 0.7, 1),
            Vec4(0.7, 0.6, 0.3, 1),
            Vec4(0.3, 0.6, 0.3, 1),
            Vec4(0.5, 0.3, 0.6, 1),
            Vec4(0.7, 0.5, 0.2, 1),
        ]

        self.nebula_colors = [
            Vec4(0.6, 0.2, 0.8, 1),
            Vec4(0.2, 0.4, 0.9, 1),
            Vec4(0.8, 0.3, 0.2, 1),
            Vec4(0.2, 0.7, 0.5, 1),
            Vec4(0.9, 0.6, 0.1, 1),
        ]

    def update(self, dt, scroll_speed):
        """Met à jour tout le décor."""
        speed_factor = scroll_speed / 20.0

        # Astéroïdes
        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed)
            self.asteroid_timer = self.ASTEROID_INTERVAL / speed_factor

        for a in self.asteroids:
            a.update(dt)
        self.asteroids = [a for a in self.asteroids if a.alive]

        # Planètes
        self.planet_timer -= dt
        if self.planet_timer <= 0:
            self._spawn_planet()
            self.planet_timer = self.PLANET_INTERVAL + random.uniform(-10, 10)

        for p in self.planets:
            p.update(dt)
        self.planets = [p for p in self.planets if p.alive]

        # Nébuleuses
        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            self._spawn_nebula()
            self.nebula_timer = self.NEBULA_INTERVAL + random.uniform(-5, 5)

        for n in self.nebulae:
            n.update(dt)
        self.nebulae = [n for n in self.nebulae if n.alive]

        # Débris
        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)

        for d in self.debris:
            d.update(dt)
        self.debris = [d for d in self.debris if d.alive]

    def check_player_collision(self, player_pos):
        """Vérifie si le joueur percute un astéroïde. Retourne les dégâts."""
        damage = 0
        for asteroid in self.asteroids:
            if not asteroid.alive:
                continue
            apos = asteroid.get_pos()
            if apos is None:
                continue

            dist = (apos - player_pos).length()
            if dist < asteroid.hit_radius + 1.0:  # 1.0 = rayon approximatif du joueur
                damage += 2  # Un astéroïde fait mal !
                asteroid.destroy()

        for debris in self.debris:
            if not debris.alive:
                continue
            dpos = debris.get_pos()
            if dpos is None:
                continue

            dist = (dpos - player_pos).length()
            if dist < debris.hit_radius + 0.8:
                damage += 1
                debris.destroy()

        return damage

    def _spawn_asteroid(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.8, 3.0)
        speed = scroll_speed * random.uniform(0.8, 1.2)

        asteroid = Asteroid(self.game.render, Point3(x, y, z), size, speed)
        self.asteroids.append(asteroid)

    def _spawn_planet(self):
        x = random.uniform(-40, 40)
        z = random.uniform(-20, 20)
        y = self.SPAWN_DEPTH + random.uniform(100, 300)
        size = random.uniform(8, 25)
        color = random.choice(self.planet_colors)

        planet = DistantPlanet(self.game.render, Point3(x, y, z), size, color)
        self.planets.append(planet)

    def _spawn_nebula(self):
        x = random.uniform(-60, 60)
        z = random.uniform(-40, 40)
        y = self.SPAWN_DEPTH + random.uniform(200, 500)
        color = random.choice(self.nebula_colors)
        size = random.uniform(15, 30)

        nebula = Nebula(self.game.render, Point3(x, y, z), color, size)
        self.nebulae.append(nebula)

    def _spawn_debris(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 30)
        size = random.uniform(0.2, 0.6)
        speed = scroll_speed * random.uniform(1.0, 1.5)

        debris = Asteroid(self.game.render, Point3(x, y, z), size, speed)
        self.debris.append(debris)
