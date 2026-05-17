"""
Environment — Décor spatial : astéroïdes (sphères déformées), nébuleuses, planètes, débris.
Tout défile vers le joueur pour l'effet de vitesse.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexArrayFormat, GeomEnums,
    GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, TransparencyAttrib,
    Fog, Texture, TextureStage, PNMImage,
    AmbientLight, PointLight, Spotlight,
    PerspectiveLens,
)
import random
import math
import os
from src.lunar_base import LunarBaseGroup, LunarBorderMountain, LunarRoad
from src.settings import LUNAR


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
        # HP proportionnel à la taille : petit~1, moyen~3, grand~5
        self.max_hp = max(1, round(size * 1.8))
        self.hp = self.max_hp
        self._hit_flash = 0.0   # timer flash blanc au hit
        self.rot_speed = Vec3(
            random.uniform(-40, 40),
            random.uniform(-40, 40),
            random.uniform(-40, 40),
        )

        # Toujours procédural (les packs sont des amas, utilisés séparément)
        self.node = self._make_deformed_sphere(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)
        self.node.setTransparency(TransparencyAttrib.MAlpha)

        # ── AmbientLight jaune — glow uniforme sur toute la surface ──
        self._glow    = AmbientLight("ast_glow")
        self._glow.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
        self._glow_np = parent.attachNewNode(self._glow)
        self.node.setLight(self._glow_np)

        # ── Spotlight directionnel — vient du côté joueur ──
        self._spot    = Spotlight("ast_spot")
        self._spot.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
        lens = PerspectiveLens()
        lens.setFov(55)
        self._spot.setLens(lens)
        self._spot_np = parent.attachNewNode(self._spot)
        self.node.setLight(self._spot_np)

        # ── PointLight halo — collé à la surface côté joueur ──
        self._halo    = PointLight("ast_halo")
        self._halo.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
        self._halo_np = parent.attachNewNode(self._halo)
        self.node.setLight(self._halo_np)

        self._danger_active = False
        self._danger_timer  = 0.0
        self._player_pos    = None
        self._fade_age      = 0.0
        self._fade_duration = 1.2   # fade-in alpha sur 1.2s

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

    def set_danger_light(self, active, player_pos=None):
        """Active/désactive les lumières danger. player_pos mis à jour chaque frame."""
        self._danger_active = active
        self._player_pos    = player_pos
        if not active:
            self._glow.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
            self._spot.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
            self._halo.setColor(Vec4(0.0, 0.0, 0.0, 1.0))

    def update(self, dt, player_y=0.0):
        if not self.alive:
            return

        self.node.setY(self.node.getY() - self.speed * dt)

        # Fade-in au spawn
        if self._fade_age < self._fade_duration:
            self._fade_age += dt

        # Flash blanc au hit
        if self._hit_flash > 0:
            self._hit_flash -= dt
            hp_ratio = self.hp / self.max_hp
            self.node.setColorScale(2.0, 1.2 + hp_ratio * 0.8, 1.0, 1.0)
        else:
            # Alpha = min(fade_in, fade_behind)
            fade_in = min(1.0, self._fade_age / self._fade_duration)
            behind = player_y - self.node.getY()
            if behind > -2.0:
                fade_behind = max(0.0, 1.0 - (behind + 2.0) / 9.0)
            else:
                fade_behind = 1.0
            alpha = min(fade_in, fade_behind)
            self.node.setColorScale(1, 1, 1, alpha)

        # Rotation lente
        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )

        # Lumières danger — intensité proportionnelle à la proximité
        if self._danger_active and self._player_pos is not None:
            self._danger_timer += dt

            ax = self.node.getX()
            ay = self.node.getY()
            az = self.node.getZ()
            dx = self._player_pos.getX() - ax
            dy = self._player_pos.getY() - ay
            dz = self._player_pos.getZ() - az
            length = math.sqrt(dx*dx + dy*dy + dz*dz)

            if length > 0.01:
                nx, ny, nz = dx/length, dy/length, dz/length
                SPOT_DIST = 8.0
                self._spot_np.setPos(ax + nx * SPOT_DIST,
                                     ay + ny * SPOT_DIST,
                                     az + nz * SPOT_DIST)
                self._spot_np.lookAt(self.node)
                HALO_DIST = self.hit_radius * 1.05
                self._halo_np.setPos(ax + nx * HALO_DIST,
                                     ay + ny * HALO_DIST,
                                     az + nz * HALO_DIST)

            # Intensité : max quand l'astéroïde est juste devant, 0 quand derrière
            raw_dy = ay - self._player_pos.getY()
            proximity = max(0.0, 1.0 - raw_dy / 120.0)
            # AmbientLight — couleur viseur (-20%)
            g = proximity * 0.51
            self._glow.setColor(Vec4(g * 0.95, g * 0.82, g * 0.18, 1.0))
            # Spotlight teinté chaud (-20%)
            spot_i = proximity * 0.51
            self._spot.setColor(Vec4(spot_i * 0.95, spot_i * 0.82, spot_i * 0.18, 1.0))
            # PointLight halo orange (-20%)
            halo_i = proximity * 1.28
            self._halo.setColor(Vec4(halo_i * 0.9, halo_i * 0.55, halo_i * 0.05, 1.0))

        elif not self._danger_active:
            # Extinction progressive
            if self._danger_timer > 0:
                self._danger_timer = max(0.0, self._danger_timer - dt * 4.0)
                g = self._danger_timer * 0.179
                self._glow.setColor(Vec4(g * 0.95, g * 0.82, g * 0.18, 1.0))
                f = self._danger_timer * 0.224
                self._spot.setColor(Vec4(f * 0.95, f * 0.82, f * 0.18, 1.0))
                self._halo.setColor(Vec4(f * 0.9, f * 0.55, f * 0.05, 1.0))

        if self.node.getY() < -20:
            self.destroy()

    def hit(self):
        """Reçoit un tir laser. Retourne True si détruit, False si encore vivant."""
        if not self.alive:
            return False
        self.hp -= 1
        self._hit_flash = 0.12   # flash blanc 120 ms
        if self.hp <= 0:
            self.destroy()
            return True
        return False

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.clearLight(self._glow_np)
            self.node.clearLight(self._spot_np)
            self.node.clearLight(self._halo_np)
            self.node.removeNode()
        if not self._glow_np.isEmpty():
            self._glow_np.removeNode()
        if not self._spot_np.isEmpty():
            self._spot_np.removeNode()
        if not self._halo_np.isEmpty():
            self._halo_np.removeNode()


class DistantPlanet:
    """Une planète fixe procédurale qui grossit lentement."""

    def __init__(self, parent, pos, size, color):
        self.alive = True
        self.initial_scale = 1.0
        self.grow_rate = 0.003  # Très lent
        self._fade_age      = 0.0
        self._fade_duration = 1.2

        self.node = self._make_sphere(size, color)
        self.node.reparentTo(parent)
        self.node.setPos(pos)
        self.node.setLightOff()
        self.node.setTransparency(TransparencyAttrib.MAlpha)
        self.node.setColorScale(1, 1, 1, 0)

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
        if self._fade_age < self._fade_duration:
            self._fade_age += dt
            self.node.setColorScale(1, 1, 1, self._fade_age / self._fade_duration)

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
        self._fade_age      = 0.0
        self._fade_duration = 1.2

        self.node = NodePath("nebula")
        self.node.reparentTo(parent)
        self.node.setPos(center_pos)
        self.node.setLightOff()
        self.node.setTransparency(TransparencyAttrib.MAlpha)
        self.node.setColorScale(1, 1, 1, 0)

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
        if self._fade_age < self._fade_duration:
            self._fade_age += dt
            self.node.setColorScale(1, 1, 1, self._fade_age / self._fade_duration)
        if self.node.getY() < -80:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# Fog mobile — nappes de brouillard qui dérivent vers le joueur
# ============================================================

class FogLayer:
    """Nappe de brouillard : N quads billboard alpha-blendés qui dérivent en Y."""

    def __init__(self, parent, color, alpha, altitude_z, spread_x, count, speed_y):
        """
        color     : Vec3(r, g, b)
        alpha     : opacité max (0.0–0.6)
        altitude_z: hauteur Z de la nappe
        spread_x  : demi-largeur en X
        count     : nombre de quads dans la nappe
        speed_y   : vitesse de dérive vers le joueur (u/s)
        """
        self.alive = True
        self.color = color
        self.alpha = alpha
        self.altitude_z = altitude_z
        self.spread_x = spread_x
        self.speed_y = speed_y
        self.parent = parent

        self.quads = []  # liste de NodePath
        self._quad_data = []  # (offset_x, size, phase) pour chaque quad

        # On initialise les quads répartis le long de Y [spawn_y - 30 .. spawn_y + 250]
        for i in range(count):
            offset_y = random.uniform(0, 280)
            self._create_quad(offset_y)

    # ----------------------------------------------------------

    def _make_quad_geom(self, size):
        """Crée un quad centré à l'origine, dans le plan XZ (horizontal)."""
        hw = size / 2.0
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("fog_quad", fmt, Geom.UHDynamic)
        vdata.setNumRows(4)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        r, g, b = self.color.getX(), self.color.getY(), self.color.getZ()
        # Dégradé centre→bord : alpha plein au centre, 0 aux coins
        # Coin ordre: centre-bas-gauche, bas-droite, haut-droite, haut-gauche
        corners = [(-hw, 0, -hw), (hw, 0, -hw), (hw, 0, hw), (-hw, 0, hw)]
        for cx, cy, cz in corners:
            vertex.addData3(cx, cy, cz)
            # Distance normalisée au centre (0..1)
            dist = math.sqrt((cx / hw) ** 2 + (cz / hw) ** 2) / math.sqrt(2.0)
            a = self.alpha * max(0.0, 1.0 - dist)
            col.addData4(r, g, b, a)

        tris = GeomTriangles(Geom.UHStatic)
        # Deux triangles (0-1-2) et (0-2-3)
        tris.addVertices(0, 1, 2)
        tris.addVertices(0, 2, 3)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode("fog_quad_node")
        gnode.addGeom(geom)
        return gnode

    def _create_quad(self, initial_y):
        size = random.uniform(4.0, 10.0)
        ox = random.uniform(-self.spread_x, self.spread_x)
        phase = random.uniform(0, math.pi * 2)  # petite oscillation latérale

        gnode = self._make_quad_geom(size)
        np = NodePath(gnode)
        np.reparentTo(self.parent)
        np.setPos(ox, initial_y, self.altitude_z + random.uniform(-0.5, 0.5))
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setLightOff()
        # Billboard axe Z : le quad reste horizontal mais tourne face caméra en Z
        np.setBillboardAxis()
        # Rendu après les objets opaques
        np.setBin("transparent", 50)

        self.quads.append(np)
        self._quad_data.append({"ox": ox, "size": size, "phase": phase, "t": phase})

    def update(self, dt, player_pos):
        if not self.alive:
            return
        player_y = player_pos.getY() if hasattr(player_pos, 'getY') else float(player_pos)
        recycle_threshold = player_y - 30.0
        respawn_y = player_y + 250.0

        for i, np in enumerate(self.quads):
            if np.isEmpty():
                continue
            data = self._quad_data[i]
            # Avancer vers le joueur
            new_y = np.getY() - self.speed_y * dt
            # Légère oscillation latérale
            data["t"] += dt * 0.3
            ox_drift = data["ox"] + math.sin(data["t"]) * 1.5
            np.setPos(ox_drift, new_y, np.getZ())

            # Recyclage
            if new_y < recycle_threshold:
                ox_new = random.uniform(-self.spread_x, self.spread_x)
                data["ox"] = ox_new
                data["t"] = random.uniform(0, math.pi * 2)
                np.setPos(ox_new, respawn_y + random.uniform(0, 30), self.altitude_z + random.uniform(-0.5, 0.5))

    def destroy(self):
        self.alive = False
        for np in self.quads:
            if not np.isEmpty():
                np.removeNode()
        self.quads.clear()
        self._quad_data.clear()


