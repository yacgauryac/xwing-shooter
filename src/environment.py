"""
Environment — Décor spatial : astéroïdes, nébuleuses, planètes, débris.
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
    """Un astéroïde qui défile."""

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.rot_speed = Vec3(
            random.uniform(-50, 50),
            random.uniform(-50, 50),
            random.uniform(-50, 50),
        )

        self.node = self._make_rock(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)

    def _make_rock(self, size):
        """Crée un astéroïde irrégulier (icosphère déformée approximée par des boîtes)."""
        root = NodePath("asteroid")

        # Plusieurs boîtes tournées pour faire un rocher irrégulier
        color = Vec4(
            random.uniform(0.3, 0.5),
            random.uniform(0.25, 0.4),
            random.uniform(0.2, 0.35),
            1,
        )
        color_light = Vec4(
            color.getX() + 0.1,
            color.getY() + 0.1,
            color.getZ() + 0.1,
            1,
        )

        # Noyau
        core = self._make_box(size, size * 0.8, size * 0.7, color)
        core.reparentTo(root)

        # Bosses aléatoires
        for _ in range(random.randint(2, 4)):
            bump_size = size * random.uniform(0.3, 0.6)
            bump = self._make_box(bump_size, bump_size, bump_size, color_light)
            bump.reparentTo(root)
            bump.setPos(
                random.uniform(-size * 0.4, size * 0.4),
                random.uniform(-size * 0.4, size * 0.4),
                random.uniform(-size * 0.4, size * 0.4),
            )
            bump.setHpr(
                random.uniform(0, 360),
                random.uniform(0, 360),
                random.uniform(0, 360),
            )

        return root

    def _make_box(self, sx, sy, sz, color):
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
        if not self.alive:
            return

        # Défile vers le joueur
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

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class DistantPlanet:
    """Une planète lointaine en arrière-plan (très lente)."""

    def __init__(self, parent, pos, size, color):
        self.alive = True
        self.speed = 0.5  # Très lent (parallaxe)

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

        # Génère les vertices
        vertices = []
        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors

                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)

                vertex.addData3(x, y, z)

                # Variation de couleur selon la latitude (bandes)
                band = math.sin(phi * 3) * 0.1
                c = Vec4(
                    max(0, min(1, color.getX() + band)),
                    max(0, min(1, color.getY() + band * 0.5)),
                    max(0, min(1, color.getZ() - band * 0.3)),
                    1,
                )
                col.addData4(c)
                vertices.append((x, y, z))

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
        self.speed = 1.0  # Très lent (très loin)

        self.node = NodePath("nebula")
        self.node.reparentTo(parent)
        self.node.setPos(center_pos)
        self.node.setLightOff()

        # Crée un nuage de points colorés
        self._make_cloud(size, color)

    def _make_cloud(self, size, color):
        num_points = 80

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("nebula", fmt, Geom.UHStatic)
        vdata.setNumRows(num_points)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        for _ in range(num_points):
            # Distribution gaussienne pour la forme
            x = random.gauss(0, size * 0.4)
            y = random.gauss(0, size * 0.3)
            z = random.gauss(0, size * 0.4)

            vertex.addData3(x, y, z)

            # Couleur avec variation
            r = color.getX() + random.uniform(-0.1, 0.1)
            g = color.getY() + random.uniform(-0.1, 0.1)
            b = color.getZ() + random.uniform(-0.1, 0.1)
            a = random.uniform(0.05, 0.15)
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
        np.setRenderModeThickness(3)
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

    # Timers de spawn
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

        # Couleurs de planètes possibles
        self.planet_colors = [
            Vec4(0.6, 0.3, 0.2, 1),   # Mars (rouge)
            Vec4(0.2, 0.4, 0.7, 1),   # Terre (bleu)
            Vec4(0.7, 0.6, 0.3, 1),   # Désert (jaune)
            Vec4(0.3, 0.6, 0.3, 1),   # Forêt (vert)
            Vec4(0.5, 0.3, 0.6, 1),   # Gaz (violet)
            Vec4(0.7, 0.5, 0.2, 1),   # Gaz (orange)
        ]

        # Couleurs de nébuleuses
        self.nebula_colors = [
            Vec4(0.6, 0.2, 0.8, 1),   # Violet
            Vec4(0.2, 0.4, 0.9, 1),   # Bleu
            Vec4(0.8, 0.3, 0.2, 1),   # Rouge
            Vec4(0.2, 0.7, 0.5, 1),   # Turquoise
            Vec4(0.9, 0.6, 0.1, 1),   # Or
        ]

    def update(self, dt, scroll_speed):
        """Met à jour tout le décor."""
        speed_factor = scroll_speed / 20.0

        # --- Astéroïdes ---
        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed)
            self.asteroid_timer = self.ASTEROID_INTERVAL / speed_factor

        for a in self.asteroids:
            a.update(dt)
        self.asteroids = [a for a in self.asteroids if a.alive]

        # --- Planètes ---
        self.planet_timer -= dt
        if self.planet_timer <= 0:
            self._spawn_planet()
            self.planet_timer = self.PLANET_INTERVAL + random.uniform(-10, 10)

        for p in self.planets:
            p.update(dt)
        self.planets = [p for p in self.planets if p.alive]

        # --- Nébuleuses ---
        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            self._spawn_nebula()
            self.nebula_timer = self.NEBULA_INTERVAL + random.uniform(-5, 5)

        for n in self.nebulae:
            n.update(dt)
        self.nebulae = [n for n in self.nebulae if n.alive]

        # --- Débris ---
        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)

        for d in self.debris:
            d.update(dt)
        self.debris = [d for a in [self.debris] for d in a if d.alive]

    def _spawn_asteroid(self, scroll_speed):
        """Fait apparaître un astéroïde."""
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.5, 2.5)
        speed = scroll_speed * random.uniform(0.8, 1.2)

        asteroid = Asteroid(self.game.render, Point3(x, y, z), size, speed)
        self.asteroids.append(asteroid)

    def _spawn_planet(self):
        """Fait apparaître une planète lointaine."""
        x = random.uniform(-40, 40)
        z = random.uniform(-20, 20)
        y = self.SPAWN_DEPTH + random.uniform(100, 300)
        size = random.uniform(8, 25)
        color = random.choice(self.planet_colors)

        planet = DistantPlanet(self.game.render, Point3(x, y, z), size, color)
        self.planets.append(planet)

    def _spawn_nebula(self):
        """Fait apparaître une nébuleuse lointaine."""
        x = random.uniform(-60, 60)
        z = random.uniform(-40, 40)
        y = self.SPAWN_DEPTH + random.uniform(200, 500)
        color = random.choice(self.nebula_colors)
        size = random.uniform(15, 30)

        nebula = Nebula(self.game.render, Point3(x, y, z), color, size)
        self.nebulae.append(nebula)

    def _spawn_debris(self, scroll_speed):
        """Fait apparaître des débris de vaisseau (petits astéroïdes métalliques)."""
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 30)
        size = random.uniform(0.2, 0.8)
        speed = scroll_speed * random.uniform(1.0, 1.5)

        # Les débris sont juste des petits astéroïdes gris métallique
        debris = Asteroid(self.game.render, Point3(x, y, z), size, speed)
        # Override la couleur pour du métal
        debris.node.setColorScale(Vec4(0.5, 0.5, 0.6, 1))
        self.debris.append(debris)
