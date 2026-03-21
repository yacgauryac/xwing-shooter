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
import os


class AsteroidModelCache:
    """Cache de modèles d'astéroïdes extraits du pack gltf."""

    PACK_PATH = "assets/models/asteroids/scene.gltf"
    _templates = []
    _loaded = False

    @classmethod
    def load(cls, game):
        """Charge le pack et extrait chaque astéroïde individuel."""
        if cls._loaded:
            return
        cls._loaded = True

        if not os.path.exists(cls.PACK_PATH):
            print(f"[Asteroids] Pack non trouvé: {cls.PACK_PATH}, mode procédural")
            return

        try:
            model = game.loader.loadModel(cls.PACK_PATH)
            if model:
                # Structure: root → parent → 8 astéroïdes (Object_2..Object_9)
                # On descend jusqu'aux enfants qui ont des meshes
                parent = model
                # Descendre tant qu'il n'y a qu'un seul enfant (nodes conteneurs)
                while True:
                    children = parent.getChildren()
                    if len(children) == 1 and not children[0].node().isGeomNode():
                        parent = children[0]
                    else:
                        break

                children = parent.getChildren()
                for child in children:
                    template = NodePath(f"asteroid_tpl_{len(cls._templates)}")
                    child.copyTo(template)

                    # Recentre le modèle sur son propre centre
                    bounds = template.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        center = (bmin + bmax) / 2
                        # Décale tous les enfants pour centrer à l'origine
                        for c in template.getChildren():
                            c.setPos(c.getPos() - center)
                        template.setPos(0, 0, 0)

                    cls._templates.append(template)

                print(f"[Asteroids] Pack chargé: {len(cls._templates)} astéroïdes")
        except Exception as e:
            print(f"[Asteroids] Erreur chargement: {e}")

    @classmethod
    def get_random(cls):
        """Retourne un clone d'un astéroïde aléatoire du pack, ou None."""
        if not cls._templates:
            return None
        template = random.choice(cls._templates)
        return template.copyTo(NodePath("asteroid_inst"))


class Asteroid:
    """Un astéroïde individuel — sphère déformée procédurale bleu-gris."""

    COLOR_PALETTES = [
        {"base": (0.22, 0.24, 0.30), "var": 0.04},
        {"base": (0.25, 0.27, 0.33), "var": 0.05},
        {"base": (0.20, 0.22, 0.28), "var": 0.04},
        {"base": (0.28, 0.30, 0.36), "var": 0.05},
        {"base": (0.18, 0.20, 0.26), "var": 0.03},
    ]

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.size = size
        self.hit_radius = size * 0.5
        self.rot_speed = Vec3(
            random.uniform(-40, 40),
            random.uniform(-40, 40),
            random.uniform(-40, 40),
        )

        # Toujours procédural (les packs sont des amas, utilisés séparément)
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
    """Une planète fixe procédurale qui grossit lentement."""

    def __init__(self, parent, pos, size, color):
        self.alive = True
        self.initial_scale = 1.0
        self.grow_rate = 0.003  # Très lent

        self.node = self._make_sphere(size, color)
        self.node.reparentTo(parent)
        self.node.setPos(pos)
        self.node.setLightOff()

    def _make_sphere(self, radius, color):
        root = NodePath("planet")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("sphere", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        rings, sectors = 14, 18
        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)
                vertex.addData3(x, y, z)

                band = math.sin(phi * 4) * 0.08
                band2 = math.sin(phi * 7 + theta * 2) * 0.03
                c = Vec4(
                    max(0, min(1, color.getX() + band + band2)),
                    max(0, min(1, color.getY() + band * 0.5 + band2)),
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
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt):
        if not self.alive:
            return
        self.initial_scale += self.grow_rate * dt
        self.node.setScale(self.initial_scale)

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class StarDestroyerDecor:
    """Star Destroyer en arrière-plan — grossit lentement (approche)."""

    MODEL_PATH = "assets/models/star_destroyer/scene.gltf"

    def __init__(self, game, pos, scale=0.01):
        self.alive = True
        self.node = None

        if os.path.exists(self.MODEL_PATH):
            try:
                model = game.loader.loadModel(self.MODEL_PATH)
                if model:
                    self.node = model
                    self.node.reparentTo(game.render)
                    self.node.setPos(pos)
                    self.node.setScale(scale)
                    self.node.setH(90)
                    self.node.setColorScale(Vec4(1.5, 1.5, 1.8, 1))
                    self.node.setLightOff()
                    # Rendu en arrière-plan (derrière les planètes)
                    self.node.setBin("background", 10)
                    print(f"[StarDestroyer] Modèle chargé, scale={scale}")
            except Exception as e:
                print(f"[StarDestroyer] Erreur: {e}")

    def update(self, dt):
        pass


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

    ASTEROID_INTERVAL = 1.8     # Moins fréquents
    NEBULA_INTERVAL = 35.0
    DEBRIS_INTERVAL = 5.0       # Moins de débris aussi

    SPAWN_DEPTH = 200.0
    FIELD_WIDTH = 25.0
    FIELD_HEIGHT = 15.0

    def __init__(self, game):
        self.game = game

        # Charge le cache de modèles d'astéroïdes
        AsteroidModelCache.load(game)

        self.asteroids = []
        self.planets = []
        self.nebulae = []
        self.debris = []

        self.asteroid_timer = 2.0
        self.nebula_timer = 15.0
        self.debris_timer = 4.0

        # 2 planètes fixes
        self._spawn_fixed_planets()
        self.star_destroyer = None

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

        # Planètes (fixes, grossissent lentement)
        for p in self.planets:
            p.update(dt)

        # Star Destroyer en fond
        if self.star_destroyer:
            self.star_destroyer.update(dt)

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

    def _spawn_fixed_planets(self):
        """Crée 2 planètes procédurales fixes — visibles dès le départ."""
        p1 = DistantPlanet(
            self.game.render,
            Point3(-20, 150, 12),
            size=18,
            color=Vec4(0.6, 0.35, 0.2, 1),
        )
        self.planets.append(p1)

        p2 = DistantPlanet(
            self.game.render,
            Point3(25, 200, -8),
            size=12,
            color=Vec4(0.25, 0.4, 0.65, 1),
        )
        self.planets.append(p2)

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