# ============================================================
# L2 — Surface lunaire
# ============================================================

class LunarTerrain:
    """Dalle de terrain lunaire — plan horizontal défilant à Z=-7.8."""

    GROUND_Z = -7.8

    def __init__(self, parent, x_center, y_pos, width=240.0, depth=22.0):
        self.alive = True
        self._depth = depth
        self.node = self._make_tile(width, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_center, y_pos, self.GROUND_Z)
        self.node.setLightOff()   # Pas de lumière scène — couleurs vertex brutes

    # Rayon de courbure planétaire (plus grand = plus plat)
    # À x=±120 (width=240) : chute = 120²/(2×420) ≈ 17u → horizon bien visible
    SPHERE_R = 420.0

    def _make_tile(self, w, d):
        root = NodePath("lunar_tile")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("tile", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Densité réduite sur X (w grand) pour rester performant
        segs_x = max(16, int(w / 8))
        segs_y = max(8, int(d / 2))
        R = self.SPHERE_R

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y

                # ── Courbure sphérique (approximation parabolique) ──────────
                # z = -(x²+y²)/(2R) → centre haut, bords courbés vers le bas
                # Déterministe aux bords → joints seamless entre dalles
                sphere_z = -(x * x + y * y) / (2.0 * R)

                # Déformation de cratères uniquement à l'intérieur
                edge = (j == 0 or j == segs_y)
                bump = 0.0 if edge else random.uniform(-0.35, 0.35)
                z = sphere_z + bump

                vertex.addData3(x, y, z)

                # Gris lunaire — légèrement bleuté, pas de rouge
                g = 0.30 + random.uniform(-0.05, 0.07)
                # Zones creuses (cratères) plus sombres
                dark = 0.72 if bump < -0.18 else (0.88 if bump < 0 else 1.0)
                col.addData4(g * 0.93 * dark, g * 0.95 * dark, g * dark, 1.0)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("lunar_tile_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)

        # ── Quadrillage de couloirs ────────────────────────────────────────────
        # Lignes longitudinales (Y) = limites de couloirs, tous les 4u en X
        # Lignes transversales (X)  = repères de distance, tous les 4u en Y
        CORRIDOR_W = 4.0
        BOUNDS_X   = 14.0
        c_lane  = Vec4(0.50, 0.44, 0.24, 0.55)   # orange chaud — limites couloirs
        c_cross = Vec4(0.32, 0.30, 0.20, 0.30)   # gris-brun discret — repères Y

        vd2 = GeomVertexData("grid", GeomVertexFormat.getV3c4(), Geom.UHStatic)
        vw2 = GeomVertexWriter(vd2, "vertex")
        cw2 = GeomVertexWriter(vd2, "color")
        lns = GeomLines(Geom.UHStatic)
        gi  = [0]

        def gline(x0, y0, z0, x1, y1, z1, col):
            vw2.addData3(x0, y0, z0); cw2.addData4(col)
            vw2.addData3(x1, y1, z1); cw2.addData4(col)
            lns.addVertices(gi[0], gi[0]+1); gi[0] += 2

        # Limites longitudinales
        nx = int(BOUNDS_X / CORRIDOR_W)
        for i in range(-nx, nx+1):
            x = i * CORRIDOR_W
            if abs(x) > BOUNDS_X + 0.1:
                continue
            gz = -(x*x) / (2.0 * self.SPHERE_R) + 0.06
            gline(x, -d/2, gz, x, d/2, gz, c_lane)

        # Repères transversaux (grille complète)
        y = -d / 2
        while y <= d / 2 + 0.01:
            for i in range(-nx, nx):
                x0 = i * CORRIDOR_W
                x1 = (i+1) * CORRIDOR_W
                gz0 = -(x0*x0) / (2.0 * self.SPHERE_R) + 0.06
                gz1 = -(x1*x1) / (2.0 * self.SPHERE_R) + 0.06
                gz  = (gz0 + gz1) / 2
                gline(x0, y, gz, x1, y, gz, c_cross)
            y += CORRIDOR_W

        geom2 = Geom(vd2); geom2.addPrimitive(lns)
        gn2   = GeomNode("corridor_grid"); gn2.addGeom(geom2)
        grid_np = NodePath(gn2)
        grid_np.reparentTo(root)
        grid_np.setRenderModeThickness(1.2)
        grid_np.setTransparency(TransparencyAttrib.MAlpha)
        grid_np.setLightOff()
        grid_np.setDepthWrite(False)

        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -45:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class LunarRock:
    """Rocher lunaire procédural — plus plat et gris que les astéroïdes classiques."""

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.size = size
        self.hit_radius = size * 0.45
        self.rot_speed = Vec3(
            random.uniform(-20, 20),
            random.uniform(-20, 20),
            random.uniform(-15, 15),
        )
        self.node = self._make_rock(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)

    def _make_rock(self, size):
        root = NodePath("lunar_rock")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("rock", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        rings, sectors = 6, 8
        radius = size / 2
        deform = random.uniform(0.25, 0.50)
        freq = random.uniform(1.5, 2.8)
        flat = random.uniform(0.55, 0.75)   # Aplati verticalement (style rocher)

        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors
                nx = math.sin(phi) * math.cos(theta)
                ny = math.sin(phi) * math.sin(theta)
                nz = math.cos(phi)
                noise = (
                    math.sin(nx * freq + 1.1) * 0.4 +
                    math.sin(ny * freq + 2.3) * 0.3 +
                    math.cos(nz * freq + 0.8) * 0.3 +
                    random.uniform(-0.1, 0.1)
                )
                r = radius * (1.0 + noise * deform)
                vertex.addData3(nx * r, ny * r, nz * r * flat)
                g = 0.28 + random.uniform(-0.05, 0.07)
                # Gris lunaire légèrement bleuté
                col.addData4(g * 0.96, g * 0.97, g, 1.0)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("rock_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - self.speed * dt)
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


# ============================================================
# L3 — Tranchée
# ============================================================

# ── Format vertex custom : position + color + UV ──────────────────────────────
def _make_v3c4t2():
    """Crée (une fois) un GeomVertexFormat avec position, couleur RGBA et UV."""
    arr = GeomVertexArrayFormat()
    arr.addColumn("vertex",   3, GeomEnums.NT_float32, GeomEnums.C_point)
    arr.addColumn("color",    4, GeomEnums.NT_float32, GeomEnums.C_color)
    arr.addColumn("texcoord", 2, GeomEnums.NT_float32, GeomEnums.C_texcoord)
    fmt = GeomVertexFormat()
    fmt.addArray(arr)
    return GeomVertexFormat.registerFormat(fmt)

_V3C4T2 = _make_v3c4t2()


def _draw_wall_tex(img, size):
    """Texture mur Death Star structurée en registres horizontaux.

    Pattern harmonieux (non-aléatoire dans sa structure globale) :
      - Registre A (haut, ~20%) : panneaux lisses clairs — zone propre
      - Registre B (~30%) : zone de détail circuit (traces + pads)
      - Registre C (~20%) : panneaux lisses — zone propre
      - Registre D (~30%) : autre zone de détail circuit
      - Joints horizontaux épais entre registres (marque la structure)

    À l'intérieur des registres de détail : variation par colonne
    (colonnes larges avec ou sans circuit → rythme vertical cohérent).
    """
    rng  = random.Random(42)
    buf  = [[0.0] * size for _ in range(size)]

    # ── Découpage en registres horizontaux ────────────────────
    # Y = 0 en haut, Y = size-1 en bas dans PNMImage
    reg_cuts = [0,
                int(size * 0.20),   # fin registre A (propre)
                int(size * 0.50),   # fin registre B (circuit)
                int(size * 0.70),   # fin registre C (propre)
                size]               # fin registre D (circuit)
    reg_types = ['clean', 'circuit', 'clean', 'circuit']

    # Colonnes : alterner "détail" / "propre" sur ~150px de largeur
    col_w = rng.randint(90, 160)
    col_pattern = []   # list of (x_start, x_end, has_detail)
    cx = 0
    detail = True
    while cx < size:
        w = rng.randint(80, 160)
        col_pattern.append((cx, min(cx + w, size), detail))
        detail = not detail
        cx += w

    for ri, (y0, y1) in enumerate(zip(reg_cuts, reg_cuts[1:])):
        rtype = reg_types[ri]
        # Valeur de base du registre
        if rtype == 'clean':
            base = 0.62 + rng.uniform(-0.04, 0.04)
        else:
            base = 0.34 + rng.uniform(-0.03, 0.03)

        for py in range(y0, y1):
            for px in range(size):
                # Trouver la colonne
                has_detail = False
                for (cx0, cx1, det) in col_pattern:
                    if cx0 <= px < cx1:
                        has_detail = det
                        break

                if rtype == 'clean' or not has_detail:
                    g = base
                else:
                    # Zone de circuit : variation par sous-panneau
                    sp_x = (px // 48)
                    sp_y = (py // 48)
                    sv = math.sin(sp_x * 1.73 + sp_y * 2.31) * 0.06
                    g = 0.38 + sv
                buf[py][px] = g

    # Joints horizontaux entre registres (5px, sombres)
    for cut in reg_cuts[1:-1]:
        for j in range(5):
            yj = min(cut + j - 2, size - 1)
            if 0 <= yj < size:
                for px in range(size):
                    buf[yj][px] = 0.15

    # Joints verticaux entre colonnes (3px)
    for (cx0, cx1, _) in col_pattern:
        for j in range(3):
            xj = min(cx1 + j - 1, size - 1)
            if 0 <= xj < size:
                for py in range(size):
                    buf[py][xj] = min(buf[py][xj], 0.20)

    # ── Traces PCB uniquement dans les zones "circuit" + colonne "détail" ─
    rng2 = random.Random(77)
    for ri, (y0, y1) in enumerate(zip(reg_cuts, reg_cuts[1:])):
        if reg_types[ri] != 'circuit':
            continue
        for (cx0, cx1, has_detail) in col_pattern:
            if not has_detail:
                continue
            # 2-4 traces H dans cette cellule
            n_h = rng2.randint(2, 4)
            for _ in range(n_h):
                ty  = rng2.randint(y0 + 4, y1 - 4)
                tx0 = cx0 + rng2.randint(0, (cx1 - cx0) // 4)
                tx1 = cx1 - rng2.randint(0, (cx1 - cx0) // 4)
                tw  = rng2.randint(2, 4)
                br  = 0.70 * rng2.uniform(0.9, 1.1)
                for px in range(tx0, tx1):
                    for dy in range(-tw // 2, tw // 2 + 1):
                        py = ty + dy
                        if y0 <= py < y1 and cx0 <= px < cx1:
                            buf[py][px] = max(buf[py][px], br)
            # 1-2 traces V
            n_v = rng2.randint(1, 2)
            for _ in range(n_v):
                tx  = rng2.randint(cx0 + 4, cx1 - 4)
                ty0b = y0 + rng2.randint(0, (y1 - y0) // 4)
                ty1b = y1 - rng2.randint(0, (y1 - y0) // 4)
                tw   = rng2.randint(2, 3)
                br   = 0.65 * rng2.uniform(0.9, 1.05)
                for py in range(ty0b, ty1b):
                    for dx in range(-tw // 2, tw // 2 + 1):
                        px = tx + dx
                        if y0 <= py < y1 and cx0 <= px < cx1:
                            buf[py][px] = max(buf[py][px], br)
            # Pads
            n_pads = rng2.randint(1, 3)
            for _ in range(n_pads):
                cy2 = rng2.randint(y0 + 6, y1 - 6)
                cx2 = rng2.randint(cx0 + 6, cx1 - 6)
                r   = rng2.randint(4, 8)
                br  = min(1.0, 0.75 * rng2.uniform(1.0, 1.2))
                for py in range(cy2 - r, cy2 + r + 1):
                    for px in range(cx2 - r, cx2 + r + 1):
                        if (px - cx2)**2 + (py - cy2)**2 <= r*r:
                            if y0 <= py < y1 and cx0 <= px < cx1:
                                buf[py][px] = br

    # ── Écriture finale ────────────────────────────────────────
    nrng = random.Random(13)
    for py in range(size):
        for px in range(size):
            g = max(0.0, min(1.0, buf[py][px] + nrng.uniform(-0.008, 0.008)))
            img.setXelA(px, py, g * 1.02, g, g * 0.95, 1.0)


def _draw_circuit_tex(img, size, rng, base_g, trace_g, panel_g):
    """Texture circuit Death Star lisible en mouvement.

    Principes anti-moiré :
    - Grandes zones propres (panneaux sans traces) — ~40% de la surface
    - Peu de traces (8-12 H, 6-9 V) mais épaisses (3-6px)
    - UV scale élevée → chaque tuile couvre ~6u monde (grand = moins de répétition)
    - Pads larges (r 5-10px) bien visibles
    """
    buf = [[base_g] * size for _ in range(size)]

    # ── Grandes plaques irrégulières ───────────────────────────
    # Deux niveaux : grandes zones (~25% propres) puis subdivisions
    zone_sizes = [96, 128, 160]
    x = 0
    while x < size:
        pw = rng.choice(zone_sizes)
        y  = 0
        while y < size:
            ph  = rng.choice(zone_sizes)
            pv  = rng.uniform(-0.05, 0.07)
            # ~35% des grandes zones sont "propres" (pas de traces dessus)
            clean = rng.random() < 0.35
            for py in range(y, min(y + ph, size)):
                for px in range(x, min(x + pw, size)):
                    buf[py][px] = (panel_g + pv, 'clean' if clean else panel_g + pv)[0]
                    if clean:
                        # Marquer propre avec valeur légèrement différente
                        buf[py][px] = panel_g * 0.82 + pv * 0.5
            # Joint épais (4px) entre grandes plaques
            for j in range(4):
                jy = min(y + ph + j, size - 1)
                for px2 in range(x, min(x + pw, size)):
                    buf[jy][px2] = base_g * 0.55
            y += ph
        for j in range(4):
            jx = min(x + pw + j, size - 1)
            for py2 in range(size):
                buf[py2][jx] = base_g * 0.55
        x += pw

    # Identifier les zones propres pour éviter les traces dessus
    clean_mask = [[buf[py][px] < panel_g * 0.85 + 0.01 for px in range(size)]
                  for py in range(size)]

    # ── Traces horizontales (peu, épaisses) ────────────────────
    n_h = rng.randint(8, 12)
    for _ in range(n_h):
        ty  = rng.randint(10, size - 10)
        tx0 = rng.randint(0, size // 4)
        tx1 = rng.randint(3 * size // 4, size - 1)
        tw  = rng.randint(3, 6)
        brightness = trace_g * rng.uniform(0.90, 1.10)
        for px in range(tx0, tx1):
            for dy in range(-tw // 2, tw // 2 + 1):
                py = ty + dy
                if 0 <= py < size and not clean_mask[py][px]:
                    buf[py][px] = max(buf[py][px], brightness)

    # ── Traces verticales (peu, épaisses) ─────────────────────
    n_v = rng.randint(6, 9)
    for _ in range(n_v):
        tx  = rng.randint(10, size - 10)
        ty0 = rng.randint(0, size // 4)
        ty1 = rng.randint(3 * size // 4, size - 1)
        tw  = rng.randint(3, 5)
        brightness = trace_g * rng.uniform(0.85, 1.05)
        for py in range(ty0, ty1):
            for dx in range(-tw // 2, tw // 2 + 1):
                px = tx + dx
                if 0 <= px < size and not clean_mask[py][px]:
                    buf[py][px] = max(buf[py][px], brightness)

    # ── Pads larges aux intersections ─────────────────────────
    n_pads = rng.randint(8, 16)
    for _ in range(n_pads):
        cx = rng.randint(15, size - 15)
        cy = rng.randint(15, size - 15)
        if clean_mask[cy][cx]:
            continue
        r  = rng.randint(5, 10)
        brightness = min(1.0, trace_g * rng.uniform(1.05, 1.25))
        for py in range(cy - r, cy + r + 1):
            for px in range(cx - r, cx + r + 1):
                if 0 <= px < size and 0 <= py < size:
                    if (px - cx) ** 2 + (py - cy) ** 2 <= r * r:
                        buf[py][px] = brightness

    # ── Écriture dans PNMImage ─────────────────────────────────
    noise_rng = random.Random(rng.randint(0, 99999))
    for py in range(size):
        for px in range(size):
            g = buf[py][px] + noise_rng.uniform(-0.010, 0.010)
            g = max(0.0, min(1.0, g))
            img.setXelA(px, py, g * 1.02, g, g * 0.94, 1.0)


def _gen_trench_wall_tex(size=512):
    """Texture mur Death Star structurée en registres harmonieux."""
    img = PNMImage(size, size)
    img.makeRgb()
    _draw_wall_tex(img, size)
    tex = Texture("trench_wall")
    tex.load(img)
    tex.setWrapU(Texture.WM_repeat)
    tex.setWrapV(Texture.WM_repeat)
    tex.setMagfilter(Texture.FT_linear)
    tex.setMinfilter(Texture.FT_linear_mipmap_linear)
    tex.generateRamMipmapImages()
    return tex


def _gen_trench_floor_tex(size=512):
    """Texture circuit imprimé plus sombre pour le sol."""
    img = PNMImage(size, size)
    img.makeRgb()
    rng = random.Random(99)
    _draw_circuit_tex(img, size, rng,
                      base_g=0.10,
                      trace_g=0.55,
                      panel_g=0.22)
    tex = Texture("trench_floor")
    tex.load(img)
    tex.setWrapU(Texture.WM_repeat)
    tex.setWrapV(Texture.WM_repeat)
    tex.setMagfilter(Texture.FT_linear)
    tex.setMinfilter(Texture.FT_linear_mipmap_linear)
    tex.generateRamMipmapImages()
    return tex


# Cache module-level — générés une fois, réutilisés par toutes les dalles
_TRENCH_WALL_TEX  = None   # régénéré au prochain démarrage
_TRENCH_FLOOR_TEX = None


def _get_wall_tex():
    global _TRENCH_WALL_TEX
    if _TRENCH_WALL_TEX is None:
        _TRENCH_WALL_TEX = _gen_trench_wall_tex()
    return _TRENCH_WALL_TEX


def _get_floor_tex():
    global _TRENCH_FLOOR_TEX
    if _TRENCH_FLOOR_TEX is None:
        _TRENCH_FLOOR_TEX = _gen_trench_floor_tex()
    return _TRENCH_FLOOR_TEX


# TextureStage partagé (mode Modulate — multiplie texture × vertex color)
_TS_MODULATE = TextureStage("modulate")
_TS_MODULATE.setMode(TextureStage.M_modulate)


class TrenchWallPanel:
    """Panneau de mur latéral de tranchée — défile en Y, fixe en X."""

    WALL_X_LEFT  = -13.5
    WALL_X_RIGHT =  13.5

    # Panneaux vertex-color : joints fins + gradient Z (haut clair, bas sombre)
    PANEL_SIZE = 3.0   # taille d'un panneau en unités monde
    SEAM_W     = 0.06  # épaisseur du joint (fraction de l'unité)

    def __init__(self, parent, x_side, y_pos, height=16.0, depth=22.0, lit=True):
        self.alive = True
        self.is_right = (x_side > 0)
        self.lit = lit
        # Offset UV unique par segment — brise la répétition visuelle
        self.uv_offset_y = (y_pos * 0.137) % 1.0
        self.uv_offset_z = (y_pos * 0.073 + abs(x_side) * 0.031) % 1.0
        self.node = self._make_wall(height, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_side, y_pos, 0)
        self.node.setLightOff()

    def _wall_color(self, z, h):
        """Couleur vertex × texture = pixel final (M_modulate).
        Lit  : 0.80 (bas) → 1.30 (haut) → texture 0.62 × 1.30 ≈ 0.80 gris clair
        Dark : 0.12 (bas) → 0.30 (haut) → texture 0.62 × 0.30 ≈ 0.19 gris très sombre
        """
        t = (z + h / 2) / h
        if self.lit:
            g = 0.80 + 0.50 * t    # max ~1.30, clampé par Panda → ~0.78 gris doux
        else:
            g = 0.12 + 0.18 * t    # 0.12→0.30, très sombre côté ombre
        return Vec4(g * 1.02, g, g * 0.96, 1.0)

    def _make_wall(self, h, d):
        root = NodePath("trench_wall")
        vdata = GeomVertexData("wall", _V3C4T2, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        tw = GeomVertexWriter(vdata, "texcoord")

        segs_z = max(4, int(h))
        segs_y = max(4, int(d))
        uv_scale = 1.0 / 6.0

        for i in range(segs_z + 1):
            for j in range(segs_y + 1):
                y = -d / 2 + j * d / segs_y
                z = -h / 2 + i * h / segs_z
                vw.addData3(0, y, z)
                cw.addData4(self._wall_color(z, h))
                # Offset unique par segment : chaque dalle montre une zone différente
                tw.addData2(y * uv_scale + self.uv_offset_y,
                            z * uv_scale + self.uv_offset_z)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_z):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                if self.is_right:
                    tris.addVertices(a, b, a + 1)
                    tris.addVertices(a + 1, b, b + 1)
                else:
                    tris.addVertices(a, a + 1, b)
                    tris.addVertices(a + 1, b + 1, b)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_wall_mesh")
        node.addGeom(geom)
        np = NodePath(node)
        np.setTexture(_TS_MODULATE, _get_wall_tex())
        np.reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TrenchFloorPanel:
    """Dalle de sol de tranchée — défile en Y, fixe en Z."""

    FLOOR_Z = -7.5

    def __init__(self, parent, x_center, y_pos, width=28.0, depth=22.0):
        self.alive = True
        self.node = self._make_floor(width, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_center, y_pos, self.FLOOR_Z)
        self.node.setLightOff()

    def _make_floor(self, w, d):
        root  = NodePath("trench_floor")
        vdata = GeomVertexData("floor", _V3C4T2, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        tw = GeomVertexWriter(vdata, "texcoord")

        segs_x = max(4, int(w / 2))
        segs_y = max(4, int(d / 2))
        uv_scale = 1.0 / 7.0   # grands panneaux sol, peu de répétition

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y
                vw.addData3(x, y, 0)
                # Vertex color : gris sombre uniforme (texture porte le détail)
                g = 0.55
                cw.addData4(g * 1.01, g, g * 0.92, 1.0)
                tw.addData2(x * uv_scale, y * uv_scale)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_floor_mesh")
        node.addGeom(geom)
        np = NodePath(node)
        np.setTexture(_TS_MODULATE, _get_floor_tex())
        np.reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TrenchWallCrest:
    """Objets qui dépassent du sommet du mur — antennes, blocs, équipements.
    Brise la ligne droite du bord supérieur et ajoute de la silhouette.
    """

    CREST_Z = 8.0   # Z sommet des murs

    def __init__(self, parent, x_wall, y_pos, depth=22.0):
        self.alive = True
        self.inward = 1.0 if x_wall < 0 else -1.0
        rng = random.Random(int(round(abs(x_wall) * 211 + y_pos * 53.7)) & 0xFFFFFF)
        self.node = NodePath("wall_crest")
        self.node.reparentTo(parent)
        self.node.setPos(x_wall, y_pos, self.CREST_Z)
        self.node.setLightOff()
        self._build(rng, depth)

    def _shade(self, dz):
        """Gris sombre — éléments en silhouette contre le ciel."""
        g = max(0.08, min(0.45, 0.25 + dz * 0.04))
        return Vec4(g * 1.02, g, g * 0.95, 1.0)

    def _make_block(self, w, h, d, dz=0):
        root  = NodePath("cblock")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("cb", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        hx, hy, hz = w/2, d/2, h/2
        corners = [
            (-hx,-hy,-hz),( hx,-hy,-hz),( hx, hy,-hz),(-hx, hy,-hz),
            (-hx,-hy, hz),( hx,-hy, hz),( hx, hy, hz),(-hx, hy, hz),
        ]
        for cx2,cy2,cz2 in corners:
            vw.addData3(cx2, cy2, cz2)
            cw.addData4(self._shade(dz + cz2))
        tris = GeomTriangles(Geom.UHStatic)
        for f in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),
                  (2,6,7),(2,7,3),(0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
            tris.addVertices(*f)
        geom = Geom(vdata); geom.addPrimitive(tris)
        gn = GeomNode("cb_m"); gn.addGeom(geom)
        NodePath(gn).reparentTo(root)
        return root

    def _build(self, rng, depth):
        half_d = depth / 2.0
        n_items = rng.randint(2, 5)
        placed  = []
        for _ in range(n_items * 8):
            if len(placed) >= n_items:
                break
            y = rng.uniform(-half_d + 0.5, half_d - 0.5)
            if any(abs(y - yp) < rng.uniform(1.0, 2.5) for yp in placed):
                continue
            kind = rng.choice(['block','block','block','antenna','antenna'])
            if kind == 'block':
                w = rng.uniform(0.4, 2.0)
                h = rng.uniform(0.3, 1.8)   # dépasse vers le haut
                d = rng.uniform(0.3, 1.2)
                obj = self._make_block(w, h, d, h/2)
                obj.reparentTo(self.node)
                obj.setPos(self.inward * rng.uniform(0.1, 1.5), y, h/2)
            else:  # antenna — tige fine très haute
                r  = rng.uniform(0.04, 0.10)
                h  = rng.uniform(1.0, 3.5)
                # cylindre vertical simple
                root2 = NodePath("cant")
                fmt2  = GeomVertexFormat.getV3c4()
                vd2   = GeomVertexData("ant", fmt2, Geom.UHStatic)
                vw2 = GeomVertexWriter(vd2, "vertex")
                cw2 = GeomVertexWriter(vd2, "color")
                segs = 6
                for zi in (0, h):
                    for s in range(segs):
                        a = 2*math.pi*s/segs
                        vw2.addData3(r*math.cos(a), r*math.sin(a), zi)
                        cw2.addData4(self._shade(zi))
                tr2 = GeomTriangles(Geom.UHStatic)
                for s in range(segs):
                    b0=s; b1=(s+1)%segs; t0=segs+s; t1=segs+(s+1)%segs
                    tr2.addVertices(b0,b1,t0); tr2.addVertices(b1,t1,t0)
                g2 = Geom(vd2); g2.addPrimitive(tr2)
                gn2 = GeomNode("ant_m"); gn2.addGeom(g2)
                NodePath(gn2).reparentTo(root2)
                root2.reparentTo(self.node)
                root2.setPos(self.inward * rng.uniform(0.2, 2.0), y, 0)
            placed.append(y)

    def update(self, dt, scroll_speed):
        if not self.alive: return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TrenchSurfacePanel:
    """Surface de la Death Star de part et d'autre de la tranchée.
    Panneau horizontal au sommet des murs pour boucher le ciel 'espace'.
    """

    SURFACE_Z  = 8.2      # sommet des murs de tranchée (h=16, centre Z=0 → top = +8)
    WALL_HALF  = 13.5     # bord intérieur = bord du mur
    SURFACE_W  = 110.0    # largeur depuis le mur vers l'extérieur (couvre le FOV 60° à Y=200)

    def __init__(self, parent, side, y_pos, depth=22.0):
        """side: -1 gauche, +1 droite."""
        self.alive = True
        self.node = self._make_surface(depth)
        self.node.reparentTo(parent)
        x_center = side * (self.WALL_HALF + self.SURFACE_W / 2.0)
        self.node.setPos(x_center, y_pos, self.SURFACE_Z)
        self.node.setLightOff()

    def _make_surface(self, d):
        root = NodePath("trench_surface")
        w = self.SURFACE_W
        fmt  = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("surface", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        segs_x = max(8, int(w / 8))
        segs_y = max(4, int(d / 4))
        ps, sw = 3.0, 0.06

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y
                vw.addData3(x, y, 0)
                px = x % ps;  py = y % ps
                dx = min(px, ps - px);  dy_v = min(py, ps - py)
                bevel = min(1.0, min(dx, dy_v) / sw)
                pi = int((x + 200) / ps);  pj = int((y + 100) / ps)
                pv = math.sin(pi * 1.73 + pj * 2.31) * 0.04
                base = (0.38 + pv) * (0.14 + 0.86 * bevel)
                g = max(0.03, min(0.65, base))
                cw.addData4(g * 1.03, g, g * 0.95, 1.0)

        # Face visible depuis le BAS (winding CCW vu d'en bas)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, a + 1, b)
                tris.addVertices(a + 1, b + 1, b)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_surface_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# L3 — Décorations 3D murs de tranchée
# ============================================================

class TrenchDecorGroup:
    """Groupe de décorations 3D fixées sur un segment de mur de tranchée.

    Génère aléatoirement des boîtes, cylindres, disques, marches et rails
    avec coloration par vertex simulant un éclairage zénithal (haut lumineux,
    bas dans l'ombre).
    """

    WALL_Z_LO = -7.5    # Z sol tranchée
    WALL_Z_HI =  8.0    # Z sommet murs

    def __init__(self, parent, x_wall, y_pos, depth=22.0, lit=True):
        self.alive = True
        self.lit = lit
        # Direction de protrusion depuis le mur vers l'intérieur de la tranchée
        self.inward = 1.0 if x_wall < 0 else -1.0

        # Seed déterministe — même (x_wall, y_pos) = même décor à chaque spawn
        rng = random.Random(int(round(abs(x_wall) * 137 + y_pos * 73.1)) & 0xFFFFFF)

        self.node = NodePath("decor_group")
        self.node.reparentTo(parent)
        self.node.setPos(x_wall, y_pos, 0)
        self.node.setLightOff()

        self._build(rng, depth)

    # ----------------------------------------------------------
    # Nuance vertex — gradient Z (ombre bas → lumière haut)
    # ----------------------------------------------------------

    def _shade(self, z_world):
        """Gris Death Star, gradient vertical : ombre en bas, lumière en haut.
        Côté éclairé (lit=True) : 0.22→0.78 | Côté ombre (lit=False) : 0.08→0.30
        """
        t = (z_world - self.WALL_Z_LO) / (self.WALL_Z_HI - self.WALL_Z_LO)
        t = max(0.0, min(1.0, t))
        if self.lit:
            g = 0.20 + t * 0.42   # 0.20 (ombre) → 0.62 (lumière)
        else:
            g = 0.07 + t * 0.18   # 0.07 → 0.25 (côté nuit)
        return Vec4(g * 1.03, g * 1.00, g * 0.96, 1.0)  # Légèrement chaud

    # ----------------------------------------------------------
    # Primitives géométriques
    # ----------------------------------------------------------

    def _make_box(self, bw, bh, bd, z_center):
        """Boîte pleine — bw=X(protrusion), bh=Z(hauteur), bd=Y(épaisseur)."""
        root = NodePath("dbox")
        fmt  = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hx, hy, hz = bw / 2, bd / 2, bh / 2
        corners = [
            (-hx, -hy, -hz), ( hx, -hy, -hz), ( hx,  hy, -hz), (-hx,  hy, -hz),
            (-hx, -hy,  hz), ( hx, -hy,  hz), ( hx,  hy,  hz), (-hx,  hy,  hz),
        ]
        for cx, cy, cz in corners:
            vw.addData3(cx, cy, cz)
            cw.addData4(self._shade(z_center + cz))

        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0, 1, 2), (0, 2, 3),           # bas
            (4, 6, 5), (4, 7, 6),           # haut
            (0, 4, 5), (0, 5, 1),           # avant
            (2, 6, 7), (2, 7, 3),           # arrière
            (0, 3, 7), (0, 7, 4),           # gauche
            (1, 5, 6), (1, 6, 2),           # droite
        ]:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dbox_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_cylinder_v(self, radius, height, z_center, segs=8):
        """Cylindre vertical (axe Z) — colonne / tuyau debout."""
        root  = NodePath("dcylv")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("cylv", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hz = height / 2
        for zi in (-hz, hz):
            for s in range(segs):
                a = 2 * math.pi * s / segs
                vw.addData3(radius * math.cos(a), radius * math.sin(a), zi)
                cw.addData4(self._shade(z_center + zi))

        # Centres des disques bas/haut
        vw.addData3(0, 0, -hz);  cw.addData4(self._shade(z_center - hz))
        vw.addData3(0, 0,  hz);  cw.addData4(self._shade(z_center + hz))
        c_bot = 2 * segs
        c_top = 2 * segs + 1

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            b0 = s;           b1 = (s + 1) % segs
            t0 = segs + s;    t1 = segs + (s + 1) % segs
            # Manteau
            tris.addVertices(b0, b1, t0)
            tris.addVertices(b1, t1, t0)
            # Disque bas (CW vu d'en bas)
            tris.addVertices(c_bot, b1, b0)
            # Disque haut (CCW vu d'en haut)
            tris.addVertices(c_top, t0, t1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dcylv_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_cylinder_h(self, radius, length, z_center, segs=6):
        """Cylindre horizontal (axe Y) — rail / barre / tuyau couché."""
        root  = NodePath("dcylh")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("cylh", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hl = length / 2
        for yi in (-hl, hl):
            for s in range(segs):
                a = 2 * math.pi * s / segs
                x = radius * math.cos(a)
                z = radius * math.sin(a)
                vw.addData3(x, yi, z)
                cw.addData4(self._shade(z_center + z))

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            b0 = s;           b1 = (s + 1) % segs
            t0 = segs + s;    t1 = segs + (s + 1) % segs
            tris.addVertices(b0, t0, b1)
            tris.addVertices(b1, t0, t1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dcylh_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_disc(self, radius, thickness, z_center, segs=12):
        """Disque circulaire dans le plan YZ — hublot / panneau rond."""
        root  = NodePath("ddisc")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("disc", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        ht = thickness / 2

        # Face avant (+X) : centre puis anneau
        vw.addData3(ht, 0, 0);  cw.addData4(self._shade(z_center))
        c_front = 0
        for s in range(segs):
            a = 2 * math.pi * s / segs
            y, z = radius * math.cos(a), radius * math.sin(a)
            vw.addData3(ht, y, z);  cw.addData4(self._shade(z_center + z))
        # Anneau avant : indices 1..segs

        # Face arrière (−X) : centre puis anneau
        vw.addData3(-ht, 0, 0);  cw.addData4(self._shade(z_center))
        c_back = segs + 1
        for s in range(segs):
            a = 2 * math.pi * s / segs
            y, z = radius * math.cos(a), radius * math.sin(a)
            vw.addData3(-ht, y, z);  cw.addData4(self._shade(z_center + z))
        # Anneau arrière : indices segs+2..2*segs+1

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            f0 = 1 + s;           f1 = 1 + (s + 1) % segs
            b0 = c_back + 1 + s;  b1 = c_back + 1 + (s + 1) % segs
            # Face avant
            tris.addVertices(c_front, f0, f1)
            # Face arrière
            tris.addVertices(c_back, b1, b0)
            # Tranche
            tris.addVertices(f0, b0, f1)
            tris.addVertices(f1, b0, b1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("ddisc_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_steps(self, size, n_steps, z_center):
        """Marches empilées décroissantes — escalier / piédestal."""
        root = NodePath("dsteps")
        total_h = size * 0.40 * n_steps
        for i in range(n_steps):
            t = (n_steps - 1 - i) / max(n_steps - 1, 1)
            sw = size * (0.35 + 0.65 * t)
            sh = size * 0.38
            sd = size * (0.4 + 0.6 * t)
            z_off = -total_h / 2 + i * sh + sh / 2
            box = self._make_box(sw, sh * 0.92, sd, z_center + z_off)
            box.reparentTo(root)
            box.setPos(0, 0, z_off)
        return root

    def _make_light_spot(self, rng, color):
        """Halo de lumière diffuse collé au mur — gradient centre opaque → bord transparent.
        Deux couches : noyau brillant (r_core) + halo large (r_halo) semi-transparent.
        """
        r_core = rng.uniform(0.12, 0.25)
        r_halo = r_core * rng.uniform(2.5, 4.5)
        root   = NodePath("dlspot")
        root.setTransparency(TransparencyAttrib.MAlpha)

        fmt  = GeomVertexFormat.getV3c4()

        def make_disc(radius, c_center, c_edge):
            vdata = GeomVertexData("lspot", fmt, Geom.UHStatic)
            vw = GeomVertexWriter(vdata, "vertex")
            cw = GeomVertexWriter(vdata, "color")
            segs = 14
            vw.addData3(0.01, 0, 0);  cw.addData4(c_center)
            for s in range(segs):
                a = 2 * math.pi * s / segs
                vw.addData3(0.01, radius * math.cos(a), radius * math.sin(a))
                cw.addData4(c_edge)
            tris = GeomTriangles(Geom.UHStatic)
            for s in range(segs):
                tris.addVertices(0, 1 + s, 1 + (s + 1) % segs)
            geom = Geom(vdata)
            geom.addPrimitive(tris)
            gn = GeomNode("lspot_m")
            gn.addGeom(geom)
            np = NodePath(gn)
            np.setTwoSided(True)
            np.reparentTo(root)

        # Noyau : couleur pleine
        c_full  = Vec4(color.getX(), color.getY(), color.getZ(), 1.0)
        # Halo : même teinte mais transparent sur les bords
        c_mid   = Vec4(color.getX(), color.getY(), color.getZ(), 0.55)
        c_fade  = Vec4(color.getX() * 0.6, color.getY() * 0.6, color.getZ() * 0.6, 0.0)

        make_disc(r_core, c_full, c_mid)
        make_disc(r_halo, c_mid,  c_fade)
        return root

    def _make_conduit_group(self, rng, z_center, length):
        """2-4 tuyaux horizontaux parallèles de diamètres variés."""
        root  = NodePath("dconduit")
        n_pipes = rng.randint(2, 4)
        z_off = 0.0
        for _ in range(n_pipes):
            r   = rng.uniform(0.06, 0.22)
            gap = rng.uniform(0.04, 0.12)
            pipe = self._make_cylinder_h(r, length * rng.uniform(0.7, 1.0),
                                         z_center + z_off, segs=6)
            pipe.reparentTo(root)
            pipe.setPos(self.inward * (r + 0.04), 0, z_off)
            z_off += r * 2 + gap
        return root

    def _make_antenna(self, rng, z_center):
        """Antenne : colonne mince + disque en tête + optionnellement un anneau."""
        root   = NodePath("dantenna")
        h_col  = rng.uniform(1.2, 3.5)
        r_col  = rng.uniform(0.04, 0.10)
        col    = self._make_cylinder_v(r_col, h_col, z_center)
        col.reparentTo(root)
        col.setPos(0, 0, 0)
        # Disque au sommet
        r_cap = rng.uniform(0.18, 0.45)
        cap   = self._make_disc(r_cap, r_cap * 0.3, z_center + h_col / 2)
        cap.reparentTo(root)
        cap.setPos(0, 0, h_col / 2)
        # Anneau intermédiaire optionnel
        if rng.random() < 0.5:
            r_ring = rng.uniform(0.12, 0.28)
            ring   = self._make_disc(r_ring, r_ring * 0.25,
                                     z_center + h_col * rng.uniform(0.3, 0.6))
            ring.reparentTo(root)
            ring.setPos(0, 0, h_col * rng.uniform(0.3, 0.6))
        return root

    def _make_l_bracket(self, rng, z_center):
        """L-bracket : une boîte horizontale + une boîte verticale connectées en L."""
        root = NodePath("dlbracket")
        # Bras horizontal (le long du mur, axe Y)
        bh_w = rng.uniform(0.25, 0.55)   # épaisseur (X, protrusion)
        bh_h = rng.uniform(0.20, 0.40)   # hauteur (Z)
        bh_d = rng.uniform(1.0,  2.5)    # longueur (Y)
        arm_h = self._make_box(bh_w, bh_h, bh_d, z_center)
        arm_h.reparentTo(root)
        arm_h.setPos(0, 0, 0)
        # Bras vertical (axe Z) connecté à une extrémité
        bv_w = rng.uniform(0.20, 0.45)
        bv_h = rng.uniform(0.8,  2.0)
        bv_d = rng.uniform(0.20, 0.40)
        y_end = bh_d / 2 * rng.choice([-1, 1])
        arm_v = self._make_box(bv_w, bv_h, bv_d, z_center + bv_h / 2)
        arm_v.reparentTo(root)
        arm_v.setPos(0, y_end, bv_h / 2)
        return root

    def _make_tower(self, rng, z_center, depth=4):
        """Tour fractale récursive : boîte de base + éléments plus petits au sommet.
        depth contrôle la profondeur de récursion (1-3 niveaux pratiques).
        """
        root = NodePath("dtower")
        if depth <= 0:
            return root
        size = rng.uniform(0.5, 1.6) * (0.55 ** (3 - depth))
        bw = size * rng.uniform(0.8, 1.4)
        bh = size * rng.uniform(0.7, 1.2)
        bd = size * rng.uniform(0.7, 1.2)
        box = self._make_box(bw, bh, bd, z_center)
        box.reparentTo(root)
        box.setPos(0, 0, 0)
        if depth > 1 and rng.random() < 0.75:
            child = self._make_tower(rng, z_center + bh / 2, depth - 1)
            child.reparentTo(root)
            child.setPos(rng.uniform(-bw * 0.2, bw * 0.2),
                         rng.uniform(-bd * 0.2, bd * 0.2),
                         bh / 2)
        return root

    def _make_connected_cluster(self, rng, z_center, length):
        """Groupe connecté : 2 boîtes reliées par un rail + optionnellement une antenne.
        Principe puzzle — les pièces s'assemblent autour d'un axe commun.
        """
        root = NodePath("dcluster")
        # Rail central
        r_rail = rng.uniform(0.05, 0.12)
        rail   = self._make_cylinder_h(r_rail, length, z_center)
        rail.reparentTo(root)

        # Boîte A à une extrémité
        bw_a = rng.uniform(0.3, 0.9);  bh_a = rng.uniform(0.4, 1.2);  bd_a = rng.uniform(0.3, 0.7)
        box_a = self._make_box(bw_a, bh_a, bd_a, z_center)
        box_a.reparentTo(root)
        box_a.setPos(0, -length / 2, 0)

        # Boîte B à l'autre extrémité (taille différente)
        bw_b = rng.uniform(0.25, 0.7);  bh_b = rng.uniform(0.3, 1.0);  bd_b = rng.uniform(0.25, 0.6)
        box_b = self._make_box(bw_b, bh_b, bd_b, z_center)
        box_b.reparentTo(root)
        box_b.setPos(0, length / 2, 0)

        # Nœud intermédiaire optionnel (cylindre vertical)
        if rng.random() < 0.55:
            r_node = rng.uniform(0.12, 0.25)
            h_node = rng.uniform(0.4, 0.9)
            y_node = rng.uniform(-length * 0.3, length * 0.3)
            node_v = self._make_cylinder_v(r_node, h_node,
                                           z_center + rng.uniform(-0.3, 0.3))
            node_v.reparentTo(root)
            node_v.setPos(0, y_node, 0)

        return root

    # ----------------------------------------------------------
    # Construction du groupe — placement fractal/puzzle
    # ----------------------------------------------------------

    def _build(self, rng, depth):
        """Génère les décorations selon un placement fractal contextuel.

        Hiérarchie :
          1. Rails de fond (traversent tout le segment — structure globale)
          2. Conduits groupés (structure secondaire)
          3. Clusters connectés (pièces qui s'assemblent autour d'un axe)
          4. Éléments terminaux (boîtes, tours, antennes, disques)
        """
        half_d = depth / 2.0

        # ── 1. Rails de fond (1-3, traversent tout le segment) ─
        n_rails = rng.randint(1, 3)
        z_rail_candidates = [-5.0, -3.5, -2.0, -0.5, 1.0, 2.5, 4.0, 5.5]
        rng.shuffle(z_rail_candidates)
        for ri in range(n_rails):
            z_r  = z_rail_candidates[ri]
            r_r  = rng.uniform(0.05, 0.15)
            rail = self._make_cylinder_h(r_r, depth * rng.uniform(0.88, 1.0), z_r)
            rail.reparentTo(self.node)
            rail.setPos(self.inward * (r_r + 0.03), 0, z_r)

        # ── 2. Conduits groupés (50% du temps) ─────────────────
        if rng.random() < 0.50:
            z_c = rng.uniform(self.WALL_Z_LO + 1.2, self.WALL_Z_HI - 1.2)
            cg  = self._make_conduit_group(rng, z_c, depth * rng.uniform(0.45, 0.85))
            cg.reparentTo(self.node)
            cg.setPos(0, rng.uniform(-half_d * 0.35, half_d * 0.35), z_c)

        # ── 3. Clusters connectés (1-3, pièces assemblées) ─────
        n_clusters = rng.randint(1, 3)
        cluster_y  = []
        for _ in range(n_clusters * 6):
            if len(cluster_y) >= n_clusters:
                break
            y   = rng.uniform(-half_d + 1.5, half_d - 1.5)
            sep = rng.uniform(2.5, 4.5)
            if any(abs(y - yp) < sep for yp in cluster_y):
                continue
            z_c   = rng.uniform(self.WALL_Z_LO + 1.0, self.WALL_Z_HI - 1.0)
            cl_l  = rng.uniform(1.2, 3.5)
            cl    = self._make_connected_cluster(rng, z_c, cl_l)
            cl.reparentTo(self.node)
            cl.setPos(self.inward * rng.uniform(0.3, 0.7), y, z_c)
            cluster_y.append(y)

        # ── 4. Éléments terminaux ───────────────────────────────
        terminal_pool = [
            'tower', 'tower', 'tower',
            'antenna', 'antenna',
            'l_bracket', 'l_bracket',
            'box',
            'disc',
            'steps',
        ]
        n_items  = rng.randint(3, 7)
        placed_y = list(cluster_y)   # évite les chevauchements avec clusters

        for _ in range(n_items * 10):
            if len(placed_y) - len(cluster_y) >= n_items:
                break
            y   = rng.uniform(-half_d + 0.6, half_d - 0.6)
            sep = rng.uniform(0.7, 1.6)
            if any(abs(y - yp) < sep for yp in placed_y):
                continue

            z_ctr = rng.uniform(self.WALL_Z_LO + 0.6, self.WALL_Z_HI - 0.6)
            shape = rng.choice(terminal_pool)

            if shape == 'tower':
                sn = self._make_tower(rng, z_ctr, depth=rng.randint(2, 3))
                protrude = 0.5

            elif shape == 'antenna':
                sn = self._make_antenna(rng, z_ctr)
                protrude = 0.08

            elif shape == 'l_bracket':
                sn = self._make_l_bracket(rng, z_ctr)
                protrude = 0.3

            elif shape == 'box':
                bw = rng.uniform(0.3, 2.2)
                bh = rng.uniform(0.25, 1.8)
                bd = rng.uniform(0.25, 1.4)
                sn = self._make_box(bw, bh, bd, z_ctr)
                protrude = bw / 2

            elif shape == 'disc':
                r   = rng.uniform(0.3, 1.0)
                th  = rng.uniform(0.12, 0.35)
                sn  = self._make_disc(r, th, z_ctr)
                protrude = th / 2

            else:  # steps
                sz   = rng.uniform(0.7, 2.0)
                n_st = rng.randint(2, 4)
                sn   = self._make_steps(sz, n_st, z_ctr)
                protrude = sz * 0.35

            sn.reparentTo(self.node)
            sn.setPos(self.inward * protrude, y, z_ctr)
            placed_y.append(y)

        # ── 5. Petites lumières colorées sur le mur ─────────────
        # Orange, rouge, vert — accrochées directement au mur (X≈0)
        light_colors = [
            Vec4(1.00, 0.50, 0.08, 1.0),   # orange
            Vec4(1.00, 0.50, 0.08, 1.0),   # orange (plus fréquent)
            Vec4(0.85, 0.12, 0.08, 1.0),   # rouge
            Vec4(0.15, 0.90, 0.20, 1.0),   # vert
        ]
        n_lights = rng.randint(2, 5)
        for _ in range(n_lights):
            ly = rng.uniform(-half_d + 0.5, half_d - 0.5)
            lz = rng.uniform(self.WALL_Z_LO + 0.8, self.WALL_Z_HI - 0.8)
            col = rng.choice(light_colors)
            ls  = self._make_light_spot(rng, col)
            ls.reparentTo(self.node)
            # Collé au mur (X=0 car node est déjà à x_wall), orienté vers l'intérieur
            ls.setPos(self.inward * 0.04, ly, lz)

    # ----------------------------------------------------------

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class _StaticDecor:
    """Wrapper minimal pour stocker un NodePath statique dans la liste planets."""

    def __init__(self, np):
        self.alive = True
        self.node = np

    def update(self, dt):
        pass  # statique, ne bouge pas

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# Environment principal (level-aware)
# ============================================================

class Environment:
    """Gère tout le décor spatial — adapté selon le niveau actif."""

    ASTEROID_INTERVAL = 1.8
    NEBULA_INTERVAL = 35.0
    DEBRIS_INTERVAL = 5.0

    SPAWN_DEPTH = 230.0   # Poussé de 200→230 pour que le fog cache le spawn
    FIELD_WIDTH = 25.0
    FIELD_HEIGHT = 15.0

    TILE_DEPTH = 22.0   # Profondeur d'une dalle/panneau (L2 + L3)

    def __init__(self, game, level=1):
        self.game = game
        self.level = level

        # Nettoie tout brouillard d'un niveau précédent
        game.render.clearFog()

        AsteroidModelCache.load(game)

        # Listes communes
        self.asteroids = []
        self.planets = []
        self.nebulae = []
        self.debris = []

        # Listes spécifiques L2/L3
        self.terrain_tiles      = []   # L2 sol lunaire
        self.base_groups        = []   # L2 bâtiments spaceport
        self.border_mountains   = []   # L2 montagnes de bord (X ≈ ±18-22)
        self.roads              = []   # L2 routes horizontales
        self.wall_panels    = []   # L3 murs tranchée
        self.floor_panels   = []   # L3 sol tranchée
        self.surface_panels = []   # L3 surface Death Star (au-dessus des murs)
        self.decor_groups   = []   # L3 décorations 3D sur les murs

        # Nappes de brouillard mobiles (T3)
        self.fog_layers = []

        # Timers — niveau 99 (debug) : 3× plus d'astéroïdes, vitesses aléatoires
        self._debug_asteroids = (level == 99)
        debug = self._debug_asteroids
        self.asteroid_timer = 0.1 if debug else 2.0
        self.nebula_timer   = 15.0
        self.debris_timer   = 4.0
        self._asteroid_interval = 0.1 if debug else self.ASTEROID_INTERVAL   # L99 : 10/s

        self.star_destroyer = None

        # Couleurs nébuleuses (L1/L4) — L4 utilise une palette violet/rose
        if level == 4:
            self.nebula_colors = [
                Vec4(0.55, 0.1, 0.80, 1),   # violet profond
                Vec4(0.75, 0.2, 0.60, 1),   # rose-magenta
                Vec4(0.45, 0.05, 0.70, 1),  # indigo
                Vec4(0.80, 0.25, 0.50, 1),  # rose chaud
                Vec4(0.60, 0.15, 0.85, 1),  # violet saturé
            ]
        else:
            self.nebula_colors = [
                Vec4(0.6, 0.2, 0.8, 1),
                Vec4(0.2, 0.4, 0.9, 1),
                Vec4(0.8, 0.3, 0.2, 1),
                Vec4(0.2, 0.7, 0.5, 1),
                Vec4(0.9, 0.6, 0.1, 1),
            ]

        # Init selon le niveau (L99 = visuels L1)
        if level in (1, 99):
            self._spawn_fixed_planets()
        elif level in (2, 0):
            self._init_lunar()
        elif level == 3:
            self._init_trench()
        elif level == 4:
            self._spawn_nebula_planet()

        # Fog globale (L3 a son propre fog dans _init_trench)
        if level not in (3, 99):
            self._setup_distance_fog(level)

        # Nappes de brouillard mobiles (T3) — L1, L2, L4 seulement
        self._setup_fog_layers(level)

    # ----------------------------------------------------------
    # Fog global — cache le pop-in lointain
    # ----------------------------------------------------------

    def _setup_distance_fog(self, level):
        """Fog linéaire adaptée au background du niveau."""
        if level == 1:
            color, onset, opaque = (0.0, 0.0, 0.0), 150.0, 230.0
        elif level in (2, 0):
            color, onset, opaque = (0.04, 0.04, 0.05), 130.0, 210.0
        elif level == 4:
            color, onset, opaque = (0.03, 0.01, 0.05), 100.0, 190.0
        else:
            return
        fog = Fog("distance_fog")
        fog.setColor(*color)
        fog.setLinearRange(onset, opaque)
        self.game.render.setFog(fog)

    def _setup_fog_layers(self, level):
        """Crée les nappes de brouillard mobiles selon le niveau (T3)."""
        render = self.game.render
        if level in (1, 99):
            # 3 nappes noires légères — légèrement visibles pour donner de la profondeur
            self.fog_layers.append(FogLayer(
                render, Vec3(0.0, 0.0, 0.0), alpha=0.11,
                altitude_z=-2.0, spread_x=28.0, count=9, speed_y=3.5,
            ))
            self.fog_layers.append(FogLayer(
                render, Vec3(0.0, 0.0, 0.0), alpha=0.11,
                altitude_z=1.5, spread_x=28.0, count=9, speed_y=4.5,
            ))
            self.fog_layers.append(FogLayer(
                render, Vec3(0.02, 0.02, 0.04), alpha=0.07,
                altitude_z=0.0, spread_x=24.0, count=6, speed_y=5.5,
            ))
        elif level in (2, 0):
            # 2 nappes grises — ras du sol + légèrement au-dessus
            self.fog_layers.append(FogLayer(
                render, Vec3(0.55, 0.55, 0.52), alpha=0.16,
                altitude_z=-7.0, spread_x=30.0, count=11, speed_y=3.0,
            ))
            self.fog_layers.append(FogLayer(
                render, Vec3(0.48, 0.48, 0.46), alpha=0.09,
                altitude_z=-5.5, spread_x=28.0, count=7, speed_y=2.5,
            ))
        elif level == 3:
            pass  # Tranchée : pas de nappe
        elif level == 4:
            # 4 nappes violettes/roses/indigo étagées en altitude
            self.fog_layers.append(FogLayer(
                render, Vec3(0.55, 0.10, 0.75), alpha=0.30,
                altitude_z=-3.0, spread_x=30.0, count=13, speed_y=5.0,
            ))
            self.fog_layers.append(FogLayer(
                render, Vec3(0.75, 0.22, 0.55), alpha=0.34,
                altitude_z=2.5, spread_x=26.0, count=11, speed_y=4.5,
            ))
            self.fog_layers.append(FogLayer(
                render, Vec3(0.42, 0.05, 0.62), alpha=0.27,
                altitude_z=0.0, spread_x=35.0, count=14, speed_y=6.0,
            ))
            # 4ème nappe haute — bleu-indigo très léger pour depth
            self.fog_layers.append(FogLayer(
                render, Vec3(0.18, 0.05, 0.42), alpha=0.15,
                altitude_z=5.5, spread_x=32.0, count=8, speed_y=7.0,
            ))

    # ----------------------------------------------------------
    # Init par niveau
    # ----------------------------------------------------------

    def _init_lunar(self):
        """L2 — Sol continu + groupes de bâtiments spaceport + montagnes de bord + routes."""
        d = self.TILE_DEPTH
        y = 15.0
        while y <= self.SPAWN_DEPTH + d:
            self.terrain_tiles.append(LunarTerrain(self.game.render, 0, y, depth=d))
            y += d
        # Groupes de bâtiments toutes les ~55 unités
        by = 50.0
        seed = 1337
        while by <= self.SPAWN_DEPTH:
            self.base_groups.append(LunarBaseGroup(self.game, by, seed))
            by += random.uniform(48, 70)
            seed += 97

        # Montagnes de bord — une bande continue de Y=15 à SPAWN_DEPTH
        self.border_mountains.append(
            LunarBorderMountain(self.game.render, 15.0, self.SPAWN_DEPTH + 30.0, seed=42)
        )

        # Routes horizontales — 2-3 positions fixes espacées dans le niveau initial
        road_ys = [random.uniform(40, 60), random.uniform(90, 120), random.uniform(155, 185)]
        self.roads.append(LunarRoad(self.game.render, road_ys))

    def _init_trench(self):
        """L3 — Tranchée continue + brouillard linéaire pour masquer le clipping."""
        # Brouillard : fond gris sombre, onset 90u → opaque 215u
        bg = (0.04, 0.04, 0.05)
        fog = Fog("trench_fog")
        fog.setColor(*bg)
        fog.setLinearRange(90.0, 215.0)
        self.game.render.setFog(fog)
        self._trench_fog = fog

        # Lune côté droit (source de lumière) — haute, lointaine, fixe
        moon = DistantPlanet(
            self.game.render,
            Point3(-18, 140, 28),         # gauche (-X), loin, très haut
            size=4.5,
            color=Vec4(0.88, 0.88, 0.78, 1),   # blanc-chaud lunaire
        )
        moon.grow_rate = 0.0   # ne grossit pas — planète fixe
        self.planets.append(moon)

        d = self.TILE_DEPTH
        y = 15.0
        while y <= self.SPAWN_DEPTH + d:
            self._spawn_trench_row(y)
            y += d

    def _spawn_trench_row(self, y):
        d = self.TILE_DEPTH
        self.wall_panels.append(TrenchWallPanel(
            self.game.render, TrenchWallPanel.WALL_X_LEFT,  y, depth=d, lit=False))
        self.wall_panels.append(TrenchWallPanel(
            self.game.render, TrenchWallPanel.WALL_X_RIGHT, y, depth=d, lit=True))
        self.floor_panels.append(TrenchFloorPanel(
            self.game.render, 0, y, depth=d))
        self.surface_panels.append(TrenchSurfacePanel(
            self.game.render, -1, y, depth=d))
        self.surface_panels.append(TrenchSurfacePanel(
            self.game.render, +1, y, depth=d))
        self.decor_groups.append(TrenchDecorGroup(
            self.game.render, TrenchWallPanel.WALL_X_LEFT,  y, depth=d, lit=False))
        self.decor_groups.append(TrenchDecorGroup(
            self.game.render, TrenchWallPanel.WALL_X_RIGHT, y, depth=d, lit=True))
        self.decor_groups.append(TrenchWallCrest(
            self.game.render, TrenchWallPanel.WALL_X_LEFT,  y, depth=d))
        self.decor_groups.append(TrenchWallCrest(
            self.game.render, TrenchWallPanel.WALL_X_RIGHT, y, depth=d))

    def _spawn_nebula_planet(self):
        """L4 — Nébuleuse colorée en fond + filaments de gaz + ambient violet."""
        # Lumière ambiante violette — teinte toute la scène L4
        from panda3d.core import AmbientLight as AL
        self._l4_ambient = AL("l4_ambient")
        self._l4_ambient.setColor(Vec4(0.18, 0.05, 0.28, 1.0))
        self._l4_ambient_np = self.game.render.attachNewNode(self._l4_ambient)
        self.game.render.setLight(self._l4_ambient_np)

        # Planète principale — teinte violette profonde
        p = DistantPlanet(
            self.game.render,
            Point3(-5, 180, 5),
            size=32,
            color=Vec4(0.48, 0.12, 0.72, 1),
        )
        self.planets.append(p)

        # Planète secondaire rose/magenta — décalée en hauteur
        p2 = DistantPlanet(
            self.game.render,
            Point3(28, 215, 12),
            size=15,
            color=Vec4(0.72, 0.18, 0.52, 1),
        )
        self.planets.append(p2)

        # 3ème planète — lointaine, bleue-indigo, petite
        p3 = DistantPlanet(
            self.game.render,
            Point3(-22, 250, -8),
            size=8,
            color=Vec4(0.25, 0.10, 0.65, 1),
        )
        p3.grow_rate = 0.0   # planète fixe — ne grossit pas
        self.planets.append(p3)

        # Filaments de gaz multicolores
        self._spawn_gas_filaments(count=16)

    def _spawn_gas_filaments(self, count=16):
        """L4 — Filaments de gaz multicolores semi-transparents en arrière-plan.

        Géométrie : 1 vertex central (alpha plein) + 4 coins (alpha=0).
        5 triangles en éventail → dégradé radial, aucun bord rectangulaire visible.
        """
        render = self.game.render

        # Palettes de couleurs nébuleuses : (r, g, b)
        _FILAMENT_PALETTES = [
            (0.45, 0.08, 0.65),   # violet profond
            (0.70, 0.15, 0.50),   # rose-magenta
            (0.30, 0.05, 0.55),   # indigo sombre
            (0.60, 0.25, 0.75),   # violet clair
            (0.80, 0.20, 0.45),   # rose chaud
            (0.20, 0.08, 0.50),   # bleu-violet
        ]

        for _ in range(count):
            r_col, g_col, b_col = random.choice(_FILAMENT_PALETTES)
            x = random.uniform(-55, 55)
            z = random.uniform(-22, 22)
            y = random.uniform(90, 270)
            # Dimensions allongées (filament)
            width  = random.uniform(3.0, 8.0)
            length = random.uniform(22.0, 65.0)
            alpha  = random.uniform(0.18, 0.38)

            fmt = GeomVertexFormat.getV3c4()
            vdata = GeomVertexData("filament", fmt, Geom.UHStatic)
            # 5 vertices : 0=centre, 1=BL, 2=BR, 3=TR, 4=TL
            vdata.setNumRows(5)
            vertex = GeomVertexWriter(vdata, "vertex")
            col_w  = GeomVertexWriter(vdata, "color")

            hw, hl = width / 2.0, length / 2.0

            # Centre — alpha plein
            vertex.addData3(0, 0, 0)
            col_w.addData4(r_col, g_col, b_col, alpha)

            # 4 coins — alpha=0 (bords totalement transparents)
            for cx, cz in [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]:
                vertex.addData3(cx, 0, cz)
                col_w.addData4(r_col, g_col, b_col, 0.0)

            # 4 triangles en éventail depuis le centre
            tris = GeomTriangles(Geom.UHStatic)
            tris.addVertices(0, 1, 2)
            tris.addVertices(0, 2, 3)
            tris.addVertices(0, 3, 4)
            tris.addVertices(0, 4, 1)

            geom = Geom(vdata)
            geom.addPrimitive(tris)
            gnode = GeomNode("filament_node")
            gnode.addGeom(geom)
            np = NodePath(gnode)
            np.reparentTo(render)
            np.setPos(x, y, z)
            # Légère rotation aléatoire pour varier l'orientation
            np.setR(random.uniform(-30, 30))
            np.setTransparency(TransparencyAttrib.MAlpha)
            np.setDepthWrite(False)
            np.setLightOff()
            np.setBin("transparent", 30)
            # Stocker dans planets pour cleanup
            self.planets.append(_StaticDecor(np))

    # ----------------------------------------------------------
    # Update principal
    # ----------------------------------------------------------

    def update(self, dt, scroll_speed):
        player_y = self.game.player.node.getY() if hasattr(self.game, 'player') and self.game.player else 0.0

        if self.level in (1, 99):
            self._update_l1(dt, scroll_speed, player_y)
        elif self.level in (2, 0):
            self._update_l2(dt, scroll_speed, player_y)
        elif self.level == 3:
            self._update_l3(dt, scroll_speed)
        elif self.level == 4:
            self._update_l4(dt, scroll_speed, player_y)

        # Nappes de brouillard mobiles (T3)
        for fl in self.fog_layers:
            fl.update(dt, Point3(0, player_y, 0))

        # Cleanup commun
        self.asteroids          = [a  for a  in self.asteroids        if a.alive]
        self.nebulae            = [n  for n  in self.nebulae          if n.alive]
        self.debris             = [d  for d  in self.debris           if d.alive]
        self.terrain_tiles      = [t  for t  in self.terrain_tiles    if t.alive]
        self.wall_panels        = [w  for w  in self.wall_panels      if w.alive]
        self.floor_panels       = [f  for f  in self.floor_panels     if f.alive]
        self.surface_panels     = [s  for s  in self.surface_panels   if s.alive]
        self.decor_groups       = [dg for dg in self.decor_groups     if dg.alive]
        self.border_mountains   = [m  for m  in self.border_mountains if m.alive]
        self.roads              = [r  for r  in self.roads            if r.alive]

        for p in self.planets:
            p.update(dt)
        if self.star_destroyer:
            self.star_destroyer.update(dt)

    def _update_l1(self, dt, scroll_speed, player_y=0.0):
        """L1 — Astéroïdes + nébuleuses."""
        speed_factor = scroll_speed / 20.0

        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed)
            if self._debug_asteroids:
                self.asteroid_timer = self._asteroid_interval   # fixe 0.1s en L99
            else:
                self.asteroid_timer = self._asteroid_interval / speed_factor

        for a in self.asteroids:
            a.update(dt, player_y)

        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            self._spawn_nebula()
            self.nebula_timer = self.NEBULA_INTERVAL + random.uniform(-5, 5)
        for n in self.nebulae:
            n.update(dt)

        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    def _update_l2(self, dt, scroll_speed, player_y=0.0):
        """L2 — Surface lunaire : terrain continu + bâtiments spaceport (pas de rochers)."""

        # Terrain sol — spawn basé sur la position Y (pas de timer)
        for t in self.terrain_tiles:
            t.update(dt, scroll_speed)

        alive_tiles = [t for t in self.terrain_tiles if t.alive and not t.node.isEmpty()]
        max_tile_y = max((t.node.getY() for t in alive_tiles), default=0)
        if max_tile_y < self.SPAWN_DEPTH - self.TILE_DEPTH / 2:
            new_y = max_tile_y + self.TILE_DEPTH
            self.terrain_tiles.append(
                LunarTerrain(self.game.render, 0, new_y, depth=self.TILE_DEPTH))

        # Bâtiments spaceport
        for bg in self.base_groups:
            bg.update(dt, scroll_speed)
            if not bg.node.isEmpty():
                behind = player_y - bg.node.getY()
                if behind > 20.0:
                    # Loin derrière — caché, zéro draw call
                    bg.node.hide()
                elif behind > 5.0:
                    # Zone de fade — transparence activée sur CE groupe seulement
                    alpha = max(0.0, 1.0 - (behind - 5.0) / 15.0)
                    bg.node.show()
                    bg.node.setTransparency(TransparencyAttrib.MAlpha)
                    bg.node.setColorScale(1, 1, 1, alpha)
                else:
                    # Devant le joueur — opaque, pas de tri transparence
                    bg.node.show()
                    bg.node.clearTransparency()
                    bg.node.setColorScale(1, 1, 1, 1)
        self.base_groups = [bg for bg in self.base_groups if bg.alive]
        # Spawn de nouveaux groupes
        if self.base_groups:
            max_by = max(bg.node.getY() for bg in self.base_groups if not bg.node.isEmpty())
        else:
            max_by = 40.0
        if max_by < self.SPAWN_DEPTH - 50:
            new_y  = max_by + random.uniform(LUNAR["base_spacing_min"], LUNAR["base_spacing_max"])
            seed   = int(abs(new_y) * 17 + len(self.base_groups) * 53) & 0xFFFF
            self.base_groups.append(LunarBaseGroup(self.game, new_y, seed))

        # Montagnes de bord
        for m in self.border_mountains:
            m.update(dt, scroll_speed)
        # Spawn une nouvelle bande quand la plus récente a scrollé de ~160 unités
        # (node.Y va de 0 → -250, on respawn vers -160 pour qu'il y ait toujours
        #  des montagnes loin devant grâce à la géométrie baked à ~SPAWN_DEPTH+80)
        alive_mtns = [m for m in self.border_mountains if m.alive]
        if not alive_mtns or max(m.node.getY() for m in alive_mtns) < -160:
            seed_m = int(abs(len(self.border_mountains) * 31 + random.random() * 1000)) & 0xFFFF
            self.border_mountains.append(
                LunarBorderMountain(self.game.render, 15.0,
                                    self.SPAWN_DEPTH + 30.0, seed=seed_m)
            )

        # Routes — update + respawn quand le batch courant est trop avancé
        for r in self.roads:
            r.update(dt, scroll_speed)
        alive_roads = [r for r in self.roads if r.alive and not r.node.isEmpty()]
        if not alive_roads or max(r.node.getY() for r in alive_roads) < -60:
            # Spawn un nouveau batch de routes baked à l'avance
            rys = [random.uniform(155, 185), random.uniform(110, 140), random.uniform(70, 100)]
            self.roads.append(LunarRoad(self.game.render, rys))

    def _update_l3(self, dt, scroll_speed):
        """L3 — Tranchée : murs + sol + surface Death Star continus."""
        # Update
        for w in self.wall_panels:
            w.update(dt, scroll_speed)
        for f in self.floor_panels:
            f.update(dt, scroll_speed)
        for s in self.surface_panels:
            s.update(dt, scroll_speed)
        for dg in self.decor_groups:
            dg.update(dt, scroll_speed)

        # Spawn : ajoute une rangée quand le dernier panneau se rapproche trop
        alive_walls = [w for w in self.wall_panels if w.alive and not w.node.isEmpty()]
        if alive_walls:
            max_wall_y = max(w.node.getY() for w in alive_walls)
        else:
            max_wall_y = 0
        # Spawn quand le bord avant du dernier panneau arrive à SPAWN_DEPTH
        # → nouveau panneau exactement un TILE_DEPTH devant, zéro overlap, zéro Z-fighting
        if max_wall_y < self.SPAWN_DEPTH - self.TILE_DEPTH / 2:
            self._spawn_trench_row(max_wall_y + self.TILE_DEPTH)

        # Débris métalliques rares
        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = (self.DEBRIS_INTERVAL * 2.0) + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    def _update_l4(self, dt, scroll_speed, player_y=0.0):
        """L4 — Nébuleuse : astéroïdes + nuages denses."""
        speed_factor = scroll_speed / 20.0

        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed * 0.9)
            self.asteroid_timer = (self.ASTEROID_INTERVAL * 0.7) / speed_factor
        for a in self.asteroids:
            a.update(dt, player_y)

        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            # L4 : double nappe pour densifier le fond nébuleux
            self._spawn_nebula(scale=2.2)
            self._spawn_nebula(scale=1.6)
            self.nebula_timer = (self.NEBULA_INTERVAL * 0.4) + random.uniform(-3, 3)
        for n in self.nebulae:
            n.update(dt)

        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    # ----------------------------------------------------------
    # Collisions
    # ----------------------------------------------------------

    def check_player_collision(self, player_pos):
        """Vérifie collision avec décor. Retourne (damage, push_x, push_z)."""
        damage = 0
        push_x = 0.0
        push_z = 0.0

        for asteroid in self.asteroids:
            if not asteroid.alive:
                continue
            apos = asteroid.get_pos()
            if apos is None:
                continue
            dist = (apos - player_pos).length()
            if dist < asteroid.hit_radius + 1.0:
                damage += 2
                asteroid.destroy()

        for d in self.debris:
            if not d.alive:
                continue
            dpos = d.get_pos()
            if dpos is None:
                continue
            dist = (dpos - player_pos).length()
            if dist < d.hit_radius + 0.8:
                damage += 1
                d.destroy()

        # Bâtiments L2
        for bg in self.base_groups:
            dmg, (px, pz) = bg.check_collision(player_pos)
            if dmg > 0:
                damage += dmg
                push_x  = px
                push_z  = pz
                break   # un seul bâtiment à la fois

        return damage, push_x, push_z

    def check_laser_hits(self, bolts):
        """
        Vérifie collision bolts joueur vs astéroïdes + débris.
        Détruit le bolt ET l'objet touché, retourne la liste des positions d'impact.
        """
        hits = []
        for bolt in bolts:
            if not bolt.alive:
                continue
            bpos = bolt.node.getPos()

            # Astéroïdes
            for asteroid in self.asteroids:
                if not asteroid.alive:
                    continue
                apos = asteroid.get_pos()
                if apos is None:
                    continue
                if (apos - bpos).length() < asteroid.hit_radius + 0.4:
                    destroyed = asteroid.hit()
                    if destroyed:
                        hits.append(apos)   # explosion seulement à la mort
                    bolt.destroy()
                    break

            if not bolt.alive:
                continue

            # Débris
            for d in self.debris:
                if not d.alive:
                    continue
                dpos = d.get_pos()
                if dpos is None:
                    continue
                if (dpos - bpos).length() < d.hit_radius + 0.3:
                    hits.append(dpos)
                    d.destroy()
                    bolt.destroy()
                    break

        return hits

    # ----------------------------------------------------------
    # Spawners
    # ----------------------------------------------------------

    def _spawn_asteroid(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.8, 3.0)
        if getattr(self, '_debug_asteroids', False):
            speed = scroll_speed * random.uniform(0.5, 2.0)   # L99 : vitesse aléatoire large
        else:
            speed = scroll_speed * random.uniform(0.8, 1.2)
        self.asteroids.append(Asteroid(self.game.render, Point3(x, y, z), size, speed))

    def _spawn_lunar_rock(self, scroll_speed):
        """Rocher lunaire — gris, moins haut que les astéroïdes."""
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-7.0, 5.0)   # Plus proche du sol lunaire
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.5, 2.2)
        speed = scroll_speed * random.uniform(0.85, 1.15)
        self.asteroids.append(LunarRock(self.game.render, Point3(x, y, z), size, speed))

    def _spawn_fixed_planets(self):
        p1 = DistantPlanet(
            self.game.render, Point3(-20, 150, 12),
            size=18, color=Vec4(0.6, 0.35, 0.2, 1),
        )
        self.planets.append(p1)
        p2 = DistantPlanet(
            self.game.render, Point3(25, 200, -8),
            size=12, color=Vec4(0.25, 0.4, 0.65, 1),
        )
        self.planets.append(p2)

    def _spawn_nebula(self, scale=1.0):
        x = random.uniform(-60, 60)
        z = random.uniform(-40, 40)
        y = self.SPAWN_DEPTH + random.uniform(200, 500)
        color = random.choice(self.nebula_colors)
        size = random.uniform(15, 30) * scale
        self.nebulae.append(Nebula(self.game.render, Point3(x, y, z), color, size))

    def _spawn_debris(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 30)
        size = random.uniform(0.2, 0.6)
        speed = scroll_speed * random.uniform(1.0, 1.5)
        self.debris.append(Asteroid(self.game.render, Point3(x, y, z), size, speed))
